# LawTracker — Pilot source inventory

Status: widened 2026-04-25 from US-only to global. Pilot scope is **anti-corruption enforcement and compliance guidance across the United States, Australia, and Chile**, plus multilateral indexes and one curated aggregator. Statutes themselves are out of scope — Ellen needs enforcement and government messaging, not statutory text.

Each source has a kind: `document` (changes in place; hash + diff) or `event_list` (entries appear over time; new-entry detection). One Python module per source under `src/lawtracker/sources/`.

Sources marked `[x]` are live in the scout (verify with `py -m lawtracker scout`). `[ ]` are deferred, blocked, or pending. **Source numbers are stable — never renumber** — they're referenced throughout the codebase, ROADMAP, and design notes (e.g. `Source 16 (FCPA Blog)`).

URLs marked **(approximate)** were not verified during inventory drafting; the adapter implementer must confirm the exact path before wiring extraction. Spanish-language sources need a corruption / cohecho / soborno keyword filter inside the adapter to limit emissions to anti-corruption content.

## Onboarding progress (as of 2026-04-28)

**11 of 23 sources onboarded.**

| Category | Onboarded | Total |
|---|---|---|
| Primary government — United States | 2 | 9 |
| Primary government — Australia | 1 | 2 |
| Primary government — Chile | 2 | 3 |
| Multilateral / cross-jurisdictional | 0 | 2 |
| Curated aggregator + practitioner blogs | 6 | 7 |
| **Total** | **11** | **23** |

Most outstanding sources are deferred — `document`-kind sources (1–4, 14) wait on item 4 (storage + change detection); blocked sources (16 FCPA Blog, plus several law firms) wait on a `curl_cffi` / Playwright / email-subscription decision at item 18 review.

## Category 1 — Primary government agencies

### United States (2 of 9 onboarded)

- [ ] **1. DOJ FCPA Resource Guide** — `document`. Joint DOJ/SEC compliance guidance; canonical interpretation document. Deferred until item 4 (storage + change detection) lands.
  - https://www.justice.gov/criminal/criminal-fraud/fcpa-resource-guide

- [ ] **2. DOJ Corporate Enforcement Policy (JM 9-47.120)** — `document`. Voluntary self-disclosure / cooperation / remediation framework.
  - https://www.justice.gov/jm/jm-9-47000-foreign-corrupt-practices-act-1977

- [ ] **3. DOJ Evaluation of Corporate Compliance Programs (ECCP)** — `document`. DOJ's framework for evaluating compliance programs in enforcement decisions. PDF.
  - https://www.justice.gov/criminal-fraud/page/file/937501/download

- [ ] **4. JM 9-28.000 — Principles of Federal Prosecution of Business Organizations** — `document`. Broader corporate-prosecution principles framing FCPA cases.
  - https://www.justice.gov/jm/jm-9-28000-principles-federal-prosecution-business-organizations

- [x] **5. DOJ FCPA enforcement actions — chronological list** — `event_list`. Anchor adapter for the framework; live with link-following enrichment that pulls `industry`, `defendant`, `defendant_type`, `penalty_usd`, `disgorgement_usd`, `resolution_type` from each press-release page. Historical-year support iterates 24 months back.
  - Adapter URL: https://www.justice.gov/criminal/criminal-fraud/case/related-enforcement-actions/2026 (current year; rolls over each January)
  - Landing (navigation only): https://www.justice.gov/criminal-fraud/related-enforcement-actions
  - Adapter: `src/lawtracker/sources/doj_fcpa_actions.py`

- [x] **6. SEC FCPA enforcement actions** — `event_list`, LLM-extracted. SEC's enforcement-actions index for the FCPA Unit. The page is a single long narrative — year headers + bolded company names + free-text paragraphs — so Claude reads it and emits structured `EventRecord`s for the most recent 1-2 years (Ellen's slice).
  - https://www.sec.gov/spotlight/fcpa/fcpa-cases.shtml
  - Adapter: `src/lawtracker/sources/sec_fcpa_cases.py`

- [ ] **7. DOJ FCPA Opinion Procedure releases** — `event_list`. DOJ's formal opinion responses to industry inquiries.
  - https://www.justice.gov/criminal/criminal-fraud/foreign-corrupt-practices-act/opinion-procedure-releases

- [ ] **8. DOJ press releases (FCPA-filtered)** — `event_list`. RSS or topic-tagged feed; ranked lower than the curated enforcement list because of higher noise.
  - https://www.justice.gov/news (filter)

