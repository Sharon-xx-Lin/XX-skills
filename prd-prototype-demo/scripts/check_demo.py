#!/usr/bin/env python3
"""
Demo 自检：机械校验 AI 味回归和单文件可用性。

静态检查很便宜，但能拦住绝大多数问题。检查项对应真实踩过的坑：

1. 字面量颜色值 —— 这是"AI 味"的头号来源。一旦允许模型直接写 #xxx，
   它就会滑回训练数据里最高频的那套配色。所有颜色必须走 tokens 变量。
2. emoji —— 团队看到 emoji 当图标会立刻判定"这是 AI 生成的"。
3. fetch() 外部依赖 —— file:// 协议下浏览器禁止 fetch，用户双击打开时
   图标会全部消失。本地起服务时不会暴露这个问题，只有用户打开才发现。
4. sprite 是否内联 —— 同上，单文件交付的前提。
5. 圆角/阴影异常值 —— 超大圆角和厚阴影是 AI 味的典型特征。

用法：
  python3 check_demo.py --html demo.html
  python3 check_demo.py --html demo.html --tokens tokens.css   # 额外校验变量是否都有定义
  python3 check_demo.py --css components.css                    # 单独检查 CSS
"""
import argparse
import re
import sys

EMOJI_RANGES = (
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F000-\U0001F2FF"
    "\U0000FE0F"
    "\U00002190-\U000021FF"
)
EMOJI_RE = re.compile(f"[{EMOJI_RANGES}]")

# 允许的例外：纯黑白在极少数场景（如 SVG 描边占位）可接受，但仍会提示
NEUTRAL_OK = {"#FFF", "#FFFFFF", "#000", "#000000"}


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def strip_token_defs(css):
    """
    剔除 :root / html / [data-theme] 等 token 定义块。

    这些地方本来就必须写字面量色值 —— 它们是颜色的源头。
    单文件交付时 tokens.css 必须内联进 HTML，所以定义块一定会出现在
    style 里。真正该拦的是组件层/页面层/内联 style/JS 里绕过 var()
    直接写色值，那才是配色漂移的入口。
    """
    return re.sub(r"(?::root|html|\[data-theme[^\]]*\])[^{]*\{[^}]*\}", "",
                  css, flags=re.S)


# 只认合法的十六进制色值长度（3/4/6/8），且后面不能再接标识符字符 ——
# 否则 CSS 选择器和 JS 里的 id（#add-dash、#face）会被误判成色值。
HEX_RE = re.compile(
    r"#(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{3})(?![-\w])"
)


def find_color_literals(text, allow_neutral=False):
    hits = []
    for m in HEX_RE.finditer(text):
        v = m.group()
        # 前面紧跟引号 = 选择器字符串（$('#fff')、querySelector("#dad")），不是色值
        if m.start() > 0 and text[m.start() - 1] in "'\"`":
            continue
        if allow_neutral and v.upper() in NEUTRAL_OK:
            continue
        hits.append(v)
    hits += re.findall(r"rgba?\([^)]*\)", text)
    hits += re.findall(r"hsla?\([^)]*\)", text)
    return hits


