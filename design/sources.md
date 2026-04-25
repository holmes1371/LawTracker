# LawTracker — Pilot source inventory

Status: locked 2026-04-25 with Tom's approval. Pilot scope is **US anti-corruption enforcement and compliance guidance**, with FCPA and FEPA as priority subject matter. Statutes themselves are out of scope — Ellen needs enforcement and government messaging, not statutory text.

Each source has a kind: `document` (changes in place; hash + diff) or `event_list` (entries appear over time; new-entry detection). One Python module per source under `src/lawtracker/sources/`.

## Compliance and enforcement guidance — *document* sources

Change rarely; each change is high-signal. Hash + diff on each poll.

1. **DOJ FCPA Resource Guide** — joint DOJ/SEC compliance guidance, the canonical interpretation document.
   - https://www.justice.gov/criminal/criminal-fraud/fcpa-resource-guide
2. **DOJ Corporate Enforcement Policy (JM 9-47.120)** — voluntary self-disclosure / cooperation / remediation framework.
   - https://www.justice.gov/jm/jm-9-47000-foreign-corrupt-practices-act-1977
3. **DOJ Evaluation of Corporate Compliance Programs (ECCP)** — DOJ's framework for evaluating compliance programs in enforcement decisions.
   - https://www.justice.gov/criminal-fraud/page/file/937501/download
4. **JM 9-28.000 — Principles of Federal Prosecution of Business Organizations** — the broader corporate-prosecution principles that frame FCPA cases.
   - https://www.justice.gov/jm/jm-9-28000-principles-federal-prosecution-business-organizations

## Enforcement and messaging — *event_list* sources

Steady stream. New-entry detection on each poll.

5. **DOJ FCPA enforcement actions list** — DOJ's curated list of cases.
   - https://www.justice.gov/criminal/criminal-fraud/related-enforcement-actions
6. **SEC FCPA enforcement actions** — SEC's enforcement-actions index for the FCPA Unit.
   - https://www.sec.gov/spotlight/fcpa/fcpa-cases.shtml
7. **DOJ FCPA Opinion Procedure releases** — DOJ's formal opinion responses to industry inquiries.
   - https://www.justice.gov/criminal/criminal-fraud/foreign-corrupt-practices-act/opinion-procedure-releases
8. **DOJ press releases (FCPA-filtered)** — RSS or topic-tagged feed; ranked lower than the curated enforcement list because of higher noise.
   - https://www.justice.gov/news (filter)
9. **DOJ senior-official speeches** — AG, DAG, AAG-Criminal Division. Primary surface for enforcement-priority and strategy announcements.
   - https://www.justice.gov/speeches (filter to senior officials)

## Out of scope — pilot

- The FCPA statute itself (15 U.S.C. §§ 78dd-1 et seq.) and the FEPA statute (18 U.S.C. § 1352). Statutory text changes are not Ellen's signal.
- Domestic bribery (18 U.S.C. § 201), honest-services fraud, AML Act / Corporate Transparency Act, Magnitsky / OFAC SDN updates. File future ROADMAP items if the pilot expands.
- Non-US jurisdictions (UK Bribery Act, EU directives, OECD anti-bribery work).

## Future — trusted third-party sources

Tom plans to provide an approved list — large law-firm client-alert pages, FCPA Blog, Stanford FCPA Clearinghouse, etc. The adapter framework is built so these slot in as additional `event_list` (or `document`) sources without schema changes.

When the list arrives, file as a separate ROADMAP item rather than appending here — keeping pilot vs. expansion separate makes scope creep visible.

## Implementation order

When the source-adapter framework lands (item 3), build it against **source #5 (DOJ FCPA enforcement actions list)** as the anchor adapter — single highest-signal source for Ellen, and exercises the `event_list` shape end to end. Items 6–9 follow with the same shape; items 1–4 (`document` shape) come after the event-list pattern is proven.
