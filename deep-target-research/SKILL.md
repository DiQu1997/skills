---
name: deep-target-research
description: >
  Decision-grade deep research and intelligence profiling on any target — person, institution,
  policy, technology, or geopolitical actor. Produces analytical reports with source references,
  contradiction mapping, forward-projection scenarios, and a persistent JSON dossier for
  longitudinal tracking and cross-referencing. Trigger whenever the user asks to "deeply research",
  "profile", "investigate", "deep dive on", "intelligence brief on", "understand who someone is",
  "what someone believes", "map connections", "find controversies", "analyze track record", or
  any multi-source synthesis beyond surface summary. NOT for quick lookups or simple bios. If the
  user says "do deep research on X" or "I need to understand X for decisions", always trigger.
---

# Deep Target Research

Multi-phase intelligence research system. Produces decision-grade analytical profiles
with source references, bias awareness, and actionable forward projections.

## When to Read Reference Files

Before starting research, read the relevant reference file:
- **All targets**: Read `references/methodology.md` for the full technique library
- **Deep investigation**: Read `references/primary_sources.md` for structured database protocols,
  target-type investigation playbooks, and analytical techniques (court records, SEC filings,
  corporate ownership, political donations, licensing records, international records)
- **Dossier output**: Read `references/dossier_schema.md` for the structured profile format
- **Person targets**: Pay special attention to Phases 3 (Network) and 4 (Opposition)
- **Institution/policy targets**: Emphasize Phases 2 (Substance) and 5 (Strongest Case)
- **Geopolitical targets**: Emphasize Phases 3 (Network) and 6 (Controversy Deep-Dive)

## Core Principle

**This is analysis, not summary.** Every factual section must have a companion analytical
block that asks: "What does this pattern reveal?" The output must surface contradictions,
map incentive structures, and project forward — not just retell a timeline.

## High-Level Workflow

```
Phase 0: REQUEST DECOMPOSITION      → Break request into analytical dimensions
Phase 1: FOUNDATION                 → Biographical/factual skeleton
Phase 2: INTELLECTUAL SUBSTANCE     → Positions, evolution, framework
Phase 3: NETWORK / POWER MAP        → Connections, incentives, conflicts
Phase 4: OPPOSITION                 → Strongest critics, substantive critiques
Phase 5: TARGET'S STRONGEST CASE    → Best arguments in their own voice
Phase 6: CONTROVERSY DEEP-DIVES     → Factual verification of every major controversy
Phase 7: ADVERSARIAL VERIFICATION   → Deliberately try to disprove your emerging thesis
Phase 8: SYNTHESIS & WRITING        → Central insight, contradiction map, scenarios
Phase 9: DELIVERY (DUAL OUTPUT)     → Analytical report (.md) + Dossier profile (.json)
```

---

## Research Depth Principles

There are **no hard limits** on the number of searches or fetches. The right amount of research
is determined by information gain, not by a counter. Follow these principles:

- **Phases are not single-pass.** If a phase surfaces new leads — names, events, documents,
  connections — follow them. A Phase 1 discovery may send you back to Phase 3 for a new
  relationship search. This is expected, not a failure.
- **Always read full text of valuable sources.** Search snippets are 200-500 words; full
  articles are 1,500-5,000 words. The information loss from snippet-only research is 70-90%.
  If a source is worth citing in the final report, it is worth fetching and reading in full.
- **Verify from multiple independent sources.** Every major factual claim in the final report
  should be corroborated by at least 2-3 independent sources. Single-source claims must be
  flagged as such.
- **Stop a phase when searches yield diminishing returns** — when two consecutive searches
  produce no new substantive information beyond what you already have. Do not stop because
  you hit an arbitrary number.
- **When in doubt, go deeper.** Shallow research with false confidence is worse than thorough
  research that honestly maps what is known and unknown. A decision-maker reading your report
  is relying on its completeness.

---

## Structured Records Intelligence

Web search tells you what **other people say** about the target. Primary source investigation
reveals what the target has **actually done** — in their own filings, legal record, financial
transactions, and corporate structures. This layer is more neutral, more revealing, and harder
to spin. **Every deep research run must include structured records, not just articles.**

