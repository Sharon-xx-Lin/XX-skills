#!/usr/bin/env python3
"""
线框图构件库：把 UI 档案的 tokens 变成可复用的 SVG 构件。

为什么需要这个
--------------
高保真逐帧线框图每帧 100~200 个 SVG 元素，6 帧就上千个。手写不现实，
而且手写必然出现坐标错位、配色漂移。用构件库拼装才能保证
「每帧都是同一个产品」且「帧与帧之间只有该变的地方在变」。

两类构件，职责严格分开
--------------------
1. 产品界面构件（win/topbar/sidebar/table/panel/...）—— 画的是真实产品，
   尺寸必须按实测比例，配色只从档案 tokens 取。
2. 图纸语言构件（stage_banner/frame_tag/anno/cursor/emphasis_*）—— 画的是
   图纸标注，不属于产品 UI，用固定的图纸色（黑色横幅 + 紫色批注）。

不要混淆这两类。想突出重点时用图纸语言（紫框强调），
绝不能去改产品控件的尺寸比例 —— 那会画出真实产品里不存在的界面，
线框图就失去了参考价值。

用法
----
    import wireframe_kit as k
    k.use_profile("artifacts/ui-profiles/my-product")   # 载入档案 tokens
    svg = k.win(0, 0, 1180, 660) + k.topbar(...) + ...
"""
import os
import re

# ---------------- 图纸语言固定色（不属于产品 UI）----------------
INK = "#1F1F1F"      # 阶段横幅 / 帧标签底色
ANNO = "#6B4DE6"     # 批注与强调框
WHITE = "#FFFFFF"

# ---------------- 产品 tokens（由 use_profile 载入）----------------
# 语义名 -> 档案里可能的变量名（按优先级），兼容不同命名习惯
CANON = {
    "primary":   ["--primary", "--color-primary", "--brand-primary", "--blue",
                  "--accent", "--accent-color", "--theme-color"],
    "primary_bg": ["--primary-bg-weak", "--primary-bg", "--bg-selected-blue",
                   "--blue-bg", "--primary-light", "--accent-bg"],
    "brand":     ["--brand", "--brand-purple", "--brand-color"],
    "link":      ["--link", "--color-link"],
    "text1":     ["--text-1", "--text-primary", "--color-text-primary"],
    "text2":     ["--text-2", "--text-secondary", "--color-text-secondary"],
    "text3":     ["--text-3", "--text-tertiary", "--color-text-placeholder"],
    "bg":        ["--bg-body", "--bg", "--bg-page", "--color-bg"],
    "bg_input":  ["--bg-input", "--bg-fill", "--input-bg", "--bg-elevated",
                  "--bg-quote"],
    "bg_hover":  ["--bg-hover", "--bg-soft", "--hover-bg", "--bg-card",
                  "--bg-secondary"],
    "bg_sel":    ["--bg-selected-gray", "--bg-selected", "--bg-gray-sel",
                  "--bg-seg-active", "--bg-active"],
    "border":    ["--border", "--line", "--color-border", "--divider"],
    "border_st": ["--border-strong", "--border-2", "--line-strong"],
}
# 浅色主题的兜底值。深色档案会走 _dark_fallback() 重算 —— 见 use_profile。
FALLBACK = {
    "primary": "#2B5CE6", "primary_bg": "#EDF2FD", "brand": "#7A4DE6",
    "link": "#2B5CE6", "text1": "#1F2329", "text2": "#646A73",
    "text3": "#8F959E", "bg": "#FFFFFF", "bg_input": "#F5F6F7",
    "bg_hover": "#F5F6F7", "bg_sel": "#E8E9E9",
    "border": "#DEE0E3", "border_st": "#C4C8CE",
}


def _lum(hexs):
    h = hexs.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _mix(hexs, target, ratio):
    """把 hexs 朝 target 混 ratio，用于按主背景推导层次色"""
    def parts(x):
        x = x.lstrip("#")
        if len(x) == 3:
            x = "".join(c * 2 for c in x)
        return [int(x[i:i + 2], 16) for i in (0, 2, 4)]
    a, b = parts(hexs), parts(target)
    return "#%02X%02X%02X" % tuple(
        round(a[i] + (b[i] - a[i]) * ratio) for i in range(3))


def _dark_fallback(bg):
    """
    深色档案的兜底值：由主背景朝白色递进推导。

    必须这么做 —— 写死浅色兜底会让深色档案画出「纯黑底 + 浅灰 hover 块」，
    整张图花掉。档案没写的层次色，用主背景推导出的同色系值才不破坏主题。
    """
    return {
        "bg_input":  _mix(bg, "#FFFFFF", 0.14),
        "bg_hover":  _mix(bg, "#FFFFFF", 0.10),
        "bg_sel":    _mix(bg, "#FFFFFF", 0.22),
        "border":    _mix(bg, "#FFFFFF", 0.18),
        "border_st": _mix(bg, "#FFFFFF", 0.30),
        "text1":     "#FFFFFF",
        "text2":     _mix(bg, "#FFFFFF", 0.72),
        "text3":     _mix(bg, "#FFFFFF", 0.55),
    }


T = dict(FALLBACK)
FONT = "Noto Sans SC, PingFang SC, sans-serif"
_missing = []