- [ ] **9. DOJ senior-official speeches** — `event_list`. AG, DAG, AAG-Criminal Division. Primary surface for enforcement-priority and strategy announcements.
  - https://www.justice.gov/speeches (filter to senior officials)

### Australia (1 of 2 onboarded)

- [x] **10. AFP foreign-bribery search** — `event_list`. Australian Federal Police site search keyed on "foreign bribery". Captures media releases that mention foreign bribery in title / body. Discovery during build (2026-04-25): the general media-releases page had zero foreign-bribery hits across 30 pages — AFP's foreign-bribery cases are sparse and the topic-tagged landing only highlights ~4 unrelated fraud items. The site search is the only viable surface.
  - Adapter URL: https://www.afp.gov.au/search?keys=foreign+bribery
  - Adapter: `src/lawtracker/sources/afp_foreign_bribery.py`

- [ ] **11. CDPP case reports** — `event_list`. Commonwealth Director of Public Prosecutions; prosecutorial-stage announcements. Often paired with AFP item above on the same case at different stages. **Blocked**: timeout from this dev environment, likely AU geo-block. Revisit at item 18 review.
  - https://www.cdpp.gov.au/case-reports (filter to bribery / foreign bribery) **(approximate)**

### Chile (2 of 3 onboarded)

- [x] **12. Fiscalía Nacional — noticias nacionales** — `event_list`, Spanish. Chile's national prosecutor; news/press section. Discovery during build (2026-04-25): the URL the original inventory listed (`/Fiscalia/sala_prensa`) was 404; Fiscalía moved press to `/actualidad/noticias/nacionales`. Adapter applies a Spanish-language keyword filter (`cohecho`, `corrupci[oó]n`, `soborn`, `lavado`, `fraude al fisco`, `Ley 20.393`, `funcionario p[uú]blico`) over title + body so only anti-corruption-relevant items are emitted. Signal is sparse — most pages return zero matches — which is itself useful pilot signal.
  - Adapter URL: https://www.fiscaliadechile.cl/actualidad/noticias/nacionales
  - Adapter: `src/lawtracker/sources/fiscalia_chile.py`

- [ ] **13. Contraloría General de la República — dictámenes / pronunciamientos** — `event_list`, Spanish. Comptroller-general findings on public-administration compliance and corruption.
  - https://www.contraloria.cl **(approximate; specific section TBD)**

- [x] **13a. Consejo para la Transparencia (CPLT)** — `event_list`, Spanish, RSS. Chilean Council for Transparency; oversees the access-to-information regime under Law 20.285. Built via `RssFeedAdapter` since it's a WordPress site with a clean RSS 2.0 feed. No keyword filter — outlet's whole beat is transparency / probity.
  - Adapter URL: https://www.consejotransparencia.cl/feed/
  - Adapter: `src/lawtracker/sources/consejo_transparencia_cl.py`

## Category 2 — Multilateral / cross-jurisdictional indexes (0 of 2 onboarded)

- [ ] **14. OECD Working Group on Bribery — country evaluation reports** — `document`, low-frequency. Gold-standard assessments of OECD-member enforcement vigor against the OECD Anti-Bribery Convention. Years between reports per country, but extremely high signal for trend-watching. Pilot countries (US, Australia, Chile) are all OECD members. **Blocked**: CDN 403. Revisit with `curl_cffi` / Playwright at item 18.
  - https://www.oecd.org/corruption/anti-bribery (specific country-report index path **approximate**)

- [ ] **15. World Bank sanctions / debarred firms list** — `event_list`. Debarments for fraud/corruption in World-Bank-financed projects; cross-jurisdictional.
  - https://www.worldbank.org/en/about/unit/sanctions-system/debarred-firms **(approximate)**

## Category 3 — Curated aggregator + practitioner blogs (6 of 7 onboarded)

- [ ] **16. FCPA Blog** — `event_list`, RSS. Practitioner-focused aggregator covering global anti-corruption news despite the name. Single most efficient source for breadth across jurisdictions; free. **Blocked (2026-04-25):** all candidate URLs (`/`, `/feed/`, `/rss`, `/feed.xml`, `/atom.xml`, `/blog/`, www subdomain) return HTTP 401 with a Cloudflare "you have been blocked" page even from a realistic Chrome User-Agent. The site appears to require auth or has hardened CDN bot protection. Options: subscribe / acquire a credentialed feed, swap with a different aggregator (Harvard Anticorruption Blog, GIR if subscription is available), or scrape via headless browser.
  - https://fcpablog.com  (RSS feed at https://fcpablog.com/feed/ **approximate**)