See `references/primary_sources.md` for the full database-by-database guide with URLs, search
queries, and per-target-type investigation playbooks.

### Intelligence Domains

| Domain | What It Reveals | Key Sources |
|--------|----------------|-------------|
| **Legal & Court** | Lawsuits, judgments, enforcement actions, disciplinary history | PACER, CourtListener, SEC enforcement, FINRA BrokerCheck, state bar records |
| **Financial & SEC** | Insider trades, compensation, related-party deals, ownership stakes | SEC EDGAR (10-K, DEF 14A, Form 4, 13F, 13D), Form ADV |
| **Corporate Ownership** | Entity webs, shell companies, shared agents/addresses, hidden interests | State Secretary of State registries, OpenCorporates, UCC filings, property records |
| **Political & Lobbying** | Donation patterns, access-buying, revolving door, lobbying priorities | FEC, OpenSecrets, Senate lobbying disclosures, FollowTheMoney |
| **Professional & Academic** | Credentials verification, publication record, patent portfolio, peer standing | Google Scholar, USPTO/Google Patents, state licensing boards, Retraction Watch |
| **International** | Offshore structures, sanctions exposure, cross-border activity | ICIJ Offshore Leaks, OFAC/EU/UN sanctions lists, Companies House (UK), foreign registries |

### Cross-Cutting Analytical Techniques

Apply these across all phases when structured records are available:

- **Follow the Money**: Trace capital flow — where does income come from, where does money go,
  does the flow tell a different story than the public narrative?
- **Timeline Juxtaposition**: Place primary source events (Form 4 trades, lawsuit filings,
  entity creation dates) on the same timeline as public statements. Gaps between words and
  actions that articles miss become visible.
- **Entity Web Mapping**: Start with known entities, look up registered agents and addresses,
  search for OTHER entities at the same address/agent. Reveals connections not publicly
  associated with the target.
- **Absence Detection**: What's MISSING is often the most revealing finding — a financial
  professional with no FINRA record, a scholar with no citations, a government official
  whose disclosure is late, a company that claims expertise with no patents.

---

## Phase 0: Request Decomposition

Before any search, decompose the request into **analytical dimensions**.

### Dimensional Checklist

| Dimension | Question | Output Type |
|-----------|----------|-------------|
| Biography/Facts | Who/what is this? Timeline? | Chronological skeleton |
| Intellectual Framework | What do they believe? How has it evolved? | Idea map with timestamps |
| Network/Power | Who are they connected to? Incentive structures? | Relationship graph |
| Track Record | When right? When wrong? | Prediction audit |
| Personality/Character | What behavioral patterns across contexts? | Contradiction map |
| Controversy | What do strongest critics say? | Steel-manned opposition |
| Forward Projection | What does the pattern predict? | Scenario framework |

### Define Output Spec