def use_profile(path):
    """
    从 UI 档案载入 tokens。path 可以是档案目录或 tokens.css 文件。

    档案里没有的 token 会退回兜底值并记录 —— 这些位置意味着该产品的
    这个 token 还没采样，值得回去补，而不是默默用默认色。

    兜底值按主背景亮度分明暗两套：深色档案（主背景亮度 <128）用主背景
    朝白色推导，否则会画出「纯黑底 + 浅灰 hover 块」这种撞色。
    返回 {"loaded": 命中数, "missing": [...], "theme": "dark"|"light"}
    """
    global _missing
    css = path
    if os.path.isdir(path):
        cand = os.path.join(path, "tokens.css")
        css = cand if os.path.exists(cand) else path
    if not os.path.isfile(css):
        raise FileNotFoundError(f"找不到 tokens：{path}")
    src = re.sub(r"/\*.*?\*/", "", open(css, encoding="utf-8").read(), flags=re.S)
    raw = {}
    for m in re.finditer(r"(--[A-Za-z0-9-]+)\s*:\s*([^;]+);", src):
        raw[m.group(1)] = m.group(2).strip()

    def pick(names):
        for n in names:
            v = raw.get(n, "")
            if re.match(r"^#[0-9A-Fa-f]{3,6}$", v):
                return v.upper()
        return None

    # 先定主背景，据此判明暗主题，再决定兜底值基线
    bg = pick(CANON["bg"])
    theme = "dark" if bg and _lum(bg) < 128 else "light"
    # 原地更新，不要写 T = dict(...) 重新绑定 —— 那样 `from wireframe_kit import T`
    # 的调用方仍持有旧字典，会静默画出上一套（或兜底的）配色。
    T.clear()
    T.update(FALLBACK)
    if theme == "dark":
        T.update(_dark_fallback(bg))
    _missing = []
    for sem, names in CANON.items():
        v = pick(names)
        if v:
            T[sem] = v
        else:
            _missing.append(sem)
    return {"loaded": len(CANON) - len(_missing), "missing": _missing,
            "theme": theme}


def missing_tokens():
    """返回档案里缺失、当前用默认值代替的 token 语义名"""
    return list(_missing)


# ==================== 基础图元 ====================

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def rect(x, y, w, h, fill=None, stroke=None, sw=1, rx=0):
    a = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"'
    if rx:
        a += f' rx="{rx}"'
    a += f' fill="{fill or "none"}"'
    if stroke:
        a += f' stroke="{stroke}" stroke-width="{sw}"'
    return a + "/>"


def text(x, y, s, size=11, fill=None, weight=None, anchor="start"):
    a = (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}"'
         f' font-family="{FONT}" fill="{fill or T["text1"]}"')
    if weight:
        a += f' font-weight="{weight}"'
    if anchor != "start":
        a += f' text-anchor="{anchor}"'
    return a + f">{esc(s)}</text>"


def line(x1, y1, x2, y2, stroke=None, sw=1, dash=None):
    a = (f'<path d="M{x1:.1f} {y1:.1f}L{x2:.1f} {y2:.1f}" '
         f'stroke="{stroke or T["border"]}" stroke-width="{sw}" fill="none"')
    if dash:
        a += f' stroke-dasharray="{dash}"'
    return a + "/>"


def circle(cx, cy, r, fill=None, stroke=None, sw=1):
    a = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill or "none"}"'
    if stroke:
        a += f' stroke="{stroke}" stroke-width="{sw}"'
    return a + "/>"


def path(d, fill="none", stroke=None, sw=1.3, dash=None):
    a = f'<path d="{d}" fill="{fill}"'
    if stroke:
        a += f' stroke="{stroke}" stroke-width="{sw}"'
    if dash:
        a += f' stroke-dasharray="{dash}"'
    return a + "/>"


def tw(s, size=11):
    """
    估算文本宽度。中文按 1em、ASCII 按 0.58em 分别计算 ——
    混排时用 len() * size 会严重高估，导致 --check 报 text-overflow。
    """
    wide = sum(1 for c in str(s) if ord(c) > 0x2E80)
    return wide * size + (len(str(s)) - wide) * size * 0.58


# ==================== 图纸语言构件 ====================

def stage_banner(x, y, w, label, h=26):
    """阶段横幅：黑色矩形 + 右侧尖角，跨在该组画面上方"""
    tip = 16
    d = (f"M{x} {y}L{x+w-tip} {y}L{x+w} {y+h/2}L{x+w-tip} {y+h}L{x} {y+h}Z")
    return path(d, fill=INK) + text(x + 14, y + h / 2 + 4.5, label, 13,
                                    WHITE, "500")


def frame_tag(x, y, label):
    """帧标签：深色小块，标在帧左上角"""
    w = tw(label, 11.5) + 22
    return (rect(x, y, w, 22, INK, rx=3) +
            text(x + w / 2, y + 15, label, 11.5, WHITE, "500", "middle"))


def fidelity_tag(x, y, label):
    """保真度标签：标明该组画面画到什么程度（高保真 / 中低保真）"""
    w = tw(label, 11.5) + 22
    return (rect(x, y, w, 24, INK, rx=3) +
            text(x + w / 2, y + 16, label, 11.5, WHITE, "500", "middle"))


def anno(x, y, lines, size=11):
    """批注：紫色小字。放在帧下方横向铺开，不挤占画面宽度"""
    return "".join(text(x, y + i * 17, ln, size, ANNO)
                   for i, ln in enumerate(lines))


def cursor(x, y):
    """鼠标光标：交互动作的落点。相邻帧靠光标位置变化表达「点了哪里」"""
    d = (f"M{x} {y}L{x} {y+15}L{x+4.2} {y+11}L{x+7} {y+16.5}"
         f"L{x+9.6} {y+15.2}L{x+6.8} {y+9.8}L{x+12} {y+9.4}Z")
    return path(d, fill=WHITE, stroke=T["text1"], sw=1.2)


def flow_arrow(x1, y1, x2, y2, label=None, curve=True):
    """帧间跳转连线：细紫线 + 极短动作标签（连线是辅助，不该抢戏）"""
    if curve:
        mx = (x1 + x2) / 2
        d = f"M{x1} {y1}C{mx} {y1} {mx} {y2} {x2} {y2}"
    else:
        d = f"M{x1} {y1}L{x2} {y2}"
    o = [path(d, stroke=ANNO, sw=1.4),
         path(f"M{x2-6} {y2-4}L{x2} {y2}L{x2-6} {y2+4}", stroke=ANNO, sw=1.4)]
    if label:
        o.append(text((x1 + x2) / 2, min(y1, y2) - 8, label, 10.5, ANNO,
                      anchor="middle"))
    return "".join(o)


