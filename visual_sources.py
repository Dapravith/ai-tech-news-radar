"""Original-publisher RSS sources for Khmer visual editions only.

These are publisher-owned feed endpoints, NOT Google News search/index URLs,
aggregators, synthetic headlines, or social media reposts. A feed being
configured does not prove its uptime; the live availability canary checks it.
Article links must match the original publisher domain in visual_news.py.
"""
from __future__ import annotations

CAMBODIA_FEEDS = {
    # Feed URL verified by public RSS discovery service (2026-10-31).
    "Khmer Times": "https://www.khmertimeskh.com/feed/",
    # Publisher-owned endpoints checked by CI; failures are surfaced as outages.
    "CamboJA News": "https://cambojanews.com/feed/",
    "Phnom Penh Post": "https://phnompenhpost.com/feed/",
    "Cambodianess": "https://www.cambodianess.com/feed/",
    "Kiripost": "https://kiripost.com/feed",
}

GLOBAL_ADDITIONAL_FEEDS = {
    # CNA's official feed directory publishes this exact World RSS endpoint.
    "CNA World": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6311",
}

GADGET_FEEDS = {
    "MacRumors": "https://feeds.macrumors.com/MacRumors-All",
    "Android Authority": "https://www.androidauthority.com/feed/",
    "GSMArena": "https://www.gsmarena.com/rss-news-reviews.php3",
}
