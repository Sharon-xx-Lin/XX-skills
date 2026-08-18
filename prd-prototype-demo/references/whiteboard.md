# 协作白板：能力边界、安全 SVG 子集与实操

> **本文的「安全 SVG 子集」和「能力边界」两节对所有协作白板都适用** ——
> Figma / FigJam / Miro / tldraw 在阴影、字体、圆角量化上有类似限制，
> 守住这个子集能保证 SVG 导入任何白板都不错位。
>
> **「完整命令序列」一节是飞书画板专属**，需要飞书环境和字节内部的 `lark-cli`。
> 没有这套环境的话跳过即可：用 `whiteboard_publish.py --dry-run` 出本地预览图核对，
> 再把 SVG 或 PNG 分享 / 导入你团队用的白板。


## 目录

- [为什么用 SVG 路线](#为什么用-svg-路线)
- [能力边界（实测）](#能力边界实测)
- [画板安全 SVG 子集](#画板安全-svg-子集)
- [完整命令序列](#完整命令序列)
- [实测踩坑](#实测踩坑)
- [授权处理](#授权处理)
- [排版实操建议](#排版实操建议)

---

> 本文档是画板的**技术底座**说明。画什么、怎么排布见 SKILL.md 第 ④ 步
> 与 `references/frame-by-frame.md`。

## 为什么用 SVG 路线

画板支持三条输入通道，能力差别很大：

| 通道 | 适用 | 保真度 |
|---|---|---|
| Mermaid / PlantUML | 思维导图、时序图、类图 | 低。引擎自动排版，样式不可控 |
| DSL JSON | 架构图、泳道图、漏斗图 | 高，自带 flex/dagre 自动布局 |
| **SVG** | **任意自由设计，UI 原型** | **高，坐标完全可控** |

原型图要精确控制页面卡片的位置和内部布局，所以走 SVG。DSL 路线留给纯结构化图表——而且它的校验报错很误导（用了不支持的类型时报的是"缺字段"而不是"类型不存在"），调试成本更高。

转换后得到的是**可编辑的画板原生节点**，不是一张图片。团队能在画板里继续拖拽、批注、讨论——这是画板相对"生成 PNG 贴文档"的核心优势。

---

## 能力边界（实测）

### 支持

- 任意 hex 填充/边框/文字色，**线性渐变**（`fill_gradient`，stops 保留）
- 富文本 run 级样式：bold / italic / underline / 删除线 / 字号 / 颜色 / 背景色 / 超链接 / 有序无序列表 / 缩进 / 引用
- 形状：`rect` `ellipse` `cylinder` `diamond` `triangle` `trapezoid` `frame`(容器)
- 连线：4 种线型（直线/圆角折线/曲线/直角折线）× 5 种箭头 × 实线虚线点线，支持 label 和 waypoints
- 内置图标库 144 个（`whiteboard-cli --icons` 可列出），可指定颜色
- 本地图片上传（需上传到目标画板本身，见下）

### 不支持 —— 设计时必须绕开

| 限制 | 影响 | 应对 |
|---|---|---|
| **无阴影** | `shadow`/`boxShadow` 静默丢弃 | 层次靠 1px 边框 + 浅底色表达 |
| **字体锁死 Noto Sans SC** | 无 `font_family` 字段 | 接受，不要试图还原品牌字体 |
| **圆角量化丢失** | `rx=0` 和 `rx=24` 都变成 `round_rect` | **不要用圆角承载语义** |
| **边框宽度只有 4 档** | 1→extra_narrow, 2→narrow, 4→medium, ≥8→bold | 1px 发丝线和 2px 描边会被归并 |
| 无径向渐变 / filter / pattern / clipPath / mask | 会导致渲染异常 | 全部禁用 |
| 无交互态 | 静态图，无 hover/跳转 | 交互由 HTML demo 承载 |

**圆角这条最容易踩。** 如果设计上靠"胶囊 vs 直角"区分两类状态标签，转换后两者变成一样的圆角，信息就丢了。要用颜色或文案区分。

### 规模

官方未公开节点上限。实测 300 节点 DSL → 601 openapi 节点转换正常；本次原型图 142 节点写入无问题。接口频率限制 50 次/秒。建议单批控制在 500~600 节点以内，超了分批写。

SVG 中不可识别的元素会**降级为内嵌图片**（能显示但不可编辑），所以复杂度是软限制而非硬失败——但降级意味着失去可编辑性，应当避免。

---

## 画板安全 SVG 子集

### 禁用清单

```
filter, feGaussianBlur, feDropShadow   —— 阴影/模糊，静默丢弃
radialGradient                         —— 只支持线性渐变
clipPath, mask                         —— 不支持
pattern                                —— 不支持图案填充
foreignObject                          —— 无法解析
<image>                                —— SVG 内嵌图片会失败
```

### 必须遵守

- **文字用 `<text>` 元素**，不能用 `foreignObject` 包 HTML
- **不依赖圆角和阴影传递信息**
- **配色全部取自 UI 档案 tokens** —— 画板图和 HTML demo 同源，团队看到的才是一致的东西
- 显式写 `width`/`height`/`viewBox`，避免尺寸推断歧义
- 箭头用 `<path>` 手画（起止点明确），转换器能识别成 connector 并保留 label

### 图片节点

SVG 内不能嵌图片。需要真实图片时，先上传到目标画板再用 DSL image 节点引用：

```bash
lark-cli docs +media-upload --file ./photo.jpg \
  --parent-type whiteboard --parent-node <whiteboard_token>
# → 得到 file_token，在 DSL 里用 {"type":"image","image":{"src":"<token>"}}
```

必须 `--parent-type whiteboard` 且指向**目标画板本身**。用 `docx_image` 域或 Drive token 会让画板 API 报 500（错误码 2891001）或图片消失；跨画板 token 也不可用。

---

## 完整命令序列

推荐直接用 `scripts/whiteboard_publish.py`，它已封装全流程并做了错误处理。下面是底层命令，供排查问题时参考。

```bash
# 1. 几何校验：文字溢出 / 节点重叠。errors 必须为 0
npx --yes @larksuite/whiteboard-cli@latest -i flow.svg --check

# 2. 本地预览（先看效果，比上传后再改便宜）
npx --yes @larksuite/whiteboard-cli@latest -i flow.svg -o flow.png -s 1

# 3. 转画板节点
npx --yes @larksuite/whiteboard-cli@latest -i flow.svg -t openapi -o flow.openapi.json

# 4. 创建含画板块的文档（标题必须写在 XML 里）
printf '%s' '<title>需求名 · 原型图</title><whiteboard type="blank"></whiteboard>' \
  | lark-cli docs +create --api-version v2 --content - --doc-format xml --as user
# → 从 data.document.new_blocks[] 里 block_type=="whiteboard" 那条取 block_token

# 5. 写入节点（--source 要完整输出对象，不是裸数组）
lark-cli whiteboard +update --whiteboard-token <token> \
  --input_format raw --source @flow.openapi.json --as user \
  --idempotent-token <≥10字符纯字母数字>

# 6. 回读服务端渲染图核对
lark-cli whiteboard +query --whiteboard-token <token> \
  --output_as image --output ./out --as user
```

`<whiteboard>` 块的 `type` 支持 `blank` / `mermaid` / `plantuml` / `svg`。建议用 `blank` 再写入，链路更可控。

### 增量编辑

画板**没有单节点 patch/delete 接口**。改一个框的文字实际是：`+query --output_as raw` 拿全量节点 JSON → 改 → `+update --overwrite` 全量重写。

不带 `--overwrite` 是**追加**，新内容会和已有内容坐标重叠。重新生成时记得加。

---

## 实测踩坑

1. **`--source` 要完整输出对象。** 转换器输出是 `{"nodes": [...]}`，直接喂裸数组会报 `cannot unmarshal array into Go value of type whiteboard.WbCliOutput`。
2. **文档标题必须写在 XML 的 `<title>` 里。** `--title` 参数不生效，会得到"未命名文档"并伴随 `missing_document_title` 警告。
3. **`--content @/abs/path` 被拒绝。** lark-cli 只接受当前目录下的相对路径，绝对路径报 `invalid file path`。用 stdin（`printf ... | lark-cli ... --content -`）绕过。
4. **`docs +create` 必须带 `--content`**，无法创建纯空文档。
5. **`--whiteboard-token` 不是 `--whiteboard`。** 参数名写错时 CLI 会给出 suggestion，留意读。
6. **`--idempotent-token` 需 ≥10 字符**，且建议只用字母数字（带连字符可能被拒）。
7. **connector 必须放顶层 `nodes`**，不能放进 `frame.children`（DSL 路线）。
8. **无填充无边框的 frame 会被优化掉**，外部 connector 引用它会失效（DSL 路线）。

---

## 授权处理

写画板需要 user 身份（bot 在用户云空间没有落点，`docs +create` 会直接被拒，错误码 3380004）。

**采用"先探测再引导"，不要一上来就拦人要授权。** 平台侧通常已配置凭证，探测一下就能过；把授权做成阻塞式的第一步，老手每次都被拦一道，体验很差。

```bash
# 探测
lark-cli doctor          # 看 user_identity 是 pass 还是 warn

# 静默尝试（平台已有凭证时会直接返回 authorization_complete）
lark-cli auth login --domain docs,drive --no-wait --json

# 确实需要用户扫码时，返回里会带 verification_url / user_code，
# 原样展示给用户并停下等待，不要替用户点确认
```

需要的 scope：`board:whiteboard:node:create`、`docx:document:create`、`drive:file:upload`。

授权失败时**要优雅降级**：把 SVG 和本地预览 PNG 留在本地，告诉用户产物在哪、授权后可以重跑，不要让前面的工作白费。

---

## 排版实操建议（逐帧线框图）

- **画布留白**：内容不贴边，四周留 80px 以上
- **`<text>` 不会自动换行**：长文案自己拆多行，或加宽容器。`--check` 报 text-overflow 必须修
- **文本宽度估算**：中文按 1em、ASCII 按 0.58em（`wireframe_kit.tw()` 已实现）。
  用 `len() * size` 会严重高估，导致容器画太宽或标签溢出
- **帧间距**：横向 150~200px（留给连线和标签），纵向 200px 以上（留给帧下方批注）
- **批注放帧下方横向铺开**，不要放右侧 —— 放右侧会把帧挤窄，破坏真实比例
- **强调框会外扩 8px**，排布时预留，否则会压住相邻帧或批注
- **node-overlap 警告**：卡片内嵌图标属于预期嵌套，可忽略；`text-overflow` 必须修
- **节点规模**：高保真每帧 100~200 节点。超过 ~600 分批写入，每批带 x/y 偏移；
  不带 `--overwrite` 是追加，会坐标重叠