def emphasis_frame(x, y, w, h, label=None, lx=None, ly=None):
    """
    整帧强调：紫色粗框 + 标签，表明这是流程重点帧。

    这是突出重点的正确手段。不要改产品控件比例来「让重点更大」——
    比例一改就画出了真实产品里不存在的界面。
    """
    o = [rect(x - 8, y - 8, w + 16, h + 16, None, ANNO, 2.2, 8)]
    if label:
        lw = tw(label, 12) + 24
        o.append(rect(lx if lx is not None else x - 8,
                      ly if ly is not None else y - 34, lw, 24, ANNO, rx=4))
        o.append(text((lx if lx is not None else x - 8) + lw / 2,
                      (ly if ly is not None else y - 34) + 16, label, 11.5,
                      WHITE, "500", "middle"))
    return "".join(o)


def emphasis_area(x, y, w, h, label=None, side="right", limit=None):
    """
    局部强调：框住帧内某个控件（气泡、卡片…），带引线标签。

    side 控制标签在框的哪一侧。limit 传入画布右边界时，
    标签若会越界会自动翻到左侧 —— 强调框常用在帧的右侧面板里，
    往右放标签很容易超出画布，那会让 --check 报 text-overflow。
    """
    o = [rect(x, y, w, h, None, ANNO, 1.8, 6)]
    if not label:
        return "".join(o)
    if side == "right" and limit is not None:
        if x + w + 20 + tw(label, 11) > limit:
            side = "left"
    # 标签用一个透明底矩形承载，宽度按 tw() 算准 ——
    # 直接把 text 放在引线旁边时，转换器会把它归属到引线容器，
    # 引线只有十几像素宽，必然报 text-overflow。
    # 容器需比文字宽出充足内边距（转换器自身还有 padding），
    # 且文字在容器内居中 —— 否则会报 text-overflow。
    lw = tw(label, 11) + 26
    cy = y + h / 2
    if side == "right":
        o.append(line(x + w, cy, x + w + 12, cy, ANNO, 1.4))
        o.append(rect(x + w + 14, cy - 11, lw, 22, WHITE))
        o.append(text(x + w + 14 + lw / 2, cy + 4, label, 11, ANNO, "500",
                      "middle"))
    else:
        o.append(line(x, cy, x - 12, cy, ANNO, 1.4))
        o.append(rect(x - 14 - lw, cy - 11, lw, 22, WHITE))
        o.append(text(x - 14 - lw / 2, cy + 4, label, 11, ANNO, "500",
                      "middle"))
    return "".join(o)


# ==================== 产品界面构件（全参数化）====================

def win(x, y, w, h):
    """窗口外框"""
    return rect(x, y, w, h, T["bg"], T["border_st"], 1)


def icon(kind, x, y, size=16, color=None):
    """
    通用线性图标。kind: search plus star bell more close check chevron
    clock refresh copy like dislike table dash flow doc folder send at mic
    只画产品里常见的那些 —— 需要新图标时按同样的 stroke 风格加一个分支。
    """
    c = color or T["text2"]
    s = size / 16.0
    cx, cy = x + size / 2, y + size / 2
    if kind == "search":
        return (circle(cx - 1 * s, cy - 1 * s, 4.6 * s, None, c, 1.2) +
                line(cx + 2.3 * s, cy + 2.3 * s, cx + 5 * s, cy + 5 * s, c, 1.3))
    if kind == "plus":
        return path(f"M{cx} {cy-5*s}v{10*s}M{cx-5*s} {cy}h{10*s}", stroke=c, sw=1.3)
    if kind == "star":
        return path(f"M{cx} {cy-6*s}l{1.8*s} {4.2*s} {4.2*s} {1.8*s}"
                    f"-{4.2*s} {1.8*s}L{cx} {cy+6*s}l-{1.8*s}-{4.2*s}"
                    f"-{4.2*s}-{1.8*s} {4.2*s}-{1.8*s}z", fill=c)
    if kind == "bell":
        return (path(f"M{cx-5*s} {cy+3*s}c0-{4*s} {1*s}-{5*s} {1*s}-{7*s}"
                     f"a{3.6*s} {3.6*s} 0 0 1 {7*s} 0c0 {2*s} {1*s} {3*s} {1*s} {7*s}z",
                     stroke=c, sw=1.2) +
                path(f"M{cx-1.6*s} {cy+4.6*s}a{1.6*s} {1.6*s} 0 0 0 {3.2*s} 0",
                     stroke=c, sw=1.2))
    if kind == "more":
        return "".join(circle(cx - 4.6 * s + k * 4.6 * s, cy, 1.15 * s, c)
                       for k in range(3))
    if kind == "close":
        return path(f"M{cx-4.4*s} {cy-4.4*s}l{8.8*s} {8.8*s}"
                    f"M{cx+4.4*s} {cy-4.4*s}l-{8.8*s} {8.8*s}", stroke=c, sw=1.3)
    if kind == "check":
        return path(f"M{cx-4.4*s} {cy}l{2.8*s} {2.8*s} {6*s}-{6.4*s}",
                    stroke=c, sw=1.4)
    if kind == "chevron":
        return path(f"M{cx-3.6*s} {cy-1.8*s}l{3.6*s} {3.6*s} {3.6*s}-{3.6*s}",
                    stroke=c, sw=1.25)
    if kind == "clock":
        return (circle(cx, cy, 5.6 * s, None, c, 1.2) +
                path(f"M{cx} {cy-3.2*s}v{3.2*s}l{2.4*s} {1.6*s}", stroke=c, sw=1.2))
    if kind == "refresh":
        return (path(f"M{cx+5*s} {cy}a{5*s} {5*s} 0 0 1-{8.6*s} {3.4*s}"
                     f"M{cx-5*s} {cy}a{5*s} {5*s} 0 0 1 {8.6*s}-{3.4*s}",
                     stroke=c, sw=1.2) +
                path(f"M{cx+3.4*s} {cy-5.6*s}v{2.4*s}h-{2.4*s}", stroke=c, sw=1.2))
    if kind == "copy":
        return (rect(cx - 4 * s, cy - 3 * s, 7 * s, 8 * s, None, c, 1.15, 1.5) +
                path(f"M{cx-1*s} {cy-3*s}v-{2*s}h{7*s}v{8*s}h-{2*s}", stroke=c, sw=1.15))
    if kind == "like":
        return path(f"M{cx-4*s} {cy+5*s}v-{5*s}l{3*s}-{4*s} {1*s} {1*s}v{3*s}"
                    f"h{3.5*s}l-{1.2*s} {5*s}z", stroke=c, sw=1.15)
    if kind == "dislike":
        return path(f"M{cx-4*s} {cy-5*s}v{5*s}l{3*s} {4*s} {1*s}-{1*s}v-{3*s}"
                    f"h{3.5*s}l-{1.2*s}-{5*s}z", stroke=c, sw=1.15)
    if kind == "table":
        return (rect(cx - 5 * s, cy - 4 * s, 10 * s, 8 * s, None, c, 1.15, 1.2) +
                line(cx - 5 * s, cy - 1 * s, cx + 5 * s, cy - 1 * s, c, 1.15))
    if kind == "dash":
        return (circle(cx, cy, 5 * s, None, c, 1.15) +
                line(cx, cy, cx + 2.6 * s, cy - 2 * s, c, 1.15))
    if kind == "flow":
        return (circle(cx - 2.6 * s, cy - 3 * s, 2 * s, None, c, 1.15) +
                circle(cx + 2.6 * s, cy + 3 * s, 2 * s, None, c, 1.15) +
                line(cx - 1.4 * s, cy - 1.4 * s, cx + 1.4 * s, cy + 1.4 * s, c, 1.15))
    if kind == "doc":
        return (path(f"M{cx-4*s} {cy-6*s}h{5*s}l{3*s} {3*s}v{9*s}h-{8*s}z",
                     stroke=c, sw=1.15) +
                path(f"M{cx+1*s} {cy-6*s}v{3*s}h{3*s}", stroke=c, sw=1.15))
    if kind == "folder":
        return path(f"M{cx-5.6*s} {cy-3.4*s}h{3.4*s}l{1.6*s} {1.8*s}h{5.8*s}"
                    f"v{5.4*s}h-{10.8*s}z", stroke=c, sw=1.15)
    if kind == "send":
        return path(f"M{cx-4.6*s} {cy}h{7.6*s}M{cx-0.6*s} {cy-3.4*s}"
                    f"l{3.6*s} {3.4*s}-{3.6*s} {3.4*s}", stroke=c, sw=1.3)
    if kind == "at":
        return (circle(cx, cy, 5.6 * s, None, c, 1.2) +
                text(cx, cy + 3.4 * s, "@", 8 * s, c, anchor="middle"))
    if kind == "mic":
        return (rect(cx - 2 * s, cy - 6 * s, 4 * s, 7 * s, None, c, 1.2, 2 * s) +
                path(f"M{cx-4.2*s} {cy-0.4*s}a{4.2*s} {4.2*s} 0 0 0 {8.4*s} 0"
                     f"M{cx} {cy+3.8*s}v{2*s}", stroke=c, sw=1.2))
    # 未知类型：留一个中性方框，比画错更诚实
    return rect(x + 1, y + 1, size - 2, size - 2, None, c, 1.1, 2)


