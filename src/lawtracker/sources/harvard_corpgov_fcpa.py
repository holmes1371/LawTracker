"""Harvard Law School Forum on Corporate Governance — FCPA tag.

Topic-tagged RSS feed restricted to posts categorized as Foreign Corrupt
Practices Act. Single-topic, no keyword filter needed. Volume is low (the
forum is academic / commentary, not a case feed).

Cloudflare-fingerprint-blocked when fetched with httpx, so `use_curl_cffi
= True`.
"""

from lawtracker.sources.rss_feed import RssFeedAdapter


class HarvardCorpGovFcpaAdapter(RssFeedAdapter):
    source_id = "harvard_corpgov_fcpa"
    kind = "event_list"
    url = "https://corpgov.law.harvard.edu/category/foreign-corrupt-practices-act/feed/"
    country = None
    use_curl_cffi = True
