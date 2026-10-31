"""Original-publisher RSS sources for Khmer visual editions only.

These are publisher-owned feed endpoints, NOT Google News search/index URLs,
aggregators, synthetic headlines, or social media reposts. A feed being
configured does not prove its uptime; the live availability canary checks it.
Article links must match the original publisher domain in visual_news.py.
"""
from __future__ import annotations

CAMBODIA_FEEDS = {
    # Verified live on GitHub Actions runner 2026-10-31:
    # https://github.com/Dapravith/ai-tech-news-radar/actions/runs/41154108551
    "Koh Santepheap": "https://kohsantepheapdaily.com.kh/feed/",
    "Kampuchea Thmey": "https://kampucheathmey.com/feed/",
    "CamboJA News": "https://cambojanews.com/feed/",
}

# Keep as disabled candidates until a real cloud-runner RSS validation passes.
# Failures verified on 2026-10-31: 403/HTTPError or invalid XML (Kiripost).
CAMBODIA_DISABLED_CANDIDATES = {
    "Khmer Times": "https://www.khmertimeskh.com/feed/",
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
