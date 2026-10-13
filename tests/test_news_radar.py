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
from news_radar import clean, normalize_url, parse_feed, score, select_items, build_message, parse_ai_response, ai_summarize, send_telegram

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


if __name__ == '__main__':
    unittest.main()