Before researching, establish what makes the output decision-grade:
- Every claim should be **falsifiable** and testable against evidence
- Every statement/position change must be **dated**
- Every action must have a **motivation mapping** (what incentive explains this?)
- Contradictions must be **explicitly surfaced**, not smoothed into coherent narrative
- **Known unknowns** must be registered (what can't we find?)

---

## Phase 1: Foundation Layer

### Search Design
```
Query: "[Target name] biography background history"
```
Keep it broad. The goal is to:
- Establish the complete arc (career phases, key dates)
- Identify which events are most discussed (frequency = importance)
- Discover the **vocabulary** sources use (seeds future searches)
- Map the **source ecosystem** (which outlets cover this target, from what angles)

### Source Triage
Classify every source found:

| Type | Trust for Facts | Trust for Analysis |
|------|----------------|-------------------|
| Institutional bio (employer, org) | High | Low (self-serving) |
| Encyclopedia (Wikipedia, Britannica) | Medium (check citations) | Low |
| Quality journalism (WSJ, FT, NYT) | Medium-High | Medium-High |
| Think tank / policy analysis | Medium | High (but check lean) |
| Biography sites / tabloids | Low | Very Low |

### Extraction Protocol
From foundation sources, extract and timestamp:
- Career phases with exact dates
- Key relationships mentioned (names → future search targets)
- Self-descriptions / self-framing quotes
- Controversy flags (anything mentioned as criticism, even briefly)
- Vocabulary inventory (recurring phrases → the target's own language)

### Records to Query
After initial web searches, check structured databases to verify and extend the foundation:
- **Corporate registries** — search state Secretary of State databases for entities where
  target is listed as officer, director, or registered agent
- **Professional licensing** — verify claimed credentials via state licensing boards, bar
  associations, FINRA BrokerCheck, medical boards
- **Academic records** — check Google Scholar / Semantic Scholar for publication record;
  verify claimed degrees and affiliations
- **Property records** — county assessor databases for real estate holdings (reveals
  lifestyle and wealth indicators independent of self-reporting)

---

## Phase 2: Intellectual Substance

### Search Design
```
Query: "[Target name] [core policy domain] views criticism analysis"
```
Including evaluative terms ("criticism", "views", "analysis") pulls analytical sources.

### Position Evolution Mapping
For any target with a public record, build a timestamped position tracker:
```
[Date]: [Position stated] — [Context/audience] — [Political environment]
```
Then overlay political/institutional context to check for correlation patterns.

### Idea Decomposition
For each major position, break into:
1. **Premise** — what must be true for the argument to hold
2. **Logic** — the inferential chain
3. **Prediction** — what it implies about the future
4. **Testability** — how we would know if it's right or wrong

---

## Phase 3: Network / Power Map

### Search Design
```
Query: "[Target name] [key relationship] connections controversy"
```

### Relationship Protocol
For each discovered relationship, document:
- **Nature**: Family / Patron / Mentor / Business partner / Political ally
- **Duration**: How long, through what phases
- **Power dynamic**: Who needs whom more
- **Relevance to role**: How does this connection affect their current position
- **Incentive alignment**: Do their interests converge or diverge

### Records to Query
- **DEF 14A proxy filings** — board interlocks: does the target sit on boards with the same
  people across multiple companies? Cross-reference directors across filings.
- **Corporate registries** — search for entities where both the target and the connected person
  appear as officers/directors. Shared registered agents or addresses signal hidden connections.
- **FEC donation records** — donation clustering: do the target and their connections donate
  to the same candidates/PACs? Reveals coordinated political influence.
- **IRS 990 filings** — overlapping nonprofit boards: do the same people appear across the
  target's for-profit and nonprofit entities?
- **OpenSecrets revolving door** — did connections move between government and the target's industry?

---

## Phase 4: Opposition Layer

### Search Design (two searches recommended)
```
Search A: "[Target name] [role/appointment context] criticism controversy"
Search B: "[Target name] 'case against' qualifications [domain] criticism"
```
Separate **contextual criticism** (political framing) from **substantive criticism** (competence).

### Criticism Taxonomy
Classify every criticism:

| Type | Weight | Example |
|------|--------|---------|
| Credential-based | High | "Lacks formal training in X" |
| Track record-based | High | "Was wrong about Y in [year]" |
| Motivation-based | Medium | "Changes positions with political winds" |
| Connection-based | Medium | "Appointed due to family ties" |
| Partisan | Low | "Chosen by [disliked politician]" |
| Ad hominem | Very Low | Personal attacks without substance |

### Steel-Manning Protocol
For each major criticism, construct the **strongest possible version**:
- Weak: "[Target] is unqualified because no PhD"
- Steel-manned: "[Target] would be the Nth consecutive holder without formal training in
  [domain], at a time when [specific challenges] require [specific expertise]. Historical
  comparison shows [data about predecessors' qualifications vs outcomes]."

### Records to Query
- **Court records** — search CourtListener / PACER for lawsuits where target is defendant;
  state court systems for civil litigation. Pattern of lawsuits reveals systematic issues.
- **SEC enforcement** — search SEC AAER database and enforcement actions for target name
- **FINRA BrokerCheck** — for financial professionals: disciplinary history, customer complaints,
  regulatory actions (this is often the single most revealing source for finance targets)
- **State licensing boards** — bar disciplinary records for attorneys, medical board actions
  for physicians, CPA board actions for accountants
- **ICIJ Offshore Leaks** — search for target name in Panama/Paradise/Pandora Papers databases

---

## Phase 5: Target's Strongest Case

### Search Design
```
Query: "[Target name] [their key concept/speech title] [domain] independence"
```
Find the target's most-cited original intellectual contributions.

### Fairness Requirement
You MUST hear the target at their intellectual best before finalizing analysis.
Third-party summaries introduce interpretation drift. If possible, use `web_fetch`
to retrieve full text of key speeches, op-eds, or reports.

---

## Phase 6: Controversy Deep-Dives

Investigate **every** HIGH-severity controversy identified so far, and any MEDIUM controversy
that could shift the central insight. Each controversy gets its own dedicated search-and-verify
cycle — do not bundle them into a single search.

### Search Design (per controversy)
```
Query: "[Target name] [specific incident] [specific factual claim to verify]"
```
For each controversy, seek:
- Primary documentation (official records, transcripts, audits)
- Timeline precision (exact dates)
- Multi-source corroboration (≥3 independent sources for key claims)
- Both sides of the dispute — who made the allegation, who defended, what evidence exists

Continue searching each controversy until you can construct a precise timeline with
corroborated facts, or until you've exhausted available sources and can honestly state
what remains unknown.

### Records to Query (per controversy)
- **Court filings** — fetch the actual complaint, opinion, or settlement document, not just
  articles about them. Court filings contain specific allegations, dates, and evidence that
  journalism summarizes and often simplifies.
- **SEC filings contemporaneous with the controversy** — what was filed in the same time period?
  8-K filings, 10-Q risk disclosures, or proxy amendments may reveal internal awareness.
- **Form 4 insider trades** — apply Timeline Juxtaposition: did the target or insiders trade
  stock around the controversy dates? Selling before bad news is a strong signal.
- **Financial disclosures** — for government officials, were disclosures filed on time? Were
  assets added or removed around the controversy period?
- **Government records** — IG reports, FOIA releases, congressional hearing transcripts
  related to the specific controversy

---

## Phase 7: Adversarial Verification

Before writing the report, deliberately try to **disprove your emerging thesis**.

### Method
1. State your central insight as a falsifiable claim
2. Design search queries specifically intended to find counter-evidence
3. Execute them — search for the strongest case against your own analysis
4. If strong counter-evidence is found, revise the central insight and re-evaluate
   which earlier phases need revisiting
5. If no counter-evidence is found, note this as supporting confidence — but register
   the specific searches you ran so the reader knows what was tested

This phase is **not optional**. Decision-grade analysis requires that the analyst has
actively tried to break their own conclusions. Skipping this produces analysis that
confirms whatever the first few sources suggested — which is worse than useless because
it creates false confidence.

### Example Adversarial Queries
- If central insight is "Target's positions correlate with political cycles":
  → Search: `"[Name]" consistent principled independent bipartisan`
- If central insight is "Target prioritizes growth over safety":
  → Search: `"[Name]" safety investment responsible "slowed down"`
- If central insight is "Target avoided risk throughout career":
  → Search: `"[Name]" decisive bold "took action" "against advice"`

---

## Phase 8: Synthesis & Writing

### 7.1 Writing Principle: This Is a Research Report, Not a Spreadsheet

The analytical report is a **human-readable narrative** — written like an intelligence
brief or long-form investigative article. It should read as compelling prose that a
decision-maker would actually want to read cover-to-cover.

**DO:** Write in flowing analytical paragraphs. Use section headers to organize, but
within each section, write full prose with argumentation, evidence, and interpretation
woven together. Use the target's actual quotes (sparingly) to bring the analysis alive.
After each factual narrative block, include a **"Deep Analysis"** paragraph that extracts
the larger meaning — what pattern does this reveal, what does it predict, what contradiction
does it surface.

**DON'T:** Write as a series of tables, bullet lists, or data sheets. Tables and structured
elements are supporting tools — use them occasionally to present specific comparisons,
timelines, or contradiction pairs — but they should never be the primary content. The report
should feel like reading a New Yorker profile or a Brookings policy brief, not a database dump.

### 7.2 Choose Analytical Architecture

| Structure | When to Use |
|-----------|------------|
| Chronological | When the timeline IS the story |
| Thematic | When ideas matter more than sequence |
| Dialectical | When there's genuine debate |
| **Hybrid (chrono-spine + analytical interludes)** | When both matter — **default choice** |

The default hybrid structure: tell the story chronologically (career phases, key events),
but interrupt the timeline at each major phase transition with an analytical paragraph
that asks "what does this phase reveal about the target's character, incentives, or
intellectual framework?"

### 7.3 Central Insight Identification
Across all research, find the **single most explanatory pattern** — the one insight
that explains the most contradictions and predicts the most behavior. State it as a
single sentence. Every section should test, illustrate, or complicate this insight.
This becomes the thesis of the report, introduced early and threaded throughout.

### 7.4 Contradiction Surfacing (for person targets)
Identify pairs of contradictory evidence and weave them into the narrative. Present the
tension in prose: "On one hand, [evidence A] suggests [trait]. Yet [evidence B] complicates
this picture..." Do NOT resolve contradictions that the evidence doesn't resolve — honest
ambiguity is more useful than false coherence.

When the contradictions are numerous or systematic enough, a brief summary table can support
the prose — but the analysis itself should be written as paragraphs, not as a table.

### 7.5 Forward Projection
End the report with 2-3 scenarios written as narrative descriptions, not bullet lists.
For each scenario, explain in prose: what would trigger it, how likely it is, what it
means for stakeholders, and what signals to watch. This should read like the "what comes
next" section of a good analytical article.

### 7.6 Confidence and Limitations
Close the report with an honest assessment — written in prose — of what the analysis
can and cannot tell us. Where are the gaps? What biases might be present? What new
information would change the conclusions?

---

## Phase 9: Delivery — Dual Output

Every research run produces **two outputs**:

### Output 1: Analytical Report (`.md`) — for human consumption

A narrative research report written in prose, structured like an intelligence brief or
investigative profile. The report should be compelling to read, not just informative.

**Structure guide (adapt per target):**
```
I.    The Origin Story — who they are, where they came from, formative experiences
II.   Career Timeline — major phases, each followed by a "Deep Analysis" paragraph
III.  The Intellectual Framework — what they believe, how it evolved, with direct
      quotes and idea decomposition woven into the narrative
IV.   Network & Power Map — key relationships told as narrative, not as a table;
      explain *why* each connection matters, not just *that* it exists
V.    Character & Personality — contradictions surfaced through comparative
      storytelling, not through a spreadsheet of traits
VI.   The Controversies — each told as a mini-narrative with steel-manned
      opposition, evidence on both sides, and honest assessment
VII.  What Comes Next — forward scenarios written as prose, with monitoring signals
VIII. Sources — classified reference list (this section can be structured/tabular)
```

**Style guidance:**
- Write in analytical prose paragraphs throughout — like a long-form magazine profile
  crossed with a policy brief
- Use section headers (##, ###) to organize, but fill each section with real writing
- Tables are acceptable ONLY as occasional supporting elements — for timelines,
  specific data comparisons, or summary reference. Never as the primary content.
- Include the target's own words (sparingly) to make the analysis vivid
- Every factual section needs a companion analytical paragraph: "What does this mean?"
- The central insight should be introduced early and threaded throughout, not stated
  once and forgotten
- End sections with forward-looking questions, not just backward-looking summaries

### Output 2: Target Profile / Dossier (`.json`) — for persistent storage & cross-referencing

The dossier is the **living document**. It captures structured, queryable data:

- **`meta`** — target identity, research session log
- **`biography`** — education, career phases with dates and significance
- **`positions`** — timestamped ledger of every public statement/position, tagged with:
  - `topic` (inflation, qe, fed_independence, etc.)
  - `context` (board meeting, earnings call, keynote, op-ed, congressional testimony, TV interview)
  - `political_env` (which party/president in power)
  - `outcome_assessment` (CORRECT / WRONG / DEBATABLE / UNTESTED / CONTESTED)
- **`network`** — relationship entries with nature, duration, power dynamic, significance
- **`controversies`** — each with severity, critics, defenders, source references
- **`intellectual_framework`** — core beliefs with consistency ratings and first-articulated dates
- **`central_insight`** — one-sentence thesis with confidence and falsification condition
- **`forward_scenarios`** — each with probability, monitoring indicators
- **`sources`** — master registry with stable IDs referenced throughout the profile
- **`change_detection`** — pending checks and flags for new activity comparison

See `references/dossier_schema.md` for the complete JSON schema and worked example.

### File Organization
```
profiles/
├── [target_id]/
│   ├── profile.json              ← structured dossier (append-only updates)
│   ├── report_YYYY-MM-DD.md      ← analytical report (dated snapshots)
│   └── sources/                  ← optional: archived full-text source extracts
│       ├── src_001_[short_name].md
│       └── ...
```

### Updating an Existing Profile
When new research is done on the same target:
1. **Append** new position entries (never overwrite existing ones)
2. **Add** new source entries with new IDs (continue numbering)
3. **Update** `meta.last_updated` and add a new `research_sessions` entry
4. **Run change detection** — compare new positions against existing entries:
   - `CONSISTENT` — aligns with prior positions
   - `EVOLVED` — gradual shift in emphasis or framing
   - `CONTRADICTED` — direct reversal of a prior position
   - `NEW_TOPIC` — no prior position on this topic

### Cross-Referencing Across Profiles
When multiple profiles exist, cross-reference via:
- **Network overlap** — shared connections (compare `network.relationships`)
- **Position alignment** — agreement/disagreement on topics (compare by `topic` tag)
- **Temporal correlation** — synchronized position shifts (date-based comparison)
- **Scenario interaction** — one target's scenario affects another's

### Reference Library Format
Classify all sources into tiers:
1. **Primary/Institutional** — official records, transcripts, org bios
2. **Analytical/Journalistic** — quality analysis from credible outlets
3. **Critical/Opposition** — substantive critiques
4. **Supportive/Framework** — policy analysis supporting the target
5. **Market/Practical** — investment/business implications
6. **Network/Connection** — relationship and power structure sources

Include URLs for all sources. Assign stable IDs (src_001, src_002...) that persist across updates.

### Output Format
- Analytical report: Markdown (`.md`) by default; Word (`.docx`) on request
- Dossier: JSON (`.json`) — machine-parseable, queryable
- Language: Match user's preference (check memory/conversation context)

---

## Quality Assurance Checklist

Before delivering, verify:

```
□ Source diversity: Not dominated by one political lean or outlet type
□ Temporal coverage: Not over-indexed on recent events
□ Steel-manning: Strongest opposition arguments presented fairly
□ Target's voice: Their best intellectual case included
□ Contradiction surfacing: Tensions flagged, not smoothed
□ Known unknowns: Gaps in knowledge explicitly stated
□ Confidence tags: Major claims rated HIGH/MEDIUM/LOW
□ Forward projection: Actionable scenarios with monitoring indicators
□ References: All sources listed with URLs and type classification
□ Bias check: Reviewed for confirmation, availability, authority,
  narrative, and recency bias
□ Records intelligence: Structured databases queried (court, financial,
  corporate, political) — not just articles
□ Ownership mapping: Corporate entities connected to target identified
  and cross-referenced via registries and SEC filings
□ Primary document retrieval: Key filings and transcripts fetched in
  full, not relied on via third-party summaries
```

---

## Tool Usage Guide

| Tool | When to Use | When to Stop |
|------|------------|-------------|
| `web_search` | Discovery — finding sources, verifying claims, exploring leads | When consecutive searches yield no new substantive information |
| `web_fetch` | Deep reading — full text of any analytically valuable source | When every source worth citing has been read in full |
| `create_file` | Output — writing the deliverable document | When both report and dossier are written |
| `present_files` | Delivery — making files available | Once per delivery |
| `conversation_search` | Context — checking for prior research on this target | Once at start |

### Critical: Read What You Cite
Search snippets are 200-500 words. Full articles are 1,500-5,000 words.
The information loss from snippet-only research is 70-90%.
**If a source is worth citing in the final report, it is worth fetching and reading in full.**

Priority for `web_fetch` (but do not limit yourself to these):
1. Primary source documents (speeches, testimony, reports authored by target)
2. The most sophisticated analytical critiques
3. The most comprehensive biographical profiles
4. Any source containing data tables, chronologies, or systematic comparisons
5. Op-eds, papers, or interviews authored by the target
6. Financial disclosures, official filings, or audit reports

---

## Adaptation by Target Type

See `references/primary_sources.md` Section 11 for full investigation playbooks with specific
database URLs and search queries per target type. Summary below:

### Financial Professional (Banker, Fund Manager, Trader)
**Phase emphasis**: 2 (track record), 4 (regulatory), 6 (controversies)
**Priority records**: FINRA BrokerCheck (disciplinary/complaints), SEC EDGAR (Form ADV, 13F,
Form 4 insider trades), SEC enforcement actions, court records (investor lawsuits), FEC
donations, corporate registries for controlled entities, proxy statements (compensation)
**Key questions**: Actual vs. claimed track record? Regulatory actions or complaints? Insider
trading patterns? Entity structures?

### Attorney / Legal Professional
**Phase emphasis**: 4 (opposition), 6 (controversies)
**Priority records**: State bar records (disciplinary history, active status), CourtListener/PACER
(cases litigated, win/loss pattern), SEC filings (if advising public companies), lobbying
disclosures, FEC donations
**Key questions**: Bar disciplinary actions? Case outcome patterns? Client conflict patterns?

### Tech Executive / Founder
**Phase emphasis**: 2 (substance), 3 (network), 6 (controversies)
**Priority records**: SEC EDGAR (10-K, proxy, insider trades), patent filings (actual inventive
contribution), court records (IP, employment, antitrust), FEC/lobbying, corporate registries
**Key questions**: Technical reputation backed by patents/code/publications? Insider selling
before bad quarters? Compensation vs. shareholder returns? What has been litigated?

### Military / Intelligence Official
**Phase emphasis**: 3 (network), 4 (opposition)
**Priority records**: Congressional testimony transcripts, OGE financial disclosures, IG reports,
FOIA releases, published war college papers, post-service employment (revolving door to
defense contractors)
**Key questions**: Actual accomplishments vs. biography claims? IG investigations? Post-service
employer conflicts? Testimony vs. subsequent reality?

### Politician / Government Official
**Phase emphasis**: 3-4 heavy (network, opposition)
**Priority records**: FEC (all contributions given/received), financial disclosures (assets,
income, outside positions), voting record (congress.gov), lobbying disclosures, committee
assignments, earmarks, court records
**Key questions**: Votes match stated positions? Donor interests align with votes? Unexplained
wealth changes? Revolving door timing?

### Scientist / Academic
**Phase emphasis**: 2 (substance), 5 (strongest case)
**Priority records**: Google Scholar/Semantic Scholar (publication record, citations), funding
sources (NIH RePORTER, NSF awards), patent filings, Retraction Watch, conflict of interest
disclosures, expert witness history (court records)
**Key questions**: Citation count genuine vs. self-inflated? Funding conflicts? Retractions?
Industry consulting that conflicts with research conclusions?

### Institution / Organization
**Phase emphasis**: 1-2 heavy (foundation, substance)
**Priority records**: IRS 990s (for nonprofits — revenue, compensation, grants), SEC filings
(if public), government contracts (USAspending.gov), IG reports, corporate registries
(subsidiary structure), lobbying disclosures
**Key questions**: Funding sources and dependencies? Leadership compensation vs. mission?
Government contract reliance? Regulatory history?

### Geopolitical Actor
**Phase emphasis**: 3 heavy (network/alliances)
**Priority records**: Sanctions lists (OFAC, EU, UN), trade databases, international court
records, treaty databases, defense spending data, international organization voting records
**Key questions**: Sanctions exposure? Alliance reliability? Economic dependencies? Military
capability vs. claims?
