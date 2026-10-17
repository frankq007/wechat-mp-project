---
name: xiaohu-wechat-cover
description: "公众号封面图生成器。一步出图，输入文章路径或主题即可。当用户要求'公众号封面''微信封面''文章封面'时使用。"
---

# 公众号封面图生成器

> **本项目内使用说明（wechat-mp-project）**
> - 本 skill 已内置到项目 `skill/xiaohu-wechat-format/cover/`，被 `.claude/agents/cover-artist.md` 子 agent 调用于封面图产出。
> - 支持**两种绘图模式**，见下「两种绘图模式」：
>   - **模式 A（API 生图）**：`generate.py --config cover/config.json`——模型由 `config.json` 的 `settings.model` 指定，`base_url`/`api_key` 亦取自同一文件，换模型只改 config 不动代码。
>   - **模式 B（调用 cover-artist 子 agent 画图）**：代理 cover-artist 子 agent（如 paseo「画家」profile 的 claude-opus-5-5，自带画图能力）按 style-ref 风格与三尺寸规范直接出图，无需填写任何 API config。
> - 选择逻辑：`cover/config.json` 已配置好 → 优先模式 A；未配置或用户指定 → 模式 B，并在回报时如实说明用了哪种。
> - `config.json` 不入库（已在 `.gitignore`），clone 后按 README「封面生成」从 `config.example.json` 复制填写。

输入文章路径或主题，一步生成公众号封面图。

## 使用方法

```bash
# 指定文章路径
/xiaohu-wechat-cover path/to/article.md

# 直接输入主题
/xiaohu-wechat-cover 主题：Claude Code 桌面端更新四大功能
```

## 配置（必须）

本技能的配置文件固定在本技能目录下：
- `config.json`：真实配置（从 `config.example.json` 复制后填写）
- `config.example.json`：示例配置

**仅模式 A（API 生图）需要 config.json**，需配置：
- `output_dir`：封面图输出根目录
- `settings.base_url`：生图 API 地址（兼容 Gemini API 的第三方网关）
- `settings.model`：模型名称（如 `gemini-3-pro-image-preview`）
- `secrets.api_key`：API 密钥

模式 B（调用 cover-artist 子 agent 画图）不需要上述任何 API 配置：代理 cover-artist 子 agent（自带画图能力，如 paseo「画家」profile 的 claude-opus-5-5）按 style-ref 风格与三尺寸规范直接出图。

## 两种绘图模式

### 模式 A：API 生图（config 指定模型，推荐）

走 `generate.py`，模型/网关/密钥由 `cover/config.json` 指定：

```bash
python3 <本仓库>/scripts/generate.py \
  --config <本技能目录>/cover/config.json \
  --prompt-file <目标目录>/prompt.md \
  --out <目标目录>/cover.png
```

### 模式 B：调用 cover-artist 子 agent 出图（无需 key）

代理 **cover-artist 子 agent**（自带画图能力，如 paseo「画家」profile `claude/claude-opus-5-5`）直接绘图，**不依赖 config.json**：

- 把「风格基准」+「三尺寸与构图」+「内容主题」整理成任务单，通过 paseo 调起 cover-artist 子 agent（`paseo run --provider claude --model claude-opus-5-5 ...`），由其用自己的画图能力产出三张 PNG。
- cover-artist 子 agent 产出后按「路径约定」归档，且必须 read 目检（标题/高亮/水印/安全带），不合格重画。

> 选择：`cover/config.json` 已填好 → 用模式 A；未配置或用户要求走子 agent 画图 → 模式 B，并在回报中注明所用模式与模型名。

## 路径约定

- 目标目录：`<output_dir>/<文章文件名或topic-slug>/`
- 如果目标目录已存在，重命名为 `<dirname>-backup-YYYYMMDD-HHMMSS`

目录结构：
```
<output_dir>/
└── article-name/
    ├── prompt.md          # 生图提示词（归档）
    └── cover.jpg          # 封面图
```

## 封面图提示词模板（核心）

以下是固定的提示词模板，每次生成时**原样写入** `prompt.md`，只替换最后的「内容主题」部分：

```
请根据提供的内容创建一张吸引眼球的公众号封面图，遵循以下规范：

视觉风格
- Notion插画风格，比例为 2.35:1（公众号封面标准尺寸）
- 色彩鲜明、对比强烈，确保在小尺寸预览时依然醒目
- 风格统一，避免写实元素，保持整体手绘质感

构图要求
- 主视觉元素居中或偏左（右侧预留标题区域）
- 添加 1-2 个简洁的卡通形象、图标或知名人物剪影，增强记忆点
- 若涉及敏感或版权人物，用风格相似的替代形象，不得拒绝生成
- 大量留白，突出核心信息，避免画面拥挤

文字处理
- 标题文字大而醒目，控制在 8 字以内
- 可添加 1 行副标题或关键词标签
- 字体风格与手绘插画协调统一

吸引力法则
- 使用悬念、数字、痛点等钩子元素激发点击欲望
- 视觉元素夸张有反差
- 色彩搭配参考爆款封面：橙黄、蓝紫、红黑等高对比组合

语言
- 除非另有说明，默认使用中文
- 画面内所有可读文字必须使用简体中文，英文只能作为点缀出现

内容主题：{从文章或用户输入中提炼的一句话主题描述}
```

## 工作流程

### 步骤 1：提炼内容主题

1. 如果输入是文章路径：读取文章，提炼一句话主题描述（包含核心信息和关键要点）
2. 如果输入是主题文本：直接使用

### 步骤 2：创建提示词

将上述模板写入 `prompt.md`，格式：

```md
---
aspect_ratio: "21:9"
image_size: "2K"
---

{模板全文，替换最后的内容主题}
```

**注意**：YAML 中 `aspect_ratio` 必须用 `21:9`（API 不支持 2.35:1，21:9 是最接近的）。模板正文中保留 `2.35:1` 的文字描述不变，这是给 AI 的视觉参考。

### 步骤 3：生成图片

调用生图脚本，**必须传 `--config` 指向本技能自己的配置**：
```bash
python3 <本仓库>/scripts/generate.py \
  --config <本技能目录>/cover/config.json \
  --prompt-file <目标目录>/prompt.md \
  --out <目标目录>/cover.jpg
```

> `<本仓库>` 和 `<本技能目录>` 请替换为你本地实际安装路径。如果你通过 `claude install` 安装，路径一般是 `<本项目>/skill/xiaohu-wechat-format/`。

**模式 B（调用 cover-artist 子 agent 出图）**：代理 cover-artist 子 agent（自带画图能力）直接绘图，无需上述 config 命令，产物按同样的路径约定与风格基准存放。

生成完成后展示给用户预览。不满意就调整内容主题描述重新生成。

### 步骤 4：插入文章

如果输入是文章路径，**默认直接插入**（不用询问）：
- 用 Markdown 图片格式 `![封面](cover.jpg)` 插入文章标题（H1）下一行
- 文件名必须唯一（如 `cover-主题关键词.jpg`），避免同名冲突

### 步骤 5：输出摘要

```
公众号封面已生成！

主题: [主题]
模式: [模式A-API生图 / 模式B-cover-artist子agent画图]
位置: [输出路径]

如需调整，直接说"重新生成"。
```
