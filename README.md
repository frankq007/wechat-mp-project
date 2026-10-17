# 微信公众平台发布 Agent 项目

一个面向**程序员**的微信公众号内容运营项目，由 Claude agent 维护：用现成 skill 排版发布文章（图文 + 图片消息两种），并把微信草稿箱 / 已发布文章与本地 SQLite 双向同步。

## 公众号定位

- **受众**：程序员。
- **四大内容支柱**：
  1. Agent 编程（Claude / AI 编程 / 自主 Agent）
  2. 鸿蒙开发（HarmonyOS / OpenHarmony）
  3. 开源工具介绍与实测
  4. 业界最新动态
- **作者署名**：小河（已在 `xiaohu-wechat-format/config.json` 配置）。

## 目录结构

```
wechat-mp-project/
├── README.md
├── .claude/agents/
│   ├── content-manager.md   # 内容创作/排版/发布编排（写）
│   ├── data-sync.md         # 草稿箱/已发布 ↔ 本地 DB 同步（管）
│   └── cover-artist.md      # 封面图生成（图）
├── sync/                    # 轻量同步层（纯 stdlib Python）
│   ├── db.py                # SQLite 建表 + CRUD
│   ├── api.py               # 微信 API（取 token/拉草稿/拉已发布）
│   ├── meta.py              # 扫描 articles/*.md 提取元数据
│   ├── sync.py              # 同步引擎 + 差异/漂移报告
│   └── cli.py               # wechat-mp-sync 子命令 CLI
├── scripts/newspic.py       # 参数化图片消息发布（复用 config 凭据）
├── articles/                # md 源稿（正文真源）
├── images/                  # 封面/style 参照图
├── skill/
│   └── xiaohu-wechat-format/ # 排版发布 + 封面生图 skill（已内置）
└── data/wechat_mp.db        # SQLite 库（首次运行生成）
```

## 存储边界（重要）

- **正文**存 md 文件（`articles/`），是唯一真源。
- **SQLite** 只存文章元数据 + 微信侧镜像 + 映射，**不存正文**。

## 前置配置

**clone 后首次初始化（三件事）：**

```bash
# 1. 排版/发布 skill 的 config（含主题/作者/图片搜索路径）
cp skill/xiaohu-wechat-format/config.example.json \
   skill/xiaohu-wechat-format/config.json

# 2. 封面生图 skill 的 config（模型/网关/密钥都在这里，见下方「封面生成」）
cp skill/xiaohu-wechat-format/cover/config.example.json \
   skill/xiaohu-wechat-format/cover/config.json

# 3. 微信凭据走环境变量（不落明文）
export WECHAT_APP_ID="wx..."
export WECHAT_APP_SECRET="..."   # 32 位
```

config.json 均已在 `.gitignore` 中（不入库），clone 后需自行从 example 复制填写。

**排版发布 skill**：`skill/xiaohu-wechat-format/`（原外部 `/mnt/d/code/wx/xiaohu-wechat-format` 已废弃），脚本经项目内相对路径调用。`config.json` 已配：`wechat.author = 小河`、`settings.default_theme = claude-scroll`；凭据字段写占位 `$WECHAT_APP_ID` / `$WECHAT_APP_SECRET`，由 `publish.py` / `sync/api.py` / `newspic.py` 统一解析（**环境变量优先**，其次展开 `$VAR`）。

**IP 白名单**：公众号后台需把当前出口 IP 加入白名单，否则 token 报 `40164`。

## 封面与插图（cover-artist 子 agent）

cover-artist 有三个职能：**封面图 / 文章插图 / 图片消息插图**。

