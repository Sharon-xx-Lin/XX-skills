# prd-prototype-demo

**读 PRD + 产品截图，产出逐帧交互线框图和 UI 一致的可交互 demo。**

一个给产品经理用的 [Claude Code](https://claude.com/claude-code) skill。目标很具体：让 AI 生成的需求原型**不再一眼就是 AI 做的**，能直接拿去评审。

[English](./README.en.md) · [MIT License](../LICENSE)

![逐帧线框图](docs/images/wireframe-overview.png)

> 上图是完整产出：5 帧交互线框图，配色来自 [ant.design](https://ant.design) 官方文档站截图的**像素采样**。
> 采出的主色 `#1677FF`、边框 `#F0F0F0`、表头底 `#FAFAFA` 与 Ant Design 官方 design token 完全一致 ——
> 这是对采样准确度的交叉验证。（需求内容是虚构的，仅用于演示）

---

## 它解决什么问题

产品经理让 AI 生成需求 demo，产出常常「一眼就是 AI 做的」，拿给设计和研发看反而引起反感。

但成因需要说准，否则会用错力气。**模型的看图模仿能力其实不弱** —— 给它一张截图，它能采出接近真实的主色、做出像样的表格。实测对比中，无约束的一方单次生成的视觉还原度也不低。

真正的问题在四处，都不是审美能力问题：

| # | 成因 | 实测证据 |
|---|---|---|
| 1 | **配色每次都在重新发明** | 同一产品的第二个需求，无约束方只有 4 个 token 与第一个需求同名（2 个取值还不一致），另造了 28 个新颜色。单看每次都协调，放在一起就不是一个产品了 |
| 2 | **颜色绕过 token 写死** | `:root` 之外有 55 处硬编码色值，含几个连自己 token 里都没有的颜色。改几轮就漂回模型默认审美 |
| 3 | **交付形态不可用** | demo 做成多文件依赖，生成方自测正常，但把主文件发到群里，同事打开一片空白 |
| 4 | **画的不是界面，是需求说明** | 在画板上排一堆「区域 A：KPI 卡 ×4」「需新增」的文字卡片，看着像图，其实是 PRD 的图形化排版，评审时依然说不清交互 |

所以这个 skill 的重点不是「教模型模仿」，而是**把设计语言固化成可复用可校验的档案，并保证画出来的是真界面、交付出去真能用**。

---

## 两个产物

| 产物 | 是什么 | 给谁看 |
|---|---|---|
| **逐帧线框图**（SVG） | 真实界面的等比还原，按交互顺序逐帧铺开 | 团队评审对齐交互流程 |
| **可交互 HTML demo** | 单文件、双击即开、从起点自动演播到终点 | 研发和设计看「长什么样、怎么动」 |

两者共享 **UI 档案**（保证视觉同源）和**画面清单**（保证画的是同一批界面）。

### 线框图长什么样

![线框图单帧](docs/images/wireframe-frame.png)

每一帧是**完整的产品窗口**，不是「区域 A：KPI 卡 ×4」这种文字卡片。图纸语言（紫色强调框、帧标签、批注、待确认项）与产品界面严格分离 —— 想突出重点用紫框，绝不改产品控件的尺寸比例。

### demo 演的是过程

三张连续截图，来自同一次自动演播：

| 勾选行，批量操作条浮出 | 导出中的进度态 | 完成，结果提示 |
|---|---|---|
| ![](docs/images/demo-select.png) | ![](docs/images/demo-progress.png) | ![](docs/images/demo-done.png) |

注意中间那张：**进度态必须演出来**。只画「点击」和「完成」两帧的话，评审时说不清中间发生了什么。左上角有实时帧号指示（`A2` / `A4` / `A5`），与线框图帧号一一对应。

---

## 快速开始

### 安装

```bash
git clone https://github.com/Sharon-xx-Lin/XX-skills.git
# Claude Code 用户目录（跨项目可用）
cp -r XX-skills/prd-prototype-demo ~/.claude/skills/
# 或项目内
cp -r XX-skills/prd-prototype-demo .claude/skills/
```

依赖：Python 3.8+、[Pillow](https://pypi.org/project/Pillow/)（采样）、[Playwright](https://playwright.dev/python/)（渲染核对，可选但强烈建议）。

```bash
pip install Pillow playwright && playwright install chromium
```

验证安装（用内置的合成示例档案，不需要你的产品截图）：

```bash
cd examples && python3 quickstart.py
```

跑出 `quickstart.svg` 就说明环境就绪。

### 用法

安装后直接跟 Claude 说话即可，不用记命令：

```
我要给这个需求做原型图和 demo。
PRD 在 ./prd.md，产品截图在 ./shots/ 下（3 张）。
```

Claude 会走一遍六步流程，在**画之前**先给你一份画面清单确认 —— 这一步会顺带暴露 PRD 里没写清的地方。

---

## 工作流

```
① 收素材（PRD + 截图） → ② UI 档案 → ③ 画面清单 → ④ 逐帧线框图 → ⑤ HTML demo → ⑥ 自检
                          可复用资产      澄清关口      SVG 图纸         单文件        机械校验
```

**② 做一次，长期复用。** 后续需求从 ③ 开始，不用再上传截图。

### ② UI 档案是核心资产

档案存在你的工作目录 `artifacts/ui-profiles/{产品名}/`，四件套：

```
tokens.css       全部设计变量 —— 唯一的颜色来源
components.css   组件样式 —— 只允许引用 tokens 变量，不许写字面量色值
icons.svg        线性图标 sprite —— 给足图标是结构性消灭 emoji 的手段
profile.md       布局骨架、信息密度、交互范式、采样置信度
```

颜色**必须像素采样，不能靠眼睛估**。肉眼对相近色完全不可靠，而颜色错一点点「像不像」就崩了：

```bash
python3 scripts/sample_ui.py --image shot.png --list-points   # 点位建议
python3 scripts/sample_ui.py --image shot.png --auto          # 调色板摸底
python3 scripts/sample_ui.py --image shot.png --spec points.json --out t.json
```

采样按元素角色分策略，且**方向随底色自动翻转**（这条是深色主题的生死线）：

| 角色 | 策略 |
|---|---|
| `bg` | 窗口内众数 |
| `text` | 与底色反差最大的那一端（亮底取最暗、暗底取最亮） |
| `accent` | 彩度最高（`max-min`，**不是** HSV 饱和度） |
| `line` | 扫描线法：垂直穿过边框，找与底色反差最大的连续像素带 |

### ⑤ demo 演的是过程，不是结果

**最容易做错、而且做错了自己看不出来的一步。**

失败长这样：打开 demo 就是一屏「AI 已经答完」的终态。看着挺完整，其实等于把线框图的某一帧做成了网页 —— 评审的人问「这个功能是怎么一步步走完的」，demo 答不了。

根源是「可交互」这个词有歧义：**控件能响应点击 ≠ 演示了交互过程**。前者是终态加事件监听，后者是时间轴。

正确做法是 demo 打开后**从起点自动演播到终点**，帧序与画面清单一致：

| 该演的过程 | 具体做法 |
|---|---|
| 用户输入 | 逐字敲进输入框，提交按钮由禁用变可用 |
| 提交 | 点击（可加涟漪）→ 起始页内容退场 |
| 后台处理 | spinner「处理中…」，**此时结果必须还没出现** |
| 生成 | 文字流式吐出（末尾闪烁光标），不是整段瞬现 |
| 结果落位 | 图表按路径描画、表格逐行渐显 |

配套三件：模拟光标（让「点了哪里」看得见）、帧号指示（与线框图帧号对齐）、「重播 / 跳到结果」两个按钮（评审现场不想等动画）。

`assets/demo-skeleton.html` 是按此搭好的骨架，内置时间轴播放器。

---

## 目录结构

```
SKILL.md                            六步流程主文档，Claude 读它
├── references/                      查阅型细节
│   ├── ui-profile-schema.md        档案四件套字段说明
│   ├── whiteboard.md               协作白板能力边界 + 安全 SVG 子集
│   └── frame-by-frame.md           逐帧规范 + 比例实测量法 + 错误清单
├── scripts/
│   ├── wireframe_kit.py            桌面构件库（41 个构件）
│   ├── mobile_kit.py               移动端构件库（14 构件 + 39 图标）
│   ├── sample_ui.py                像素采样，明暗主题自适应
│   ├── check_demo.py               单文件可用性 + 配色规范校验
│   ├── check_profile_drift.py      档案漂移检测
│   ├── screenshot.py               file:// 渲染核对
│   └── whiteboard_publish.py       SVG 校验 / 预览（+ 飞书画板发布，可选）
└── assets/
    ├── demo-skeleton.html          单文件 demo 骨架（内置时间轴播放器）
    ├── frame-generator-skeleton.py 可直接跑的线框图生成器骨架
    ├── tokens-template.css
    ├── components-template.css
    └── icons-base.svg              55 个通用线性图标

├── examples/                        安装验证（合成配色，非真实产品）
│   ├── quickstart.py                跑一遍出示例线框图
│   └── ui-profiles/demo-saas-light/ 示例档案四件套
└── docs/images/                     README 配图
```

---

## 三个机械校验

静态检查很便宜，但能拦住绝大多数回归：

```bash
python3 scripts/check_demo.py --html demo.html            # 字面量色值 / emoji / 外链 / 图标完整性
python3 scripts/check_profile_drift.py --profile <档案> --target demo.html
python3 scripts/screenshot.py --html demo.html --out s.png # 用 file:// 加载，正是用户双击的方式
```

`check_profile_drift.py` 查同名 token 取值是否一致、有无档案外新增颜色 —— **新增颜色是最需警惕的信号**，那是配色逐轮漂移的机制。

**渲染核对不是形式主义。** 实测中它拦下过静态检查完全查不出的问题：图标全部消失、条形图不可见、整套配色因为一个 Python 引用陷阱静默失效。

---

## 关于飞书画板（可选）

`whiteboard_publish.py` 的校验和本地预览（`--check` / `--dry-run`）**不需要任何在线服务**，任何环境都能跑。

只有「发布到飞书画板」这一条需要飞书环境和字节内部的 `lark-cli`。**没有也完全不影响使用** —— 生成的 SVG 可以直接分享、转 PNG，或导入 Figma / FigJam / Miro / tldraw 等任意支持 SVG 的协作白板。

欢迎 PR 其他白板的发布适配。

---

## 验证情况

已在两个差异很大的产品上跑通四个真实需求：

| 产品形态 | 需求数 | 档案来源 |
|---|---|---|
| 浅色 B 端桌面（表格类 SaaS 的 AI 侧边栏） | 3 | 内部产品截图 |
| 深色移动端（阅读类 App 的内容聚合页） | 1 | 内部产品截图 |
| 浅色 B 端桌面（Ant Design 5） | 1（本 README 配图） | [ant.design](https://ant.design) 官方文档站，**采样值与官方 token 一致** |

跨产品验证暴露并修复了 9 个缺陷，其中 5 个是「方向性假设」类的 —— 不报错、静默产出错值，只有渲染核对能发现。这类问题**只有换产品才会暴露**，是这个 skill 目前最主要的质量来源。

**已知边界**：只验证过 2 个产品；浅色移动端、Pad、Web 响应式未实测；`use_profile()` 的语义 token 做了多命名兼容，但换命名习惯差异大的产品第一次跑可能仍需磨合。

---

## 不适用于

- 纯代码实现真实功能（这是原型工具，不是开发工具）
- 设计稿转生产代码
- 与产品界面无关的流程图 / 架构图

---

## License

[MIT](../LICENSE)