def topbar(x, y, w, crumbs, h=34, right_btns=None, right_icons=None,
           brand_dot=True):
    """
    顶栏。crumbs: 面包屑文案列表，最后一项为当前文档（加粗）
    right_btns: [(文案, 是否主按钮)]   right_icons: 图标 kind 列表
    """
    o = [rect(x, y, w, h, T["bg"]), line(x, y + h, x + w, y + h, T["border"])]
    o.append(path(f"M{x+10} {y+12}h9M{x+10} {y+17}h9M{x+10} {y+22}h5",
                  stroke=T["text2"], sw=1.3))
    o.append(path(f"M{x+28} {y+21}v-5l4.5-4 4.5 4v5h-9z", stroke=T["text2"], sw=1.3))
    cx = x + 46
    for i, c in enumerate(crumbs):
        last = i == len(crumbs) - 1
        if last and brand_dot:
            o.append(rect(cx, y + 12, 11, 11, T["brand"], rx=2))
            cx += 16
        o.append(text(cx, y + 21, c, 11.5 if last else 11,
                      T["text1"] if last else T["text2"],
                      "500" if last else None))
        cx += tw(c, 11.5 if last else 11) + 8
        if not last:
            o.append(text(cx, y + 21, "/", 11, T["text3"]))
            cx += 10
    rx0 = x + w - 12
    for i, k in enumerate(reversed(right_icons or [])):
        o.append(icon(k, rx0 - 22 - i * 24, y + 9, 16))
    bx = rx0 - 22 - len(right_icons or []) * 24
    for label, primary in reversed(right_btns or []):
        bw = tw(label, 11) + 26
        bx -= bw + 10
        o.append(rect(bx, y + 8, bw, 19, T["primary"] if primary else T["bg"],
                      None if primary else T["border"], 1, 4))
        o.append(text(bx + bw / 2, y + 21, label, 11,
                      WHITE if primary else T["text1"],
                      "500" if primary else None, "middle"))
    return "".join(o)


def sidebar(x, y, w, h, items, active=None, added=None, search="搜索"):
    """
    左侧目录树。items: [(层级, 文案, kind)]，kind 为 group 或图标名
    added: 本次需求新增的条目 —— 会加紫色左标记，让研发一眼看出改动
    """
    o = [rect(x, y, w, h, T["bg"]), line(x + w, y, x + w, y + h, T["border"])]
    if search:
        o.append(rect(x + 8, y + 8, w - 16, 20, T["bg_input"], rx=4))
        o.append(icon("search", x + 11, y + 10, 14, T["text3"]))
        o.append(text(x + 30, y + 22, search, 10.5, T["text3"]))
    cy = y + 40
    for lv, label, kind in items:
        ix = x + 10 + lv * 12
        if kind == "group":
            o.append(icon("chevron", ix - 2, cy + 1, 12))
            o.append(text(ix + 12, cy + 11, label, 10.5, T["text1"], "500"))
        else:
            on = label == active
            if on:
                o.append(rect(x + 6, cy - 3, w - 12, 20, T["primary_bg"], rx=4))
            col = T["primary"] if on else T["text2"]
            o.append(icon(kind, ix, cy + 1, 12, col))
            o.append(text(ix + 16, cy + 10, label, 10.5,
                          T["primary"] if on else T["text1"],
                          "500" if on else None))
        cy += 21
    if added:
        o.append(rect(x + 6, cy - 3, w - 12, 20, T["primary_bg"], rx=4))
        o.append(rect(x + 6, cy - 3, 2.5, 20, ANNO))
        o.append(icon("flow", x + 22, cy + 1, 12, T["primary"]))
        o.append(text(x + 38, cy + 10, added, 10.5, T["primary"], "500"))
    return "".join(o)


