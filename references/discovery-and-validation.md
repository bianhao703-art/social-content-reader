# 搜索选型与验证记录

搜索检查日期：2026-10-12；发布包整理日期：2026-10-13。此文件记录当时发现的事实，之后需核验版本变化。

## 已查看的一手来源

- https://github.com/Panniantong/Agent-Reach ：接入路由、体检与多平台上游工具。实际检查 `agent_reach/skill/SKILL.md` 与 `pyproject.toml`；当时 skill 有小红书与B站详细路由，但没有独立公众号、抖音条目，不能仅凭旧 README/分支文档说覆盖所有需求。描述还会强制接管所有网络搜索，原样安装范围过大。
- https://github.com/Jiaranbb/content-reader ：五个 skill，覆盖小红书、Twitter/X、YouTube、B站；README 中未包括公众号和抖音。其许可为 CC BY-NC 4.0。本 skill 未复制它的代码或指令。
- https://github.com/yhslgg-arch/url-reader ：支持公众号、抖音页面描述等；原 skill 写死作者的 macOS 保存目录，依赖 Firecrawl/Jina/Playwright，并把视频描述当主要提取对象，不能满足统一视频内容读取。未复制代码。
- https://github.com/EdisonChenAI/agent-reach ：独立 skill 分支含公众号、抖音，但引用未安装工具与旧 B站路径，未选择原样安装。
- https://github.com/yzfly/douyin-mcp-server ：区分无需 API 的信息解析与需要外部 API 的语音文案提取。未注册服务器、未配置密钥、未上传媒体。

结论：存在可复用的单平台工具与跨平台路由，但未发现可原样安装且无需补齐就覆盖本次需求的方案。因此独立创建统一读取流程，优先使用已有工具，保留适用范围。

## 验证边界

运行时依赖用 `scripts/reader.py doctor` 查询。结构校验检查 skill 格式；离线行为验证可以通过 `python -m unittest discover -s tests -v` 复现，不需要平台账号或真实网页。

仅取得公开 HTML 不证明图片、视频、评论或分页已读。不得将本地样例称为四个平台真实链接全部实测。

### 创建时验收

- skill-creator `quick_validate.py`：通过；未保留 scaffold 占位内容。
- 本地功能检查共13项通过：四平台分享路由、精确域名识别、访问参数脱敏、公众号正文与作者、未读取图片标记、验证页拦截、视频元数据范围、公开JSON-LD正文、VTT/SRT/B站JSON字幕、JSON/Markdown保存、gzip解码、HTTP拒绝状态。
- 创建环境为 Windows / Python 3.13.3；HTML、路由与字幕脚本使用可移植Python代码。没有把维护者本机依赖或路径写成所有用户的配置。
- 真实网络样例：example.com 与 Python.org 成功响应并取得页面元数据，没有被当成文章正文。
- 真实B站样例 `https://www.bilibili.com/video/BV1GJ411x7h7`：浏览器读取到视频标题、UP主“索尼音乐中国”与可见页面信息；尚未提取字幕/媒体正文。直接HTTP读取一次未得正文，后续诊断出现412，已经停止对此目标的自动请求。
- 公众号、抖音、小红书真实目标链接、图片 OCR、视频完整转写和用户登录态均未验收。不能称这些平台已全部贯通。

### 后续真实工作流验证（2026-10-12）

- 用户指定B站创作者公开空间，通过授权浏览器核对账号、合集和公开作者说明。
- 5条搬运视频沿作者说明中的原版链接，使用浏览器公开字幕能力读取完整YouTube英文字幕。分开保留搬运者、原作者及自动字幕状态，不声称Python脚本直接读取了B站全文。
- 3条原创视频只读取作者发布说明；另用Steam公开页面核对发售日期。未把“发售”写成“盈利”。
- 按用户要求完成本地知识库的来源摘要、综合分析、索引与链接检查。发布仓库不包含用户知识库、私人目录或完整平台原文。
- 这些实测仅证明相应公开内容在当次环境可读，未证明公众号、抖音、小红书或视频号均已完成完整流程。