- [x] **17. Volkov Law — Corruption, Crime & Compliance blog** — `event_list`, RSS. Michael Volkov's practitioner blog on FCPA / AML / sanctions. WordPress; standard RSS 2.0; English; multi-jurisdictional commentary so `country = None` (the LLM derives effective country from event text during analysis).
  - Adapter URL: https://blog.volkovlaw.com/feed/
  - Adapter: `src/lawtracker/sources/volkov_law.py`

- [x] **18. Gibson, Dunn & Crutcher — publications feed** — `event_list`, RSS, English. Major US law firm; `/feed/` returns ALL publications across practice areas, so `keyword_filter = ANTI_CORRUPTION_EN` keeps only FCPA / AML / sanctions items. Cloudflare TLS-fingerprint block bypassed via `use_curl_cffi = True`.
  - Adapter URL: https://www.gibsondunn.com/feed/
  - Adapter: `src/lawtracker/sources/gibson_dunn.py`

- [x] **19. Global Anticorruption Blog (GAB)** — `event_list`, RSS, English. Matthew Stephenson at Harvard Law School. Academic, single-topic, multi-jurisdictional. No keyword filter — every post is on-topic.
  - Adapter URL: https://globalanticorruptionblog.com/feed/
  - Adapter: `src/lawtracker/sources/global_anticorruption_blog.py`

- [x] **20. Miller & Chevalier — FCPA & International Anti-Corruption practice search** — `event_list`, HTML, English. Drupal-driven `/search` endpoint accepting filter parameters that pin results to the FCPA practice area (`related_practice=8965`). Adapter fetches three content types per poll (publications, news, events) by overriding `urls`. Publications include the Winter / Spring / Summer / Autumn FCPA Reviews; news is media mentions; events are speaking engagements. `use_curl_cffi = True` (Cloudflare).
  - Adapter URL (publications): https://www.millerchevalier.com/search?search_term=&related_practice=8965&...&content_types%5B0%5D=publication
  - Adapter: `src/lawtracker/sources/miller_chevalier.py`

- [x] **21. Foley & Lardner LLP — publications RSS** — `event_list`, RSS, English. Major US firm with a mixed-topic `/feed/`; adapter applies `ANTI_CORRUPTION_EN` to keep only FCPA / AML / sanctions items. `use_curl_cffi = True`.
  - Adapter URL: https://www.foley.com/feed/
  - Adapter: `src/lawtracker/sources/foley_llp.py`

- [x] **22. Harvard Law School Forum on Corporate Governance — FCPA tag** — `event_list`, RSS, English. Academic / commentary outlet, FCPA-tag-restricted feed so single-topic (no filter). `use_curl_cffi = True`. Volume is low (commentary, not a case feed).
  - Adapter URL: https://corpgov.law.harvard.edu/category/foreign-corrupt-practices-act/feed/
  - Adapter: `src/lawtracker/sources/harvard_corpgov_fcpa.py`

### Law-firm feeds that could not be added (audited 2026-04-25)

These firms appeared in `possibleSources.txt` but offered no usable RSS from this environment:

- **404 / no exposed RSS feed**: WilmerHale, Paul Weiss, Latham & Watkins, Cleary Gottlieb, Hogan Lovells, Freshfields, Allens, Clayton Utz, King & Wood Mallesons (HTML, not RSS), Gilbert + Tobin (HTML, not RSS), A&O Shearman, King & Spalding. Many probably have HTML practice-area / search pages that work like Miller & Chevalier's; per-firm investigation, not RSS-blanket. Defer until item 18 surfaces which firms are worth the effort.
- **CDN bot block (HTTP 403, even with browser UA)**: Sidley, Skadden, Debevoise, Dentons, Herbert Smith Freehills, Foley LLP, Foley Hoag, Covington & Burling, Ropes & Gray, Harvard CorpGov Forum. Same TLS-fingerprint block that affects Miller & Chevalier and Gibson Dunn intermittently; `curl_cffi` unblocked some (Foley, Harvard CorpGov, Miller & Chevalier, Gibson Dunn) but not all.
- **Rate-limited (HTTP 429)**: DLA Piper.
- **JS-rendered (no inline data)**: ASIC.

Three concrete paths to unblock the CDN-fingerprinted set (Tom decides at item 18):

1. **`curl_cffi` runtime dep** — drop-in httpx replacement that mimics curl's TLS fingerprint. Beats Cloudflare's JA3 hash matching. ~1 hour to swap. New runtime dependency. Already adopted for sources 18, 20, 21, 22.
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
