#!/usr/bin/env python3
"""
移动端构件库 —— 在 wireframe_kit 之上补移动端专属构件。

为什么单独一个文件：移动端不是「窄一点的桌面」。画布按逻辑像素
（375×812）、必画状态栏/导航栏/标签栏、没有 hover 只有按压、
信息密度和字号都是另一套。混进桌面构件库只会让两边都别扭。

用法
----
    import mobile_kit as m
    m.k.use_profile("artifacts/ui-profiles/my-app")   # 先载入档案
    m.load_extra("artifacts/ui-profiles/my-app")      # 再载入移动端扩展 token
    o = [m.phone(0, 0), m.statusbar(0, 0)]
    nb, nh = m.navbar(0, m.H_STATUS, title="标题", sub="副标题",
                      right=["search", "select"])
    ...

所有颜色一律走 k.T[...]（档案 tokens），不写字面量色值。
图纸语言构件（frame_tag / anno / emphasis_* / cursor）仍从 k 取。
"""
import os
import sys

# 与 wireframe_kit 同目录时直接可 import；被复制到工作目录时按环境变量找
_here = os.path.dirname(os.path.abspath(__file__))
for _c in (_here, os.path.join(os.environ.get("PRD_SKILL_DIR", ""), "scripts"),
           os.path.expanduser("~/.claude/skills/prd-prototype-demo/scripts")):
    if _c and os.path.isfile(os.path.join(_c, "wireframe_kit.py")):
        sys.path.insert(0, _c)
        break
import wireframe_kit as k
from wireframe_kit import rect, text, line, circle, path, icon, tw, T, WHITE

# 移动端基准尺寸（iPhone 逻辑像素，画板上 1:1 使用）
SW, SH = 375, 812          # 屏幕
H_STATUS, H_NAV, H_TAB = 44, 44, 49
PAD = 16                   # 页面左右边距


def phone(x, y, w=SW, h=SH):
    """手机外框：深色主题下用根背景色 + 一圈弱边框（画板无阴影）"""
    return rect(x, y, w, h, T["bg"], T["border_st"], 1, 8)


def statusbar(x, y, w=SW, time="19:20"):
    """状态栏：时间 + 信号/wifi/电量"""
    o = [text(x + 26, y + 27, time, 12, T["text1"], "500")]
    bx = x + w - 22
    # 电量
    o.append(rect(bx - 22, y + 16, 22, 11, T["bg"], T["text1"], 1, 3))
    o.append(rect(bx - 20, y + 18, 15, 7, T["text1"], rx=1))
    # wifi（三段弧用折线近似，画板不支持复杂弧）
    wx = bx - 34
    o.append(path(f"M{wx-7} {y+23}q7 -7 14 0", stroke=T["text1"], sw=1.6))
    o.append(path(f"M{wx-4} {y+26}q4 -4 8 0", stroke=T["text1"], sw=1.6))
    o.append(circle(wx, y + 28.5, 1.2, T["text1"]))
    # 信号：4 根递增竖条
    sx = bx - 52
    for i in range(4):
        bh = 4 + i * 2.4
        o.append(rect(sx + i * 4, y + 26 - bh, 2.6, bh, T["text1"], rx=1))
    return "".join(o)


def navbar(x, y, w=SW, title="", sub=None, back=True,
           right=None, left_text=None):
    """
    导航栏。right 传图标名列表（最多 2 个，本产品范式）。
    sub 传统计副标题 —— 标题下方小字，会自动加高。
    """
    o = []
    h = H_NAV if not sub else H_NAV + 14
    cy = y + (22 if not sub else 20)
    if back:
        o.append(path(f"M{x+24} {cy-6}l-6 6l6 6", stroke=T["text_icon"], sw=1.8))
    if left_text:
        o.append(text(x + PAD, cy + 4, left_text, 15, T["text_icon"]))
    if title:
        o.append(text(x + w / 2, cy + 6, title, 17, T["text1"], "500",
                      anchor="middle"))
    if sub:
        o.append(text(x + w / 2, cy + 24, sub, 12, T["text3"], anchor="middle"))
    for i, ic in enumerate(right or []):
        o.append(icon(ic, x + w - 20 - 32 - i * 34, cy - 8, 19, T["text_icon"]))
    return "".join(o), h


