"""GAB — The Global Anticorruption Blog.

Academic blog, Matthew Stephenson at Harvard Law School. Multi-jurisdictional
commentary on anti-corruption law and enforcement. Single-topic outlet, so
no keyword filter — every post is on-topic for the scout.

Standard WordPress RSS 2.0; handled entirely by `RssFeedAdapter`.
"""

from lawtracker.sources.rss_feed import RssFeedAdapter


class GlobalAnticorruptionBlogAdapter(RssFeedAdapter):
    source_id = "global_anticorruption_blog"
    kind = "event_list"
    url = "https://globalanticorruptionblog.com/feed/"
    country = "US"
