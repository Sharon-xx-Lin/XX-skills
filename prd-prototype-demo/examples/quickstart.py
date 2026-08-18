#!/usr/bin/env python3
"""
安装验证脚本 —— 用示例档案生成一张线框图，确认环境就绪。

    cd examples && python3 quickstart.py

跑通说明：Python 依赖装好了、构件库可用、档案能载入。
接下来把 PROFILE 换成你自己的档案，把帧函数改成你的需求即可。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import wireframe_kit as k  # noqa: E402

PROFILE = os.path.join(HERE, "ui-profiles", "demo-saas-light")
W, H, SB, PANEL = 1180, 660, 220, 320

TREE = [(0, "工作台", "group"), (1, "我的任务", "table"), (1, "全部项目", "table"),
        (0, "报表", "group"), (1, "月度概览", "table"), (1, "成员效率", "table")]
COLS = [("任务 ID", 90), ("任务名称", 180), ("负责人", 90),
        ("状态", 80), ("截止日期", 110), ("优先级", 80)]
ROWS = [
    ["T-1024", "补充埋点方案", "张三", "进行中", "2026-09-01", "高"],
    ["T-1025", "登录页改版走查", "李四", "待开始", "2026-09-03", "中"],
    ["T-1026", "接口性能压测", "王五", "已完成", "2026-08-28", "高"],
    ["T-1027", "文档补充与归档", "赵六", "进行中", "2026-09-10", "低"],
]


def frame(ox, oy, tag, note, active="我的任务"):
    o = [k.win(ox, oy, W, H)]
    o.append(k.topbar(ox, oy, W, ["示例空间", "项目管理"],
                      right_btns=[("新建", True)], right_icons=["bell", "search"]))
    cy = oy + 34
    o.append(k.sidebar(ox, cy, SB, H - 34, TREE, active=active))
    mx, mw = ox + SB, W - SB
    o.append(k.tabs(mx, cy, mw, ["表格视图"]))
    o.append(k.toolbar(mx, cy + 28, mw, ["筛选", "排序", "分组"], lead="+ 添加任务"))
    # rows 会按可用高度自动循环撑满 —— 真实产品一屏十几行，留白会一眼假
    o.append(k.table(mx, cy + 56, mw, H - 34 - 56, COLS, ROWS, foot="128 条记录"))
    o.append(k.frame_tag(ox, oy - 32, tag))
    o.append(k.anno(ox, oy + H + 34, note))
    return o


def main():
    r = k.use_profile(PROFILE)
    print(f"档案载入：{r['loaded']}/13  主题={r['theme']}")
    if r["missing"]:
        print("缺失 token（用兜底值）:", r["missing"])

    parts = []
    parts += frame(90, 200, "A1 工作台默认态",
                   ["示例：新用户安装验证用的最小线框图",
                    "把 PROFILE 换成你自己的档案，把帧函数改成你的需求即可"])
    parts += frame(90 + W + 170, 200, "A2 切换到报表",
                   ["与 A1 的差异：侧边栏选中项变化 —— 逐帧的本质是「每帧只变一处」"],
                   active="月度概览")
    parts.append(k.flow_arrow(90 + W + 10, 200 + H / 2,
                              90 + W + 160, 200 + H / 2, "点报表"))
    parts.append(k.stage_banner(90, 104, 2 * W + 170, "① 示例流程"))
    head = [k.text(90, 70, "安装验证 · 示例线框图", 32, k.T["text1"], "bold")]

    total_w = 90 + 2 * (W + 170) + 60
    svg = k.svg_doc(total_w, 200 + H + 220, "".join(head + parts))
    out = os.path.join(HERE, "quickstart.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"已生成 {out}（元素约 {svg.count('<') - 1} 个）")
    print("\n下一步：")
    print("  python3 ../scripts/whiteboard_publish.py \\")
    print("      --svg quickstart.svg --dry-run     # 出本地预览图核对")


if __name__ == "__main__":
    main()
