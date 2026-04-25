"""Volkov Law — Corruption, Crime & Compliance blog (RSS).

Michael Volkov's practitioner-oriented FCPA blog. US-based outlet that
covers cases globally; `country` set to the outlet's home jurisdiction
("US") per Ellen 2026-04-25 — she wants the country column populated
in the scout Excel. Per-article jurisdiction may differ from the outlet
home; that's metadata for a future enhancement.

Standard WordPress RSS 2.0 — handled entirely by `RssFeedAdapter`. No
keyword filter for v1; the blog's primary subject matter is anti-corruption,
so most posts are on-topic.
"""

from lawtracker.sources.rss_feed import RssFeedAdapter


class VolkovLawAdapter(RssFeedAdapter):
    source_id = "volkov_law"
    kind = "event_list"
    url = "https://blog.volkovlaw.com/feed/"
    country = "US"