def segbar(x, y, w, segs, active=0):
    """
    胶囊型分段控件。segs = [(名称, 计数或 None)]
    PRD 4.2：灰底容器 + 圆角选中块 + 加粗文字。
    深色主题下选中块是「亮块 + 白字」（浅色版是白块 + 深字，对比关系一致）。
    """
    o = [rect(x, y, w, 32, T["bg_segbar"], rx=16)]
    n = len(segs)
    iw = (w - 6) / n
    for i, (name, cnt) in enumerate(segs):
        sx = x + 3 + i * iw
        lb = name if cnt is None else f"{name} {cnt}"
        if i == active:
            o.append(rect(sx, y + 3, iw, 26, T["bg_sel"], rx=13))
        o.append(text(sx + iw / 2, y + 20, lb, 13,
                      T["text1"] if i == active else T["text3"],
                      "600" if i == active else "400", anchor="middle"))
    return "".join(o)


def agg_card(x, y, w, num, unit, title, meta, right="cover", h=96):
    """
    聚合项卡片：三行范式 + 左文右图（PRD 6.2，沿用笔记页）
    right: cover(书封 3:4) / avatar(圆形头像) / square(公众号头像)
    """
    o = [rect(x, y, w, h, T["bg_card"], rx=12)]
    tx = x + PAD
    # 第一行：大号数字 + 小号量词
    o.append(text(tx, y + 34, str(num), 26, T["text1"], "600"))
    o.append(text(tx + tw(str(num), 26) + 5, y + 34, unit, 13, T["text1"]))
    # 第二行：主标题（超长中部截断）
    maxw = w - PAD * 2 - 60
    o.append(text(tx, y + 60, _mid_trunc(title, maxw, 15), 15, T["text1"]))
    # 第三行：次级统计
    o.append(text(tx, y + 80, meta, 12, T["text3"]))
    # 右侧图
    rx0 = x + w - PAD - (36 if right == "cover" else 44)
    if right == "cover":
        o.append(rect(rx0, y + h / 2 - 24, 36, 48, T["bg_quote"], rx=3))
        o.append(line(rx0 + 4, y + h / 2 - 24, rx0 + 4, y + h / 2 + 24,
                      T["border"], 1))
    elif right == "avatar":
        o.append(circle(rx0 + 22, y + h / 2, 22, T["bg_quote"]))
        o.append(icon("user", rx0 + 11, y + h / 2 - 11, 22, T["text3"]))
    else:
        o.append(rect(rx0, y + h / 2 - 22, 44, 44, T["bg_quote"], rx=8))
        o.append(icon("article", rx0 + 11, y + h / 2 - 11, 22, T["text3"]))
    return "".join(o)


