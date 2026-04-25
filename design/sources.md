# LawTracker — Pilot source inventory

Status: widened 2026-04-25 from US-only to global. Pilot scope is **anti-corruption enforcement and compliance guidance across the United States, Australia, and Chile**, plus multilateral indexes and one curated aggregator. Statutes themselves are out of scope — Ellen needs enforcement and government messaging, not statutory text.

Each source has a kind: `document` (changes in place; hash + diff) or `event_list` (entries appear over time; new-entry detection). One Python module per source under `src/lawtracker/sources/`. Sources are organized below by the three categories settled with Tom on 2026-04-25.

URLs marked **(approximate)** were not verified during inventory drafting; the adapter implementer must confirm the exact path before wiring extraction. Spanish-language sources will need a corruption/cohecho/soborno keyword filter inside the adapter to limit emissions to anti-corruption content.

## Category 1 — Primary government agencies

### United States

1. **DOJ FCPA Resource Guide** (document) — joint DOJ/SEC compliance guidance; canonical interpretation document.
   - https://www.justice.gov/criminal/criminal-fraud/fcpa-resource-guide
2. **DOJ Corporate Enforcement Policy (JM 9-47.120)** (document) — voluntary self-disclosure / cooperation / remediation framework.
   - https://www.justice.gov/jm/jm-9-47000-foreign-corrupt-practices-act-1977
3. **DOJ Evaluation of Corporate Compliance Programs (ECCP)** (document) — DOJ's framework for evaluating compliance programs in enforcement decisions. PDF.
   - https://www.justice.gov/criminal-fraud/page/file/937501/download
4. **JM 9-28.000 — Principles of Federal Prosecution of Business Organizations** (document) — broader corporate-prosecution principles framing FCPA cases.
   - https://www.justice.gov/jm/jm-9-28000-principles-federal-prosecution-business-organizations
5. **DOJ FCPA enforcement actions — chronological list** (event_list) — DOJ's per-year list of cases. The landing page is a navigation hub (alphabetical + chronological year index), not a case list, so the adapter targets the **current-year subpage** directly. URL pattern is stable; the year in the path needs to roll over each January.
   - Adapter URL: https://www.justice.gov/criminal/criminal-fraud/case/related-enforcement-actions/2026 (current year)
   - Landing (navigation only): https://www.justice.gov/criminal-fraud/related-enforcement-actions
6. **SEC FCPA enforcement actions** (event_list) — SEC's enforcement-actions index for the FCPA Unit.
   - https://www.sec.gov/spotlight/fcpa/fcpa-cases.shtml
7. **DOJ FCPA Opinion Procedure releases** (event_list) — DOJ's formal opinion responses to industry inquiries.
   - https://www.justice.gov/criminal/criminal-fraud/foreign-corrupt-practices-act/opinion-procedure-releases
8. **DOJ press releases (FCPA-filtered)** (event_list) — RSS or topic-tagged feed; ranked lower than the curated enforcement list because of higher noise.
   - https://www.justice.gov/news (filter)
9. **DOJ senior-official speeches** (event_list) — AG, DAG, AAG-Criminal Division. Primary surface for enforcement-priority and strategy announcements.
   - https://www.justice.gov/speeches (filter to senior officials)

### Australia

10. **AFP foreign-bribery search** (event_list) — Australian Federal Police site search keyed on "foreign bribery". Captures media releases that mention foreign bribery in title / body. Discovery during build (2026-04-25): the general media-releases page (`/news-media/media-releases`) has zero foreign-bribery hits across 30 pages of recent releases — AFP's foreign-bribery cases are sparse and the topic-tagged landing only highlights ~4 unrelated fraud items. The site search is the only viable surface and currently returns ~12 historical media releases on page 0.
    - Adapter URL: https://www.afp.gov.au/search?keys=foreign+bribery
11. **CDPP case reports** (event_list) — Commonwealth Director of Public Prosecutions; prosecutorial-stage announcements. Often paired with AFP item above on the same case at different stages.
    - https://www.cdpp.gov.au/case-reports (filter to bribery / foreign bribery) **(approximate)**

### Chile

12. **Fiscalía Nacional — noticias nacionales** (event_list, Spanish) — Chile's national prosecutor; news/press section. Discovery during build (2026-04-25): the URL the original inventory listed (`/Fiscalia/sala_prensa`) is a 404; Fiscalía moved press to `/actualidad/noticias/nacionales`. Adapter applies a Spanish-language keyword filter (`cohecho`, `corrupci[oó]n`, `soborn`, `lavado`, `fraude al fisco`, `Ley 20.393`, `funcionario p[uú]blico`) over title + body so only anti-corruption-relevant items are emitted. Signal is sparse — most pages return zero matches — which is itself useful pilot signal.
    - Adapter URL: https://www.fiscaliadechile.cl/actualidad/noticias/nacionales
