# Skills

我个人创建与维护的 skill 合集。每个 skill 是一个独立子目录,遵循渐进式披露(progressive disclosure)结构:一个 `SKILL.md` 描述能力与方法论,按需附带 `references/`、`scripts/`、`evals/` 等资源。

## 目录约定

```
.
├── README.md              # 本文件:仓库总览
├── LICENSE                # MIT
├── .gitignore
└── <skill-name>/          # 每个 skill 一个独立目录
    ├── SKILL.md           # skill 主体:frontmatter(触发描述) + 方法论正文
    ├── README.md          # 该 skill 的单独说明(可选)
    ├── references/        # 供模型按需读取的参考文档(可选)
    ├── scripts/           # 可执行脚本(可选)
    └── evals/             # 评估套件:测试用例 + 标准答案(开发/回归用,可选)
```

## Skill 列表

| Skill | 作用 | 状态 |
|---|---|---|
| [`doc-review`](doc-review/) | 轻量级文档审查:分层查文字质量与结构完整性,产出区分「硬错 / 主观建议」的审查报告,只审不改原稿。 | 可用 |
| [`prd-prototype-demo`](prd-prototype-demo/) | PRD + 产品截图 → 逐帧交互线框图与可交互 demo。先把设计语言像素采样成可复用档案,再据此出图,解决 AI 原型「配色每次重新发明、一眼就是 AI 做的」。 | 可用 |


## 什么是 skill

Skill 是一份让 AI agent 在特定场景下按既定方法论工作的说明包。核心是 `SKILL.md`:

- **frontmatter** —— `name` 与 `description`,决定 skill 在什么意图下被触发;
- **正文** —— 边界、流程、判断标准等方法论,告诉 agent「在找什么、怎么判、怎么输出」,而非硬编码规则。

## 使用方式

将某个 skill 目录接入支持 skill 的 agent 环境(如 Claude Code / Codex / Trae),agent 会依据 `SKILL.md` 的 `description` 在匹配到相应用户意图时自动加载并遵循其中的方法论。运行时通常只需 `SKILL.md`;`evals/` 仅用于迭代与回归测试。


## 注意

本仓库仅存放通用、可公开的 skill 定义与合成测试数据,**不提交任何真实业务文档、机密内容或个人敏感信息**。评估运行产物、打包文件等由 `.gitignore` 排除。
