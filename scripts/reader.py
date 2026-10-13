"""Public HTML reader, share URL router and timestamped subtitle normalizer."""
import argparse
import html
import importlib.util
import json
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime
from pathlib import Path
from uuid import uuid4

DOMAINS = {
    'wechat-article': ['mp.weixin.qq.com'],
    'douyin': ['douyin.com'],
    'bilibili': ['bilibili.com', 'b23.tv'],
    'xiaohongshu': ['xiaohongshu.com', 'xiaohongshu.cn', 'xhslink.com'],
    'wechat-channels': ['channels.weixin.qq.com', 'weixin.qq.com'],
    'youtube': ['youtube.com', 'youtu.be'],
}
PRIVATE_PARAMS = re.compile(r'token|cookie|auth|signature|password|secret|^sn$', re.I)
MAX_BYTES = 8 * 1024 * 1024


def platform(url):
    host = (urllib.parse.urlsplit(url).hostname or '').lower()
    for name, domains in DOMAINS.items():
        if any(host == d or host.endswith('.' + d) for d in domains):
            return name
    return 'web'


def safe_url(url):
    p = urllib.parse.urlsplit(url)
    host = p.hostname or ''
    if p.port:
        host += ':' + str(p.port)
    params = [(k, '[redacted]' if PRIVATE_PARAMS.search(k) else v)
              for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)]
    return urllib.parse.urlunsplit((p.scheme, host, p.path, urllib.parse.urlencode(params), ''))


def route(text):
    urls = re.findall(r'https?://[^\s<>"\u3000]+', text)
    result = []
    for raw in urls:
        url = raw.rstrip('。，、！？；：）】》」』.,;!?)\'')
        if url not in [r['_url'] for r in result]:
            result.append({'_url': url, 'url': safe_url(url), 'platform': platform(url)})
    return [{k: v for k, v in r.items() if k != '_url'} for r in result]


def record(url='', method=''):
    return {'source_url': safe_url(url) if url else '', 'platform': platform(url),
            'read_at': datetime.now().astimezone().isoformat(timespec='seconds'),
            'method': method, 'status': 'needs_browser', 'title': '', 'author': '',
            'published_at': '', 'text': '', 'images': [], 'coverage': [],
            'limitations': ['完整性尚未核验；图片、视频、评论及分页需要分别读取。']}


def extract_html(raw, url=''):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError('missing_dependency: beautifulsoup4')
    soup = BeautifulSoup(raw, 'html.parser')
    r = record(url, 'public-html')
    def text_of(selector):
        node = soup.select_one(selector)
        return node.get_text('\n', strip=True) if node else ''
    def meta(key):
        node = soup.find('meta', attrs={'property': key}) or soup.find('meta', attrs={'name': key})
        return node.get('content', '').strip() if node else ''
    r['title'] = text_of('#activity-name') or meta('og:title') or text_of('title')
    r['author'] = text_of('#js_name') or meta('author')
    r['published_at'] = text_of('#publish_time') or meta('article:published_time')
    candidate = soup.select_one('#js_content') or soup.select_one('article') or soup.select_one('main')
    # Extract only public Article/BlogPosting schema, not hidden framework state.
    schema_body = ''
    def visit(obj):
        nonlocal schema_body
        if isinstance(obj, list):
            for item in obj:
                visit(item)
        elif isinstance(obj, dict):
            types = obj.get('@type', [])
            types = [types] if isinstance(types, str) else types
            if any(t in ['Article', 'BlogPosting', 'NewsArticle', 'SocialMediaPosting'] for t in types):
                body = obj.get('articleBody', '')
                if isinstance(body, str) and len(body) > len(schema_body):
                    schema_body = body.strip()
                if not r['title']:
                    r['title'] = obj.get('headline', '')
            if '@graph' in obj:
                visit(obj['@graph'])
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            visit(json.loads(node.string or node.get_text()))
        except (ValueError, TypeError):
            pass
    if candidate:
        for node in candidate.select('script,style,nav,footer,form'):
            node.decompose()
        body = candidate.get_text('\n', strip=True)
        for image in candidate.select('img'):
            src = image.get('data-src') or image.get('src')
            if src and not src.startswith('data:'):
                r['images'].append({'url': safe_url(urllib.parse.urljoin(url, src)),
                                    'alt': image.get('alt', ''), 'read': False})
    else:
        body = schema_body
    visible = soup.get_text(' ', strip=True)
    challenge_title = re.search(r'^(访问验证|安全验证|请完成验证|验证码|access denied|just a moment|attention required)', r['title'], re.I)
    challenge_shell = len(visible) < 1800 and re.search(r'访问过于频繁|请完成安全验证|完成验证后|环境异常|系统检测到|captcha|verify you are human', visible, re.I)
    if challenge_title or challenge_shell:
        r.update(status='access_blocked', text='', images=[], limitations=['访问验证或安全检查；停止自动重试，由用户手动处理。'])
    elif body.strip():
        r.update(status='body_extracted', text=body, coverage=['article-text'])
    else:
        r['text'] = meta('og:description') or meta('description')
        r['status'] = 'metadata_only' if r['title'] or r['text'] else 'needs_browser'
        r['coverage'] = ['page-metadata'] if r['status'] == 'metadata_only' else []
        r['limitations'].append('未提取目标正文；可尝试授权浏览器中的可见页面。')
    return r