13. **Contraloría General de la República — dictámenes / pronunciamientos** (event_list, Spanish) — comptroller-general findings on public-administration compliance and corruption.
    - https://www.contraloria.cl **(approximate; specific section TBD)**
13a. **Consejo para la Transparencia (CPLT)** (event_list, Spanish, RSS) — Chilean Council for Transparency; oversees the access-to-information regime under Law 20.285. Built via `RssFeedAdapter` since it's a WordPress site with a clean RSS 2.0 feed. No keyword filter — outlet's whole beat is transparency / probity.
    - Adapter URL: https://www.consejotransparencia.cl/feed/

## Category 2 — Multilateral / cross-jurisdictional indexes

14. **OECD Working Group on Bribery — country evaluation reports** (document, low-frequency) — gold-standard assessments of OECD-member enforcement vigor against the OECD Anti-Bribery Convention. Years between reports per country, but extremely high signal for trend-watching. Pilot countries (US, Australia, Chile) are all OECD members.
    - https://www.oecd.org/corruption/anti-bribery (specific country-report index path **approximate**)
15. **World Bank sanctions / debarred firms list** (event_list) — debarments for fraud/corruption in World-Bank-financed projects; cross-jurisdictional.
    - https://www.worldbank.org/en/about/unit/sanctions-system/debarred-firms **(approximate)**

## Category 3 — Curated aggregator

16. **FCPA Blog** (event_list, RSS) — practitioner-focused aggregator covering global anti-corruption news despite the name. Single most efficient source for breadth across jurisdictions; free.
    - https://fcpablog.com  (RSS feed at https://fcpablog.com/feed/ **approximate**)
    - **BLOCKER (2026-04-25):** all candidate URLs (`/`, `/feed/`, `/rss`, `/feed.xml`, `/atom.xml`, `/blog/`, www subdomain) return HTTP 401 with a Cloudflare "you have been blocked" page even from a realistic Chrome User-Agent. The site appears to require auth or has hardened CDN bot protection. No adapter built in this round; revisit options at scout review (item 18) — possibilities: subscribe / acquire a credentialed feed, replace with a different aggregator (Harvard Anticorruption Blog, GIR if subscription is available), or scrape via a headless browser if the access is genuinely public from interactive sessions.
17. **Volkov Law — Corruption, Crime & Compliance blog** (event_list, RSS) — Michael Volkov's practitioner blog on FCPA / AML / sanctions. WordPress; standard RSS 2.0; English; multi-jurisdictional commentary so `country = None`. Built via `RssFeedAdapter`.
    - Adapter URL: https://blog.volkovlaw.com/feed/
18. **Gibson, Dunn & Crutcher — publications feed** (event_list, RSS, English) — major US law firm; `/feed/` returns ALL publications across practice areas, so `keyword_filter = ANTI_CORRUPTION_EN` keeps only FCPA / AML / sanctions items. **Intermittent**: served 200 to curl during fixture capture but Cloudflare returned 403 to httpx on a subsequent run. Production reliability would need a TLS-fingerprint-aware client (`curl_cffi`) or headless browser.
    - Adapter URL: https://www.gibsondunn.com/feed/
19. **Global Anticorruption Blog (GAB)** (event_list, RSS, English) — Matthew Stephenson at Harvard Law School. Academic, single-topic, multi-jurisdictional. No keyword filter — every post is on-topic. Built via `RssFeedAdapter`.
    - Adapter URL: https://globalanticorruptionblog.com/feed/

20. **Miller & Chevalier — FCPA & International Anti-Corruption practice search** (event_list, HTML, English) — Drupal-driven `/search` endpoint accepting filter parameters that pin results to the FCPA practice area (`related_practice=8965`). Adapter fetches three content types per poll (publications, news, events) by overriding `urls`. Publications are the Winter / Spring / Summer / Autumn FCPA Reviews Tom flagged; news is media mentions; events are speaking engagements.
    - Adapter URL (publications): https://www.millerchevalier.com/search?search_term=&related_practice=8965&...&content_types%5B0%5D=publication
    - **Live access intermittent**: returns 200 to curl during fixture capture but 403 to httpx (Cloudflare appears to fingerprint TLS, not just User-Agent). Same failure mode as Gibson Dunn. Reliable production access needs `curl_cffi`, Playwright, or a manual fixture refresh process.

### Law-firm feeds that could not be added (audited 2026-04-25)

