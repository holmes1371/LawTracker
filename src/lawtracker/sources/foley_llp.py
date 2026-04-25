"""Foley & Lardner LLP — publications RSS feed.

Major US law firm. `/feed/` returns ALL publications across practice areas,
so the adapter applies the English anti-corruption keyword filter to keep
only FCPA / AML / sanctions / anti-bribery items in the scout.

Cloudflare-fingerprint-blocked when fetched with httpx, so `use_curl_cffi
= True` to mimic Chrome's TLS handshake.
"""

from lawtracker.sources._filters import ANTI_CORRUPTION_EN
from lawtracker.sources.rss_feed import RssFeedAdapter


class FoleyLlpAdapter(RssFeedAdapter):
    source_id = "foley_llp"
    kind = "event_list"
    url = "https://www.foley.com/feed/"
    country = "US"
    keyword_filter = ANTI_CORRUPTION_EN
    use_curl_cffi = True