def check_html(path, tokens_path=None):
    src = open(path, encoding="utf-8").read()
    issues, notes = [], []

    # --- 颜色字面量：分区检查，便于定位 ---
    # sprite 区域内的 fill/stroke 属于图标定义，单独看待
    sprite_blocks = re.findall(r"<svg[^>]*display:\s*none.*?</svg>", src, flags=re.S)
    body = src
    for b in sprite_blocks:
        body = body.replace(b, "")

    styles = re.findall(r"<style>(.*?)</style>", body, flags=re.S)
    scripts = re.findall(r"<script>(.*?)</script>", body, flags=re.S)
    inline = re.findall(r'style="([^"]*)"', body)

    lits = []
    for blk in styles:
        lits += find_color_literals(strip_token_defs(strip_comments(blk)))
    for s in inline:
        lits += find_color_literals(s)
    for j in scripts:
        lits += find_color_literals(j)

    if lits:
        uniq = sorted(set(lits))
        issues.append(
            f"发现 {len(lits)} 处字面量颜色值（{len(uniq)} 个不同值）：{uniq[:12]}"
            + ("…" if len(uniq) > 12 else "")
            + "\n    → 颜色必须走 var(--token)。注意 :root 里的 token 定义已排除，"
            "\n      这里报出的是组件层/页面层/JS 里绕过变量直接写的色值"
        )

    # --- emoji ---
    emo = EMOJI_RE.findall(src)
    if emo:
        issues.append(
            f"发现 {len(emo)} 个 emoji：{sorted(set(emo))}"
            "\n    → 用 icons.svg 里的线性图标替代；缺图标就按同风格补一个"
        )

    # --- fetch 外部依赖 ---
    if re.search(r"\bfetch\s*\(", src):
        issues.append(
            "使用了 fetch()：file:// 协议下会被浏览器拦截，"
            "用户双击打开时相关资源会加载失败"
            "\n    → sprite 和样式都要内联进 HTML"
        )

    # --- 外链样式/脚本 ---
    ext_css = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', src)
    ext_js = re.findall(r'<script[^>]+src=["\'][^"\']+["\']', src)
    if ext_css or ext_js:
        notes.append(
            f"存在外部资源引用（{len(ext_css)} 个样式表 / {len(ext_js)} 个脚本）。"
            "若要单文件交付，需全部内联"
        )

    # --- sprite 内联与图标使用 ---
    # JS 里常用模板拼接图标名（'<use href="#i-' + name + '"/>'），这类引用
    # 静态解析不出真实名字，只统计不校验，否则会误报成"未定义图标"。
    all_uses = re.findall(r'<use[^>]+href="#([^"]+)"', src)
    uses = [u for u in all_uses if not re.search(r"""['"`+${]|\s""", u)]
    dynamic = len(all_uses) - len(uses)
    symbols = re.findall(r'<symbol[^>]+id="([^"]+)"', src)
    if all_uses and not symbols:
        issues.append(
            f"有 {len(all_uses)} 处图标引用，但 HTML 内没有 <symbol> 定义"
            "\n    → sprite 未内联，图标不会显示"
        )
    missing = sorted(set(uses) - set(symbols))
    if symbols and missing:
        issues.append(f"引用了未定义的图标：{missing}")
    if dynamic:
        notes.append(
            f"有 {dynamic} 处图标名由 JS 拼接，静态检查无法校验是否存在。"
            "请在渲染核对时确认没有空白图标"
        )

    # --- 圆角与阴影异常值：AI 味的典型特征 ---
    big_radius = [
        v for v in re.findall(r"border-radius:\s*([0-9]+)px", " ".join(styles) + " ".join(inline))
        if int(v) >= 16
    ]
    if big_radius:
        notes.append(
            f"存在 ≥16px 的圆角：{sorted(set(big_radius))}px。"
            "成熟 B 端产品圆角通常 4~8px，超大圆角是 AI 味特征，"
            "确认这是产品截图里真实存在的再保留"
        )
    shadows = re.findall(r"box-shadow:\s*([^;]+);", " ".join(styles))
    heavy = [s for s in shadows if re.search(r"\b(1[0-9]|[2-9][0-9])px\b", s)]
    if heavy:
        notes.append(
            f"存在较重阴影：{heavy[:3]}。很多 B 端产品几乎只用 1px 边框分层，"
            "厚阴影是 AI 味特征"
        )

    # --- tokens 变量是否都有定义 ---
    if tokens_path:
        tok = strip_comments(open(tokens_path, encoding="utf-8").read())
        defined = set(re.findall(r"(--[a-zA-Z0-9-]+)\s*:", tok))
        used = set(re.findall(r"var\((--[a-zA-Z0-9-]+)", src))
        undef = sorted(used - defined)
        if undef:
            issues.append(f"引用了 tokens.css 中未定义的变量：{undef}")
        unused = sorted(defined - used)
        if unused:
            notes.append(f"tokens 中有 {len(unused)} 个变量未被使用（正常，仅供参考）")

    # --- 统计 ---
    stats = {
        "文件大小": f"{len(src.encode('utf-8')) / 1024:.1f} KB",
        "图标引用": len(uses),
        "图标定义": len(symbols),
        "tokens 变量引用": len(set(re.findall(r"var\((--[a-zA-Z0-9-]+)", src))),
    }
    return issues, notes, stats


def check_css(path):
    css = strip_comments(open(path, encoding="utf-8").read())
    issues, notes = [], []
    # 组件层不允许出现字面量色值 —— 所有颜色应来自 tokens
    is_tokens = "tokens" in path.lower()
    if not is_tokens:
        lits = find_color_literals(strip_token_defs(css))
        if lits:
            issues.append(
                f"组件样式中有 {len(lits)} 处字面量颜色值：{sorted(set(lits))[:12]}"
                "\n    → 组件层只应引用 tokens 变量"
            )
    stats = {
        "变量定义": len(re.findall(r"--[a-zA-Z0-9-]+\s*:", css)),
        "变量引用": len(set(re.findall(r"var\((--[a-zA-Z0-9-]+)", css))),
    }
    return issues, notes, stats


def main():
    ap = argparse.ArgumentParser(description="Demo 自检")
    ap.add_argument("--html")
    ap.add_argument("--css")
    ap.add_argument("--tokens", help="tokens.css 路径，用于校验变量定义完整性")
    args = ap.parse_args()

    if not args.html and not args.css:
        sys.exit("需要 --html 或 --css")

    if args.html:
        print(f"=== 检查 {args.html} ===")
        issues, notes, stats = check_html(args.html, args.tokens)
    else:
        print(f"=== 检查 {args.css} ===")
        issues, notes, stats = check_css(args.css)

    for k, v in stats.items():
        print(f"  {k}: {v}")

    if issues:
        print(f"\n❌ 需要修复（{len(issues)} 项）：")
        for i in issues:
            print(f"  • {i}")
    if notes:
        print(f"\n⚠ 请确认（{len(notes)} 项）：")
        for n in notes:
            print(f"  • {n}")
    if not issues and not notes:
        print("\n✅ 全部通过")

    print("\n静态检查不能替代视觉核对。"
          "请用 screenshot.py 渲染后与原始截图逐项比对："
          "配色 / 圆角与阴影克制度 / 字号字重层级 / 信息密度 / 图标风格。")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
