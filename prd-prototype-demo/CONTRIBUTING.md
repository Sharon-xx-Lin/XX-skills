# 参与改进 prd-prototype-demo

仓库通用约定见[根 README 的「开发约定」](../README.md#开发约定)。本文只补充这个 skill 特有的、踩过坑才知道的纪律。

## 改采样逻辑：方向判断不能写死

`scripts/sample_ui.py` 里凡是「哪个像素才是真值」的判断，都**必须由背景亮度推导方向，不能写成固定的一端**。

最初的实现把三处方向写死了，浅色主题下全部正确，换到深色主题全线崩掉：

| 角色 | 写死的实现 | 深色下的后果 |
|---|---|---|
| `text` | 取窗口内最暗像素 | 白字被采成近黑 —— 文字在深底上几乎不可见 |
| `line` | 取亮度最低的连续像素带 | 深底上的浅色分隔线完全采不到 |
| `accent` | 按 HSV 饱和度排序 | `(20,0,0)` 这种近黑噪点饱和度也是 1.0,被当成品牌色 |

正确做法：`text` 取与底色反差最大的一端;`line` 先求底色众数,再取离它最远的一端;`accent` 用**彩度**(`max(c) - min(c)`)而不是 HSV 饱和度 —— 近黑噪点彩度只有 20,真实品牌色能到 130 以上。

这类 bug 的危险在于**不报错、静默产出错值**。静态检查全过,只有把渲染结果和原始截图并排看才能发现。所以：

> 改动采样或配色推导逻辑后,必须用**明、暗两套**素材各跑一遍回归,不能只验一侧。

## 改 wireframe_kit / mobile_kit：注意 `T` 的引用语义

两个构件库共享 `wireframe_kit.T` 这一份 token 字典,而 `mobile_kit` 是用 `from wireframe_kit import T` 拿到它的。

因此 `use_profile()` 里**只能原地更新,不能重新绑定**：

```python
T.clear(); T.update(FALLBACK)   # ✅ 持有旧引用的模块也能看到新值
T = dict(FALLBACK)              # ❌ 只换了本模块的名字,mobile_kit 仍指向旧字典
```

写成后者时,整套配色会静默失效并退回浅色兜底值 —— 渲染出来是「纯黑底 + 深色文字」,查 SVG 才看得到 `fill` 是浅色主题的值。同理,在自己的脚本里请 `import wireframe_kit as k` 后用 `k.T[...]`,不要 `from wireframe_kit import T`。

## 加构件：产品构件与图纸构件不混用

- **产品构件**(`win` / `topbar` / `table` / `panel` …)按实测比例画真实界面,尺寸就是产品的尺寸。
- **图纸构件**(`emphasis_frame` / `anno` / `frame_tag` …)是标注语言,叠在产品之上。

想强调某个区域时只能加图纸构件,**绝不能放大产品控件的比例** —— 比例一改就画出了真实产品里不存在的界面,线框图随之失去参考价值。

另外画板坐标**不要用负值**,`emphasis_area` 的标签向左引出时容易溢出到负坐标。

## 提交前跑一遍

```bash
python3 scripts/check_demo.py --html <你的 demo>.html
python3 scripts/check_profile_drift.py --profile <档案目录> --target <demo>.html
python3 scripts/screenshot.py --html <demo>.html --out /tmp/s.png   # 渲染核对
python3 scripts/whiteboard_publish.py --svg <线框图>.svg --check     # 不联网,任何环境可跑
```

前两个是静态检查,便宜但只能兜住一部分。**渲染核对不是形式主义** —— 实测中它拦下过图标全部消失、条形图不可见、整套配色静默退回错误主题这三类静态检查完全查不出的问题。

playwright 装不上时,请在说明里如实写「静态检查已过,未做渲染核对」,不要当作验证过了。
