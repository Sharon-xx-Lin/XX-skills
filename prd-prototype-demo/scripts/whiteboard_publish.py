#!/usr/bin/env python3
"""
把画板安全 SVG 发布到飞书画板。

完整链路：校验 SVG → 转画板节点 → 探测登录态 → 创建文档与画板块 →
写入节点 → 回读服务端渲染图供核对。

用法：
  # 只做本地校验与预览（不需要授权，先跑这个）
  python3 whiteboard_publish.py --svg flow.svg --dry-run

  # 完整发布
  python3 whiteboard_publish.py --svg flow.svg --title "需求名 · 原型图"

  # 写入已存在的画板（覆盖）
  python3 whiteboard_publish.py --svg flow.svg --whiteboard-token wb_xxx --overwrite

设计说明：授权采用"先探测再引导"。直接拦住用户要求授权是多余的 ——
平台侧通常已有凭证，探测一下就能过；真的缺凭证时才给出引导。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile  # 仅用于本地预览临时文件

WB_CLI = ["npx", "--yes", "@larksuite/whiteboard-cli@latest"]

# 画板不支持的 SVG 特性。用了会静默丢失或降级成图片（丢失可编辑性）
FORBIDDEN = {
    "filter": "画板不支持滤镜/阴影，会静默丢弃",
    "radialGradient": "画板只支持线性渐变",
    "clipPath": "画板不支持裁剪路径",
    "mask": "画板不支持蒙版",
    "foreignObject": "画板无法解析，文字必须用 <text>",
    "pattern": "画板不支持图案填充",
    "feGaussianBlur": "画板不支持模糊",
}


def run(cmd, stdin_data=None, timeout=300):
    return subprocess.run(
        cmd, input=stdin_data, capture_output=True, text=True, timeout=timeout
    )


def extract_json(text):
    """
    CLI 输出可能混有 WARN 行（proxy 提示等），抓出其中的 JSON。

    不能用贪婪 r"\\{.*\\}" —— 警告行里只要出现一个 `{`，贪婪匹配就会从它开始，
    把非 JSON 前缀一起吞掉导致解析失败。逐个候选起点试，取第一个能解析的。
    """
    if not text:
        return None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        # 从每个 { 起，用解码器尝试读出一个完整对象
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def lint_svg(path):
    """检查 SVG 是否落在画板安全子集内"""
    src = open(path, encoding="utf-8").read()
    problems = []
    for tag, why in FORBIDDEN.items():
        if re.search(rf"<{tag}\b|{tag}\s*=|url\(#", src) and tag in src:
            problems.append(f"{tag} — {why}")
    if re.search(r"<image\b", src):
        problems.append("<image> — SVG 内嵌图片会失败，需改用画板 image 节点单独上传")
    # 圆角依赖检查：画板会把任意圆角量化成默认值
    radii = set(re.findall(r'\brx="([0-9.]+)"', src))
    big = [r for r in radii if float(r) >= 10]
    notes = []
    if big:
        notes.append(
            f"存在较大圆角 rx={sorted(big)}：画板会量化成默认圆角，"
            "确保圆角没有承载语义信息（如靠圆角区分状态）"
        )
    return problems, notes


def wb_check(svg):
    r = run(WB_CLI + ["-i", svg, "--check"])
    d = extract_json(r.stdout)
    if not d:
        return None, r.stdout + r.stderr
    return d, None


def wb_to_openapi(svg, out):
    r = run(WB_CLI + ["-i", svg, "-t", "openapi", "-o", out])
    return extract_json(r.stdout), r.stdout + r.stderr


def wb_preview(svg, out, scale=1):
    r = run(WB_CLI + ["-i", svg, "-o", out, "-s", str(scale)])
    return extract_json(r.stdout), r.stdout + r.stderr


def probe_auth():
    """探测 user 身份登录态。返回 (是否就绪, 提示信息)"""
    r = run(["lark-cli", "doctor"], timeout=90)
    txt = r.stdout + r.stderr
    m = re.search(r'"name":\s*"user_identity".*?"status":\s*"(\w+)".*?"message":\s*"([^"]*)"',
                  txt, re.S)
    if not m:
        return False, "无法解析 lark-cli doctor 输出"
    return m.group(1) == "pass", m.group(2)


def try_login():
    """尝试静默授权。平台侧常已有凭证，这时会直接完成"""
    r = run(["lark-cli", "auth", "login", "--domain", "docs,drive",
             "--no-wait", "--json"], timeout=120)
    txt = r.stdout + r.stderr
    if "authorization_complete" in txt:
        return True, None
    # 需要用户扫码时，把验证链接提取出来交给调用方展示
    for key in ["verification_url", "verification_uri", "authorize_url", "url"]:
        m = re.search(rf'"{key}":\s*"([^"]+)"', txt)
        if m:
            code = re.search(r'"(?:user_code|device_code)":\s*"([^"]+)"', txt)
            return False, {"url": m.group(1),
                           "code": code.group(1) if code else None,
                           "raw": txt[:600]}
    return False, {"raw": txt[:600]}


def create_doc(title):
    """创建含空白画板块的文档。标题必须写在 XML 里 —— --title 参数不生效"""
    xml = f"<title>{title}</title><whiteboard type=\"blank\"></whiteboard>"
    r = run(["lark-cli", "docs", "+create", "--api-version", "v2",
             "--content", "-", "--doc-format", "xml", "--as", "user"],
            stdin_data=xml, timeout=180)
    d = extract_json(r.stdout)
    if not d or not d.get("ok"):
        return None, r.stdout + r.stderr
    doc = d["data"]["document"]
    token = None
    for b in doc.get("new_blocks", []):
        if b.get("block_type") == "whiteboard":
            token = b.get("block_token")
    return {"doc_id": doc.get("document_id"), "url": doc.get("url"),
            "whiteboard_token": token}, None


def write_nodes(token, openapi_path, overwrite=False, idem=None):
    """
    写入节点。注意：--source 要的是转换器的完整输出对象（{"nodes": [...]}），
    不是裸的节点数组 —— 喂数组会报 unmarshal 错误。
    """
    cmd = ["lark-cli", "whiteboard", "+update",
           "--whiteboard-token", token,
           "--input_format", "raw",
           "--source", f"@{openapi_path}",
           "--as", "user"]
    if overwrite:
        cmd.append("--overwrite")
    if idem:
        # idempotent-token 需 ≥10 字符且不含特殊符号。
        # 必须带上画板 token —— 只用「文件名 + 节点数」时，重发同一份 SVG
        # 到新画板会被服务端判成重复请求：它返回上次的 created_node_ids
        # （于是脚本打印「写入成功 751 个」），而新画板实际一片空白。
        cmd += ["--idempotent-token", re.sub(r"[^A-Za-z0-9]", "", idem)[:64]]
    r = run(cmd, timeout=300)
    d = extract_json(r.stdout)
    if not d or not d.get("ok"):
        return None, r.stdout + r.stderr
    return d["data"], None


def count_remote_nodes(token):
    """
    回查服务端实际存了多少节点。

    写入接口的返回值不可信（幂等命中时会回放上次结果），必须实查。
    返回 (节点数, 错误)；节点数为 0 且无错误说明画板确实是空的。
    """
    r = run(["lark-cli", "whiteboard", "+query",
             "--whiteboard-token", token,
             "--output_as", "raw", "--json", "--as", "user"], timeout=120)
    # 只认 stdout —— stderr 里有 proxy 警告等噪声
    d = extract_json(r.stdout)
    if not d or not d.get("ok"):
        return None, ((r.stdout or "") + (r.stderr or ""))[:400]
    data = d.get("data") or {}
    if isinstance(data, dict) and "whiteboard is empty" in str(data.get("msg", "")):
        return 0, None
    found = []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("nodes"), list):
                found.append(o["nodes"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return (len(max(found, key=len)) if found else 0), None


def readback(token, outdir="wb_readback"):
    """
    回读服务端渲染图。outdir 必须是当前目录下的相对路径 ——
    lark-cli 的路径参数一律不接受绝对路径。
    """
    os.makedirs(outdir, exist_ok=True)
    r = run(["lark-cli", "whiteboard", "+query", "--whiteboard-token", token,
             "--output_as", "image", "--output", outdir, "--as", "user"],
            timeout=180)
    d = extract_json(r.stdout)
    if not d or not d.get("ok"):
        return None, r.stdout + r.stderr
    p = d["data"].get("preview_image_path")
    return (os.path.abspath(p) if p else None), None


def main():
    ap = argparse.ArgumentParser(description="发布 SVG 到飞书画板")
    ap.add_argument("--svg", required=True)
    ap.add_argument("--title", default="需求原型图")
    ap.add_argument("--whiteboard-token", help="写入已存在的画板")
    ap.add_argument("--overwrite", action="store_true", help="清空后写入")
    ap.add_argument("--check", action="store_true",
                    help="只做安全子集 + 几何校验，不出预览图、不联网")
    ap.add_argument("--dry-run", action="store_true", help="只做本地校验和预览")
    ap.add_argument("--preview", help="本地预览 PNG 输出路径")
    args = ap.parse_args()

    # 1. SVG 安全子集检查
    print("=== SVG 安全子集检查 ===")
    problems, notes = lint_svg(args.svg)
    for p in problems:
        print(f"  ❌ {p}")
    for n in notes:
        print(f"  ⚠ {n}")
    if problems:
        sys.exit("\n存在画板不支持的特性，请先修改 SVG。详见 references/whiteboard.md")
    if not notes:
        print("  ✅ 通过")

    # 2. 几何校验
    print("\n=== 几何校验（文字溢出 / 节点重叠）===")
    d, err = wb_check(args.svg)
    if not d:
        sys.exit(f"校验失败：{err[:800]}")
    # 转换器有两种返回结构：全部通过时是扁平的 metadata（width/height/
    # nodeCount/connectorCount），有问题时才包一层 {code, data:{metadata, check}}。
    # 只认后者会让通过的图打印出 errors=None，看着像校验没跑起来。
    if "nodeCount" in d:
        meta, chk = d, {}
    else:
        data = d.get("data") or {}
        meta, chk = data.get("metadata") or {}, data.get("check") or {}
    errors, warnings = chk.get("errors", 0), chk.get("warnings", 0)
    print(f"  节点 {meta.get('nodeCount')} 个，连线 {meta.get('connectorCount')} 条")
    print(f"  errors={errors}  warnings={warnings}")
    for issue in (chk.get("issues") or [])[:10]:
        print(f"    - {issue}")
    if not errors and not warnings:
        print("  ✅ 几何校验通过")
    if errors:
        sys.exit("有 error 必须先修复：通常是文字超出容器，加宽容器或缩短文案")

    # --check：校验到此为止。不出图、不联网，任何环境都能跑。
    if args.check:
        print("\n--check 结束：校验通过，未生成预览、未做任何线上写入。")
        return

    # 3. 本地预览
    if args.preview or args.dry_run:
        out = args.preview or tempfile.mktemp(suffix=".png")
        print(f"\n=== 本地预览 ===")
        d2, err2 = wb_preview(args.svg, out)
        if d2 and d2.get("data", {}).get("outputPath"):
            print(f"  已生成：{d2['data']['outputPath']}")
        else:
            print(f"  预览失败：{err2[:400]}")

    if args.dry_run:
        print("\n--dry-run 结束，未做任何线上写入。")
        return

    # 4. 转画板节点
    # 注意：节点文件必须落在当前工作目录下，且用相对路径传给 lark-cli ——
    # lark-cli 的 @file 只接受当前目录下的相对路径，给绝对路径会报
    # invalid file path，导致「文档已创建、节点写入失败」的中间态。
    print("\n=== 转换为画板节点 ===")
    openapi = f".wb_nodes_{os.path.basename(args.svg)}.json".replace(".svg", "")
    d3, err3 = wb_to_openapi(args.svg, openapi)
    if not d3:
        sys.exit(f"转换失败：{err3[:800]}")
    nodes = json.load(open(openapi)).get("nodes", [])
    print(f"  {len(nodes)} 个节点")

    # 5. 授权：先探测，再引导
    print("\n=== 授权状态 ===")
    ok, msg = probe_auth()
    if ok:
        print(f"  ✅ user 身份就绪")
    else:
        print(f"  user 身份未就绪：{msg}")
        print("  尝试静默授权…")
        done, info = try_login()
        if done:
            print("  ✅ 授权完成")
        else:
            print("\n需要你手动完成飞书授权：")
            if isinstance(info, dict) and info.get("url"):
                print(f"  授权链接：{info['url']}")
                if info.get("code"):
                    print(f"  验证码：{info['code']}")
                print("\n完成授权后重新运行本命令即可。")
            else:
                print(f"  {info}")
            sys.exit(2)

    # 6. 创建或复用画板
    token, doc_url = args.whiteboard_token, None
    if not token:
        print("\n=== 创建文档与画板块 ===")
        doc, err4 = create_doc(args.title)
        if not doc:
            sys.exit(f"创建失败：{err4[:800]}")
        token, doc_url = doc["whiteboard_token"], doc["url"]
        print(f"  文档：{doc_url}")
        print(f"  画板 token：{token}")

    # 7. 写入
    print("\n=== 写入节点 ===")
    res, err5 = write_nodes(token, openapi, args.overwrite,
                            idem=token + os.path.basename(args.svg) + str(len(nodes)))
    if not res:
        # 走到这里说明文档已创建但内容为空 —— 明确告知用户如何续做，
        # 不要让他们对着一个空画板猜发生了什么
        print(f"写入失败：{err5[:800]}")
        if doc_url:
            print(f"\n文档已创建但内容为空：{doc_url}")
            print(f"节点文件保留在：{os.path.abspath(openapi)}")
            print(f"可手动重试（须在该文件所在目录执行）：")
            print(f"  lark-cli whiteboard +update --whiteboard-token {token} \\")
            print(f"    --input_format raw --source @{openapi} --as user")
        sys.exit(1)
    created = res.get("created_node_ids", "")
    print(f"  接口返回：{len(created.split(',')) if created else 0} 个节点")

    # 7b. 回查服务端实际节点数 —— 接口返回值不可信（幂等命中会回放上次结果），
    #     只有实查才能发现「报告成功、画板全空」这种情况。
    remote, errq = count_remote_nodes(token)
    if errq:
        print(f"  ⚠ 回查失败，无法确认写入结果：{errq}")
    elif remote == 0:
        print(f"  ❌ 服务端画板为空！接口报告成功但实际没写进去。")
        print(f"     最常见原因：idempotent-token 与之前某次请求重复，"
              f"服务端回放了旧结果。")
        print(f"     节点文件保留在：{os.path.abspath(openapi)}")
        print(f"     重试（换一个画板或加 --overwrite）：")
        print(f"       cd {os.path.dirname(os.path.abspath(openapi)) or '.'} && \\")
        print(f"       lark-cli whiteboard +update --whiteboard-token {token} \\")
        print(f"         --input_format raw --source @{os.path.basename(openapi)} "
              f"--as user --overwrite")
        if doc_url:
            print(f"\n文档：{doc_url}（当前为空画板）")
        sys.exit(1)
    elif remote < len(nodes):
        print(f"  ⚠ 服务端只有 {remote} 个节点，少于本地 {len(nodes)} 个 —— "
              f"可能被截断，建议分批写入")
    else:
        print(f"  ✅ 回查确认：服务端 {remote} 个节点")

    # 8. 回读核对
    print("\n=== 回读服务端渲染图 ===")
    img, err6 = readback(token)
    if img:
        print(f"  已导出：{img}")
        print("  建议看一眼，确认服务端渲染与本地预览一致")
    else:
        print(f"  回读失败（不影响已写入内容）：{err6[:300]}")

    try:
        os.remove(openapi)
    except OSError:
        pass

    if doc_url:
        print(f"\n完成：{doc_url}")


if __name__ == "__main__":
    main()
