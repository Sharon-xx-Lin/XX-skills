#!/usr/bin/env python3
"""
逐帧线框图生成器骨架 —— 复制改写用。

这份骨架的价值在于把「怎么排」变成可运行的代码：帧函数 + 组装函数 +
按实测比例的尺寸常量。文字规范容易理解偏差，能跑的骨架不会。

用法：
  1. 复制本文件到工作目录
  2. 改 PROFILE 指向你的 UI 档案
  3. 按实测比例改 W/H/SB/PANEL
  4. 改 TREE / COLS / ROWS 为产品真实内容
  5. 按画面清单写 frame_xx() 函数，每帧只变一处
  6. 在 main() 里排布
  7. python3 本文件 → 得到 SVG，再用 whiteboard_publish.py 发布

关键纪律：
  - 每帧是完整产品窗口，不是文字卡片
  - 相邻帧只有一处实质差异
  - 比例按实测，突出重点用紫框而非改尺寸
"""
import os
import sys

# ---- 定位 wireframe_kit ----
# 本文件设计上要被复制到工作目录改写，复制后 __file__ 旁边不再有 scripts/，
# 所以不能只 insert 自身目录（那样 import 直接 ModuleNotFoundError）。
# 依次尝试：环境变量 → 本文件的兄弟/父级 scripts → 已装 skill 的常见位置。
def _locate_kit():
    here = os.path.dirname(os.path.abspath(__file__))
    cands = []
    if os.environ.get("PRD_SKILL_DIR"):
        cands.append(os.path.join(os.environ["PRD_SKILL_DIR"], "scripts"))
    cands += [
        here,                                             # 与 kit 同目录
        os.path.join(here, "scripts"),                    # 工作目录下有 scripts/
        os.path.join(os.path.dirname(here), "scripts"),   # skill 内原位（assets/ 的兄弟）
        os.path.expanduser("~/.claude/skills/prd-prototype-demo/scripts"),
    ]
    for c in cands:
        if os.path.isfile(os.path.join(c, "wireframe_kit.py")):
            return c
    sys.exit(
        "找不到 wireframe_kit.py。请任选一种：\n"
        "  export PRD_SKILL_DIR=<skill 根目录>\n"
        "  或把 skill 的 scripts/wireframe_kit.py 复制到本文件旁边"
    )


sys.path.insert(0, _locate_kit())
import wireframe_kit as k  # noqa: E402

# ==================== 配置 ====================
PROFILE = "artifacts/ui-profiles/YOUR-PRODUCT"   # ← 改成你的档案路径
PROFILE_LINE = 54                                # 上一行的行号，仅用于报错提示
OUT = "wireframe.svg"

# 尺寸：必须按参考图实测比例，不要凭感觉给
# 量法见 references/frame-by-frame.md「比例」一节
W, H = 1180, 660      # 单帧窗口
SB = 150              # 侧边栏 ≈ 12.7%
PANEL = 322           # 右侧面板 ≈ 27.3%（实测值，勿为突出重点改大）
GAP_X, GAP_Y = 170, 230
PER_ROW = 3           # 一行放几帧，超过 4 帧总宽会大到必须缩放

# 产品真实内容 —— 全部来自 PRD 和截图，不要编
TREE = [
    (0, "1.分组名", "group"),
    (1, "数据表 A", "table"),
    (1, "数据表 B", "table"),
    (0, "2.分组名", "group"),
    (1, "看板 A", "dash"),
]
COLS = [("字段1", 74), ("字段2", 52), ("字段3", 92), ("字段4", 62)]
ROWS = [["值1", "值2", "2026/05/21 22:30", "399.98"]]
CRUMBS = ["空间名", "文档名"]


# ==================== 帧公共骨架 ====================
def shell(ox, oy, panel_title=None, panel_sub=None, active=None, added=None,
          ghost=True):
    """
    一帧的公共部分。ghost=True 时表格降为灰条 ——
    当需求重点在右侧面板时用，让视线自然落到面板上。
    """
    o = [k.win(ox, oy, W, H)]
    o.append(k.topbar(ox, oy, W, CRUMBS,
                      right_btns=[("分享", True), ("自动化", False)],
                      right_icons=["bell", "star", "plus", "search"]))
    cy = oy + 34
    o.append(k.sidebar(ox, cy, SB, H - 34, TREE, active=active, added=added))
    mx, mw = ox + SB, W - SB - PANEL
    o.append(k.tabs(mx, cy, mw, ["表格视图 1"]))
    o.append(k.toolbar(mx, cy + 28, mw, ["字段配置", "筛选", "分组", "排序"],
                       lead="+ 添加记录"))
    tbl = k.table_ghost if ghost else k.table
    args = (mx, cy + 56, mw, H - 34 - 56, COLS)
    o.append(tbl(*args, foot="90 条记录") if ghost
             else tbl(*args, ROWS, foot="90 条记录"))
    px = ox + W - PANEL
    if panel_title:
        o.append(k.panel(px, cy, PANEL, H - 34, panel_title, panel_sub,
                         icons=["refresh", "clock", "more", "close"]))
    return o, px, cy