def tabs(x, y, w, items, active=0, h=28, trailing="+ 新建视图"):
    """标签页栏。active 项下方加主色下划线"""
    o = [line(x, y + h, x + w, y + h, T["border"])]
    cx = x + 8
    for i, label in enumerate(items):
        on = i == active
        o.append(icon("table", cx, y + 6, 12,
                      T["primary"] if on else T["text2"]))
        o.append(text(cx + 16, y + 17, label, 11,
                      T["primary"] if on else T["text2"], "500" if on else None))
        wd = 16 + tw(label, 11)
        if on:
            o.append(line(cx, y + h, cx + wd, y + h, T["primary"], 1.6))
        cx += wd + 18
    if trailing:
        o.append(text(cx, y + 17, trailing, 11, T["text2"]))
    return "".join(o)


def toolbar(x, y, w, items, h=28, lead=None, lead_primary=True, tail=None):
    """工具栏。lead 为主操作（主色），items 为普通操作，tail 为右侧按钮"""
    o = [line(x, y + h, x + w, y + h, T["border"])]
    cx = x + 8
    if lead:
        o.append(text(cx, y + 18, lead, 10.5,
                      T["primary"] if lead_primary else T["text1"], "500"))
        cx += tw(lead, 10.5) + 20
    for it in items:
        o.append(icon("table", cx, y + 9, 10, T["text2"]))
        o.append(text(cx + 13, y + 18, it, 10.5, T["text1"]))
        cx += 13 + tw(it, 10.5) + 14
    if tail:
        bw = tw(tail, 10.5) + 26
        o.append(rect(x + w - bw - 8, y + 4, bw, 20, T["bg"], T["border"], 1, 4))
        o.append(text(x + w - bw / 2 - 8, y + 18, tail, 10.5, T["text1"],
                      anchor="middle"))
    return "".join(o)


def table(x, y, w, h, cols, rows, row_h=17, foot=None, tag_colors=None):
    """
    数据表格。cols: [(列名, 相对宽)]  rows: [[单元格…]]
    单元格为 (文案, 色名) 元组时画成标签；tag_colors 提供色名 -> 色值。
    行数按可用高度自动撑满 —— 真实产品一屏十几到几十行，
    留大片空白会一眼假。行数不够时循环复用，并让首列序号连续。
    """
    o = [rect(x, y, w, h, T["bg"]), line(x, y + 18, x + w, y + 18, T["border"])]
    avail = w - 26 - 4
    k = avail / sum(cw for _, cw in cols)
    cw_list = [(n, cw * k) for n, cw in cols]
    cx = x + 26
    o.append(rect(x + 8, y + 5, 8, 8, None, T["text3"], 1, 1))
    for name, cw in cw_list:
        o.append(rect(cx, y + 5, 8, 8, None, T["text3"], 1, 1))
        o.append(text(cx + 11, y + 13, name, 9.5, T["text2"]))
        cx += cw
        o.append(line(cx - 4, y, cx - 4, y + h, T["border"], 1))
    cy = y + 18
    n_fit = max(1, int((h - 18 - 14) / row_h))
    for i in range(n_fit):
        if cy + row_h > y + h - 14:
            break
        r = rows[i % len(rows)]
        o.append(text(x + 12, cy + 11.5, str(i + 1), 9, T["text3"]))
        cx = x + 26
        for j, cell in enumerate(r):
            cw = cw_list[j][1]
            if isinstance(cell, tuple):
                lbl, ck = cell
                bg = (tag_colors or {}).get(ck, T["bg_hover"])
                o.append(rect(cx + 2, cy + 3.5, tw(lbl, 9) + 8, 11, bg, rx=2))
                o.append(text(cx + 6, cy + 12, lbl, 8.5, T["text1"]))
            else:
                o.append(text(cx + 3, cy + 12, str(cell), 9, T["text1"]))
            cx += cw
        cy += row_h
        o.append(line(x, cy, x + w, cy, T["border"], 1))
    if foot:
        o.append(text(x + 30, y + h - 6, foot, 9.5, T["text2"]))
    return "".join(o)


def table_ghost(x, y, w, h, cols, row_h=17, foot=None):
    """
    简化表格：保留列头与结构，数据行画成灰条。

    用途：当需求重点在别处（如侧边面板）时，表格只需交代
    「这是在什么页面里」。画满真实数据会让 70% 面积被雷同内容占据，
    读图的人得在几帧一样的表格里找那一小块变化，重点就丢了。
    """
    o = [rect(x, y, w, h, T["bg"]), line(x, y + 18, x + w, y + 18, T["border"])]
    avail = w - 26 - 4
    k = avail / sum(cw for _, cw in cols)
    cw_list = [(n, cw * k) for n, cw in cols]
    cx = x + 26
    o.append(rect(x + 8, y + 5, 8, 8, None, T["text3"], 1, 1))
    for name, cw in cw_list:
        o.append(rect(cx, y + 5, 8, 8, None, T["text3"], 1, 1))
        o.append(text(cx + 11, y + 13, name, 9.5, T["text3"]))
        cx += cw
        o.append(line(cx - 4, y, cx - 4, y + h, T["border"], 1))
    cy = y + 18
    for i in range(max(1, int((h - 18 - 14) / row_h))):
        if cy + row_h > y + h - 14:
            break
        o.append(text(x + 12, cy + 11.5, str(i + 1), 9, T["text3"]))
        cx = x + 26
        for _, cw in cw_list:
            o.append(rect(cx + 3, cy + 5.5, cw * 0.62, 7, T["bg_sel"], rx=2))
            cx += cw
        cy += row_h
        o.append(line(x, cy, x + w, cy, T["border"], 1))
    if foot:
        o.append(text(x + 30, y + h - 6, foot, 9.5, T["text3"]))
    return "".join(o)


