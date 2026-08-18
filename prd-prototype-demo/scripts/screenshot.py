#!/usr/bin/env python3
"""
渲染 demo 并截图，用于和原始截图做视觉比对。

静态检查查不出布局问题 —— 行高、间距、信息密度这些"一眼假"的因素
只有真实渲染出来才看得见。

用法：
  python3 screenshot.py --html demo.html --out /tmp/shot.png
  python3 screenshot.py --html demo.html --out /tmp/shot.png --width 1670 --height 959
  python3 screenshot.py --html demo.html --out /tmp/shot.png --full   # 整页
  # 多状态截图：点击若干选择器后各截一张，用于验证交互
  python3 screenshot.py --html demo.html --out /tmp/shot.png \
      --click '[data-page="insight"]' --click '.ai-chip'
"""
import argparse
import pathlib
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit(
        "需要 playwright：pip install playwright && playwright install chromium\n"
        "如果环境装不上，就如实告诉用户静态检查已过但未做渲染核对，"
        "建议他们自己打开看一眼 —— 不要假装验证过了。"
    )


def main():
    ap = argparse.ArgumentParser(description="渲染 demo 截图")
    ap.add_argument("--html", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--full", action="store_true", help="整页截图")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--click", action="append", default=[],
                    help="截图后依次点击的选择器，每次点击后再截一张")
    ap.add_argument("--wait", type=int, default=800, help="加载后等待毫秒")
    args = ap.parse_args()

    path = pathlib.Path(args.html).resolve()
    if not path.exists():
        sys.exit(f"文件不存在：{path}")
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=args.scale,
        )
        page.on("console", lambda m: errors.append(f"[console] {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        # 用 file:// 加载 —— 这正是用户双击打开的方式，
        # 能暴露 fetch 被拦截之类只在 file 协议下出现的问题
        page.goto(path.as_uri())
        page.wait_for_timeout(args.wait)
        page.screenshot(path=str(out), full_page=args.full)
        print(f"已截图：{out}")

        for i, sel in enumerate(args.click, 1):
            try:
                page.click(sel, timeout=5000)
                page.wait_for_timeout(500)
                shot = out.with_name(f"{out.stem}-{i}{out.suffix}")
                page.screenshot(path=str(shot), full_page=args.full)
                print(f"已截图（点击 {sel} 后）：{shot}")
            except Exception as e:
                print(f"点击 {sel} 失败：{str(e)[:200]}")

        browser.close()

    if errors:
        print(f"\n❌ 页面报错 {len(errors)} 条：")
        for e in errors[:10]:
            print(f"  {e}")
        print("\n注意：file:// 下的 fetch 报错说明有资源没内联，用户双击打开会缺东西")
        sys.exit(1)
    print("\n✅ 无控制台错误")
    print("\n接下来请把渲染结果与用户原始截图逐项比对：")
    print("  配色是否一致（有无档案外的颜色）")
    print("  圆角与阴影的克制程度是否一致")
    print("  字号字重层级是否一致（有没有堆 600/700）")
    print("  信息密度是否一致（行高、间距、一屏信息量）")
    print("  图标风格是否统一（粗细、端点、有无混入面性图标）")


if __name__ == "__main__":
    main()