def panel_top(px, py):
    """面板内容区起点"""
    return px + 16, py + 50


# ==================== 逐帧 ====================
# 命名建议与画面清单一致（A1/A2/...），便于对照

def frame_a1(ox, oy):
    """A1 初始态：用户输入"""
    o, px, py = shell(ox, oy, "新会话")
    bx, by = panel_top(px, py)
    o.append(k.text(bx, by + 14, "今天能帮你些什么？", 13, k.T["text1"], "500"))
    ch, _ = k.chip(bx, by + 40, "快捷入口")
    o.append(ch)
    o.append(k.input_box(px + 16, oy + H - 74, PANEL - 32,
                         "用户输入的真实 query（来自 PRD 示例）",
                         focus=True, chips=["模式"]))
    o.append(k.cursor(px + PANEL - 36, oy + H - 34))
    o.append(k.frame_tag(ox, oy - 32, "A1 输入"))
    o.append(k.anno(ox, oy + H + 34, ["这一帧说明什么（依据 PRD x.x）"]))
    return o


def frame_a2(ox, oy):
    """A2 进行中：与 A1 的差异只有「出现了状态条」"""
    o, px, py = shell(ox, oy, "会话标题", "内容由 AI 生成")
    bx, by = panel_top(px, py)
    ub, uh = k.bubble(px + 40, by, PANEL - 52, ["用户消息第一行", "第二行"])
    o.append(ub)
    o.append(k.status_row(bx, by + uh + 14, PANEL - 32, "工具名", "running",
                          "调用中…"))
    o.append(k.spinner(bx, by + uh + 54, "处理中"))
    o.append(k.input_box(px + 16, oy + H - 74, PANEL - 32, "输入框占位文案",
                         chips=["模式"]))
    o.append(k.frame_tag(ox, oy - 32, "A2 进行中"))
    o.append(k.anno(ox, oy + H + 34, [
        "★ 若某个后台判断发生在此刻，在这里标出来 —— 时序信息容易被漏掉"]))
    return o


def frame_a3(ox, oy):
    """A3 核心帧：结果 + 关键控件出现。整帧加紫框强调"""
    o, px, py = shell(ox, oy, "会话标题", "内容由 AI 生成")
    bx, by = panel_top(px, py)
    o.append(k.status_row(bx, by, PANEL - 32, "工具名", "done", "已完成"))
    yy = by + 38
    o.append(k.text(bx, yy, "结果结论一行（真实数据）", 11.5, k.T["text1"], "500"))
    for i, ln in enumerate(["过程说明第一行", "过程说明第二行"]):
        o.append(k.text(bx, yy + 22 + i * 17, ln, 11))
    # 结果操作图标组
    for i, ic in enumerate(["copy", "like", "dislike", "more"]):
        o.append(k.icon(ic, bx + i * 20, yy + 62, 14))
    # 关键控件 + 局部强调
    ch, cw = k.chip(bx, yy + 90, "本需求的关键控件", hover=True)
    o.append(ch)
    o.append(k.emphasis_area(bx - 6, yy + 84, cw + 12, 38, "控件说明",
                             limit=ox + W - 10))
    o.append(k.cursor(bx + cw + 14, yy + 82))
    o.append(k.input_box(px + 16, oy + H - 74, PANEL - 32, "输入框占位文案",
                         chips=["模式"]))
    o.append(k.frame_tag(ox, oy - 32, "A3 结果 + 关键控件"))
    o.append(k.anno(ox, oy + H + 34, [
        "★ 核心规则写在这里（PRD x.x）",
        "待确认：PRD 没写清的地方逐条列出"]))
    # 整帧强调：标签放右上角，避免与左上的帧标签重叠
    o.append(k.emphasis_frame(ox, oy, W, H, "★ 本需求核心画面",
                              lx=ox + W - 172, ly=oy - 34))
    return o


