"""Consejo para la Transparencia (Chile) — RSS adapter.

Chilean Council for Transparency oversees the access-to-information regime
under Law 20.285 and publishes investigation summaries, press releases, and
policy news. WordPress site, standard RSS 2.0 — handled entirely by
`RssFeedAdapter`. Spanish-language; no keyword filter (the outlet's whole
beat is transparency / probity, so most posts are on-topic for the scout).
"""

from lawtracker.sources.rss_feed import RssFeedAdapter


class ConsejoTransparenciaClAdapter(RssFeedAdapter):
    source_id = "consejo_transparencia_cl"
    kind = "event_list"
    url = "https://www.consejotransparencia.cl/feed/"
    country = "CL"