- **封面图**：走项目内 xiaohu cover skill，支持两种模式：
  - **模式 A（API 生图）**：
    ```bash
    python3 skill/xiaohu-wechat-format/scripts/generate.py \
      --config skill/xiaohu-wechat-format/cover/config.json \
      --prompt-file <prompt.md> \
      --out <输出.png>
    ```
    模型由 `cover/config.json` 指定（`settings.base_url` / `settings.model` / `secrets.api_key`），换模型只改 config 不动代码。
  - **模式 B（自身模型绘图）**：无需 API 配置，cover-artist 用自己的模型能力直接绘制（PIL 脚本等），参考样板 `scripts/make_covers_hn.py`。
  三尺寸：master 1080×608（16:9）/ cover 900×383（21:9，2.35:1 首图重排）/ square 500×500（1:1）；文字与关键图形落在中央垂直 60% 安全带内；水印「公众号·小河」。
- **文章插图**：cover-artist 用自身模型绘制（如 PIL 数据图/示意图）→ `images/inline/<slug>-<n>.png`，md 用 `![[文件名.png]]` 引用。
- **图片消息插图**：cover-artist 用自身模型绘制海报感单张主图（900×500 等）→ `images/covers/<slug>-newspic.png`。
- `cover/config.json` 不入库；模式 A 未配置时 cover-artist 会用模式 B（自身模型绘图），或如实报告不可用，不降级。

## 发布流程（统一走 release.py，自动登记 DB）

```bash
# 图文消息（排版 → 上传封面/正文图 → 草稿箱 → 自动登记本地 DB）
python3 scripts/release.py news --input articles/xx.md --cover images/covers/xx.png

# 图片消息（本地图 → 永久素材 → newspic 草稿 → 自动登记）
python3 scripts/release.py newspic --image images/covers/xx.png --title "标题"

# 只想试跑 / 不写库
python3 scripts/release.py news --input x.md --cover c.png --dry-run
python3 scripts/release.py news --input x.md --cover c.png --no-register
```

`release.py` 是极薄封装：内部调现成 skill 的 `publish.py`（图文）或本项目 `scripts/newspic.py`（图片），成功后解析 `media_id` 并写入 SQLite + 建立 `article_sync` 映射。

- 均**只到草稿箱，不群发**，由人工在公众号后台择时发布。
- 也可直接调底层脚本（`skill/xiaohu-wechat-format/scripts/publish.py`、`scripts/newspic.py`），但那样不会自动登记 DB，需事后 `sync/cli.py pull` 补齐。

## 同步层 CLI 用法

```bash
# 建库建表
python3 sync/cli.py init

# 扫描本地 articles/*.md 写入元数据（跳过 _ 或 . 开头的文件）
python3 sync/cli.py index-articles
python3 sync/cli.py index-articles --dir /path/to/md   # 指定其他目录

# 拉微信草稿箱 + 已发布 → sqlite 镜像
python3 sync/cli.py pull --count 20

# 草稿 / 已发布 列表
python3 sync/cli.py draft ls
python3 sync/cli.py publish ls

# 差异 / 漂移核对
python3 sync/cli.py report

# 人工登记已发布（freepublish 未授权时的兜底）
python3 sync/cli.py mark-published --media-id XXX --title "标题" --type news

# 自由查询
python3 sync/cli.py db --sql "SELECT id,title,status FROM articles"
```

### ⚠ 已知平台限制：已发布列表拉不到

本公众号（个人订阅号）**未授权"发布能力"**，官方 `freepublish/batchget` 返回 `errcode 48001 api unauthorized`，因此**已发布文章无法自动拉取**。

- 草稿箱同步（`draft/batchget`）**完全正常**，实测可拉到全量草稿。
- 已发布文章需用 `mark-published` 人工登记，或后续升级公众号认证再启用自动拉取。
- `pull` 遇到 48001 会给出明确提示而不是报错退出。

## 子 Agent

| Agent | 职责 |
|---|---|
| `content-manager` | 选题/写作/排版/发布编排，含写作规则（搜索+传播优化） |
| `data-sync` | 草稿箱/已发布 ↔ 本地 DB 双向同步、查询、差异/漂移核对 |
| `cover-artist` | 封面（xiaohu cover skill 出图，模式 A：config API / 模式 B：自身模型）+ 文章插图 + 图片消息插图（插图用自身模型） |