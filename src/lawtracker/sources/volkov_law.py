"""Volkov Law — Corruption, Crime & Compliance blog (RSS).

Practitioner-oriented FCPA / AML / sanctions commentary. Multi-jurisdictional
outlet, US-based but covers cases globally; `country` left None.

Standard WordPress RSS 2.0 — handled entirely by `RssFeedAdapter`. No
keyword filter for v1; the blog's primary subject matter is anti-corruption,
so most posts are on-topic. Tom + Ellen review noise level at item 18 and
add a filter if needed.
"""

from lawtracker.sources.rss_feed import RssFeedAdapter


class VolkovLawAdapter(RssFeedAdapter):
    source_id = "volkov_law"
    kind = "event_list"
    url = "https://blog.volkovlaw.com/feed/"
    country = None
