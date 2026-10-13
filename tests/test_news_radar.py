import unittest
from datetime import datetime, timedelta, timezone
from news_radar import clean, normalize_url, parse_feed, score, select_items, build_message

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

if __name__ == '__main__':
    unittest.main()
