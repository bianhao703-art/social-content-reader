"""Offline checks for observable reader behavior; never contact platform servers."""
import contextlib
import gzip
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reader', ROOT / 'scripts' / 'reader.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class Response:
    def __init__(self, data, content_type='text/html; charset=utf-8', encoding=None):
        self.data = data
        self.headers = Message()
        self.headers['Content-Type'] = content_type
        if encoding:
            self.headers['Content-Encoding'] = encoding

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.data[:size]

    def geturl(self):
        return 'https://example.com/resolved'


class ReaderTests(unittest.TestCase):
    def test_share_links_across_platforms(self):
        links = reader.route('公众号 https://mp.weixin.qq.com/s/demo 抖音 https://v.douyin.com/demo/ B站 https://b23.tv/demo 小红书 https://xhslink.com/demo 视频号 https://channels.weixin.qq.com/demo 视频 https://youtu.be/demo')
        self.assertEqual([x['platform'] for x in links], ['wechat-article', 'douyin', 'bilibili', 'xiaohongshu', 'wechat-channels', 'youtube'])

    def test_trim_punctuation_and_deduplicate(self):
        result = reader.route('【分享】https://b23.tv/demo）。 再次 https://b23.tv/demo')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['url'], 'https://b23.tv/demo')

    def test_domain_boundary(self):
        self.assertEqual(reader.platform('https://bilibili.com.evil.example/video'), 'web')
        self.assertEqual(reader.platform('https://notbilibili.com/video'), 'web')
        self.assertEqual(reader.platform('https://www.bilibili.com/video/demo'), 'bilibili')

    def test_url_secrets_are_redacted(self):
        value = reader.safe_url('https://fake:secret@example.com/a?id=123&xsec_token=fictional-token&signature=fictional-signature#private-fragment')
        self.assertNotIn('fictional-token', value)
        self.assertNotIn('fictional-signature', value)
        self.assertNotIn('secret', value)
        self.assertNotIn('private-fragment', value)
        self.assertIn('id=123', value)

    def test_wechat_body_author_and_unread_images(self):
        html = '<title>fallback</title><h1 id="activity-name">自写标题</h1><span id="js_name">示例账号</span><span id="publish_time">2026-10-01</span><div id="js_content"><p>自写正文</p><img data-src="https://example.com/a.jpg?token=fictional-secret"><script>unwanted()</script></div>'
        result = reader.extract_html(html, 'https://mp.weixin.qq.com/s/demo')
        self.assertEqual(result['status'], 'body_extracted')
        self.assertEqual((result['title'], result['author'], result['published_at']), ('自写标题', '示例账号', '2026-10-01'))
        self.assertEqual(result['text'], '自写正文')
        self.assertFalse(result['images'][0]['read'])
        self.assertNotIn('fictional-secret', result['images'][0]['url'])

    def test_metadata_does_not_become_video_body(self):
        result = reader.extract_html('<title>示例视频</title><meta property="og:description" content="仅有分享描述">', 'https://www.bilibili.com/video/demo')
        self.assertEqual(result['status'], 'metadata_only')
        self.assertEqual(result['coverage'], ['page-metadata'])

    def test_challenge_does_not_become_body(self):
        result = reader.extract_html('<title>安全验证</title><main>请完成安全验证 verify you are human</main>')
        self.assertEqual(result['status'], 'access_blocked')
        self.assertEqual(result['text'], '')

    def test_public_article_jsonld(self):
        schema = {'@graph':[{'@type':'Article','headline':'示例文章','articleBody':'这是自写结构化正文'}]}
        result = reader.extract_html('<script type="application/ld+json">'+json.dumps(schema)+'</script>')
        self.assertEqual(result['status'], 'body_extracted')
        self.assertEqual(result['text'], '这是自写结构化正文')

    def test_framework_state_not_extracted(self):
        result = reader.extract_html('<script type="application/json">{"body":"private framework state"}</script>')
        self.assertEqual(result['status'], 'needs_browser')
        self.assertEqual(result['text'], '')

    def test_vtt_timestamps_and_html_entities(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'demo.vtt'
            path.write_text('WEBVTT\n\n00:00.000 --> 00:02.000 align:start\n<b>示例 &amp; 字幕</b>\n', encoding='utf-8')
            result=reader.subtitles(path)
            self.assertEqual(result['status'], 'transcript_extracted')
            self.assertEqual(result['cues'][0], {'start':'00:00.000','end':'00:02.000','text':'示例 & 字幕'})

    def test_srt_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'demo.srt'
            path.write_text('1\n00:00:01,250 --> 00:00:02,750\n示例\n', encoding='utf-8')
            result=reader.subtitles(path)
            self.assertEqual(result['cues'][0]['start'], '00:00:01.250')
            self.assertEqual(result['cues'][0]['end'], '00:00:02.750')

    def test_bilibili_json_subtitles(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'demo.json'
            path.write_text(json.dumps({'body':[{'from':1.5,'to':2.75,'content':'示例'}]}), encoding='utf-8')
            result=reader.subtitles(path)
            self.assertEqual(result['cues'][0], {'start':'00:00:01.500','end':'00:00:02.750','text':'示例'})

    def test_empty_subtitles_are_not_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'empty.vtt'
            path.write_text('WEBVTT\n', encoding='utf-8')
            self.assertEqual(reader.subtitles(path)['status'], 'empty_subtitles')

    def test_each_http_denial_stops_after_one_request(self):
        for code in (401,403,412,429):
            with self.subTest(code=code):
                denial=urllib.error.HTTPError('https://example.com/a',code,'denied',None,None)
                with patch.object(reader.urllib.request,'urlopen',side_effect=denial) as request:
                    result=reader.fetch('https://example.com/a')
                self.assertEqual(result['status'],'access_blocked')
                self.assertEqual(result['http_status'],code)
                self.assertEqual(request.call_count,1)

    def test_gzip_response_is_read(self):
        data=gzip.compress('<article>自写压缩正文</article>'.encode('utf-8'))
        with patch.object(reader.urllib.request,'urlopen',return_value=Response(data,encoding='gzip')):
            result=reader.fetch('https://example.com/a')
        self.assertEqual(result['text'],'自写压缩正文')
        self.assertEqual(result['resolved_url'],'https://example.com/resolved')

    def test_non_html_response_is_not_article(self):
        with patch.object(reader.urllib.request,'urlopen',return_value=Response(b'fake-video',content_type='video/mp4')):
            result=reader.fetch('https://example.com/a')
        self.assertEqual(result['status'],'unsupported_response')
        self.assertEqual(result['text'],'')

    def test_invalid_url_is_not_requested(self):
        with patch.object(reader.urllib.request,'urlopen') as request:
            for url in ['file:///private','https://fake:fictional-password@example.com/a']:
                with self.assertRaises(ValueError):
                    reader.fetch(url)
        request.assert_not_called()

    def test_outputs_are_distinct_and_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            source=reader.extract_html('<article>自写输出正文</article>','https://example.com/a?token=fictional-value')
            with contextlib.redirect_stdout(io.StringIO()):
                first=dict(source)
                second=dict(source)
                reader.emit(first,folder)
                reader.emit(second,folder)
            self.assertNotEqual(first['output_directory'],second['output_directory'])
            output=Path(first['output_directory'])
            evidence=json.loads((output/'evidence.json').read_text(encoding='utf-8'))
            self.assertEqual(evidence['text'],'自写输出正文')
            self.assertNotIn('fictional-value',(output/'content.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
