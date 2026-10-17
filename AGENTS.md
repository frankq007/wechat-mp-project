# AGENTS.md — 微信公众号运营项目（小河）

> **任何 agent 进入本仓库，先读这份文件。** 三个子 agent 的完整定义在 `.claude/agents/`，本文件是总览与铁律。

## 项目是什么

一个由 agent 维护的**面向程序员**的微信公众号运营项目：用现成 skill 排版发布文章（**图文消息 + 图片消息**两种），并把微信草稿箱 / 已发布文章与本地 SQLite 同步。

**四大内容支柱**（一切选题的锚点）：
1. Agent 编程（Claude / AI 编程 / 自主 Agent）
2. 鸿蒙开发（HarmonyOS / OpenHarmony）
3. 开源工具介绍与实测
4. 业界最新动态

**作者署名**：小河　|　**默认排版主题**：`claude-scroll`（Claude 风格）

## 三个子 agent 与分工

| Agent | 定义文件 | 负责 | 绝不碰 |
|---|---|---|---|
| `content-manager` | `.claude/agents/content-manager.md` | 选题、写 md、配标题/摘要、编排发布 | 数据库、生图 |
| `cover-artist` | `.claude/agents/cover-artist.md` | 封面（xiaohu cover skill 出图）+ 文章插图 + 图片消息插图 | 写作、排版、发布、同步 |
| `data-sync` | `.claude/agents/data-sync.md` | 草稿箱/已发布 ↔ SQLite 同步、查询、差异核对 | 写作、排版、发布 |

协作链：**content-manager 写稿 → cover-artist 出封面 → release.py 发布并自动登记 → data-sync 核对**。

## 目录地图

```
wechat-mp-project/
├── AGENTS.md                  # ← 你在这里（入口总览）
├── README.md                  # 人类向说明：配置、用法、平台限制
├── .claude/
│   ├── agents/                # 三个子 agent 定义
│   └── settings.json          # 权限：deny 群发接口
├── articles/                  # md 源稿（正文唯一真源）；_template.md 是写作模板
├── images/
│   ├── style-ref.png          # 封面风格唯一真源（1080×608）
│   └── covers/                # cover-artist 产出 <slug>-{master,cover,square}.png
├── scripts/
│   ├── release.py             # 发布封装（图文/图片两条线，自动登记 DB）★首选入口
│   └── newspic.py             # 参数化图片消息（被 release.py 调用）
├── sync/                      # 同步层（纯 stdlib）：db/api/meta/sync/cli
└── data/wechat_mp.db          # SQLite：元数据 + 微信侧镜像（不存正文）
```

**排版发布 skill 已内置**：`skill/xiaohu-wechat-format/`（已从外部仓库迁入内置，外部副本废弃）。脚本经 `PROJECT/skill/...` 相对解析，排版/发布**必须复用它，不自研**。

## 铁律（所有 agent 必须遵守）

1. **正文只存 md**（`articles/`）。SQLite 只存元数据 + 微信侧镜像 + 映射，**绝不存正文**。
2. **只到草稿箱，绝不群发**。`.claude/settings.json` 已 deny `freepublish/submit` 与 `message/mass`；发布时间由人工在公众号后台决定。
3. **凭据只走环境变量** `WECHAT_APP_ID` / `WECHAT_APP_SECRET`。任何文件不落明文密钥（skill 的 `config.json` 里 `app_secret` 是占位 `$WECHAT_APP_SECRET`）。
4. **排版/发布复用现成 skill**，默认主题 `claude-scroll`、作者 `小河`。
5. **已发布文章拉不到**（个人订阅号未授权"发布能力"，`freepublish/batchget` 返回 48001）。需要已发布记录时用 `sync/cli.py mark-published` 人工登记；向用户汇报时**如实说明**，不得把官方返回当全量事实。
6. **报错不反复重试**。`40001/40125`=Secret 无效、`40164`=IP 不在白名单、`48001`=接口未授权——如实转告用户。
7. **微信响应不带 charset**，解析必须显式 `json.loads(r.content.decode("utf-8"))`，否则中文标题乱码（已踩过的坑）。
8. **发布后即提交**：凡是当天推过草稿箱的 md / 封面 / 脚本变更，当天 `git commit` 并 push 到 GitHub（`git@github.com:frankq007/wechat-mp-project.git`），保持远程与本地同步；凭据仍不得入库。
9. **正文不重复标题**：微信消息本身已展示标题，正文**不得再写 H1 大标题**（md 中不要 `# 标题`，frontmatter 的 `title` 就是微信标题）；正文以导语/开场直接开头，把首屏留给内容。

## 标准工作流

### 图文消息（主力）
```bash
# 1. content-manager：写稿（过写作规则检查项）→ articles/<slug>.md
# 2. cover-artist：出三尺寸封面 → images/covers/<slug>-{master,cover,square}.png
# 3. 发布 + 自动登记 DB
python3 scripts/release.py news --input articles/<slug>.md --cover images/covers/<slug>-cover.png
# 4. data-sync：核对
python3 sync/cli.py report
```

### 图片消息
```bash
python3 scripts/release.py newspic --image images/covers/<slug>-cover.png --title "标题"
```

### 数据同步
```bash
python3 sync/cli.py init            # 建库
python3 sync/cli.py index-articles  # 扫 md 元数据（跳过 _ 开头）
python3 sync/cli.py pull --count 20 # 拉草稿箱+已发布 → sqlite
python3 sync/cli.py draft ls        # 草稿列表
python3 sync/cli.py publish ls      # 已发布列表
python3 sync/cli.py report          # 差异/漂移核对
python3 sync/cli.py db --sql "..."  # 自由查询
```

## 写作规则速览（完整见 content-manager.md）

- **标题公式**：`[主关键词] + [具体动作/对象] + [结果或反差]`；中文 15~24 字；宁具体不文青。
- **搜索**：标题埋真实搜索词、主词靠前、名词全篇统一、开头自然用一次主词（禁堆砌）。
- **传播**：标题给明确收益/结果；程序员最吃"踩坑+解法 / 实测对比 / 上手即用"。
- **开头前两段**：3 秒说清"谁/讲什么/对我有什么用" + 给承诺 + 具体场景钩子；禁"随着科技发展…"式铺垫。

## 数据模型（三张表）

```
articles     本地稿元数据：title/summary/author/theme/tags/src_path(UNIQUE)/md_hash/status
sync_items   微信侧镜像：media_id(PK)/message_id/article_type(news|newspic)/wx_status/时间
article_sync 映射：article_id ↔ media_id + local_hash/remote_hash + sync_at
```

## 封面规范速览（完整见 cover-artist.md）

- 参照 `images/style-ref.png`：奶油底 + 顶部标题条（珊瑚红关键词）+ 中央机器人 + 四色环形流程框 + 底部标语 + 角落装饰（叠书/睡猫/云朵）+ 水印 `公众号·和弦代码`。
- **产出三尺寸**：`-master`(1080×608 文内头图)、`-cover`(900×383 微信首图 2.35:1 **重排非裁切**)、`-square`(500×500 分享卡)。
- 2.35:1 / 1:1 版本关键元素落在中央垂直 60% 安全带内。