These firms appeared in `possibleSources.txt` but offered no usable RSS from this environment:

- **404 / no exposed RSS feed**: WilmerHale, Paul Weiss, Latham & Watkins, Cleary Gottlieb, Hogan Lovells, Freshfields, Allens, Clayton Utz, King & Wood Mallesons (HTML, not RSS), Gilbert + Tobin (HTML, not RSS), A&O Shearman, King & Spalding. Many of these probably have HTML practice-area / search pages that work like Miller & Chevalier's — Tom found M&C's by clicking around the site. Pattern is per-firm investigation, not RSS-blanket; defer until item 18 surfaces which firms are worth the effort.
- **CDN bot block (HTTP 403, even with browser UA)**: Sidley, Skadden, Debevoise, Dentons, Herbert Smith Freehills, Foley LLP, Foley Hoag, Covington & Burling, Ropes & Gray, Harvard CorpGov Forum. **Same TLS-fingerprint block** that affects Miller & Chevalier and Gibson Dunn intermittently.
- **Rate-limited (HTTP 429)**: DLA Piper.
- **JS-rendered (no inline data)**: ASIC.

Three concrete paths to unblock the CDN-fingerprinted set (Tom decides at item 18):

1. **`curl_cffi` runtime dep** — drop-in httpx replacement that mimics curl's TLS fingerprint. Beats Cloudflare's JA3 hash matching. ~1 hour to swap. New runtime dependency.
2. **Headless browser (Playwright)** — beats both Cloudflare and JS-rendered sites (ASIC). ~half-day setup. Adds Chromium dep.
3. **Email-subscription parsing** — most firms publish via mailing list; ingest forwarded mail. Operational work, no scraping fragility.

## Out of scope — pilot

- The FCPA statute itself (15 U.S.C. §§ 78dd-1 et seq.), FEPA (18 U.S.C. § 1352), Australia's Criminal Code Division 70 (foreign bribery), and Chile's Ley 20.393 (corporate criminal liability). Statutory text changes are not Ellen's signal.
- Domestic bribery (18 U.S.C. § 201), honest-services fraud, AML Act / Corporate Transparency Act, Magnitsky / OFAC SDN updates. File future ROADMAP items if the pilot expands.
- Other jurisdictions with active anti-corruption enforcement: UK (SFO, FCA), France (PNF, AFA), Germany (state-level prosecutors), Brazil (MPF, CGU), Switzerland (OAG), Netherlands (OM, FIOD), Italy (ANAC, Milan/Rome prosecutors), Singapore (CPIB), Hong Kong (ICAC). These are the priority post-pilot expansions — see architecture note's "Future scope" list.
- Paid aggregators (Global Investigations Review). High signal but subscription-gated; pilot stays free.
- Law-firm client alerts (Latham, Skadden, Gibson Dunn, Cleary, Debevoise, WilmerHale, Hogan Lovells, Freshfields). Will arrive with item 15 once Tom finalizes the approved list.

## Implementation order

When the source-adapter framework lands (item 3), build it against **source #5 (DOJ FCPA enforcement actions list)** as the anchor adapter — well-structured English-language government primary source, validates the `event_list` shape end to end. Subsequent adapters in priority order:

1. **Source 16 (FCPA Blog)** — proves the RSS / aggregator pattern, low effort, gives global coverage immediately.
2. **Source 10 (AFP)** — proves non-US English-language event_list against an agency site.
3. **Source 12 (Fiscalía Chile)** — proves Spanish-language extraction with keyword filtering.
4. **Sources 6–9** — fill out US event_list coverage (SEC, DOJ press releases, opinion procedure, senior speeches).
5. **Sources 11, 13, 15** — CDPP, Contraloría, World Bank sanctions.
6. **Source 14 (OECD WGB)** — document-kind once item 4 (storage + change detection) is in.
7. **Sources 1–4** — US document-kind compliance guidance (Resource Guide, JM 9-47.120, ECCP, JM 9-28.000), once the document path is proven.

## Future — expansion candidates

When the pilot proves out, the adapter framework absorbs additional sources without schema change:

- Per-jurisdiction: UK SFO + FCA, French PNF + AFA, German state prosecutors, Brazilian MPF + CGU, Swiss OAG, Dutch OM + FIOD, Italian ANAC, Singapore CPIB, Hong Kong ICAC, Australian ASIC.
- Paid: Global Investigations Review (subscription).
- Law-firm alerts: Tom's approved list — file as item 15.
- Academic: Stanford FCPA Clearinghouse, Harvard Anticorruption Blog.

When ready, file each as a separate ROADMAP item rather than appending here — keeping pilot vs. expansion separate makes scope creep visible.
