#!/usr/bin/env python3
"""
从产品截图中采样真实 UI 设计 token。

核心思想：不同角色的元素需要不同的采样策略。统一用"取众数"会让文字
颜色全部采成背景色 —— 文字笔画细、边缘有抗锯齿，小窗口里背景像素永远占多数。

四种策略：
  bg     取窗口内众数        —— 背景、卡片底色、选中态底色
  text   取窗口内最暗像素     —— 文字（笔画核心才是真值）
  accent 取最高饱和度像素     —— 品牌色、链接色、主按钮
  line   扫描线法            —— 1px 发丝边框、网格线、分隔线

用法：
  # 看点位建议和图片信息
  python3 sample_ui.py --image shot.png --list-points

  # 自动量化调色板（快速摸底，不能替代定点采样）
  python3 sample_ui.py --image shot.png --auto

  # 按点位配置采样
  python3 sample_ui.py --image shot.png --spec points.json --out result.json

points.json 格式（scale 用于显示坐标→原图坐标换算，缺省 1.0）：
  {
    "scale": 1.309,
    "points": [
      {"name": "页面背景",   "x": 1500, "y": 200, "role": "bg"},
      {"name": "一级文字",   "x": 1000, "y": 288, "role": "text"},
      {"name": "品牌主色",   "x": 1240, "y": 290, "role": "accent"},
      {"name": "卡片边框",   "x": 600,  "y": 832, "role": "line",
       "horizontal": false, "span": 25, "group": "border"}
    ]
  }
"""
import argparse
import colorsys
import json
import sys
from collections import Counter

try:
    from PIL import Image
except ImportError:
    sys.exit("需要 Pillow：pip install Pillow")


def to_hex(c):
    return "#%02X%02X%02X" % tuple(c[:3])