def _mid_trunc(s, maxw, size):
    """中部截断 + …（PRD：沿用笔记页范式）"""
    if tw(s, size) <= maxw:
        return s
    lo, hi = 1, len(s)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        cand = s[:mid // 2] + "…" + s[-(mid - mid // 2):]
        if tw(cand, size) <= maxw:
            lo = mid
        else:
            hi = mid - 1
    return s[:lo // 2] + "…" + s[-(lo - lo // 2):]


def post_card(x, y, w, name, date, body, quote=None, src=None,
              likes=None, comments=None, liked=True, h=None):
    """
    内容卡片（存量复用，PRD 6.3）：
    头像 + 昵称 + 时间 + 正文 + 灰底引用块 + 来源书卡 + 互动行
    body / quote 传字符串列表（每项一行）
    """
    body = body if isinstance(body, list) else [body]
    quote = quote if quote is None or isinstance(quote, list) else [quote]
    # 自动算高
    hh = 16 + 36 + 12 + len(body) * 22
    if quote:
        hh += 12 + 12 + len(quote) * 20 + 12
    if src:
        hh += 12 + 48
    hh += 12 + 24 + 16
    h = h or hh
    o = [rect(x, y, w, h, T["bg_card"], rx=12)]
    cx, cy = x + PAD, y + PAD
    # 头部
    o.append(circle(cx + 18, cy + 18, 18, T["bg_quote"]))
    o.append(icon("user", cx + 7, cy + 7, 22, T["text3"]))
    o.append(text(cx + 46, cy + 23, name, 14, T["accent_nick"]))
    o.append(text(x + w - PAD, cy + 23, date, 12, T["text4"], anchor="end"))
    cy += 36 + 12
    # 正文
    for ln in body:
        o.append(text(cx, cy + 14, ln, 15, T["text1"]))
        cy += 22
    # 引用块
    if quote:
        cy += 12
        qh = 12 + len(quote) * 20 + 12
        o.append(rect(cx, cy, w - PAD * 2, qh, T["bg_quote"], rx=8))
        qy = cy + 12
        for ln in quote:
            o.append(text(cx + 12, qy + 14, ln, 13, T["text2"]))
            qy += 20
        cy += qh
    # 来源书卡
    if src:
        cy += 12
        o.append(rect(cx, cy, 30, 40, T["bg"], rx=2))
        o.append(text(cx + 42, cy + 17, src[0], 13, T["text1"]))
        o.append(text(cx + 42, cy + 34, src[1], 11, T["text3"]))
        cy += 48
    # 互动行
    cy += 12
    third = (w - PAD * 2) / 3
    o.append(icon("share", cx + third * 0.5 - 8, cy + 4, 17, T["text3"]))
    o.append(icon("comment", cx + third * 1.5 - 16, cy + 4, 17, T["text3"]))
    if comments is not None:
        o.append(text(cx + third * 1.5 + 6, cy + 17, str(comments), 13,
                      T["text3"]))
    lc = T["primary"] if liked else T["text3"]
    o.append(icon("heart" + ("-solid" if liked else ""),
                  cx + third * 2.5 - 16, cy + 4, 17, lc))
    if likes is not None:
        o.append(text(cx + third * 2.5 + 6, cy + 17, str(likes), 13, lc))
    return "".join(o), h


def tabbar(x, y, w=SW, active=3):
    """底部标签栏：阅读 / 书架 / 书友 / 我"""
    o = [line(x, y, x + w, y, T["border"], 1)]
    items = [("book", "阅读"), ("shelf", "书架"), ("planet", "书友"),
             ("user-solid", "我")]
    iw = w / 4
    for i, (ic, lb) in enumerate(items):
        cx = x + iw * (i + 0.5)
        c = T["brand"] if i == active else T["text3"]
        o.append(icon(ic, cx - 11, y + 8, 22, c))
        o.append(text(cx, y + 42, lb, 10, c, anchor="middle"))
    return "".join(o)


def searchbar(x, y, w, placeholder="搜索赞过的内容", value=None,
              caret=False):
    """搜索页顶部：输入框 + 取消"""
    o = []
    cw = tw("取消", 15) + 4
    iw = w - PAD * 2 - cw - 12
    o.append(rect(x + PAD, y, iw, 36, T["bg_input"], rx=8))
    o.append(icon("search", x + PAD + 10, y + 9, 18, T["text3"]))
    tx = x + PAD + 36
    if value:
        o.append(text(tx, y + 24, value, 15, T["text1"]))
        if caret:
            cx = tx + tw(value, 15) + 2
            o.append(rect(cx, y + 10, 1.6, 17, T["primary"]))
    else:
        o.append(text(tx, y + 24, placeholder, 15, T["text3"]))
        if caret:
            o.append(rect(tx, y + 10, 1.6, 17, T["primary"]))
    o.append(text(x + w - PAD, y + 24, "取消", 15, T["link"], anchor="end"))
    return "".join(o)


def empty_state(x, y, w, title, desc, action=None, icon_name="inbox"):
    """空态：图形 + 主文案 + 说明 + 直达按钮（PRD 6.6 三准则）"""
    o = []
    cx = x + w / 2
    o.append(icon(icon_name, cx - 26, y, 52, T["text4"]))
    o.append(text(cx, y + 86, title, 16, T["text1"], anchor="middle"))
    dy = y + 110
    for ln in (desc if isinstance(desc, list) else [desc]):
        o.append(text(cx, dy, ln, 13, T["text3"], anchor="middle"))
        dy += 20
    if action:
        o.append(text(cx, dy + 22, action, 15, T["link"], anchor="middle"))
    return "".join(o)


def skeleton_card(x, y, w, h=96):
    """骨架屏卡片（PRD：加载中用骨架屏，禁止抢先显示无记录）"""
    o = [rect(x, y, w, h, T["bg_card"], rx=12)]
    o.append(rect(x + PAD, y + 20, 46, 22, T["bg_quote"], rx=4))
    o.append(rect(x + PAD, y + 52, w * 0.5, 13, T["bg_quote"], rx=3))
    o.append(rect(x + PAD, y + 73, w * 0.32, 11, T["bg_quote"], rx=3))
    o.append(rect(x + w - PAD - 36, y + h / 2 - 24, 36, 48, T["bg_quote"], rx=3))
    return "".join(o)


def grid_cell(x, y, w, h, ic, ic_color, name, sub, dot=False):
    """「我的」页 2×1 宫格单元"""
    o = [rect(x, y, w, h, T["bg_card"], rx=16)]
    o.append(circle(x + PAD + 18, y + 30, 18, ic_color))
    o.append(icon(ic, x + PAD + 8, y + 20, 20, WHITE))
    o.append(text(x + PAD + 48, y + 37, name, 16, T["text1"]))
    if dot:
        o.append(circle(x + PAD + 48 + tw(name, 16) + 10, y + 30, 3.5,
                        T["primary"]))
    o.append(text(x + PAD, y + 66, sub, 12, T["text3"]))
    return "".join(o)


def seg_note(x, y, w, txt):
    """段内说明行（「书友」段阈值说明）"""
    return text(x + PAD, y + 12, txt, 12, T["text3"])


def highlight_text(x, y, s, kw, size=15, color=None, hl=None):
    """把 s 里的 kw 用强调色标出（搜索命中高亮）"""
    color = color or T["text1"]
    hl = hl or T["primary"]
    o, cx = [], x
    i = s.find(kw)
    if i < 0:
        return text(x, y, s, size, color)
    if i:
        o.append(text(cx, y, s[:i], size, color))
        cx += tw(s[:i], size)
    o.append(text(cx, y, kw, size, hl, "500"))
    cx += tw(kw, size)
    if i + len(kw) < len(s):
        o.append(text(cx, y, s[i + len(kw):], size, color))
    return "".join(o)


# 把档案里的扩展 token 塞进 T，供上面构件使用
def load_extra(profile_path):
    import re, os
    src = open(os.path.join(profile_path, "tokens.css"), encoding="utf-8").read()
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    raw = dict(re.findall(r"(--[A-Za-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})\s*;", src))
    # 移动端常用的扩展 token。档案里没有的会退回同色系推导值，
    # 不会撞色 —— 但值得回去补采样，返回值里会列出来。
    extra = {
        "bg_card":     ["--bg-card", "--bg-secondary", "--bg-hover"],
        "bg_quote":    ["--bg-quote", "--bg-elevated", "--bg-input"],
        "bg_segbar":   ["--bg-segbar", "--bg-input", "--bg-card"],
        "text4":       ["--text-4", "--text-quaternary", "--text-3"],
        "text_icon":   ["--text-icon", "--text-2"],
        "accent_nick": ["--accent-nickname", "--accent-name", "--link"],
    }
    miss = []
    for sem, names in extra.items():
        for n in names:
            if n in raw:
                T[sem] = raw[n].upper()
                break
        else:
            # 兜底：按主背景朝白推导，深浅主题都不撞色
            T[sem] = k._mix(T["bg"], "#FFFFFF",
                            0.10 if sem.startswith("bg") else 0.60)
            miss.append(names[0])
    # 产品自有的模块图标色（--icon-*）原样带上，有多少收多少
    for var, val in raw.items():
        if var.startswith("--icon-"):
            T[var[2:].replace("-", "_")] = val.upper()
    return miss


# ==================== 移动端图标扩展 ====================
# wireframe_kit.icon() 是为 B 端桌面攒的 21 个图标，移动端这些都没有。
# 风格对齐档案 icons.svg：圆头端点、stroke 1.7（按 size 缩放）。
_BASE_ICON = k.icon


def icon(kind, x, y, size=20, color=None):          # noqa: F811
    c = color or T["text2"]
    s = size / 24.0                                  # 本组按 24 基准设计
    cx, cy = x + size / 2, y + size / 2
    sw = 1.7 * s * 1.2
    P = lambda d: path(d, stroke=c, sw=sw)           # noqa: E731

    if kind == "back":
        return P(f"M{cx+3*s} {cy-7.5*s}l-{7.5*s} {7.5*s}l{7.5*s} {7.5*s}")
    if kind == "chevron-right":
        return P(f"M{cx-2.5*s} {cy-6.5*s}l{6.5*s} {6.5*s}l-{6.5*s} {6.5*s}")
    if kind == "arrow-right":
        return P(f"M{cx-7*s} {cy}h{14*s}M{cx+1*s} {cy-5.5*s}l{5.5*s} {5.5*s}"
                 f"l-{5.5*s} {5.5*s}")
    if kind == "select":
        return (circle(cx, cy, 8.4 * s, None, c, sw) +
                P(f"M{cx-3.6*s} {cy+0.2*s}l{2.5*s} {2.5*s}l{4.7*s}-{4.9*s}"))
    if kind == "heart":
        return P(f"M{cx} {cy+8*s}s-{7.5*s}-{4.7*s}-{7.5*s}-{9.6*s}"
                 f"a{4.4*s} {4.4*s} 0 0 1 {7.5*s}-{2.8*s}"
                 f"a{4.4*s} {4.4*s} 0 0 1 {7.5*s} {2.8*s}"
                 f"c0 {4.9*s}-{7.5*s} {9.6*s}-{7.5*s} {9.6*s}z")
    if kind == "heart-solid":
        return path(f"M{cx} {cy+8*s}s-{7.5*s}-{4.7*s}-{7.5*s}-{9.6*s}"
                    f"a{4.4*s} {4.4*s} 0 0 1 {7.5*s}-{2.8*s}"
                    f"a{4.4*s} {4.4*s} 0 0 1 {7.5*s} {2.8*s}"
                    f"c0 {4.9*s}-{7.5*s} {9.6*s}-{7.5*s} {9.6*s}z", fill=c)
    if kind == "comment":
        return P(f"M{cx+8.4*s} {cy-0.4*s}c0 {3.9*s}-{3.8*s} {7.1*s}-{8.4*s} {7.1*s}"
                 f"c-{1*s} 0-{2*s}-{0.15*s}-{3*s}-{0.45*s}L{cx-7.5*s} {cy+8*s}"
                 f"l{1.35*s}-{3.75*s}a{6.8*s} {6.8*s} 0 0 1-{2.25*s}-{4.85*s}"
                 f"c0-{3.9*s} {3.8*s}-{7.1*s} {8.4*s}-{7.1*s}s{8.4*s} {3.2*s} {8.4*s} {7.1*s}z")
    if kind == "share":
        return P(f"M{cx} {cy+3.5*s}v-{11*s}M{cx-4*s} {cy-3.5*s}l{4*s}-{4*s}l{4*s} {4*s}"
                 f"M{cx-6.5*s} {cy+1*s}v{5.9*s}a{1.6*s} {1.6*s} 0 0 0 {1.6*s} {1.6*s}"
                 f"h{9.8*s}a{1.6*s} {1.6*s} 0 0 0 {1.6*s}-{1.6*s}v-{5.9*s}")
    if kind == "user":
        return (circle(cx, cy - 3.6 * s, 3.9 * s, None, c, sw) +
                P(f"M{cx-7.2*s} {cy+8.4*s}c0-{3.5*s} {3.2*s}-{6.3*s} {7.2*s}-{6.3*s}"
                  f"s{7.2*s} {2.8*s} {7.2*s} {6.3*s}"))
    if kind == "user-solid":
        return (circle(cx, cy - 3.6 * s, 3.9 * s, c) +
                path(f"M{cx-7.2*s} {cy+8.4*s}c0-{3.5*s} {3.2*s}-{6.3*s} {7.2*s}-{6.3*s}"
                     f"s{7.2*s} {2.8*s} {7.2*s} {6.3*s}z", fill=c))
    if kind == "users":
        return (circle(cx - 3 * s, cy - 3.6 * s, 3.6 * s, None, c, sw) +
                P(f"M{cx-8.4*s} {cy+7.5*s}c0-{3*s} {2.4*s}-{5.4*s} {5.4*s}-{5.4*s}"
                  f"s{5.4*s} {2.4*s} {5.4*s} {5.4*s}") +
                P(f"M{cx+4*s} {cy-6.8*s}a{3.4*s} {3.4*s} 0 0 1 0 {6.4*s}"
                  f"M{cx+5.6*s} {cy+2.4*s}c{1.7*s} {0.8*s} {2.8*s} {2.5*s} {2.8*s} {4.5*s}"))
    if kind == "book":
        return (P(f"M{cx-7.5*s} {cy-6.6*s}a{1.4*s} {1.4*s} 0 0 1 {1.4*s}-{1.4*s}"
                  f"h{5.4*s}a{1.4*s} {1.4*s} 0 0 1 {1.4*s} {1.4*s}v{14.6*s}"
                  f"a{2.4*s} {2.4*s} 0 0 0-{2.4*s}-{1.6*s}h-{4.4*s}"
                  f"a{1.4*s} {1.4*s} 0 0 1-{1.4*s}-{1.4*s}z") +
                P(f"M{cx+7.5*s} {cy-6.6*s}a{1.4*s} {1.4*s} 0 0 0-{1.4*s}-{1.4*s}"
                  f"h-{5.4*s}a{1.4*s} {1.4*s} 0 0 0-{1.4*s} {1.4*s}v{14.6*s}"
                  f"a{2.4*s} {2.4*s} 0 0 1 {2.4*s}-{1.6*s}h{4.4*s}"
                  f"a{1.4*s} {1.4*s} 0 0 0 {1.4*s}-{1.4*s}z"))
    if kind == "shelf":
        return P(f"M{cx-8.4*s} {cy-5.5*s}h{16.8*s}M{cx-8.4*s} {cy}h{16.8*s}"
                 f"M{cx-8.4*s} {cy+5.5*s}h{16.8*s}")
    if kind == "planet":
        return (circle(cx, cy, 6.4 * s, None, c, sw) +
                P(f"M{cx-9.4*s} {cy+3.4*s}q{9.4*s}-{6.8*s} {18.8*s}-{6.8*s}"))
    if kind == "article":
        return (rect(cx - 7.8 * s, cy - 8.4 * s, 15.6 * s, 16.8 * s, None, c,
                     sw, 1.8 * s) +
                P(f"M{cx-4.2*s} {cy-4*s}h{8.4*s}M{cx-4.2*s} {cy}h{8.4*s}"
                  f"M{cx-4.2*s} {cy+4*s}h{5*s}"))
    if kind == "note":
        return (P(f"M{cx+6.6*s} {cy-7.4*s}a{2.1*s} {2.1*s} 0 0 1 0 {3*s}"
                  f"L{cx-2.6*s} {cy+4.8*s}l-{4*s} {1.2*s}l{1.2*s}-{4*s}z") +
                P(f"M{cx+2.4*s} {cy-5.2*s}l{2.8*s} {2.8*s}"))
    if kind == "rank":
        return P(f"M{cx-6*s} {cy+7*s}v-{8*s}M{cx} {cy+7*s}v-{14*s}"
                 f"M{cx+6*s} {cy+7*s}v-{5.5*s}")
    if kind == "reading":
        return (circle(cx, cy, 8.4 * s, None, c, sw) +
                P(f"M{cx-3.6*s} {cy}h{6.4*s}M{cx+0.4*s} {cy-2.6*s}l{2.8*s} {2.6*s}"
                  f"l-{2.8*s} {2.6*s}"))
    if kind == "check-circle":
        return (circle(cx, cy, 8.4 * s, None, c, sw) +
                P(f"M{cx-3.8*s} {cy+0.2*s}l{2.6*s} {2.6*s}l{4.9*s}-{5.1*s}"))
    if kind == "booklist":
        return (rect(cx - 7.8 * s, cy - 7.8 * s, 15.6 * s, 15.6 * s, None, c,
                     sw, 2 * s) +
                P(f"M{cx-4*s} {cy-3.4*s}h{8*s}M{cx-4*s} {cy}h{8*s}"
                  f"M{cx-4*s} {cy+3.4*s}h{5*s}"))
    if kind == "eye":
        return (P(f"M{cx-9.2*s} {cy}s{3.6*s}-{6.2*s} {9.2*s}-{6.2*s}"
                  f"s{9.2*s} {6.2*s} {9.2*s} {6.2*s}s-{3.6*s} {6.2*s}-{9.2*s} {6.2*s}"
                  f"S{cx-9.2*s} {cy} {cx-9.2*s} {cy}z") +
                circle(cx, cy, 2.9 * s, None, c, sw))
    if kind == "history":
        return (P(f"M{cx-7.8*s} {cy}a{7.8*s} {7.8*s} 0 1 0 {2.5*s}-{5.7*s}"
                  f"L{cx-7.8*s} {cy-3.4*s}") +
                P(f"M{cx-7.8*s} {cy-7.4*s}v{4*s}h{4*s}") +
                P(f"M{cx} {cy-3.6*s}v{3.6*s}l{2.8*s} {1.8*s}"))
    if kind == "monitor":
        return (rect(cx - 8.8 * s, cy - 7 * s, 17.6 * s, 11.6 * s, None, c,
                     sw, 1.8 * s) +
                P(f"M{cx-3*s} {cy+8*s}h{6*s}M{cx} {cy+4.6*s}v{3.4*s}"))
    if kind == "tablet":
        return (rect(cx - 6.4 * s, cy - 8.6 * s, 12.8 * s, 17.2 * s, None, c,
                     sw, 2 * s) +
                P(f"M{cx-1.4*s} {cy+5.8*s}h{2.8*s}"))
    if kind == "inbox":
        return (P(f"M{cx-8.4*s} {cy+1.2*s}L{cx-6*s} {cy-6.6*s}"
                  f"a{1.6*s} {1.6*s} 0 0 1 {1.5*s}-{1.2*s}h{9*s}"
                  f"a{1.6*s} {1.6*s} 0 0 1 {1.5*s} {1.2*s}l{2.4*s} {7.8*s}") +
                P(f"M{cx-8.4*s} {cy+1.2*s}h{4.2*s}l{1.2*s} {2.4*s}h{6*s}"
                  f"l{1.2*s}-{2.4*s}h{4.2*s}v{4.6*s}"
                  f"a{1.8*s} {1.8*s} 0 0 1-{1.8*s} {1.8*s}h-{13.2*s}"
                  f"a{1.8*s} {1.8*s} 0 0 1-{1.8*s}-{1.8*s}z"))
    if kind == "trash":
        return (P(f"M{cx-7.2*s} {cy-4.8*s}h{14.4*s}"
                  f"M{cx-2.4*s} {cy-4.8*s}v-{1.8*s}a{1.2*s} {1.2*s} 0 0 1 {1.2*s}-{1.2*s}"
                  f"h{2.4*s}a{1.2*s} {1.2*s} 0 0 1 {1.2*s} {1.2*s}v{1.8*s}") +
                P(f"M{cx-5.4*s} {cy-4.8*s}l{0.9*s} {11.4*s}"
                  f"a{1.6*s} {1.6*s} 0 0 0 {1.6*s} {1.5*s}h{5.8*s}"
                  f"a{1.6*s} {1.6*s} 0 0 0 {1.6*s}-{1.5*s}l{0.9*s}-{11.4*s}"))
    if kind == "mail":
        return (rect(cx - 9 * s, cy - 6.6 * s, 18 * s, 13.2 * s, None, c,
                     sw, 1.6 * s) +
                P(f"M{cx-8.4*s} {cy-5.6*s}L{cx} {cy+1*s}l{8.4*s}-{6.6*s}"))
    if kind == "settings":
        return (P(f"M{cx-8*s} {cy-4.5*s}h{16*s}M{cx-8*s} {cy}h{16*s}"
                  f"M{cx-8*s} {cy+4.5*s}h{16*s}") +
                circle(cx - 3 * s, cy - 4.5 * s, 2.1 * s, T["bg"], c, sw) +
                circle(cx + 3 * s, cy + 4.5 * s, 2.1 * s, T["bg"], c, sw))
    if kind == "scan":
        return P(f"M{cx-8*s} {cy-3.5*s}v-{2.9*s}a{1.6*s} {1.6*s} 0 0 1 {1.6*s}-{1.6*s}"
                 f"h{2.9*s}M{cx+3.5*s} {cy-8*s}h{2.9*s}"
                 f"a{1.6*s} {1.6*s} 0 0 1 {1.6*s} {1.6*s}v{2.9*s}"
                 f"M{cx+8*s} {cy+3.5*s}v{2.9*s}a{1.6*s} {1.6*s} 0 0 1-{1.6*s} {1.6*s}"
                 f"h-{2.9*s}M{cx-3.5*s} {cy+8*s}h-{2.9*s}"
                 f"a{1.6*s} {1.6*s} 0 0 1-{1.6*s}-{1.6*s}v-{2.9*s}"
                 f"M{cx-5.5*s} {cy}h{11*s}")
    if kind == "quote":
        return path(f"M{cx-3*s} {cy-5.4*s}c-{2.5*s} {1.4*s}-{3.6*s} {3.4*s}-{3.6*s} {6*s}"
                    f"c0 {2*s} {1.2*s} {3.4*s} {2.9*s} {3.4*s}"
                    f"c{1.5*s} 0 {2.6*s}-{1.1*s} {2.6*s}-{2.5*s}"
                    f"c0-{1.4*s}-{1*s}-{2.4*s}-{2.3*s}-{2.4*s}h-{0.8*s}"
                    f"c{0.2*s}-{1.3*s} {1*s}-{2.4*s} {2.3*s}-{3.2*s}z"
                    f"M{cx+5.4*s} {cy-5.4*s}c-{2.5*s} {1.4*s}-{3.6*s} {3.4*s}-{3.6*s} {6*s}"
                    f"c0 {2*s} {1.2*s} {3.4*s} {2.9*s} {3.4*s}"
                    f"c{1.5*s} 0 {2.6*s}-{1.1*s} {2.6*s}-{2.5*s}"
                    f"c0-{1.4*s}-{1*s}-{2.4*s}-{2.3*s}-{2.4*s}h-{0.8*s}"
                    f"c{0.2*s}-{1.3*s} {1*s}-{2.4*s} {2.3*s}-{3.2*s}z", fill=c)
    if kind == "alert":
        return (circle(cx, cy, 8.4 * s, None, c, sw) +
                P(f"M{cx} {cy-4.2*s}v{5*s}") + circle(cx, cy + 4 * s, 0.9 * s, c))
    if kind == "clock":
        return (circle(cx, cy, 8.4 * s, None, c, sw) +
                P(f"M{cx} {cy-4.8*s}v{4.8*s}l{3.4*s} {2.2*s}"))
    # 其余转交 wireframe_kit（search / plus / close / check / more / bell / refresh…）
    return _BASE_ICON(kind, x, y, size, color)
