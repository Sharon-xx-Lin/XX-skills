#!/usr/bin/env python3
"""
档案一致性检查：验证本次生成是否真的守住了 UI 档案的设计语言。

为什么需要这个：
「AI 味」最隐蔽的形态不是单次生成不像，而是**每次都不一样**。
实测对比中，没有档案约束的一方在做同一产品的第二个需求时，
只有 4 个 token 与第一个需求同名（其中 2 个取值还对不上），
另外新造了 28 个颜色 —— 每次都在重新发明配色。
单看任何一次产出都挺协调，但放在一起就不是一个产品了。

有档案约束的一方：24 个 token 取值 100% 一致，零新增颜色。

所以每次生成后跑一下这个检查，比事后靠眼睛看更早发现漂移。

用法：
  python3 check_profile_drift.py --profile artifacts/ui-profiles/xxx --target demo.html
  python3 check_profile_drift.py --profile <档案目录> --target <目录>   # 扫整个目录
"""
import argparse
import os
import re
import sys


def rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def dist(a, b):
    """最大通道差。同一 token 的合理浮动应该是 0，超过 4 就该解释原因"""
    try:
        return max(abs(x - y) for x, y in zip(rgb(a), rgb(b)))
    except Exception:
        return 999


def root_color_tokens(text):
    """提取 :root（及 html / [data-theme]）里的颜色型 token"""
    out = {}
    for blk in re.findall(
            r"(?::root|html|\[data-theme[^\]]*\])[^{]*\{([^}]*)\}", text, re.S):
        blk = re.sub(r"/\*.*?\*/", "", blk, flags=re.S)
        for m in re.finditer(r"(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);", blk):
            v = m.group(2).strip()
            if re.match(r"^#[0-9A-Fa-f]{3,6}$", v):
                out[m.group(1)] = v.upper()
    return out


def gather(path, exts=(".css", ".html")):
    if os.path.isfile(path):
        return open(path, encoding="utf-8", errors="ignore").read()
    s = ""
    for dp, _, fns in os.walk(path):
        for fn in fns:
            if fn.endswith(exts):
                s += open(os.path.join(dp, fn),
                          encoding="utf-8", errors="ignore").read()
    return s


def main():
    ap = argparse.ArgumentParser(description="检查生成产物是否偏离 UI 档案")
    ap.add_argument("--profile", required=True, help="档案目录或 tokens.css")
    ap.add_argument("--target", required=True, help="本次产物（文件或目录）")
    ap.add_argument("--tolerance", type=int, default=4,
                    help="同名 token 允许的通道差，默认 4")
    args = ap.parse_args()

    prof_path = args.profile
    if os.path.isdir(prof_path):
        cand = os.path.join(prof_path, "tokens.css")
        prof_path = cand if os.path.exists(cand) else prof_path
    base = root_color_tokens(gather(prof_path))
    cur = root_color_tokens(gather(args.target))

    if not base:
        sys.exit(f"未能从 {args.profile} 解析出颜色 token")
    print(f"档案颜色 token: {len(base)} 个")
    print(f"本次产物颜色 token: {len(cur)} 个\n")

    shared = sorted(set(base) & set(cur))
    same = [n for n in shared if dist(base[n], cur[n]) <= args.tolerance]
    drift = [(n, base[n], cur[n]) for n in shared
             if dist(base[n], cur[n]) > args.tolerance]
    missing = sorted(set(base) - set(cur))
    added = {n: v for n, v in cur.items() if n not in base}

    issues = []

    if shared:
        rate = len(same) / len(shared) * 100
        print(f"同名 token 取值一致: {len(same)}/{len(shared)} = {rate:.0f}%")
    if drift:
        issues.append(f"{len(drift)} 个 token 取值偏离档案")
        print(f"\n❌ 取值偏离（超过 ±{args.tolerance}/通道）：")
        for n, b, c in drift:
            print(f"   {n}: 档案={b} → 本次={c}  (差 {dist(b, c)})")
        print("   → 这些应该直接引用档案值。若确有理由改动，请更新档案并说明")

    # 新增颜色是最需要警惕的信号：说明有颜色绕过了档案
    if added:
        issues.append(f"新增了 {len(added)} 个档案外颜色 token")
        print(f"\n⚠ 档案外新增颜色 token（{len(added)} 个）：")
        for n, v in sorted(added.items())[:15]:
            print(f"   {n}: {v}")
        if len(added) > 15:
            print(f"   …还有 {len(added) - 15} 个")
        print("   → 新需求确实可能需要新颜色，但每一个都该问：")
        print("     能不能用现有 token 表达？如果能，就别新增；")
        print("     如果不能，补进档案并在 profile.md 说明理由，让下次能复用。")
        print("     实测中「每次新造一批颜色」正是配色逐轮漂移的机制。")

    if len(shared) < min(8, len(base) // 2):
        issues.append("与档案同名的 token 过少，可能没有真正复用档案")
        print(f"\n❌ 只有 {len(shared)} 个 token 与档案同名 —— "
              "看起来是另起了一套命名，而不是复用档案")
        print("   → 档案的价值就在于跨需求复用；重新发明命名等于档案白建")

    if missing and len(missing) > len(base) * 0.6:
        print(f"\n提示：档案有 {len(missing)} 个 token 本次未用（正常，"
              "本次需求可能用不到）")

    print()
    if issues:
        print(f"❌ 发现 {len(issues)} 类问题：")
        for i in issues:
            print(f"   • {i}")
        sys.exit(1)
    print("✅ 完全守住档案：同名 token 取值一致，无档案外新增颜色")


if __name__ == "__main__":
    main()
