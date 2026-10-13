# 平台读取分支

只读取当前需要的平台。本文件列的是路径与验收条件，实时成功率由目标链接决定。

| 平台 | 先读什么 | 动态/视频处理 | 验收重点 |
|---|---|---|---|
| 公众号 `mp.weixin.qq.com` | `#js_content` 正文，`#activity-name` 标题，`#js_name` 账号 | 浏览器中的可见文章；用户提供保存网页/复制文字/截图 | 正文首尾、图片里的字、嵌入视频是否真的读取；搜索摘要只能当线索 |
| 抖音 `douyin.com` / `v.douyin.com` | 分享说明、标题、作者及可见页面 | 实际可用字幕或本地媒体转写；若已有 douyin MCP，可先查公开 schema 再执行只读解析 | 下载链接/视频信息不是口播稿；不要声称无需登录且永远成功 |
| B站 `bilibili.com` / `b23.tv` | 视频页元数据与分P信息 | 已配置的 `bili`/浏览器字幕优先；公开 `yt_dlp` 字幕为可选，遭访问拒绝即停止 | 字幕是否覆盖目标分P、语言、时长；没有字幕不算完整视频已读 |
| 小红书 `xiaohongshu.com` / `xhslink.com` / `xiaohongshu.cn` | 可见笔记正文、作者、图片、视频与标签 | 用户已控制的浏览器可见页面；已配置小红书 MCP 仅调用读取工具 | 保留完整输入访问参数直到本次读取结束，交付隐藏 `xsec_token`；图片与评论另读 |
| 微信视频号 `channels.weixin.qq.com` / `weixin.qq.com` | 公开可见页面或用户提供的素材 | 本地视频/截图/字幕；登录仅由用户手动完成 | 不能把公众号流程当成视频号通用接口 |
| 微信聊天/朋友圈 | 用户提供的文字、导出文件、截图 | 逐条读取并按用户要求总结；敏感个人信息只保留必要部分 | 无导出/可见页面就报告未取得，不访问聊天数据库 |
| YouTube `youtube.com` / `youtu.be` | 标题、原作者、来源日期 | 平台可用字幕或授权浏览器的公开转写文稿；如提供 `exportYouTubeTranscript` 能力，按工具文档使用 | 自动字幕不等于人工校对；时间戳属于该原版，不能直接套到搬运版 |
| 其他公开平台 | 用户链接中的目标正文/公开结构化内容 | 当前可用浏览器或已有专门读取工具 | 区分正文、页面导航和评论；禁止默默替换成同名文章 |

## 字幕提取示例

下面只适用于没有出现明确访问拒绝的公开视频。先检查 `python -m yt_dlp --version` 与帮助。指定单条目标，不自动展开整个账号或合集。

```powershell
python -m yt_dlp --skip-download --no-playlist --write-subs --write-auto-subs --sub-langs "zh.*,en.*" --sub-format vtt -o "<temp-dir>/%(id)s.%(ext)s" "URL"
python -X utf8 "<skill-dir>/scripts/reader.py" subtitles --file "下载的字幕.vtt" --source-url "URL" --out-dir "目标目录"
```

不添加 `--cookies-from-browser`、代理、随机 User-Agent 重试等参数来应对拒绝。普通缺字幕时可以处理用户提供的媒体。

## 可选现成工具

实际存在才调用；通过可用工具元数据、`--help` 或 MCP schema 验证命令，禁止假设安装成功。

- Agent Reach 是接入路由/体检层，具体读取依赖上游工具；新版能力清单可能变化。
- douyin-mcp-server 的视频解析与音频转写是不同能力。其当前说明中提取文案需外部 API；取得下载地址不代表转写完成。
- 小红书 MCP 可能同时含发布/评论功能，本 skill 只用读取部分。
- 不把私密链接发送到 Jina/Firecrawl 等第三方。公开链接使用第三方读取服务前先核实工具可用，明确访问拒绝时停止。
