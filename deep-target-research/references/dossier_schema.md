# Dossier Profile Schema — Generic

## Overview

Every deep research run produces **two outputs**:

1. **Analytical Report** (`.md`) — human-readable analysis
2. **Target Profile / Dossier** (`.json`) — structured, machine-parseable profile for
   persistent storage, cross-referencing, and change detection

The dossier is the **living document**. It accumulates over time — append-only for
positions, sources, and observations. When the target does something new, diff it
against the existing profile to detect evolution, contradiction, or confirmation.

---

## File Organization

```
profiles/
├── [target_id]/
│   ├── profile.json              ← the structured dossier (append-only updates)
│   ├── report_YYYY-MM-DD.md      ← analytical report (dated snapshots)
│   └── sources/                  ← optional: archived full-text extracts
│       ├── src_001_[short_name].md
│       └── ...
```

---

## JSON Schema

All fields marked `[*]` are required. Others are included when available.

```json
{
  "meta": {
    "target_id": "",            // [*] snake_case identifier
    "target_name": "",          // [*] display name
    "target_type": "",          // [*] person | institution | policy | technology | geopolitical_actor
    "domain": "",               // [*] primary domain: finance, tech, military, science, politics, culture, etc.
    "created": "",              // [*] ISO 8601
    "last_updated": "",         // [*] ISO 8601
    "research_sessions": []     // [*] array of { date, scope, search_count, source_count }
  },

  "biography": {               // For persons — adapt for other target_types (see Adaptation section)
    "birth_date": "",
    "birth_place": "",
    "education": [],            // array of { institution, degree, year, notes }
    "career_phases": []         // [*] array of { phase_id, role, organization, start, end, significance }
  },

  "positions": {
    "_description": "Timestamped ledger of public positions/statements/actions. The core of the dossier.",
    "topic_taxonomy": [],       // [*] list of topic tags used in this profile (domain-specific — see below)
    "entries": []               // [*] array — see Position Entry schema below
  },

  "network": {
    "relationships": []         // array — see Relationship Entry schema below
  },

  "controversies": [],          // array — see Controversy Entry schema below

  "intellectual_framework": {   // What the target believes and why
    "core_beliefs": [],         // array of { belief, first_articulated, consistency, key_source }
    "intellectual_influences": [], // array of strings
    "methodology_or_style": ""  // how they think/work (e.g., "data-driven", "intuition-led", "consensus-builder")
  },

  "track_record": {             // Empirical performance audit
    "predictions_or_decisions": [], // array of { date, claim, domain, outcome, assessment, source_ids }
    "summary_stats": {
      "correct": 0,
      "wrong": 0,
      "debatable": 0,
      "untested": 0
    }
  },

  "central_insight": {
    "statement": "",            // [*] one-sentence analytical thesis
    "confidence": "",           // HIGH | MEDIUM-HIGH | MEDIUM | LOW
    "falsification_condition": "" // what evidence would disprove this
  },

  "forward_scenarios": [],      // array — see Scenario Entry schema below

  "sources": {
    "_description": "Master source registry. Stable IDs persist across updates.",
    "entries": []               // [*] array of { id, type, title, url, retrieved }
  },

  "change_detection": {
    "log": [],                  // array of { date, position_id, flag, old_position_id, notes }
    "last_checked": ""
  }
}
```

---

## Entry Schemas

### Position Entry

The most important structure — this is what enables longitudinal tracking.

```json
{
  "id": "pos_001",             // [*] stable, sequential
  "date": "2024-03-15",        // [*] when stated/acted
  "topic": "",                 // [*] from topic_taxonomy — see Domain Topics below
  "position": "",              // [*] what they said/did, in plain language
  "type": "statement",         // statement | action | decision | publication | vote | investment
  "context": "",               // where/why (e.g., "FOMC meeting", "earnings call", "keynote at CES")
  "audience": "",              // who they were addressing
  "environment": "",           // relevant external context (political, market, institutional)
  "outcome_assessment": "",    // CORRECT | WRONG | DEBATABLE | UNTESTED | CONTESTED | N/A
  "assessment_date": "",       // when was this assessed (separate from statement date)
  "source_ids": []             // references to sources.entries
}
```

**The `type` field** distinguishes what kind of evidence this is:
- `statement` — said something publicly
- `action` — did something (resigned, hired, invested, deployed)
- `decision` — made a formal choice in an official capacity
- `publication` — authored a paper, report, op-ed, book
- `vote` — cast a formal vote (board, committee, legislative)
- `investment` — allocated capital (for investor/CEO targets)

### Relationship Entry

```json
{
  "person_or_entity": "",      // [*] name
  "relation": "",              // [*] role label (boss, mentor, investor, rival, ally, family, etc.)
  "nature": "",                // family | professional | political | financial | intellectual | adversarial
  "since": "",                 // approximate start
  "significance": "",          // [*] why this relationship matters to the analysis
  "source_ids": []
}
```

### Controversy Entry

```json
{
  "id": "controversy_001",
  "title": "",                 // [*] short label
  "severity": "",              // [*] HIGH | MEDIUM | LOW
  "summary": "",               // [*] what happened, in plain language
  "critics": [],               // who raised this concern
  "defenders": [],             // who defended the target
  "resolution": "",            // RESOLVED | ONGOING | DORMANT | ESCALATING
  "source_ids": []
}
```

### Scenario Entry

```json
{
  "id": "scenario_A",
  "name": "",                  // [*] descriptive label
  "description": "",           // [*] what happens in this scenario
  "probability": "",           // [*] HIGH | MEDIUM | LOW (with justification)
  "implications": [],          // who/what is affected and how
  "monitoring": [],            // [*] specific data points or events to watch
  "what_changes_this": ""      // what new info would shift the probability
}
```

