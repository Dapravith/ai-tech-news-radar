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


    def test_channel_delivery_separate_from_private_chat(self):
        article = {
            'title': 'Important Kubernetes security release',
            'url': 'https://example.org/security-release',
            'published': datetime.now(timezone.utc),
            'source': 'Kubernetes Blog',
            'summary': 'An important release for DevOps teams',
        }
        with (tempfile.TemporaryDirectory() as folder,
              patch('news_radar.FEEDS', {'Working': 'https://example.org/feed'}),
              patch('news_radar.fetch_feed', return_value=[article]),
              patch('news_radar.STATE_FILE', Path(folder) / 'seen.json'),
              patch('news_radar.OUTPUT_DIR', Path(folder) / 'out'),
              patch('news_radar.send_telegram') as notify,
              patch.dict(os.environ, {
                  'TELEGRAM_BOT_TOKEN': 'dummy',
                  'TELEGRAM_CHAT_ID': 'private-123',
                  'TELEGRAM_CHANNEL_ID': '@MyAITechRadar',
                  'OPENROUTER_API_KEY': '',
              }),
              patch.object(sys, 'argv', ['news_radar.py'])):
            self.assertEqual(news_radar.main(), 0)
            notify.assert_called_once()
            self.assertEqual(notify.call_args.args[2], '@MyAITechRadar')
            self.assertIn(news_radar.make_id(article), json.loads(
                (Path(folder) / 'seen.json').read_text()
            ))

    def test_private_chat_fallback_when_no_channel_configured(self):
        article = {
            'title': 'Important Kubernetes security release',
            'url': 'https://example.org/security-release',
            'published': datetime.now(timezone.utc),
            'source': 'Kubernetes Blog',
            'summary': 'Infrastructure security improvements',
        }
        with (tempfile.TemporaryDirectory() as folder,
              patch('news_radar.FEEDS', {'Working': 'https://example.org/feed'}),
              patch('news_radar.fetch_feed', return_value=[article]),
              patch('news_radar.STATE_FILE', Path(folder) / 'seen.json'),
              patch('news_radar.OUTPUT_DIR', Path(folder) / 'out'),
              patch('news_radar.send_telegram') as notify,
              patch.dict(os.environ, {
                  'TELEGRAM_BOT_TOKEN': 'dummy',
                  'TELEGRAM_CHAT_ID': 'private-123',
                  'TELEGRAM_CHANNEL_ID': '',
                  'OPENROUTER_API_KEY': '',
              }),
              patch.object(sys, 'argv', ['news_radar.py'])):
            self.assertEqual(news_radar.main(), 0)
            self.assertEqual(notify.call_args.args[2], 'private-123')

    def test_channel_failure_does_not_record_news_as_delivered(self):
        article = {
            'title': 'New FastAPI security advisory',
            'url': 'https://example.org/fastapi-security',
            'published': datetime.now(timezone.utc),
            'source': 'GitHub Blog',
            'summary': 'Security guidance',
        }
        with (tempfile.TemporaryDirectory() as folder,
              patch('news_radar.FEEDS', {'Working': 'https://example.org/feed'}),
              patch('news_radar.fetch_feed', return_value=[article]),
              patch('news_radar.STATE_FILE', Path(folder) / 'seen.json'),
              patch('news_radar.OUTPUT_DIR', Path(folder) / 'out'),
              patch('news_radar.send_telegram', side_effect=RuntimeError('channel access denied')),
              patch.dict(os.environ, {
                  'TELEGRAM_BOT_TOKEN': 'dummy',
                  'TELEGRAM_CHAT_ID': 'private-123',
                  'TELEGRAM_CHANNEL_ID': '@MyAITechRadar',
                  'OPENROUTER_API_KEY': '',
              }),
              patch.object(sys, 'argv', ['news_radar.py'])):
            with self.assertRaisesRegex(RuntimeError, 'channel access denied'):
                news_radar.main()
            self.assertFalse((Path(folder) / 'seen.json').exists())


    def test_same_topic_variants_are_not_posted_twice(self):
        now = datetime(2026, 10, 14, 1, 0, tzinfo=timezone.utc)
        a = {
            'title': 'Gemini 4 Argon',
            'url': 'https://example.org/gemini-argon',
            'published': now,
            'source': 'Hacker News',
            'summary': 'AI model update',
        }
        b = dict(a, title='Gemini 4 Argon for Robotics',
                 url='https://example.org/gemini-robotics')
        self.assertEqual(len(select_items([a, b], {}, now, False)), 1)

    def test_distinct_release_versions_are_not_collapsed(self):
        self.assertFalse(news_radar.similar_headline(
            'Gemini 4 Argon', 'Gemini 5 Argon'))
        self.assertFalse(news_radar.similar_headline(
            'Python 3.16 alpha 1 released', 'Python 3.16 alpha 2 released'))

    def test_tech_radar_respects_trending_delivery_state(self):
        now = datetime.now(timezone.utc)
        story = {
            'title': 'Important Kubernetes security release',
            'url': 'https://example.org/important-security',
            'published': now,
            'source': 'Kubernetes Blog',
            'summary': 'Kubernetes security update',
        }
        with (tempfile.TemporaryDirectory() as d,
              patch('news_radar.FEEDS', {'Working': 'https://example.org/rss'}),
              patch('news_radar.fetch_feed', return_value=[story]),
              patch('news_radar.STATE_FILE', Path(d) / 'seen.json'),
              patch('news_radar.TRENDING_STATE_FILE', Path(d) / 'trending.json'),
              patch('news_radar.OUTPUT_DIR', Path(d) / 'out'),
              patch('news_radar.send_telegram') as send,
              patch.dict(os.environ, {
                  'TELEGRAM_BOT_TOKEN': 'fake',
                  'TELEGRAM_CHANNEL_ID': '@MyAITechRadar',
                  'OPENROUTER_API_KEY': '',
              }),
              patch.object(sys, 'argv', ['news_radar.py'])):
            (Path(d) / 'trending.json').write_text(json.dumps({
                news_radar.make_id(story): now.isoformat(),
            }))
            self.assertEqual(news_radar.main(), 0)
            send.assert_not_called()
            self.assertFalse((Path(d) / 'seen.json').exists())

    def test_invalid_deduplication_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'broken.json'
            path.write_text('{not-valid-json')
            with self.assertRaises(json.JSONDecodeError):
                news_radar.read_seen_state(path)
            path.write_text('[]')
            with self.assertRaises(ValueError):
                news_radar.read_seen_state(path)


if __name__ == '__main__':
    unittest.main()
