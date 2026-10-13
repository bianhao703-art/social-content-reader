# Social Content Reader · 多平台内容读取

**把公众号、抖音、B站、小红书等分享链接和本地内容，整理成带出处、阅读范围与时间戳的资料。**

维护者：[bianhao703-art](https://github.com/bianhao703-art)。这是自己的 Codex / Agent Skill，包含读取流程与 Python 提取脚本。视频、图片和动态页面依赖使用环境提供的浏览器、视觉或转写能力；不是每条链接都能自动贯通。

## 功能介绍

| 功能 | 可以做什么 | 执行方式 |
|---|---|---|
| 分享链接识别 | 从分享文字中识别公众号、抖音、B站、小红书、视频号、YouTube等链接 | 内置 `route`；不把识别短链当成已解析短链 |
| 公开文章提取 | 提取标题、作者、日期、正文，以及未读取的图片地址 | 内置 `read`，支持公众号正文、HTML文章与公开文章结构化数据 |
| 动态页面读取 | 读取实际可见笔记和页面，区分正文、评论与推荐内容 | 由 Agent 调用环境中的授权浏览器或已配置读取工具 |
| 字幕整理 | 解析 VTT、SRT、B站字幕 JSON，保留起止时间 | 内置 `subtitles`；获取平台字幕需要可用工具 |
| 视频与图片理解 | 有字幕优先读字幕；没有字幕时按条件转写；图片文字逐张读取 | 依赖可用视觉/OCR/ASR能力，脚本本身不含OCR或语音模型 |
| 创作者研究 | 区分原创、搬运、评论，提炼真实读过的观点和案例 | Agent工作流，不按标题编写作者观点 |
| 知识库收录 | 生成来源摘要、主题分析和有用概念，更新现有索引与日志 | 用户要求保存后执行，遵循目标知识库规则 |
| 证据输出 | 保存JSON与Markdown、来源、读取时间、状态和遗漏 | `--out-dir` 每次建立独立结果目录 |
| 环境检查 | 检查Python依赖和已有媒体工具 | 内置 `doctor`，不会自动安装或登录 |

## 各平台读取方式

| 平台 | 可处理输入 | 主要限制 |
|---|---|---|
| 微信公众号 | 公开文章链接、保存的HTML、复制文字、截图 | 图片、嵌入视频与分页需另读；限制页不算正文 |
| 抖音 | 分享链接、可见页面、字幕或用户提供的视频 | 分享说明不是口播全文；转写取决于工具与媒体可得性 |
| B站 | 视频/空间链接、平台字幕、搬运原版、字幕文件 | 分P与字幕覆盖范围需核对；访问拒绝后停止自动重试 |
| 小红书 | 笔记分享、已授权浏览器可见内容、图片或本地文件 | 登录态及访问参数可能影响可读性；图片和评论分开读 |
| 微信视频号 | 公开可见页面、用户提供的视频、截图或字幕 | 没有通用公开正文接口保证 |
| 微信聊天/朋友圈 | 用户主动提供的文字、导出文件或截图 | 不自动读取本机微信数据库或完整账号历史 |
| YouTube / 其他公开网站 | 平台字幕、公开文章、可见页面或本地文件 | 依赖实际可用工具，逐条标注阅读范围 |

详细路线见 [平台读取分支](references/platforms.md)。

## 安装为自己的 Skill

仓库根目录就是 skill。将整个仓库放在 Codex 的 `skills/social-content-reader` 目录下；以下命令不会覆盖已存在的同名目录。

Windows PowerShell：

```powershell
$skillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
git clone https://github.com/bianhao703-art/social-content-reader.git (Join-Path $skillRoot 'social-content-reader')
```

macOS / Linux：

```bash
git clone https://github.com/bianhao703-art/social-content-reader.git "${CODEX_HOME:-$HOME/.codex}/skills/social-content-reader"
```

私有仓库需要先完成 GitHub 的正常认证。如果已经安装同名skill，请先保留自己的修改，不直接覆盖。安装后在 Codex 新会话中使用；其他兼容 Agent 采用其自己的技能安装目录。

Python脚本建议 Python 3.10+。文章提取需要 `beautifulsoup4`；路由与本地字幕解析只使用标准库：

```powershell
python -m pip install -r requirements.txt
python -X utf8 scripts/reader.py doctor
```

依赖检查通过不表示平台已登录或每个链接都可读。`yt_dlp`、FFmpeg、ASR、平台MCP都是可选能力，不在基础安装中强制安装。

## 在 Codex 中怎么用

```text
使用 $social-content-reader 读取这个公众号链接，提炼观点，说明图片和视频是否读取。

使用 $social-content-reader 读取这条B站视频，优先取得字幕，按时间戳整理要点。

使用 $social-content-reader 比较这三篇小红书笔记，区分作者正文与评论。

使用 $social-content-reader 研究这个UP的独立游戏开发与商业化内容，
保存到我指定的知识库，区分原作者、搬运者和未读条目。

使用 $social-content-reader 整理我提供的微信聊天截图，提取待办和决定。
```

没有提供可用正文时，Skill 会明确记录未取得部分，不补写虚构内容。

## 命令行示例

以下网址与文件路径是示例，请替换为自己的输入。在仓库根目录运行：

```powershell
python -X utf8 scripts/reader.py route --text '分享文字 https://b23.tv/example'
python -X utf8 scripts/reader.py read --url 'https://example.com/article' --out-dir './outputs'
python -X utf8 scripts/reader.py read --file './article.html' --source-url 'https://example.com/article' --out-dir './outputs'
python -X utf8 scripts/reader.py subtitles --file './captions.vtt' --source-url 'https://example.com/video' --out-dir './outputs'
```

返回的阅读状态包括：`body_extracted`（提取到正文，仍需核对完整性）、`metadata_only`（仅元数据）、`transcript_extracted`（取得本地字幕）、`needs_browser`（需要浏览器）、`access_blocked`（访问受限）。完整状态与字段见 [示例输出](examples/evidence.json)。

## 已验证的范围

- 可复现的离线测试：分享路由与域名边界、访问参数脱敏、文章提取、验证页识别、字幕解析、HTTP拒绝处理及证据保存。运行 `python -m unittest discover -s tests -v`。
- 2026-10-12 的实际B站创作者研究：通过浏览器读取公开作者说明，沿搬运出处完整阅读5条原作者YouTube英文字幕，另核对Steam发售页面，并完成本地知识库入库。属于Agent工作流实测，不代表Python脚本直接取得了B站视频全文。
- 公众号、抖音、小红书真实链接的完整流程，图片OCR及无字幕视频ASR：尚未完成全面验收。详见 [验证记录](references/discovery-and-validation.md)。

## 访问、隐私与内容归属

登录、验证码、HTTP 401/403/412/429和浏览器安全阻止需要停止自动重试，不换代理或客户端绕过。Skill不导出浏览器Cookie、不索要聊天里的密码、不扫描微信数据库；输出URL会隐藏常见访问凭据，但不能代替对正文中个人信息的检查。

云端转写会上传媒体，只有在说明服务与费用并取得授权后使用。知识库写入需要用户提出保存要求。Skill不用于发帖、评论、私信或后台账号全量采集。

本项目代码与指令由维护者组织维护；未复制检索中第三方项目的代码或指令。参考链接及平台原内容仍归相应权利人，不能用本项目的许可或可见性推导对其全文转载的授权。

## 项目结构

```text
social-content-reader/
├── SKILL.md                     Agent入口与读取流程
├── agents/openai.yaml           Codex界面元数据
├── scripts/reader.py            路由、HTML和字幕提取器
├── references/                  平台分支、创作者研究和验证记录
├── examples/evidence.json       虚构示例输出
├── tests/test_reader.py          离线行为验证
└── requirements.txt             基础HTML依赖
```

当前版本：1.0.0。发布包整理日期：2026-10-13。