### Change Detection Log Entry

```json
{
  "date": "2026-05-20",
  "new_position_id": "pos_017",
  "flag": "CONTRADICTED",      // CONSISTENT | EVOLVED | CONTRADICTED | NEW_TOPIC
  "prior_position_id": "pos_005",
  "notes": "Previously stated X, now states Y. Possible explanations: ..."
}
```

**Flag definitions:**
- `CONSISTENT` — new statement/action aligns with prior position on same topic
- `EVOLVED` — same general direction but shifted emphasis, framing, or degree
- `CONTRADICTED` — direct reversal of a prior position on the same topic
- `NEW_TOPIC` — no prior position existed on this topic; establishes baseline

---

## Domain-Specific Topic Taxonomies

The `topic_taxonomy` field should be populated based on the target's domain.
Below are starter taxonomies. **Extend these** based on what the research reveals —
the taxonomy is a living list, not a fixed schema.

### Finance / Central Banking / Economics
```
monetary_policy, interest_rates, inflation, quantitative_easing, fiscal_policy,
balance_sheet, financial_regulation, banking, housing, employment, trade,
tariffs, currency, debt, productivity, ai_economics, market_structure
```

### Technology / Silicon Valley
```
product_vision, ai_strategy, platform_strategy, competition, regulation,
privacy, open_source, talent, culture, m_and_a, monetization, scaling,
safety, ethics, partnerships, developer_ecosystem, hardware, infrastructure
```

### Military / Defense / Intelligence
```
force_structure, doctrine, alliance_policy, procurement, threat_assessment,
counterterrorism, cyber, nuclear, deterrence, rules_of_engagement,
civil_military_relations, budget_priorities, intelligence_reform, logistics
```

### Science / Research / Academia
```
methodology, core_thesis, reproducibility, funding, collaboration,
peer_review, public_communication, ethics, interdisciplinary, mentorship,
institutional_politics, publication_strategy, paradigm_position
```

### Politics / Governance
```
domestic_policy, foreign_policy, trade, immigration, healthcare, education,
climate, taxation, judicial, civil_rights, electoral_strategy, coalition,
institutional_reform, federalism, executive_power, media_strategy
```

### Culture / Media / Entertainment
```
artistic_vision, commercial_strategy, public_persona, controversy,
industry_position, audience, collaboration, platform_choice, cultural_impact,
creative_process, business_model, legacy
```

### Geopolitical Actor (country, bloc, alliance)
```
grand_strategy, economic_model, alliance_structure, military_posture,
trade_policy, energy_policy, technology_policy, demographic_trend,
internal_stability, territorial_claims, soft_power, institutional_capacity
```

### Institution / Organization
```
mission, governance, funding, expansion, reform, leadership, culture,
performance, accountability, mandate_creep, stakeholder_relations,
crisis_response, innovation, partnerships
```

---

## Adaptation by Target Type

### Person (default)
Use the schema as documented above. `biography` contains education and career_phases.

### Institution
Replace `biography` with:
```json
"institutional_profile": {
  "founded": "",
  "founding_purpose": "",
  "current_mandate": "",
  "governance_structure": "",
  "leadership_timeline": [],
  "scale": {},
  "evolution_phases": []
}
```

### Policy / Regulation
Replace `biography` with:
```json
"policy_profile": {
  "enacted": "",
  "jurisdiction": "",
  "original_intent": "",
  "mechanism": "",
  "amendments_timeline": [],
  "enforcement_body": "",
  "affected_population": ""
}
```

### Technology / Trend
Replace `biography` with:
```json
"technology_profile": {
  "origin": "",
  "key_milestones": [],
  "current_state": "",
  "adoption_curve_stage": "",
  "key_players": [],
  "dependencies": [],
  "competing_approaches": []
}
```

### Geopolitical Actor
Replace `biography` with:
```json
"actor_profile": {
  "type": "",
  "population": "",
  "gdp": "",
  "governance": "",
  "key_leaders": [],
  "strategic_position": "",
  "historical_phases": []
}
```

---

## Cross-Profile Queries

When you have multiple profiles, these queries enable intelligence fusion:

| Query Type | Method | Example |
|-----------|--------|---------|
| **Network overlap** | Compare `network.relationships[].person_or_entity` across profiles | "Do target A and B share connections?" |
| **Position alignment** | Match `positions.entries` by `topic` across profiles | "Do both agree on topic X?" |
| **Temporal correlation** | Compare position change dates across profiles | "Did they shift positions at the same time?" |
| **Scenario interaction** | Check if one profile's scenario is another's trigger | "Does A's Scenario 1 affect B's outlook?" |
| **Controversy overlap** | Compare `controversies[].critics` across profiles | "Are the same critics targeting both?" |
| **Influence chain** | Trace `network.relationships` transitively | "A → B → C — is there an influence path?" |

---

## Lifecycle Operations

### Create
Run the full deep-target-research skill → produce report.md + profile.json

### Update (same target, new research)
1. Load existing profile.json
2. Append new `positions.entries` (never delete old ones)
3. Append new `sources.entries` (continue ID numbering)
4. Run change detection on new positions vs. existing
5. Update `meta.last_updated` and `research_sessions`
6. Optionally revise `central_insight` and `forward_scenarios`

### Monitor (ongoing surveillance)
1. Periodically search for new statements/actions by the target
2. For each new finding, create a position entry
3. Diff against existing entries → populate `change_detection.log`
4. Alert if any flag = `CONTRADICTED` (this is the high-value signal)

### Archive
When a target becomes inactive (left office, company acquired, policy repealed):
1. Set a final `forward_scenarios` assessment (which scenario materialized?)
2. Write a final `change_detection` summary
3. Mark profile as `archived` in meta
4. Profile remains queryable for cross-reference but no longer monitored
