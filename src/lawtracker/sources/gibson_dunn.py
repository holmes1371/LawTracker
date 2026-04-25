"""Gibson, Dunn & Crutcher — publications feed.

Major US law firm; "FCPA Update" is one of the long-running practitioner
references. Their main RSS feed (`/feed/`) returns ALL publications across
practice areas, so the adapter applies the English anti-corruption keyword
filter to keep only FCPA / AML / sanctions / anti-bribery items in the scout.

The firm is US-based but the FCPA Update covers global cases, so
`country = None` (outlet, not jurisdiction).
"""

from lawtracker.sources._filters import ANTI_CORRUPTION_EN
from lawtracker.sources.rss_feed import RssFeedAdapter


class GibsonDunnAdapter(RssFeedAdapter):
    source_id = "gibson_dunn"
    kind = "event_list"
    url = "https://www.gibsondunn.com/feed/"
    country = None
    keyword_filter = ANTI_CORRUPTION_EN
