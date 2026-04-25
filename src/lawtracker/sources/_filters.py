"""Canonical keyword filters used by adapters.

This is the single source of truth for the keyword regexes that decide
which entries from broad-topic feeds (law-firm blogs, news pages with
mixed crime types, etc.) make it into the scout. Centralized so Ellen
can review and tweak in one place without touching adapter code.

Each constant is a compiled `re.Pattern[str]` with `IGNORECASE`. Adapters
import what they need:

    from lawtracker.sources._filters import ANTI_CORRUPTION_EN
    class MyFirmAdapter(RssFeedAdapter):
        keyword_filter = ANTI_CORRUPTION_EN

To tighten or loosen a filter, edit the regex string here and rerun the
scout. To add a new language pack, add a new constant alongside the
English / Spanish ones below.
"""

import re

# English-language anti-corruption keyword set.
# Used by law-firm blogs and other broad-topic feeds.
# What it catches:
#   - FCPA, FEPA (US foreign-bribery statutes)
#   - foreign bribery / anti-bribery / anti-corruption / bribery
#   - kleptocracy, foreign official, public official
#   - cartel (added 2026-04-25 per Ellen — DOJ has been emphasizing
#     cartel-adjacent enforcement as part of its anti-corruption push)
#
# Edits 2026-04-25 from Ellen's review: removed AML / money laundering /
# OFAC / SDN / sanctions / ITAR / export controls. They're related
# compliance domains but pulled too much off-topic content from law-firm
# feeds. If signal-to-noise needs adjustment again, edit here.
ANTI_CORRUPTION_EN = re.compile(
    r"\b(?:"
    r"fcpa|fepa"
    r"|foreign\s+corrupt(?:\s+practices)?"
    r"|foreign\s+brib(?:e|ery|ing)"
    r"|anti-?brib(?:e|ery)"
    r"|anti-?corrupt(?:ion)?"
    r"|brib(?:e|ery|ing)"
    r"|kleptocracy"
    r"|foreign\s+official|public\s+official"
    r"|cartels?"
    r")\b",
    re.IGNORECASE,
)

# Spanish-language anti-corruption — used by Fiscalía Chile and any future
# Spanish-language source. Captures Chilean Ley 20.393 (corporate criminal
# liability), classic prosecutorial vocabulary, and adjacent financial-
# crime terms.
#   - cohecho (bribery), corrupción, soborno
#   - lavado de activos / lavado de dinero (money laundering)
#   - fraude al fisco (fraud against the state)
#   - delitos económicos (economic crimes — Chile's umbrella term)
#   - Ley 20.393 (corporate liability statute)
#   - funcionario público (public official)
# Event-noise exclusion regex.
# Drops items advertising conferences, webinars, podcasts, networking events,
# CLE webcasts, awards announcements, and the like — Ellen 2026-04-25 doesn't
# want these polluting the table or being summarized by the LLM. Applied at
# the SourceAdapter base class level, after parse() and before translation /
# LLM enrichment, so all adapters benefit.
#
# Matches in title or summary. Keep patterns specific enough that substantive
# policy speeches and "speech at conference" coverage aren't dropped — DOJ
# senior-official speeches, for example, mention conferences but the entry
# itself is policy content, not an ad. The patterns target the framing
# (registration, panel discussion, save the date) rather than the venue.
EVENT_NOISE = re.compile(
    r"\b(?:"
    r"webinar|webcast|teleseminar"
    r"|podcast(?:\s+(?:episode|series))?"
    r"|networking\s+(?:event|reception|lunch|breakfast|dinner|cocktail)"
    r"|speaking\s+engagement|panelist|panel\s+discussion|fireside\s+chat"
    r"|register\s+(?:now|today|here|at)|registration\s+(?:open|now)"
    r"|save\s+the\s+date"
    r"|cle\s+(?:credit|webcast|seminar|program|hour)"
    r"|continuing\s+legal\s+education"
    r"|workshop|roundtable|symposium"
    r"|seminario|webinario|charla\s+virtual"
    r")\b",
    re.IGNORECASE,
)


ANTI_CORRUPTION_ES = re.compile(
    r"\b(?:"
    r"cohecho"
    r"|corrupci[oó]n"
    r"|soborn(?:o|os)?"
    r"|lavado\s+de\s+activos"
    r"|lavado\s+de\s+dinero"
    r"|fraude\s+al\s+fisco"
    r"|delitos\s+econ[oó]micos"
    r"|ley\s*20\.?393"
    r"|funcionario\s+p[uú]blico"
    r")\b",
    re.IGNORECASE,
)