def luminance(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def saturation(c):
    return colorsys.rgb_to_hsv(*[v / 255 for v in c])[1]


def chroma(c):
    """
    彩度 = max-min 的绝对值（0~255）。

    判断「哪个像素是品牌色」必须用彩度而不是 HSV 饱和度：
    (20,0,0) 这种近黑噪点饱和度也是 1.0，在深色主题上会被当成品牌色选中，
    而它的彩度只有 20 —— 真实品牌色（如 #F5708F）彩度是 133。
    """
    return max(c) - min(c)


def window(im, x, y, r):
    out = []
    w, h = im.size
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            px, py = x + dx, y + dy
            if 0 <= px < w and 0 <= py < h:
                out.append(im.getpixel((px, py))[:3])
    return out


def sample_block(im, x, y, role, r=7):
    """块采样：bg / text / accent"""
    pix = window(im, x, y, r)
    if not pix:
        return None, 0.0
    if role == "bg":
        col, cnt = Counter(pix).most_common(1)[0]
        return col, cnt / len(pix)
    if role == "text":
        # 笔画核心 = 与背景亮度反差最大的那一端。
        # 背景取窗口众数（文字只占少数像素，众数必然是底色），再据此定方向：
        #   浅色主题（亮底）→ 笔画是最暗像素
        #   深色主题（暗底）→ 笔画是最亮像素   ← 硬编码取最暗会把文字采成背景色
        bg = Counter(pix).most_common(1)[0][0]
        if luminance(bg) < 128:                    # 暗底
            col = max(pix, key=luminance)
        else:                                      # 亮底
            col = min(pix, key=luminance)
        # 置信度 = 与背景的亮度对比度。文字笔画只占窗口很小比例，
        # 用"暗像素占比"衡量会对细笔画和小字号误报，用对比度更稳。
        conf = min(1.0, abs(luminance(col) - luminance(bg)) / 128.0)
        return col, conf
    if role == "accent":
        # 按彩度取，不用 HSV 饱和度 —— 见 chroma() 的说明。
        # 深色主题上「最高饱和 + 最暗」会选中近黑噪点而不是品牌色。
        col = max(pix, key=chroma)
        conf = chroma(col) / 255.0
        return col, conf
    raise ValueError(f"未知角色：{role}")


def sample_line(im, x, y, horizontal=False, span=25):
    """
    扫描线法。垂直穿过边框扫一条线，找与底色反差最大的连续像素带。
    1px 半透明边框用任何块采样都框不住，只能这样抓。

    方向自动判别：浅色主题的分隔线比底色暗，深色主题的分隔线比底色亮。
    写死「取最暗」在深色 UI 上会把底色当成线色。
    返回 (线色, 底色, 线宽, 亮度差)
    """
    vals = []
    w, h = im.size
    for d in range(-span, span + 1):
        px, py = (x + d, y) if horizontal else (x, y + d)
        if 0 <= px < w and 0 <= py < h:
            vals.append(im.getpixel((px, py))[:3])
    if not vals:
        return None, None, 0, 0.0
    # 底色 = 扫描线上的众数（线只占少数像素）
    bg = Counter(vals).most_common(1)[0][0]
    darkest, brightest = min(vals, key=luminance), max(vals, key=luminance)
    lb = luminance(bg)
    # 谁离底色更远，谁就是线
    if abs(luminance(brightest) - lb) > abs(lb - luminance(darkest)):
        line, sign = brightest, 1
    else:
        line, sign = darkest, -1
    delta = abs(luminance(line) - lb)
    thr = lb + sign * 6
    width = sum(1 for c in vals
                if (luminance(c) > thr if sign > 0 else luminance(c) < thr))
    return line, bg, width, delta


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def max_channel_spread(hexes):
    """一组颜色在 R/G/B 任一通道上的最大极差。用于判断是否指向同一 token"""
    rgbs = [hex_to_rgb(h) for h in hexes]
    return max(max(c[i] for c in rgbs) - min(c[i] for c in rgbs) for i in range(3))


def pick_representative(hexes):
    """从一组收敛的采样值里取代表值：各通道中位数，比取众数更抗离群"""
    rgbs = [hex_to_rgb(h) for h in hexes]
    mid = []
    for i in range(3):
        vals = sorted(c[i] for c in rgbs)
        mid.append(vals[len(vals) // 2])
    return to_hex(tuple(mid))


POINT_HINTS = """
点位建议（按你的截图实际布局调整坐标）：

背景类 role=bg
  页面主背景 / 侧边栏背景 / 卡片背景 / 输入框填充
  侧边栏选中态底色  ← 容易漏，但对"像不像"很关键
  hover 态底色（如果截图里有悬停状态）

文字类 role=text
  一级文字：页面标题、表格数据、卡片标题
  二级文字：副标题、表头、分组标签
  三级文字：占位符、行号、禁用态
  → 三档齐全，信息层次才对

强调类 role=accent
  主按钮底色 / 链接色 / 选中态文字色
  Logo 附近的颜色  ← 注意：品牌色和功能色可能是两个不同的色值，
                     分工严格（品牌色只用于 Logo/AI 能力，功能色用于按钮/链接）
                     这是 AI 靠"参考风格"绝对猜不到的东西

线条类 role=line（需指定扫描方向）
  卡片上/下边框、输入框边框、表格行分隔线、表格列竖线、侧边栏分割线
  → 至少采 5~9 处不同位置做交叉验证

标签类（底色 role=bg + 文字 role=text 成对采）
  各类语义标签。注意成熟产品常常是"浅底色 + 统一深灰文字"，
  而不是"浅底色 + 同色系深文字"，这个差别很显眼

判断可信度：给语义相同的点标同一个 group（如所有边框都标 group="border"），
每组采 3 点以上。脚本会算各通道极差 —— 极差 ≤4 说明指向同一 token（真值），
并给出中位数作为取值建议；极差很大说明点位没打准，重新定位再采。

注意不要按 role 判断收敛：文字本就有三档、背景本就有多层，
它们不该收敛到一个值。收敛检查只对同语义的点有意义。
"""


def main():
    ap = argparse.ArgumentParser(description="从截图采样 UI 设计 token")
    ap.add_argument("--image", required=True)
    ap.add_argument("--spec", help="点位配置 JSON")
    ap.add_argument("--out", help="采样结果输出路径")
    ap.add_argument("--auto", action="store_true", help="自动量化调色板")
    ap.add_argument("--list-points", action="store_true", help="打印点位建议")
    ap.add_argument("--colors", type=int, default=16, help="--auto 的量化色数")
    args = ap.parse_args()

    im = Image.open(args.image).convert("RGB")
    w, h = im.size
    print(f"图片：{args.image}  尺寸：{w}x{h}")

    if args.list_points:
        print(POINT_HINTS)
        print("提示：若截图被缩放显示过，spec 里设 scale = 原图宽 / 显示宽")
        return

    if args.auto:
        print(f"\n=== 自动量化调色板 Top{args.colors} ===")
        small = im.resize((max(1, w // 3), max(1, h // 3)))
        q = small.quantize(colors=args.colors, method=Image.MAXCOVERAGE)
        pal = q.getpalette()
        counts = q.getcolors()
        total = sum(c for c, _ in counts)
        for cnt, idx in sorted(counts, reverse=True):
            col = tuple(pal[idx * 3: idx * 3 + 3])
            print(f"  {to_hex(col)}  {cnt / total * 100:5.2f}%")
        print("\n注意：量化只反映面积占比，大面积白底会淹没真正的品牌色。")
        print("必须配合定点采样，不能只靠这个。")
        return

    if not args.spec:
        print("\n未提供 --spec。先用 --list-points 看点位建议，或 --auto 快速摸底。")
        return

    spec = json.load(open(args.spec))
    scale = spec.get("scale", 1.0)
    results = []
    print(f"\n=== 定点采样（scale={scale}）===")
    for p in spec["points"]:
        x, y = int(p["x"] * scale), int(p["y"] * scale)
        role = p.get("role", "bg")
        name = p.get("name", f"{x},{y}")
        if role == "line":
            line, bg, width, delta = sample_line(
                im, x, y, p.get("horizontal", False), p.get("span", 25)
            )
            if line is None:
                print(f"  {name:24s} 采样失败（坐标越界）")
                continue
            ok = "" if delta > 8 else "  ⚠ 亮度差过小，可能没扫到边框"
            print(f"  {name:24s} 线色={to_hex(line)} 底色={to_hex(bg)} "
                  f"宽={width}px Δ={delta:.1f}{ok}")
            results.append({"name": name, "role": role, "value": to_hex(line),
                            "group": p.get("group"), "bg": to_hex(bg),
                            "width_px": width,
                            "delta_luminance": round(delta, 1)})
        else:
            col, conf = sample_block(im, x, y, role, p.get("radius", 7))
            if col is None:
                print(f"  {name:24s} 采样失败（坐标越界）")
                continue
            warn = ""
            if role == "text" and conf < 0.25:
                warn = "  ⚠ 与背景对比度过低，点位可能没打在文字上"
            if role == "accent" and conf < 0.15:
                warn = "  ⚠ 彩度过低，可能采到了背景或中性色"
            print(f"  {name:24s} {to_hex(col)}  置信度={conf:.2f}{warn}")
            results.append({"name": name, "role": role, "value": to_hex(col),
                            "group": p.get("group"),
                            "confidence": round(conf, 3)})

    # 收敛性检查：只对"语义相同"的点做一致性判断。
    # 注意不能按 role 分组 —— 文字本就有三档、背景本就有多层，
    # 要求它们收敛是错的。真正该检查的是同一语义的多点采样，
    # 比如 5 处边框是否都指向同一个 border token。
    groups = {}
    for r in results:
        g = r.get("group")
        if g:
            groups.setdefault(g, []).append(r["value"])
    if groups:
        print("\n=== 收敛性检查（同语义多点是否指向同一 token）===")
        for g, vals in groups.items():
            uniq = sorted(set(vals))
            if len(vals) < 3:
                print(f"  {g:12s} 仅 {len(vals)} 点，建议增到 3 点以上再判断")
                continue
            spread = max_channel_spread(uniq)
            if spread <= 4:
                print(f"  {g:12s} 收敛良好 ✅ 极差 {spread}  {uniq}")
                print(f"               → 取值建议 {pick_representative(vals)}")
            elif spread <= 12:
                print(f"  {g:12s} 基本收敛，极差 {spread}  {uniq}")
                print(f"               → 取值建议 {pick_representative(vals)}")
            else:
                print(f"  {g:12s} 结果分散（极差 {spread}），建议复核点位  {uniq}")
    else:
        print("\n提示：给点位加 \"group\" 字段（如多处边框都标 group=\"border\"），"
              "\n      即可自动做同语义收敛性检查 —— 这是判断采样可信度最有效的手段。")

    if args.out:
        json.dump(results, open(args.out, "w"), ensure_ascii=False, indent=2)
        print(f"\n已写出：{args.out}")


if __name__ == "__main__":
    main()