def panel(x, y, w, h, title=None, sub=None, icons=None, side="left"):
    """侧边面板外框 + 头部。side 指分割线在哪一侧"""
    o = [rect(x, y, w, h, T["bg"])]
    o.append(line(x if side == "left" else x + w, y,
                  x if side == "left" else x + w, y + h, T["border"]))
    if title:
        o.append(text(x + 14, y + 16, title, 11.5, T["text1"], "500"))
    if sub:
        o.append(text(x + 14, y + 29, sub, 9, T["text3"]))
    for i, k in enumerate(reversed(icons or [])):
        o.append(icon(k, x + w - 22 - i * 22, y + 7, 14))
    if title:
        o.append(line(x + 14, y + 38, x + w - 14, y + 38, T["border"], 1))
    return "".join(o)


def input_box(x, y, w, placeholder, h=52, focus=False, chips=None,
              send=True, ready=False):
    """输入框。chips 为下方小控件文案列表"""
    o = [rect(x, y, w, h, T["bg"], T["primary"] if focus else T["border"], 1, 6)]
    o.append(text(x + 12, y + 20, placeholder, 10.5,
                  T["text1"] if focus else T["text3"]))
    cx = x + 12
    for c in (chips or []):
        cw = tw(c, 9.5) + 22
        o.append(rect(cx, y + h - 24, cw, 16, T["bg"], T["border"], 1, 4))
        o.append(text(cx + 8, y + h - 12, c, 9.5, T["text1"]))
        cx += cw + 8
    if send:
        o.append(circle(x + w - 20, y + h - 16, 9,
                        T["primary"] if (focus or ready) else T["bg_sel"]))
        o.append(icon("send", x + w - 28, y + h - 24, 16,
                      WHITE if (focus or ready) else T["text3"]))
    return "".join(o)


def bubble(x, y, w, lines, kind="user", size=10):
    """消息气泡。kind: user 浅主色底 / ai 无底"""
    h = len(lines) * 15 + 16
    o = []
    if kind == "user":
        o.append(rect(x, y, w, h, T["primary_bg"], rx=6))
    for i, ln in enumerate(lines):
        o.append(text(x + 10, y + 19 + i * 15, ln, size, T["text1"]))
    return "".join(o), h


def chip(x, y, label, hover=False, h=26):
    """胶囊控件（推荐气泡、快捷入口都是这个形态）"""
    w = tw(label, 10.5) + 22
    return (rect(x, y, w, h, T["bg_hover"] if hover else T["bg"],
                 T["border"], 1, 5) +
            text(x + 11, y + h / 2 + 4, label, 10.5, T["text1"])), w


def card(x, y, w, h, title=None, sub=None, icon_color=None, arrow=False):
    """卡片：图标 + 标题 + 副标题，可带右侧箭头"""
    o = [rect(x, y, w, h, T["bg"], T["border"], 1, 6)]
    tx = x + 12
    if icon_color:
        o.append(rect(x + 10, y + (h - 20) / 2, 20, 20, icon_color, rx=4))
        tx = x + 38
    if title:
        o.append(text(tx, y + (h / 2 - (4 if sub else -4)), title, 10.5,
                      T["text1"], "500"))
    if sub:
        o.append(text(tx, y + h / 2 + 12, sub, 9, T["text3"]))
    if arrow:
        o.append(icon("chevron", x + w - 24, y + h / 2 - 8, 14))
    return "".join(o)


def spinner(x, y, label=None, color=None):
    """加载中：圆环缺口 + 文案。表达「正在进行」的状态帧"""
    c = color or T["brand"]
    o = [circle(x + 6, y + 6, 5.5, None, T["border"], 1.3),
         path(f"M{x+6} {y+0.5}a5.5 5.5 0 0 1 5.5 5.5", stroke=c, sw=1.8)]
    if label:
        o.append(text(x + 18, y + 10, label, 9.5, T["text2"]))
    return "".join(o)


def status_row(x, y, w, label, state="running", tail=None, h=24):
    """状态条：工具调用 / 步骤执行。state: running | done"""
    o = [rect(x, y, w, h, T["bg_hover"], rx=4)]
    if state == "running":
        o.append(spinner(x + 8, y + 6))
    else:
        o.append(icon("check", x + 7, y + 4, 16, T["primary"]))
    o.append(text(x + 28, y + h / 2 + 4, label, 10, T["text1"]))
    if tail:
        o.append(text(x + w - 10, y + h / 2 + 4, tail, 9, T["text3"],
                      anchor="end"))
    return "".join(o)


def node_card(x, y, w, idx, title, sub, icon_color, icon_kind=None, h=52,
              placeholder=False):
    """
    流程节点卡片（工作流 / 流水线 / 步骤配置都是这个形态）。
    placeholder=True 画成未生成的灰条占位 —— 用于「生成中」的中间帧。
    """
    o = [text(x - 14, y + h / 2 + 4, str(idx), 12, T["text3"])]
    if placeholder:
        o.append(rect(x, y, w, h, None, T["border"], 1, 6))
        o.append(rect(x + 12, y + 11, 30, 30, T["bg_hover"], rx=6))
        o.append(rect(x + 52, y + 16, 90, 9, T["bg_hover"], rx=2))
        o.append(rect(x + 52, y + 32, 130, 8, T["bg_hover"], rx=2))
        return "".join(o)
    o.append(rect(x, y, w, h, T["bg"], T["border"], 1, 6))
    o.append(rect(x + 12, y + 11, 30, 30, icon_color, rx=6))
    if icon_kind:
        o.append(icon(icon_kind, x + 19, y + 18, 16, WHITE))
    o.append(text(x + 52, y + 22, title, 11.5, T["text1"], "500"))
    o.append(text(x + 52, y + 38, sub, 10, T["text2"]))
    return "".join(o)