def fetch(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ['http', 'https'] or not p.hostname or p.username or p.password:
        raise ValueError('Use a valid public HTTP(S) URL without embedded credentials.')
    r = record(url, 'public-http')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'social-content-reader/1.0', 'Accept': 'text/html', 'Accept-Encoding': 'identity'})
        with urllib.request.urlopen(req, timeout=25) as response:
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('HTML exceeds the 8 MiB limit; supply a local file.')
            encoding = response.headers.get('Content-Encoding', '').lower().strip()
            if encoding in ['gzip', 'deflate']:
                decoder = zlib.decompressobj(31 if encoding == 'gzip' else zlib.MAX_WBITS)
                data = decoder.decompress(data, MAX_BYTES + 1)
                if len(data) > MAX_BYTES or decoder.unconsumed_tail:
                    raise ValueError('Decoded HTML exceeds the size limit.')
                if not decoder.eof:
                    raise ValueError('Incomplete compressed response.')
            elif encoding not in ['', 'identity']:
                r.update(status='unsupported_encoding', limitations=['当前读取器不能解码响应压缩格式；未取得正文。'])
                return r
            if 'html' not in response.headers.get('Content-Type', '').lower():
                r.update(status='unsupported_response', limitations=['响应不是HTML；请使用对应文件/媒体读取能力。'])
                return r
            charset = response.headers.get_content_charset()
            if not charset:
                m = re.search(br'charset=["\s\']*([\w-]+)', data[:4096], re.I)
                charset = m.group(1).decode('ascii') if m else 'utf-8'
            resolved = response.geturl()
            r = extract_html(data.decode(charset, errors='replace'), resolved)
            r['source_url'] = safe_url(url)
            r['resolved_url'] = safe_url(resolved)
            return r
    except urllib.error.HTTPError as e:
        r['status'] = 'access_blocked' if e.code in [401, 403, 412, 429] else 'http_error'
        r['http_status'] = e.code
        r['limitations'] = ['HTTP请求失败；未取得正文。访问限制时停止自动重试。']
    except (urllib.error.URLError, TimeoutError):
        r['status'] = 'network_error'
        r['limitations'] = ['网络请求失败；未取得正文。']
    return r


def timestamp(seconds):
    ms = round(float(seconds) * 1000)
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


def subtitles(path, url=''):
    raw = Path(path).read_text(encoding='utf-8-sig')
    cues = []
    if Path(path).suffix.lower() == '.json':
        obj = json.loads(raw)
        items = obj.get('body', []) if isinstance(obj, dict) else obj
        for row in items:
            if row.get('content', '').strip():
                cues.append({'start': timestamp(row['from']), 'end': timestamp(row['to']), 'text': row['content'].strip()})
    else:
        for block in re.split(r'\n\s*\n', raw.replace('\r\n', '\n')):
            lines = block.splitlines()
            for i, line in enumerate(lines):
                if '-->' not in line:
                    continue
                start, end = line.split('-->', 1)
                content = html.unescape(re.sub(r'<[^>]+>', '', '\n'.join(lines[i + 1:]))).strip()
                if content:
                    cues.append({'start': start.strip().replace(',', '.'), 'end': end.strip().split()[0].replace(',', '.'), 'text': content})
                break
    r = record(url, 'local-subtitles')
    r.update(status='transcript_extracted' if cues else 'empty_subtitles', cues=cues,
             coverage=['timestamped-subtitles'] if cues else [],
             text='\n'.join(f"[{c['start']} → {c['end']}] {c['text']}" for c in cues),
             limitations=['字幕完整性、语言、人工/自动生成来源及对应分P需核验；未分析画面。'])
    return r


def emit(result, out_dir=None):
    if out_dir:
        dest = Path(out_dir) / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:8])
        dest.mkdir(parents=True, exist_ok=False)
        (dest / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        md = f"# {result.get('title') or '内容读取结果'}\n\n"
        md += '\n'.join(f"- {k}: {result.get(k, '')}" for k in ['source_url', 'platform', 'read_at', 'status', 'method'])
        md += '\n\n' + result.get('text', '') + '\n\n读取限制：\n' + '\n'.join('- ' + s for s in result.get('limitations', []))
        (dest / 'content.md').write_text(md, encoding='utf-8')
        result['output_directory'] = str(dest.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    routing = commands.add_parser('route')
    routing.add_argument('--text', required=True)
    reading = commands.add_parser('read')
    source = reading.add_mutually_exclusive_group(required=True)
    source.add_argument('--url')
    source.add_argument('--file')
    reading.add_argument('--source-url', default='')
    reading.add_argument('--out-dir')
    sub = commands.add_parser('subtitles')
    sub.add_argument('--file', required=True)
    sub.add_argument('--source-url', default='')
    sub.add_argument('--out-dir')
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            emit({'python': sys.executable, 'modules': {m: importlib.util.find_spec(m) is not None for m in ['bs4', 'yt_dlp', 'faster_whisper']},
                  'commands': {m: bool(shutil.which(m)) for m in ['ffmpeg', 'bili', 'mcporter', 'agent-reach']},
                  'note': '依赖存在不代表登录、网络或目标内容读取成功；浏览器工具需由agent核验。'})
        elif args.command == 'route':
            emit({'links': route(args.text)})
        elif args.command == 'read':
            result = fetch(args.url) if args.url else extract_html(Path(args.file).read_text(encoding='utf-8-sig'), args.source_url)
            if args.file:
                result['method'] = 'local-html'
            emit(result, args.out_dir)
        else:
            emit(subtitles(args.file, args.source_url), args.out_dir)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, LookupError, zlib.error) as e:
        # Never echo an input URL or arbitrary content through an exception.
        emit({'status': 'reader_error', 'error_type': type(e).__name__, 'message': '读取器无法处理输入；检查依赖、路径或文件格式。'})
        sys.exit(1)


if __name__ == '__main__':
    main()
