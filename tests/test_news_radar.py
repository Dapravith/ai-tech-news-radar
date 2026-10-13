import unittest
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
import news_radar
from news_radar import clean, normalize_url, parse_feed, score, select_items, build_message, render_news_report, parse_ai_response, ai_summarize, send_telegram

RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>News</title><item><title>New Kubernetes release</title><link>https://example.org/k8s?utm_source=rss</link><pubDate>Tue, 13 Oct 2026 02:00:00 GMT</pubDate><description>Cloud deployment improvements for developers.</description></item></channel></rss>'''
ATOM = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>New AI agent model</title><link href="https://example.org/agent"/><updated>2026-10-13T02:00:00Z</updated><summary>Model update.</summary></entry></feed>'''

class NewsRadarTest(unittest.TestCase):
    def test_rss(self):
        results = parse_feed(RSS, 'Kubernetes Blog')
        self.assertEqual(results[0]['url'], 'https://example.org/k8s')
        self.assertEqual(results[0]['title'], 'New Kubernetes release')

    def test_atom(self):
        self.assertEqual(parse_feed(ATOM, 'AI')[0]['url'], 'https://example.org/agent')

    def test_sanitization(self):
        self.assertEqual(clean('<b>AI</b> &amp; cloud'), 'AI & cloud')
        self.assertEqual(normalize_url('javascript:alert(1)'), '')

    def test_deduplication(self):
        now = datetime(2026, 10, 13, 5, tzinfo=timezone.utc)
        item = parse_feed(ATOM, 'AI')[0]
        selected = select_items([item], {}, now, False)
        self.assertEqual(len(selected), 1)
        self.assertEqual(select_items([item], {selected[0]['id']: now.isoformat()}, now, False), [])
        self.assertGreater(score(item, now), 0)

    def test_message_links_and_flag(self):
        now = datetime(2026, 10, 13, 5, tzinfo=timezone.utc)
        item = parse_feed(ATOM, 'AI')[0]
        msg = build_message([item], now, True, False)
        self.assertIn('https://example.org/agent', msg)
        self.assertIn('TEST RUN', msg)

    def test_credible_source_ranks_higher(self):
        now = datetime(2026, 10, 13, 5, tzinfo=timezone.utc)
        original = parse_feed(ATOM, 'Independent')[0]
        trusted = dict(original, source='GitHub Blog')
        self.assertGreater(score(trusted, now), score(original, now))

    def test_empty_openrouter_content_and_fallback(self):
        with self.assertRaisesRegex(ValueError, 'empty model content'):
            parse_ai_response({'choices': [{'message': {'content': None}}]})
        item = parse_feed(ATOM, 'AI')[0]
        item['id'] = news_radar.make_id(item)
        response = json.dumps({'choices': [{'message': {'content': None}}]}).encode()
        with (patch.dict(os.environ, {'OPENROUTER_API_KEY': 'dummy'}),
              patch('news_radar.urlopen', return_value=io.BytesIO(response))):
            self.assertEqual(ai_summarize([item])[0]['id'], item['id'])

    def test_parse_valid_openrouter_json(self):
        payload = {'choices': [{'message': {'content': '{"items":[{"id":"abc","why":"Release"}]}'}}]}
        self.assertEqual(parse_ai_response(payload)[0]['id'], 'abc')

    def test_feed_failure_isolated(self):
        with (tempfile.TemporaryDirectory() as folder,
              patch('news_radar.FEEDS', {'Broken': 'https://invalid.invalid/rss', 'Working': 'https://example.org/feed'}),
              patch('news_radar.fetch_feed', side_effect=[OSError('offline'), parse_feed(ATOM, 'Working')]),
              patch('news_radar.STATE_FILE', Path(folder) / 'seen.json'),
              patch('news_radar.OUTPUT_DIR', Path(folder) / 'out'),
              patch('news_radar.send_telegram') as notify,
              patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'dummy', 'TELEGRAM_CHAT_ID': '123', 'OPENROUTER_API_KEY': ''}),
              patch.object(sys, 'argv', ['news_radar.py', '--test-mode'])):
            self.assertEqual(news_radar.main(), 0)
            notify.assert_called_once()

    def test_silent_when_no_production_news(self):
        with (tempfile.TemporaryDirectory() as folder,
              patch('news_radar.FEEDS', {'Working': 'https://example.org/feed'}),
              patch('news_radar.fetch_feed', return_value=[]),
              patch('news_radar.STATE_FILE', Path(folder) / 'seen.json'),
              patch('news_radar.send_telegram') as notify,
              patch.object(sys, 'argv', ['news_radar.py'])):
            self.assertEqual(news_radar.main(), 0)
            notify.assert_not_called()

    def test_telegram_success_and_rejection(self):
        with patch('news_radar.urlopen', return_value=io.BytesIO(b'{"ok":true}')) as mock_send:
            send_telegram('Test', 'dummy-token', '123')
            mock_send.assert_called_once()
        with patch('news_radar.urlopen', return_value=io.BytesIO(b'{"ok":false}')):
            with self.assertRaisesRegex(RuntimeError, 'Telegram rejected'):
                send_telegram('Test', 'dummy-token', '123')


    def test_parse_markdown_wrapped_model_response(self):
        response = {
            'choices': [{'message': {'content':
                'Here is the result:\\n```json\\n'
                '{"items":[{"id":"known","why":"Relevant to DevOps"}]}'
                '\\n```'}}]
        }
        self.assertEqual(parse_ai_response(response)[0]['id'], 'known')

    def test_parse_json_list_model_response(self):
        response = {'choices': [{'message': {'content': '[{"id":"known"}]'}}]}
        self.assertEqual(parse_ai_response(response)[0]['id'], 'known')

    def test_parse_malformed_response_fails_closed(self):
        for content in ('No stories today', '{"error":"not JSON items"}', None, 77):
            with self.subTest(content=content):
                with self.assertRaises(ValueError):
                    parse_ai_response({'choices': [{'message': {'content': content}}]})

    def test_production_marks_delivered_and_next_run_is_silent(self):
        now = datetime.now(timezone.utc)
        article = {
            'title': 'Major Kubernetes developer release',
            'url': 'https://example.org/unique-k8s-release',
            'published': now,
            'source': 'Kubernetes Blog',
            'summary': 'Developer infrastructure improvements',
        }
        with (tempfile.TemporaryDirectory() as folder,
              patch('news_radar.FEEDS', {'Working': 'https://example.org/rss'}),
              patch('news_radar.fetch_feed', return_value=[article]),
              patch('news_radar.STATE_FILE', Path(folder) / 'seen.json'),
              patch('news_radar.OUTPUT_DIR', Path(folder) / 'out'),
              patch('news_radar.send_telegram') as notify,
              patch.dict(os.environ, {
                  'TELEGRAM_BOT_TOKEN': 'dummy',
                  'TELEGRAM_CHAT_ID': '123',
                  'OPENROUTER_API_KEY': '',
              }),
              patch.object(sys, 'argv', ['news_radar.py'])):
            self.assertEqual(news_radar.main(), 0)
            self.assertEqual(notify.call_count, 1)
            state = json.loads((Path(folder) / 'seen.json').read_text())
            self.assertIn(news_radar.make_id(article), state)
            self.assertEqual(news_radar.main(), 0)
            self.assertEqual(notify.call_count, 1)

    def test_complete_feed_outage_does_not_send_duplicate_alert(self):
        with (tempfile.TemporaryDirectory() as folder,
              patch('news_radar.FEEDS', {'Broken': 'https://invalid.invalid/rss'}),
              patch('news_radar.fetch_feed', side_effect=OSError('outage')),
              patch('news_radar.STATE_FILE', Path(folder) / 'seen.json'),
              patch('news_radar.send_telegram') as notify,
              patch.object(sys, 'argv', ['news_radar.py'])):
            self.assertEqual(news_radar.main(), 1)
            notify.assert_not_called()


    def test_editorial_report_has_sources_and_precise_local_times(self):
        now = datetime(2026, 10, 13, 5, 2, 9, tzinfo=timezone.utc)
        entry = parse_feed(ATOM, 'Google AI Blog')[0]
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '38346920698'}):
            report = build_message([entry], now, False, False)
        self.assertIn('<b>Intelligence briefing</b>', report)
        self.assertIn('2026-10-13 12:02:09 ICT', report)
        self.assertIn('2026-10-13 09:00:00 ICT', report)
        self.assertIn('<b>REFERENCES</b>', report)
        self.assertIn('<a href="https://example.org/agent">', report)
        self.assertIn('Run record:</b> <code>38346920698</code>', report)
        self.assertIn('Publication times come from source-feed metadata', report)

    def test_editorial_report_escapes_untrusted_text_and_link(self):
        now = datetime(2026, 10, 13, 5, tzinfo=timezone.utc)
        entry = parse_feed(ATOM, 'AI & Research')[0]
        entry['title'] = 'R&D & DevOps <b>Release</b>'
        entry['summary'] = '<i>New</i> & improved developer APIs'
        entry['url'] = 'https://example.org/agent?q=ai&category=cloud'
        message = build_message([entry], now, False, False)
        self.assertIn('R&amp;D &amp; DevOps Release', message)
        self.assertIn('New &amp; improved developer APIs', message)
        self.assertIn('AI &amp; Research', message)
        self.assertIn('href="https://example.org/agent?q=ai&amp;category=cloud"', message)
        self.assertNotIn('<b>Release</b>', message)

    def test_long_original_references_do_not_break_html_or_state(self):
        now = datetime.now(timezone.utc)
        headlines = [
            'Major Kubernetes API update',
            'FastAPI typed validation release',
            'PostgreSQL storage performance analysis',
            'Next.js authentication security advisory',
            'Docker cloud observability improvements',
        ]
        articles = [
            {'title': title, 'url': 'https://example.org/' + 'p' * 1100 + str(n),
             'published': now, 'source': 'Kubernetes Blog', 'summary': 'Cloud improvement'}
            for n, title in enumerate(headlines)
        ]
        message, displayed = render_news_report(articles, now, False, False)
        self.assertLessEqual(len(message), 3800)
        self.assertTrue(1 <= len(displayed) < len(articles))
        self.assertEqual(message.count('<a href='), len(displayed))
        self.assertEqual(message.count('</a>'), len(displayed))
        with (tempfile.TemporaryDirectory() as folder,
              patch('news_radar.FEEDS', {'Working': 'https://example.org/feed'}),
              patch('news_radar.fetch_feed', return_value=articles),
              patch('news_radar.STATE_FILE', Path(folder) / 'seen.json'),
              patch('news_radar.OUTPUT_DIR', Path(folder) / 'out'),
              patch('news_radar.send_telegram') as notify,
              patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'dummy',
                                      'TELEGRAM_CHAT_ID': '123', 'OPENROUTER_API_KEY': ''}),
              patch.object(sys, 'argv', ['news_radar.py'])):
            self.assertEqual(news_radar.main(), 0)
            delivered = json.loads((Path(folder) / 'seen.json').read_text())
            self.assertEqual(len(delivered), len(displayed))
            self.assertEqual(notify.call_count, 1)

    def test_report_timezone_crosses_utc_day_boundary(self):
        now = datetime(2026, 10, 13, 23, 45, 58, tzinfo=timezone.utc)
        self.assertIn('2026-10-14 06:45:58 ICT', build_message([], now, True, False))

    def test_telegram_html_parse_mode_is_enabled(self):
        with patch('news_radar.urlopen', return_value=io.BytesIO(b'{"ok":true}')) as mock_send:
            send_telegram('<b>Report</b>', 'dummy-token', '123')
            data = json.loads(mock_send.call_args.args[0].data.decode('utf-8'))
            self.assertEqual(data['parse_mode'], 'HTML')
            self.assertEqual(data['text'], '<b>Report</b>')
            self.assertTrue(data['disable_web_page_preview'])


    def test_hacker_news_metadata_is_not_shown_as_editorial_summary(self):
        now = datetime(2026, 10, 13, 8, tzinfo=timezone.utc)
        item = {
            'title': 'New software research overview',
            'summary': 'Article URL: https://example.org/software Comments URL: https://news.ycombinator.com/item?id=5 Points: 129',
            'published': now,
            'url': 'https://example.org/software',
            'source': 'Hacker News',
        }
        report = build_message([item], now, False, False)
        self.assertIn('Community-submitted article', report)
        self.assertNotIn('Comments URL:', report)
        self.assertNotIn('Points:', report)
        self.assertIn('<a href="https://example.org/software">', report)


if __name__ == '__main__':
    unittest.main()