def node_chain(x, y, w, h, nodes, done=None, add_btn=True, node_w=300,
               gap=30):
    """
    节点竖向串联 + 连接线 + 底部添加按钮。
    nodes: [(标题, 副标题, 图标色, 图标名)]   done: 已生成的节点数
    """
    o = [rect(x, y, w, h, T["bg"])]
    nx = x + (w - node_w) / 2
    ny = y + 34
    n_done = len(nodes) if done is None else done
    for i, nd in enumerate(nodes):
        o.append(node_card(nx, ny, node_w, i + 1, nd[0], nd[1], nd[2],
                           nd[3] if len(nd) > 3 else None,
                           placeholder=i >= n_done))
        ny += 52
        if i < len(nodes) - 1:
            o.append(line(nx + node_w / 2, ny, nx + node_w / 2, ny + gap,
                          T["border"]))
            ny += gap
    if add_btn:
        o.append(line(nx + node_w / 2, ny, nx + node_w / 2, ny + 26,
                      T["border"], 1, "3 3"))
        o.append(rect(nx + node_w / 2 - 11, ny + 26, 22, 22, T["bg"],
                      T["border"], 1, 4))
        o.append(icon("plus", nx + node_w / 2 - 8, ny + 29, 16))
    return "".join(o)


def toggle(x, y, on=False, w=26, h=14):
    """开关控件"""
    return (rect(x, y, w, h, T["primary"] if on else T["bg_sel"], rx=h / 2) +
            circle(x + (w - h / 2) if on else x + h / 2, y + h / 2,
                   h / 2 - 2, WHITE))


def zoom_bar(x, y, pct="100%"):
    """画布缩放控件（画布类页面右下角）"""
    o = [icon("more", x, y, 16)]
    o.append(line(x + 22, y, x + 22, y + 16, T["border"], 1))
    o.append(icon("search", x + 30, y, 16))
    o.append(text(x + 52, y + 12, pct, 9.5, T["text1"]))
    o.append(icon("plus", x + 84, y, 16))
    return "".join(o)


# ============================================================
#  AI 对话/面板内的结果组件
#  以下构件来自实战：AI 把分析结果以「组件」而非 Markdown 文本
#  返回，是当前一类高频需求。窄面板（300px 上下）里放图表和表格
#  有其固有难点，这几个构件已处理好：轴标签防重叠、列宽等比缩放、
#  超宽列截断 + 横向滚动条。
# ============================================================

FIELD_ICONS = {"text": "A≡", "num": "#", "select": "◉", "date": "▤",
               "money": "¥", "multi": "◎"}


def chart_card(x, y, w, h, title, series_label=None, kind="line",
               data=None, y_ticks=None, x_labels=None,
               btn="+ 添加至仪表盘", show_btn=True, expand=True,
               hover_idx=None):
    """
    对话/面板内的图表卡片：标题 + 右上操作按钮 + 展开图标 + 图例
    + 折线或柱状 + 数据标签 + 轴标签。

    kind:      "line" | "bar"
    show_btn:  False 用于无权限场景（按钮整体不显示）
    hover_idx: 指定第几个数据点浮出 tooltip —— 逐帧演示 Hover 态时用
    """
    o = [rect(x, y, w, h, T["bg"], T["border"], 1, 6)]
    o.append(text(x + 14, y + 22, title, 11.5, T["text1"], "500"))
    bx = x + w - 14
    if expand:
        o.append(path(f"M{bx-14} {y+13}h7v7M{bx-7} {y+13}l-8 8"
                      f"M{bx-21} {y+27}v-7h7", stroke=T["text2"], sw=1.2))
        bx -= 28
    if show_btn:
        bw = tw(btn, 10) + 20
        o.append(rect(bx - bw, y + 11, bw, 20, T["bg"], T["border"], 1, 4))
        o.append(text(bx - bw / 2, y + 25, btn, 10, T["text2"], anchor="middle"))
    if series_label:
        o.append(circle(x + 18, y + 44, 3.2, T["primary"]))
        o.append(text(x + 26, y + 47, series_label, 9.5, T["text2"]))
    # 绘图区
    px0, py0 = x + 52, y + 62
    pw, ph = w - 68, h - 62 - 32
    for i, tk in enumerate(y_ticks or []):
        ty = py0 + ph - (i / max(1, len(y_ticks) - 1)) * ph
        o.append(line(px0, ty, px0 + pw, ty, T["bg_hover"], 1))
        o.append(text(px0 - 10, ty + 3.5, str(tk), 8.5, T["text3"], anchor="end"))
    data = data or []
    n = len(data)
    if n:
        mx = max(max(data), 1)
        step = pw / max(1, n - 1) if kind == "line" else pw / n
        pts = []
        for i, v in enumerate(data):
            cx = px0 + (i * step if kind == "line" else i * step + step / 2)
            cy = py0 + ph - (v / mx) * ph * 0.92
            pts.append((cx, cy))
        if kind == "line":
            o.append(path("M" + "L".join(f"{a:.1f} {b:.1f}" for a, b in pts),
                          stroke=T["primary"], sw=1.8))
            for i, (cx, cy) in enumerate(pts):
                o.append(text(cx, cy - 9, str(data[i]), 9, T["primary"],
                              anchor="middle"))
        else:
            for i, (cx, cy) in enumerate(pts):
                bw2 = min(30, step * 0.55)
                o.append(rect(cx - bw2 / 2, cy, bw2, py0 + ph - cy,
                              T["primary"], rx=2))
                o.append(text(cx, cy - 6, str(data[i]), 9, T["primary"],
                              anchor="middle"))
        for i, lb in enumerate(x_labels or []):
            if i < n:
                o.append(text(pts[i][0], py0 + ph + 16, lb, 9, T["text3"],
                              anchor="middle"))
        # Hover tooltip
        if hover_idx is not None and hover_idx < n:
            hx, hy = pts[hover_idx]
            o.append(circle(hx, hy, 4, T["bg"], T["primary"], 1.8))
            lbl = f"{(x_labels or [''])[hover_idx]}  {data[hover_idx]}"
            twd = tw(lbl, 9.5) + 20
            o.append(rect(hx + 10, hy - 26, twd, 22, T["text1"], rx=4))
            o.append(text(hx + 10 + twd / 2, hy - 11, lbl, 9.5, WHITE,
                          anchor="middle"))
            o.append(cursor(hx + 2, hy + 2))
    return "".join(o)