def frame_a4(ox, oy):
    """A4 跳转到另一种页面形态（如画布页）"""
    o = [k.win(ox, oy, W, H)]
    o.append(k.topbar(ox, oy, W, CRUMBS,
                      right_btns=[("分享", True)], right_icons=["search"]))
    cy = oy + 34
    mw = W - PANEL
    # 画布页顶部工具条
    o.append(k.rect(ox, cy, mw, 32, k.T["bg"]))
    o.append(k.line(ox, cy + 32, ox + mw, cy + 32, k.T["border"]))
    o.append(k.text(ox + 30, cy + 20, "画布标题", 11.5, k.T["text1"], "500"))
    o.append(k.toggle(ox + 168, cy + 10, on=False))
    o.append(k.rect(ox + mw - 90, cy + 7, 78, 19, k.T["primary"], rx=4))
    o.append(k.text(ox + mw - 51, cy + 20, "保存并启用", 10.5, k.WHITE,
                    "500", "middle"))
    # 节点链：done 控制已生成几个，用于表达「生成中」
    nodes = [("节点 1", "配置摘要", k.T["primary"], "clock"),
             ("节点 2", "配置摘要", k.T["primary"], "search"),
             ("节点 3", "配置摘要", k.T["brand"], "send")]
    o.append(k.node_chain(ox, cy + 32, mw, H - 66, nodes, done=2,
                          add_btn=False))
    o.append(k.zoom_bar(ox + mw - 140, oy + H - 26))
    px = ox + W - PANEL
    o.append(k.panel(px, cy, PANEL, H - 34, "会话标题", "内容由 AI 生成",
                     icons=["more", "close"]))
    bx, by = panel_top(px, cy)
    o.append(k.status_row(bx, by, PANEL - 32, "3 个步骤", "done"))
    o.append(k.input_box(px + 16, oy + H - 74, PANEL - 32, "输入框占位文案"))
    o.append(k.frame_tag(ox, oy - 32, "A4 生成中"))
    o.append(k.anno(ox, oy + H + 34, ["节点按序落位，未生成的画成灰条占位"]))
    return o


# ==================== 组装 ====================
FRAMES = [
    # (帧函数, 帧间连线到下一帧的标签)
    (frame_a1, "发送"),
    (frame_a2, "结果生成"),
    (frame_a3, "点击控件"),
    (frame_a4, None),
]

STAGES = [
    # (起始帧索引, 跨几帧, 横幅文案)
    (0, 2, "① 阶段一说明"),
    (2, 1, "② 阶段二 · 核心交互"),
    (3, 1, "③ 阶段三说明"),
]


def main():
    # 骨架带的是占位路径，直接跑必然找不到 —— 给出可操作提示而不是裸 traceback
    try:
        r = k.use_profile(PROFILE)
    except FileNotFoundError:
        sys.exit(
            f"找不到 UI 档案：{PROFILE}\n"
            f"请把本文件第 {PROFILE_LINE} 行的 PROFILE 改成你的档案目录"
            f"（该目录下应有 tokens.css）。\n"
            f"还没有档案？先用 scripts/sample_ui.py 对产品截图采样生成。"
        )
    if r["missing"]:
        print(f"提示：档案缺少 token {r['missing']}，已用中性默认值。"
              f"这些位置值得回去补采样。")

    parts = []
    rows = [FRAMES[i:i + PER_ROW] for i in range(0, len(FRAMES), PER_ROW)]

    def pos(idx):
        r_i, c_i = divmod(idx, PER_ROW)
        return 90 + c_i * (W + GAP_X), 250 + r_i * (H + GAP_Y)

    for idx, (fn, label) in enumerate(FRAMES):
        ox, oy = pos(idx)
        parts += fn(ox, oy)
        # 同行内连线
        if label and (idx + 1) % PER_ROW != 0 and idx + 1 < len(FRAMES):
            nx, ny = pos(idx + 1)
            parts.append(k.flow_arrow(ox + W + 8, oy + H / 2, nx - 8,
                                      ny + H / 2, label))
        # 跨行连线
        elif label and idx + 1 < len(FRAMES):
            nx, ny = pos(idx + 1)
            parts.append(k.flow_arrow(ox + W / 2, oy + H + 90,
                                      nx + W / 2, ny - 44, label))

    for start, span, label in STAGES:
        ox, oy = pos(start)
        bw = span * W + (span - 1) * GAP_X
        parts.append(k.stage_banner(ox, oy - 90, bw, label))
    # 保真度标签：每行首帧左上
    for r_i in range(len(rows)):
        ox, oy = pos(r_i * PER_ROW)
        parts.append(k.fidelity_tag(ox, oy - 58, "高保真度"))

    total_w = 90 + PER_ROW * (W + GAP_X) + 60
    total_h = 250 + len(rows) * (H + GAP_Y) + 60
    head = [
        k.text(90, 70, "需求名 · 线框图", 40, k.T["text1"], "bold"),
        k.text(90, 108, "流程名　场景：xxx　关键输入：xxx", 16, k.T["text2"]),
        k.text(90, 136, "一行说明为什么这样排（如：面板为需求主体，故表格简化为上下文）",
               13, k.T["text3"]),
        k.line(90, 152, total_w - 90, 152, k.T["border"]),
    ]
    svg = k.svg_doc(total_w, total_h, "".join(head + parts))
    open(OUT, "w").write(svg)
    print(f"已生成 {OUT}  {total_w}x{total_h}  元素约 {svg.count('<') - 1}")
    print("下一步：")
    print(f"  python3 whiteboard_publish.py --svg {OUT} --dry-run   # 先看本地预览")
    print(f"  python3 whiteboard_publish.py --svg {OUT} --title '需求名 · 线框图'")


if __name__ == "__main__":
    main()
