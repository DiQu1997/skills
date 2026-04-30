# Deep Target Research — Full Technique Library

## Table of Contents

1. [Search Query Design Patterns](#1-search-query-design-patterns)
2. [Source Evaluation Framework](#2-source-evaluation-framework)
3. [Position Evolution Mapping](#3-position-evolution-mapping)
4. [Idea Decomposition Protocol](#4-idea-decomposition-protocol)
5. [Relationship Mapping Protocol](#5-relationship-mapping-protocol)
6. [Steel-Manning Technique](#6-steel-manning-technique)
7. [Contradiction Mapping for Personality](#7-contradiction-mapping-for-personality)
8. [Central Insight Extraction](#8-central-insight-extraction)
9. [Scenario Framework Construction](#9-scenario-framework-construction)
10. [Cognitive Bias Checklist](#10-cognitive-bias-checklist)
11. [Source Diversity Audit](#11-source-diversity-audit)
12. [Search Sequencing Logic](#12-search-sequencing-logic)
13. [web_fetch Prioritization](#13-web_fetch-prioritization)
14. [Adversarial Review Pass](#14-adversarial-review-pass)
15. [Output Templates](#15-output-templates)
16. [Common Failure Modes](#16-common-failure-modes)

---

## 1. Search Query Design Patterns

### General Principles
- Keep queries short and specific: 3-8 words for best results
- Start broad, then narrow based on what you discover
- Every query must be **meaningfully distinct** from previous queries
- Include the current year for time-sensitive topics

### Phase-Specific Query Templates

**Phase 1 (Foundation):**
```
"[Name] biography background history"
"[Name] early career upbringing family"              ← optional second search
```

**Phase 2 (Substance):**
```
"[Name] [domain keyword] views criticism analysis"
"[Name] [specific concept they coined] [domain]"     ← if a key concept is discovered
```

**Phase 3 (Network):**
```
"[Name] [key relationship name] connections controversy"
"[Name] financial disclosure conflicts interest"       ← for public officials
```

**Phase 4 (Opposition):**
```
"[Name] [role context] criticism controversy"
"[Name] 'case against' qualifications [domain] criticism"
```

**Phase 5 (Strongest Case):**
```
"[Name] [their key speech/paper title] [domain] [key concept]"
```

**Phase 6 (Deep-Dive):**
```
"[Name] [specific incident] [specific factual detail to verify]"
```

### Query Anti-Patterns (avoid these)
- Don't use quotes unless searching for exact phrases
- Don't use site: or - operators unless explicitly needed
- Don't repeat substantially similar queries — diminishing returns
- Don't include meta-words like "article about" or "information on"

---

## 2. Source Evaluation Framework

### Reliability Tiers

**Tier 0 — Structured Records & Filings (ground truth for facts)**
- Court records (PACER, CourtListener, state court systems)
- SEC filings (EDGAR: 10-K, DEF 14A, Form 4, 13F, Schedule 13D)
- Government databases (FEC, USAspending, OGE financial disclosures)
- Corporate registries (state Secretary of State, OpenCorporates)
- Licensing records (FINRA BrokerCheck, state bar, medical boards)
- Tax filings (IRS 990 for nonprofits via ProPublica)
- Patent filings (USPTO, Google Patents)
- Sanctions lists (OFAC, EU, UN)
- These are factual records filed under legal obligation — highest reliability for what
  they contain. They show what happened, not why — interpretation still requires analysis.
- See `references/primary_sources.md` for the full database guide with URLs and search strategies.

**Tier 1 — Primary Sources (highest reliability for facts)**
- Official transcripts (congressional hearings, FOMC meetings)
- Financial disclosures and SEC filings
- Authored works by the target (speeches, op-eds, reports)
- Government audit reports (GAO, IG reports)
- Court documents and legal filings

**Tier 2 — Quality Analytical Sources (high reliability for analysis)**
- Major newspaper investigations (WSJ, NYT, WaPo, FT)
- Policy think tanks with declared lean (Brookings, Hoover, CFR, AEI)
- Academic journals and working papers
- Central bank and IMF publications

**Tier 3 — Professional/Market Sources (good for implications)**
- Financial institution research (Goldman, Morgan Stanley, Invesco)
- Specialized financial media (Bloomberg, CNBC, Fortune)
- Market analysis platforms (Morningstar, TradingKey)

**Tier 4 — Partisan/Advocacy Sources (useful for mapping debate)**
- Partisan media (Breitbart, Truthout, TPM, Daily Beast)
- Political commentary (Krugman's Substack, editorial pages)
- Advocacy organizations
- Note: These are valuable for understanding the **range of opinion** but should not
  be the primary basis for factual claims

**Tier 5 — Low-Reliability Sources (use with extreme caution)**
- Social media posts
- Anonymous forums
- Biography aggregator sites
- SEO-optimized content farms

### Cross-Referencing Rule
Any factual claim used in the final analysis should be corroborated by ≥2 independent
sources from Tier 1-3. Claims from a single Tier 4-5 source should be flagged as
unverified or presented as "according to [source]."

---

## 3. Position Evolution Mapping

### Construction Method

Build a timestamped ledger of the target's public positions:

**Example A — Central banker (finance domain):**
```
| Date | Position | Context | Audience | Environment |
|------|----------|---------|----------|-------------|
| 2008-03 | "Inflation risks remain elevated" | Policy meeting | Colleagues | Financial crisis deepening |
| 2011-03 | Resigned over bond-buying program | Public action | Markets | Opposition party in power |
| 2024-07 | "We need to cut rates now" | TV interview | Public | Aligned party campaigning |
```

**Example B — Tech CEO (technology domain):**
```
| Date | Position | Context | Audience | Environment |
|------|----------|---------|----------|-------------|
| 2019-05 | "AI safety is our top priority" | Developer conference | Developers | Pre-regulation era |
| 2022-11 | "We must ship fast to stay competitive" | Internal memo (leaked) | Employees | ChatGPT launch pressure |
| 2024-06 | "We've always balanced speed and safety" | Senate hearing | Congress | Regulation pending |
```

**Example C — Military commander (defense domain):**
```
| Date | Position | Context | Audience | Environment |
|------|----------|---------|----------|-------------|
| 2015 | "Counterinsurgency is the future of warfare" | War college lecture | Officers | Post-Afghanistan |
| 2022 | "Near-peer competition requires conventional readiness" | Congressional testimony | Legislators | Ukraine war |
| 2024 | "We need both COIN and conventional capabilities" | Think tank speech | Policy community | Election year |
```

### Overlay Analysis
Once the ledger is built, overlay:
- **Political cycle** — does hawkishness/dovishness correlate with party in power?
- **Career incentive** — does the position align with their next career move?
- **Peer group** — are they leading or following their intellectual community?
- **Empirical outcomes** — were they right or wrong? (check actual data)

### Red Flags for Opportunistic Positioning
- Abrupt position changes coinciding with political transitions
- Positions that consistently favor the interests of the target's network
- New justifications for old conclusions (changing the reason but not the policy)
- Asymmetric certainty (very sure about things that happen to be convenient)

---

## 4. Idea Decomposition Protocol

For each major intellectual position the target holds:

### Template
```
POSITION: [Clear statement of what they believe]

PREMISE: [What must be true for this to hold]
  - Empirical premise: [testable factual claim]
  - Theoretical premise: [which economic/political model is assumed]

LOGIC: [The inferential chain from premise to conclusion]
  - Step 1: If [premise], then [intermediate conclusion]
  - Step 2: If [intermediate], then [policy prescription]

PREDICTION: [What this position implies about future events]
  - Testable prediction 1: [specific, dated, measurable]
  - Testable prediction 2: [specific, dated, measurable]

TESTABILITY: [How would we know this is wrong?]
  - Falsification condition: [what data would disprove it]
  - Timeline: [when should we expect to see evidence]

STRONGEST COUNTER: [The best argument against this position]
  - Who makes it: [specific critic with credentials]
  - Their logic: [the counter-argument in its strongest form]
```

---

## 5. Relationship Mapping Protocol

### For Each Key Relationship

```
RELATIONSHIP: [Target] ↔ [Connected Person/Entity]

Nature:        [Family / Patron / Mentor / Business / Political / Intellectual]
Origin:        [How they met, when, context]
Duration:      [Years, through which career phases]
Power Dynamic: [Who needs whom more? Has this shifted?]
Public Visibility: [Open/known vs. behind-the-scenes]

Relevance to Current Role:
  - Access channel: [Does this relationship provide access to power/information?]
  - Incentive alignment: [Do their interests converge or diverge?]
  - Perception risk: [Does this relationship create conflict-of-interest concerns?]

Evidence:
  - [Source 1 with URL]
  - [Source 2 with URL]
```

### Network Topology Questions
After mapping all relationships, ask:
- Is there a **single point of failure** (one relationship that, if removed, would
  collapse the target's position)?
- Are there **hidden clusters** (groups of connected people who aren't obviously linked)?
- Is the network **echo-chambered** (all from the same background/ideology) or diverse?
- Are there **absent relationships** (people you'd expect to see who aren't there)?

---

## 6. Steel-Manning Technique

### Why Steel-Man
The purpose is NOT to be fair to the critic. It's to produce better analysis. A
steel-manned criticism is more useful for decision-making than a weak one because
it identifies the actual risks rather than the easy-to-dismiss ones.

### Protocol
1. Find the criticism in its original form
2. Identify its core claim (separate signal from noise/rhetoric)
3. Ask: "What would the most credible, well-informed version of this critic say?"
4. Reconstruct with: specific evidence, reasonable inference, acknowledged uncertainty
5. Evaluate the steel-manned version — is it still compelling?

### Example A — Political appointee
**Original (weak):** "He's unqualified because he married into wealth."
**Steel-manned:** "His appointment pathway has at each stage been facilitated by political
connections rather than demonstrated domain expertise. The family connections provided both
wealth and direct access to the appointing authority. While this doesn't prove incompetence,
it raises the question: would someone with this same track record but without these connections
have been considered for this role? Historical comparison suggests not."

### Example B — Tech CEO
**Original (weak):** "She's just a marketing person, not a real technologist."
**Steel-manned:** "Her career trajectory — brand management → product marketing → COO →
CEO — follows a non-technical path at a time when the company's core challenges are
engineering-intensive (AI model architecture, infrastructure scaling, security). While
non-technical CEOs can succeed by building strong technical teams, the specific decisions
ahead (build vs. buy for foundation models, infrastructure capital allocation) require
the kind of first-principles technical judgment that previous technical-CEO competitors
have and she may lack."

### Example C — Military leader
**Original (weak):** "He's never seen combat so he can't lead in a war."
**Steel-manned:** "His entire career has been in staff and planning roles, never in
command of units under fire. While strategic planning is essential, the specific demands
of this role — real-time tactical decisions, morale under casualty pressure, trust from
combat-experienced subordinates — draw on a type of judgment that is developed through
direct operational experience. Three of the four most effective holders of this position
in the past 30 years had significant combat command backgrounds."

---

## 7. Contradiction Mapping for Personality

### Construction
For each identified behavioral pattern, search for **counter-evidence**:

```
| Trait A      | Evidence A         | Trait B        | Evidence B         | Status       |
|-------------|-------------------|---------------|-------------------|-------------|
| Principled  | 15yr consistent X | Opportunistic | Pivot timing = Y  | UNRESOLVED  |
| Competent   | Crisis management | Incompetent   | Wrong predictions | DOMAIN-DEP  |
| Independent | Resigned on principle | Compliant | Adopted patron views | CONTEXT-DEP |
| Insider     | Elite memberships | Outsider      | Anti-establishment rhetoric | STRATEGIC |
```

### Status Categories
- **RESOLVED** — evidence clearly favors one side
- **UNRESOLVED** — genuine tension with evidence on both sides
- **DOMAIN-DEPENDENT** — true in one context, false in another
- **CONTEXT-DEPENDENT** — depends on which pressure is stronger
- **STRATEGIC** — the contradiction is itself a deliberate strategy

### The Rule
**Never resolve a contradiction that the evidence doesn't resolve.** Forced coherence
is the enemy of good analysis. An honest "this is genuinely ambiguous" is more useful
for decision-making than a false certainty.

---

## 8. Central Insight Extraction

### Method
After completing all research phases, ask:

1. What is the **single pattern** that explains the most data points?
2. Can I state it in one sentence?
3. Does it explain both the target's successes AND failures?
4. Does it predict behavior in novel situations?
5. Would the target's supporters and critics both recognize it as partially true?

### Quality Test
A good central insight should:
- Not be obvious from the target's public image
- Explain apparent contradictions
- Be falsifiable (what evidence would disprove it?)
- Generate predictions

### Examples Across Domains

**Finance — Central banker:** "Operational brilliance paired with analytical weakness — both
rooted in a Wall Street worldview that excels at reading rooms and moving capital but
systematically overweights financial asset prices relative to labor market conditions."

**Technology — AI CEO:** "A research-first founder who treats product-market fit as a
constraint to be solved by capability breakthroughs, which produces transformative upside
when the bet is right and catastrophic capital destruction when it's wrong — and who
cannot distinguish between the two cases in advance."

**Military — General:** "A politically astute officer whose career success came from
telling superiors what they wanted to hear, which made him excellent at navigating
peacetime bureaucracy but creates fragility when ground truth diverges from institutional
narrative."

**Geopolitics — Nation-state:** "A middle power that compensates for military weakness
through economic leverage and diplomatic agility, which works until a crisis forces
binary alignment choices that eliminate the ambiguity it depends on."

---

## 9. Scenario Framework Construction

### Template for Each Scenario

```
SCENARIO [A/B/C]: [Descriptive name]

Trigger Conditions:
  - [What would cause this path to materialize]
  - [What early signals would indicate this direction]

Probability: [High / Medium / Low] — [one-line justification]

Mechanism:
  - [Step 1 of how this plays out]
  - [Step 2]
  - [Key decision point]

Implications:
  - For [stakeholder 1]: [specific impact]
  - For [stakeholder 2]: [specific impact]
  - For [market/policy/domain]: [specific impact]

Monitoring Indicators:
  - [Data point 1 to watch — with threshold]
  - [Data point 2 to watch — with threshold]
  - [Event to watch for]

What Would Change This Assessment:
  - [New information that would raise probability]
  - [New information that would lower probability]
```

### Scenario Design Rules
- Always include at least one scenario the target's supporters expect
- Always include at least one scenario the target's critics expect
- Always include a "muddling through" / hybrid scenario (usually highest probability)
- Never assign >60% to any single scenario unless evidence is overwhelming

---

## 10. Cognitive Bias Checklist

After completing analysis, audit for each:

| Bias | Check | Mitigation |
|------|-------|-----------|
| **Confirmation** | Did I seek evidence against my emerging thesis? | Run adversarial search (Phase 14) |
| **Availability** | Am I over-weighting recent/dramatic events? | Check temporal distribution of sources |
| **Authority** | Am I giving excess weight to famous critics/supporters? | Evaluate arguments on merit, not author prestige |
| **Narrative** | Is my central insight too clean? Reality is messy. | Flag unresolved contradictions |
| **Recency** | Are recent events dominating over historical patterns? | Ensure pre-2020 sources are included |
| **Anchoring** | Did the first source frame everything that followed? | Re-examine initial assumptions |
| **Halo effect** | Am I letting one impressive trait color everything? | Check if each trait has independent evidence |

---

## 11. Source Diversity Audit

After all research, count sources by category:

```
| Category          | Count | Risk if Over-Represented | Risk if Under-Represented |
|-------------------|-------|--------------------------|---------------------------|
| Left-leaning      |       | Analysis skews critical   | Missing legitimate critiques |
| Right-leaning     |       | Analysis skews supportive | Missing structural concerns |
| Centrist/neutral  |       | Milquetoast analysis      | Missing nuance |
| Academic          |       | Too theoretical           | Missing rigor |
| International     |       | Irrelevant perspectives   | Missing external view |
| Primary sources   |       | N/A                       | Analysis built on hearsay |
| Market/financial  |       | Too investment-focused    | Missing practical implications |
```

**Target distribution:** No single category >40% of total sources. Primary sources ≥10%.
International sources ≥5% for any target with global implications.

---

## 12. Search Sequencing Logic

### The Adaptive Funnel
Each search should fill a specific gap identified by previous searches. The sequence below
is a starting template — follow leads wherever they go. There is no fixed number of searches;
continue until information gain drops to zero.

```
Foundation searches   → Establish facts, discover vocabulary, map source ecosystem
Substance searches    → Understand ideas, find analytical sources, track position evolution
Network searches      → Map connections, incentive structures (one search per key relationship)
Opposition searches   → Get strongest critics — separate partisan from substantive
Best-case searches    → Target's own strongest arguments, in their own words
Verification searches → Verify specific high-weight factual claims (one per controversy)
Adversarial searches  → Deliberately seek evidence against your emerging thesis
Follow-up searches    → Pursue any leads, names, events, or documents discovered along the way
```

### Decision Points (check after each phase, not after a fixed count)
- After foundation: Do I have the complete timeline? If gaps, keep searching.
- After substance: Do I have position evolution data with dates? If not, search for specific speeches.
- After network: Are there relationship gaps? If key people are mentioned but unmapped, search for each.
- After opposition: Is criticism balanced? If only partisan, search specifically for substantive critique.
- After best-case: Have I heard the target at their best? If only summaries, fetch full text.
- After verification: Is every HIGH controversy corroborated by ≥3 independent sources? If not, keep going.
- After adversarial: Have I tried to disprove my central insight? What happened?

### Iterative Deepening
Research is not a single pass through phases. Discoveries in later phases routinely reveal
gaps in earlier ones. When this happens, go back. A name discovered in Phase 4 (Opposition)
may require a new Phase 3 (Network) search. A contradiction found in Phase 7 (Adversarial)
may require revisiting Phase 2 (Substance). This is expected and encouraged.

---

## 13. web_fetch Prioritization

### The Rule: If You Cite It, Read It
If a source is worth referencing in the final report, it is worth fetching and reading in
full. Search snippets lose 70-90% of the information in an article. There is no cap on
the number of fetches — thoroughness is the priority.

### Always Fetch
1. **Primary source documents** — speeches, testimony, reports authored by target
2. **Sophisticated analytical critiques** — any source that makes a substantive case
   against the target or your emerging thesis
3. **Comprehensive biographical profiles** — the most detailed pieces from quality outlets
4. **Op-eds, papers, or interviews authored by the target** — hearing them in their own voice
5. **Financial disclosures, official filings, or audit reports** — primary factual evidence
6. **Any source containing data tables, chronologies, or systematic comparisons**
7. **Academic papers or policy briefs** analyzing the target's framework

### Never Waste web_fetch On
- Wikipedia (already in search snippets)
- Biography aggregator sites (low information density)
- Social media posts (too short to need fetching)
- Duplicate coverage from multiple outlets covering the same event

---

## 14. Adversarial Review Pass

After completing the draft, perform one final research step:

### Method
1. State your central insight as a falsifiable claim
2. Design a search query specifically intended to **disprove** it
3. Execute the search
4. If strong counter-evidence is found, revise the analysis
5. If no counter-evidence is found, note this as supporting confidence

### Examples

**Finance target:**
- Central insight: "Target's positions correlate with political cycles"
- Adversarial query: `"[Name]" consistent principled independent bipartisan`
- Purpose: Find evidence positions are actually stable regardless of politics

**Tech target:**
- Central insight: "Target prioritizes growth over safety"
- Adversarial query: `"[Name]" safety investment responsible "slowed down"`
- Purpose: Find evidence of genuine safety-first decisions that cost growth

**Military target:**
- Central insight: "Target avoided risk throughout career"
- Adversarial query: `"[Name]" decisive bold "took action" "against advice"`
- Purpose: Find episodes where target made high-risk calls

This step is **required** for decision-grade analysis. Skipping it produces analysis that
confirms whatever the first few sources suggested — which is worse than useless because
it creates false confidence. If you did not try to break your own thesis, the analysis
is not done.

---

## 15. Output Templates

### Writing Style: Narrative First, Data Second

The analytical report is a **research essay**, not a data sheet. It should read like an
intelligence brief or investigative profile that a busy decision-maker would read
cover-to-cover. Write in flowing analytical prose. Use the target's own words (sparingly)
to bring the analysis alive. After every factual block, add a "Deep Analysis" paragraph
that extracts the larger meaning.

Tables and structured elements are **supporting tools only** — use them occasionally for
specific comparisons, timelines, or at-a-glance summaries. They should never constitute
the primary content of any section. The Sources/Reference section at the end is the one
place where structured listing is appropriate.

### For Person Targets (default)
```
I.    The Origin Story — formative background, told as narrative
II.   Career Timeline — major phases, each with "Deep Analysis" paragraphs
III.  The Intellectual Framework — beliefs, evolution, quotes, woven into prose
IV.   Network & Power Map — key relationships as narrative, explaining WHY they matter
V.    Character & Personality — contradictions surfaced through storytelling
VI.   The Controversies — mini-narratives with steel-manned opposition
VII.  What Comes Next — forward scenarios as prose with monitoring signals
VIII. Confidence & Limitations — honest assessment of gaps and biases
IX.   Reference Library — classified source list (structured format OK here)
```

### For Institution Targets
```
I.    Central Insight — one-paragraph thesis
II.   Founding & Mission — origin story, original mandate vs. current practice
III.  Structural Evolution — told as narrative of governance and leadership changes
IV.   Doctrine & Decision-Making — how the institution thinks, written as analysis
V.    Stakeholder Map — who benefits, who's harmed, told through specific examples
VI.   Performance Record — successes and failures as case studies, not a scorecard
VII.  Controversies — narrative with both sides
VIII. Reform Scenarios — forward-looking prose
IX.   References
```

### For Policy/Regulation Targets
```
I.    Central Insight
II.   Origins & Intent — the problem it was designed to solve, told as history
III.  Mechanism — how it actually works vs. intended design, explained in prose
IV.   Winners & Losers — distributional analysis through specific examples
V.    Track Record — intended vs. actual outcomes as narrative case studies
VI.   Critics & Defenders — steel-manned debate, not a pro/con table
VII.  Reform Scenarios — forward-looking prose
VIII. References
```

---

## 16. Common Failure Modes

| Failure Mode | Symptom | Fix |
|-------------|---------|-----|
| **Data sheet syndrome** | Output is tables, bullets, and checklists instead of prose | Rewrite as narrative paragraphs; tables only for supporting data |
| **Biography trap** | Output reads like a Wikipedia article | Add "Deep Analysis" after every factual section |
| **Both-sides-ism** | Everything is "on one hand / on the other" | Take analytical positions, flag confidence |
| **Recency avalanche** | 80% of content about last 6 months | Deliberately search for pre-2020 sources |
| **Snippet synthesis** | Analysis feels shallow | Use web_fetch on top 5 sources |
| **Coherence forcing** | All contradictions resolved into neat narrative | Leave genuine tensions unresolved |
| **Source monoculture** | All sources from same outlet/lean | Run source diversity audit |
| **Missing the target's voice** | Analysis is all about what others say | Phase 5 must include target's own words |
| **No forward projection** | Report ends with "time will tell" | Build explicit scenario framework |
| **Undated claims** | "Target believes X" without when | Every position must be timestamped |
| **Motivation-free narrative** | Things happen without explaining why | Every action needs incentive mapping |
| **Article-only research** | No structured records checked | Query at least 3 record databases relevant to target type (see `primary_sources.md`) |
| **Ownership blindness** | Target's corporate entities not mapped | Check corporate registries, SEC ownership filings, proxy statements |
| **Missing the money trail** | No financial pattern analysis | Check FEC donations, Form 4 insider trades, DEF 14A compensation, 990 nonprofit flows |
| **Credential inflation** | Claimed expertise accepted at face value | Verify via publication record, patent filings, licensing databases |