def base_table_card(x, y, w, h, cols, rows, row_h=32,
                    btn="+ 添加新数据表", show_btn=True, copy=True,
                    expand=True, truncate_last=True):
    """
    对话/面板内的数据表卡片：右上按钮组 + 表头带字段类型图标
    + 数据行 + 底部横向滚动条。窄面板里放表格的通用形态。

    cols: [(字段名, 类型, 相对宽)]  类型见 FIELD_ICONS
    truncate_last: 最后一列画成被截断 —— 窄面板放不下时的真实表现
    show_btn=False 用于无建表权限场景
    """
    o = [rect(x, y, w, h, T["bg"], T["border"], 1, 6)]
    # 顶部按钮组
    bx = x + w - 12
    if expand:
        o.append(path(f"M{bx-12} {y+10}h6v6M{bx-6} {y+10}l-7 7"
                      f"M{bx-18} {y+23}v-6h6", stroke=T["text2"], sw=1.2))
        bx -= 24
    if copy:
        o.append(icon("copy", bx - 16, y + 8, 15))
        bx -= 24
    if show_btn:
        bw = tw(btn, 9.5) + 18
        o.append(rect(bx - bw, y + 7, bw, 18, T["bg"], T["border"], 1, 4))
        o.append(text(bx - bw / 2, y + 20, btn, 9.5, T["text2"], anchor="middle"))
    # 表格
    ty = y + 34
    o.append(line(x, ty, x + w, ty, T["border"], 1))
    avail = w - 34
    k = avail / sum(c[2] for c in cols)
    cw = [(c[0], c[1], c[2] * k) for c in cols]
    cx = x + 34
    for name, ft, cwd in cw:
        o.append(text(cx, ty + 20, FIELD_ICONS.get(ft, "A≡"), 9, T["text3"]))
        o.append(text(cx + 16, ty + 20, name, 10, T["text2"]))
        cx += cwd
        if cx < x + w - 4:
            o.append(line(cx - 6, ty, cx - 6, y + h - 12, T["border"], 1))
    ty += 28
    o.append(line(x, ty, x + w, ty, T["border"], 1))
    for i, r in enumerate(rows):
        if ty + row_h > y + h - 16:
            break
        o.append(text(x + 20, ty + row_h / 2 + 4, str(i + 1), 9.5, T["text3"],
                      anchor="middle"))
        cx = x + 34
        for j, cell in enumerate(r):
            cwd = cw[j][2]
            ft = cw[j][1]
            clipped = truncate_last and j == len(r) - 1
            val = str(cell)
            if ft == "select":
                o.append(rect(cx, ty + row_h / 2 - 8, tw(val, 9.5) + 12, 16,
                              T["primary_bg"], rx=3))
                o.append(text(cx + 6, ty + row_h / 2 + 4, val, 9.5, T["text1"]))
            elif ft in ("num", "money"):
                o.append(text(cx + cwd - 14, ty + row_h / 2 + 4, val, 10,
                              T["text1"], anchor="end"))
            else:
                o.append(text(cx, ty + row_h / 2 + 4, val, 10, T["text1"]))
            cx += cwd
        ty += row_h
        o.append(line(x, ty, x + w, ty, T["border"], 1))
    # 底部横向滚动条（设计图里有）
    o.append(rect(x + 6, y + h - 10, w * 0.22, 4, T["border_st"], rx=2))
    return "".join(o)


def dark_menu(x, y, items, w=None, sub=None, hl=None):
    """
    深色下拉菜单（弹出层）。飞书这类产品的二级操作菜单是深底白字，
    与页面上的浅色控件对比强烈，不要画成浅色卡片。

    items: 菜单项文字列表。项尾写 ">" 表示有下级，会画成箭头而非字符
    sub:   二级菜单项；画在一级右侧，紧贴带 ">" 的那一项
    hl:    高亮第几项（表示鼠标悬停在它上面，二级菜单由它展开）
    """
    labels = [i[:-1].rstrip() if i.endswith(">") else i for i in items]
    has_sub = [i.endswith(">") for i in items]
    w = w or max(tw(l, 10.5) for l in labels) + 46
    h = len(items) * 24 + 10
    o = [rect(x, y, w, h, T["text2"], rx=5)]
    for i, lb in enumerate(labels):
        iy = y + 5 + i * 24
        if hl == i:  # 悬停态：更深一档底色，与产品的 hover 表达一致
            o.append(rect(x + 3, iy, w - 6, 24, T["text1"], rx=4))
        o.append(text(x + 12, iy + 16, lb, 10.5, WHITE))
        if has_sub[i]:  # 右侧小箭头，而不是在文字里塞 ">"
            ax, ay = x + w - 16, iy + 12
            o.append(path(f"M{ax} {ay-3.5}l3.5 3.5l-3.5 3.5",
                          stroke=WHITE, sw=1.2))
    if sub:
        si = has_sub.index(True) if any(has_sub) else 0
        sw_ = max(tw(s, 10.5) for s in sub) + 28
        sy = y + 5 + si * 24
        o.append(rect(x + w + 6, sy, sw_, len(sub) * 24 + 10, T["text2"], rx=5))
        for i, s in enumerate(sub):
            o.append(text(x + w + 18, sy + 21 + i * 24, s, 10.5, WHITE))
    return "".join(o)


def toast(x, y, label, w=None):
    """顶部居中提示条"""
    w = w or tw(label, 10.5) + 40
    return (rect(x - w / 2, y, w, 30, T["text1"], rx=5) +
            icon("check", x - w / 2 + 12, y + 7, 15, WHITE) +
            text(x + 6, y + 20, label, 10.5, WHITE, anchor="middle"))


def svg_doc(w, h, body):
    """包成完整 SVG 文档"""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">{rect(0, 0, w, h, WHITE)}{body}</svg>')
