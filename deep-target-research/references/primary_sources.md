# Primary Source Intelligence — Deep Investigation Reference

## Philosophy

Web search tells you what **other people say** about the target. Primary source
investigation reveals what the target has **actually done** — in their own filings,
their legal record, their financial transactions, their corporate structures. This
layer is more neutral, more revealing, and harder to spin.

The goal is not to find dirt. The goal is to build a factual foundation that is
**independent of anyone's narrative** — then let the facts speak.

---

## Table of Contents

1. [Legal & Court Records](#1-legal--court-records)
2. [Financial Filings & SEC Records](#2-financial-filings--sec-records)
3. [Corporate Ownership & Structure](#3-corporate-ownership--structure)
4. [Political Donations & Lobbying](#4-political-donations--lobbying)
5. [Nonprofit & Foundation Records](#5-nonprofit--foundation-records)
6. [Government Records & Contracts](#6-government-records--contracts)
7. [Academic & Intellectual Record](#7-academic--intellectual-record)
8. [Regulatory & Licensing Records](#8-regulatory--licensing-records)
9. [International Records](#9-international-records)
10. [Primary Document Retrieval](#10-primary-document-retrieval)
11. [Investigation Playbooks by Target Type](#11-investigation-playbooks-by-target-type)
12. [Analytical Techniques for Primary Data](#12-analytical-techniques-for-primary-data)
13. [Ethical Boundaries](#13-ethical-boundaries)

---

## 1. Legal & Court Records

### What They Reveal
Lawsuits, bankruptcies, criminal records, regulatory enforcement actions, divorce
proceedings (sometimes), restraining orders, patent disputes. Legal records reveal
conflicts, disputes, and behavior under pressure — often things the target would
prefer not to discuss.

### Sources

**Federal Courts (US):**
- **PACER** (Public Access to Court Electronic Records)
  - URL: https://pacer.uscourts.gov
  - Covers: All federal civil, criminal, bankruptcy cases
  - Search: By party name, case number, date range
  - Query via web_search: `site:pacer.uscourts.gov "[Target Name]"` or
    `"[Target Name]" federal court case filing`

- **RECAP Archive** (free PACER mirror by Free Law Project)
  - URL: https://www.courtlistener.com/recap/
  - Search: https://www.courtlistener.com — free full-text search of millions of PACER docs
  - Query: `site:courtlistener.com "[Target Name]"`

**State Courts:**
- Each state has its own system. Major ones:
  - New York: https://iapps.courts.state.ny.us/webcivil/ECBSearch (eCourts)
  - California: https://www.courts.ca.gov/find-my-court.htm
  - Delaware (corporate law): https://courts.delaware.gov/chancery/
  - Florida: Various by county, many have online portals
- Query via web_search: `"[Target Name]" [state] court case` or
  `"[Target Name]" lawsuit plaintiff defendant`

**SEC Enforcement:**
- URL: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=LIT&dateb=&owner=include
- Also: https://efts.sec.gov/LATEST/search-index?q=%22Target+Name%22
- Query: `"[Target Name]" SEC enforcement action settlement consent decree`

**FINRA (Financial Industry):**
- **BrokerCheck**: https://brokercheck.finra.org/
  - Covers: Any registered broker/dealer — disciplinary history, customer complaints,
    regulatory actions, employment history, disclosures
  - Essential for anyone who has ever held a securities license
- Query: `"[Target Name]" FINRA brokercheck disciplinary`

### What to Look For
- Was the target ever a plaintiff? (reveals what they fight about)
- Was the target ever a defendant? (reveals what they've been accused of)
- Were there settlements? (amounts and terms often indicate severity)
- Any pattern? (multiple suits in same area = systematic behavior)
- Bankruptcy filings? (both personal and related companies)
- Any sealed or expunged records mentioned in other sources?

---

## 2. Financial Filings & SEC Records

### What They Reveal
Insider trading activity, executive compensation, related-party transactions,
conflicts of interest, financial health of companies they control, who they
do business with, and how they structure deals.

### Sources

**SEC EDGAR (Electronic Data Gathering, Analysis, and Retrieval):**
- Full-text search: https://efts.sec.gov/LATEST/search-index?q=%22Target+Name%22
- Company filings: https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=&type=&dateb=&owner=include&count=40&search_text=&action=getcompany
- Query: `site:sec.gov "[Target Name]"` or `"[Target Name]" SEC filing EDGAR`

**Key Filing Types to Search:**

| Filing | What It Reveals | When to Look |
|--------|----------------|--------------|
| **10-K / 10-Q** | Annual/quarterly reports of companies they lead | Target is CEO/executive |
| **DEF 14A (Proxy)** | Executive compensation, board composition, related-party transactions | Target is executive or board member |
| **13F** | Quarterly holdings of institutional investors (≥$100M AUM) | Target manages money |
| **Schedule 13D/13G** | Beneficial ownership >5% of a public company | Target is major shareholder |
| **Form 4** | Insider buying/selling of company stock | Target is officer/director |
| **Form 3** | Initial insider ownership disclosure | When target joins a company |
| **8-K** | Material events (mergers, departures, lawsuits, etc.) | Company target is affiliated with |
| **Form ADV** | Investment adviser registration and disclosures | Target runs an investment firm |
| **S-1 / F-1** | IPO prospectus — reveals detailed business history | Company going public |

**Insider Trading Analysis:**
- Track Form 4 filings: Did the target sell before bad news? Buy before good news?
- Pattern analysis: Consistent selling over time vs. sudden large sales
- Query: `"[Target Name]" Form 4 insider transaction sell buy`
- Tool: https://www.secform4.com/ or https://openinsider.com/

**Proxy Statement Deep Dive (DEF 14A):**
- Executive compensation details (base, bonus, stock, perks)
- Related-party transactions (does the company do business with target's other entities?)
- Board committee memberships (audit, compensation, nominating)
- Shareholder proposals and votes (reveals governance conflicts)

### What to Look For
- **Compensation vs. performance** — is the target paid well while the company underperforms?
- **Related-party transactions** — does the target or their family do business with entities they control?
- **Insider selling patterns** — are they selling stock before downturns?
- **Multiple board seats** — do they sit on boards of companies that do business with each other?
- **Golden parachutes** — what's the exit package structure?

---

## 3. Corporate Ownership & Structure

### What They Reveal
What companies the target controls, how entities are structured (LLCs, trusts,
holding companies), potential tax structures, related parties, and the web of
entities that may not be obviously connected to the target.

### Sources

**US State Registries:**
- Each state has a Secretary of State business search
- Delaware (most common for corporations): https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx
- Nevada: https://esos.nv.gov/EntitySearch/OnlineEntitySearch
- Wyoming: https://wyobiz.wyo.gov/Business/FilingSearch.aspx
- Query: `"[Target Name]" [state] secretary of state business registration`
- Also search for entities at the target's known address

**OpenCorporates (global):**
- URL: https://opencorporates.com/
- Covers: 200M+ companies across jurisdictions worldwide
- Query: `site:opencorporates.com "[Target Name]"`

**Property Records:**
- County assessor/recorder databases (varies by county)
- Zillow/Redfin for recent transactions (residential)
- Query: `"[Target Name]" property records [county] [state]`

**UCC Filings (Uniform Commercial Code):**
- Secured transactions — reveals loans, liens, and collateral
- State-level search, often through Secretary of State
- Query: `"[Target Name]" UCC filing lien`

### What to Look For
- **Shell companies** — entities with minimal public footprint that share addresses/agents with target
- **Entity web** — how many LLCs, trusts, holding companies are connected?
- **Registered agent overlap** — do multiple entities share the same registered agent?
- **Address overlap** — entities registered at the same address as other target-linked entities
- **Timing** — were entities created just before or after significant events?

---

## 4. Political Donations & Lobbying

### What They Reveal
Political alignment, access-buying patterns, lobbying priorities, bundling activity,
and whether stated public positions match where they actually put money.

### Sources

**Federal Elections Commission (FEC):**
- Individual contributions: https://www.fec.gov/data/receipts/individual-contributions/
- Query: `site:fec.gov "[Target Name]"` or search directly on FEC site
- Covers: All federal political contributions >$200

**OpenSecrets (Center for Responsive Politics):**
- URL: https://www.opensecrets.org/
- Donor lookup: https://www.opensecrets.org/donor-lookup
- Covers: Contributions, lobbying, bundling, revolving door
- Query: `site:opensecrets.org "[Target Name]"`

**Senate/House Lobbying Disclosure:**
- URL: https://lda.senate.gov/filings/public/filing/search/
- Query: `"[Target Name]" lobbying disclosure filing`

**State-Level Donations:**
- FollowTheMoney: https://www.followthemoney.org/
- Covers: State-level campaign contributions

### What to Look For
- **Partisan pattern** — do they donate to both parties or only one?
- **Access donations** — contributions to members of committees that regulate their industry
- **Timing** — donations that coincide with pending legislation or regulatory decisions
- **Bundling** — organizing donations from others (signals political influence)
- **Lobbying spend** — how much do their companies spend on lobbying, and on what issues?
- **Revolving door** — did they move between government and industries they regulated?

---

## 5. Nonprofit & Foundation Records

### What They Reveal
Philanthropic interests (genuine and strategic), board affiliations, compensation
from nonprofits, related-party transactions through charitable entities, and
influence networks in the nonprofit sector.

### Sources

**IRS Form 990 (tax-exempt organization returns):**
- **ProPublica Nonprofit Explorer**: https://projects.propublica.org/nonprofits/
- **GuideStar/Candid**: https://www.guidestar.org/
- Covers: Revenue, expenses, executive compensation, board members, grants made/received
- Query: `site:propublica.org/nonprofits "[Target Name]"` or
  `"[Target Name]" Form 990 nonprofit foundation`

**Foundation Directory:**
- Search for grants made by foundations the target controls
- Query: `"[Target Name] Foundation" grants 990`

### What to Look For
- **Compensation** — is the target paid by nonprofits they control?
- **Self-dealing** — does the foundation do business with the target's for-profit entities?
- **Grant patterns** — who receives grants? Are recipients connected to the target's interests?
- **Board overlap** — do the same people appear across the target's for-profit and nonprofit entities?

---

## 6. Government Records & Contracts

### What They Reveal
Government contracts, spending, financial disclosures of public officials,
inspector general reports, and official correspondence obtained through FOIA.

### Sources

**Government Spending:**
- USAspending.gov: https://www.usaspending.gov/ — all federal contracts and grants
- FPDS (Federal Procurement Data System): https://www.fpds.gov/
- Query: `site:usaspending.gov "[Target Name]"` or `"[Company Name]" federal contract`

**Financial Disclosures (for government officials):**
- Executive branch: https://extapps2.oge.gov/201/Presiden.nsf
- Congressional: https://efdsearch.senate.gov/ and https://disclosures-clerk.house.gov/
- Federal judges: https://fixthecourt.com/fix/financial-disclosures/
- Query: `"[Target Name]" financial disclosure OGE`

**FOIA Reading Rooms:**
- Many agencies maintain online reading rooms of previously released FOIA documents
- Query: `"[Target Name]" FOIA reading room [agency]`

**Inspector General Reports:**
- Each major agency has an IG: https://www.ignet.gov/
- Query: `"[Target Name]" inspector general report`

**Congressional Record:**
- URL: https://www.congress.gov/congressional-record
- Hearings: https://www.congress.gov/committee-schedule
- Query: `"[Target Name]" congressional testimony hearing`

### What to Look For
- **Government contracts to affiliated companies** — conflict of interest
- **Financial disclosure gaps** — omitted assets, late filings
- **Revolving door timing** — when did they leave government? When did they join industry?
- **Congressional testimony** — what did they promise under oath vs. what they actually did?

---

## 7. Academic & Intellectual Record

### What They Reveal
Actual expertise depth, intellectual influences, peer recognition, collaborative
networks, and whether claimed expertise is backed by real work.

### Sources

**Publication Record:**
- Google Scholar: https://scholar.google.com/
- Semantic Scholar: https://www.semanticscholar.org/
- SSRN: https://papers.ssrn.com/ (social science/law/economics)
- NBER: https://www.nber.org/ (economics working papers)
- Query: `"[Target Name]" author site:scholar.google.com`

**Patent Record:**
- USPTO: https://patft.uspto.gov/
- Google Patents: https://patents.google.com/
- Query: `"[Target Name]" inventor patent`

**Dissertation/Thesis:**
- ProQuest Dissertations: https://www.proquest.com/dissertations-theses
- Query: `"[Target Name]" dissertation thesis`

**Speaking Record:**
- Conference programs, lecture series archives
- Query: `"[Target Name]" keynote speech conference transcript`

### What to Look For
- **Publication count and quality** — do they actually publish, or just claim expertise?
- **Citation count** — are they cited by others? (peer recognition)
- **Co-author network** — who do they collaborate with? (intellectual tribe)
- **Patent portfolio** — do they actually invent, or is it strategic filing?
- **Gap between credentials and output** — if they hold a position that implies
  expertise, is there published work to back it up?

---

## 8. Regulatory & Licensing Records

### What They Reveal
Professional standing, disciplinary actions, compliance history, and whether
they are authorized to do what they claim.

### Sources

**Financial Industry:**
- FINRA BrokerCheck: https://brokercheck.finra.org/
- SEC Investment Adviser search: https://adviserinfo.sec.gov/
- NFA (futures): https://www.nfa.futures.org/basicnet/

**Legal Profession:**
- State bar associations — each state maintains a directory with disciplinary history
- Query: `"[Target Name]" bar association [state] disciplinary`

**Medical/Healthcare:**
- State medical boards
- National Practitioner Data Bank (limited public access)
- Medicare provider data: https://data.cms.gov/

**Real Estate:**
- State real estate commission records
- Query: `"[Target Name]" real estate license [state]`

**General Professional Licenses:**
- Query: `"[Target Name]" professional license [industry] [state]`

### What to Look For
- **Active vs. inactive license** — did they let certifications lapse?
- **Disciplinary actions** — warnings, suspensions, revocations
- **Customer complaints** — pattern of complaints in same area
- **Employment history gaps** — periods not accounted for in official records

---

## 9. International Records

### What They Reveal
Global business activities, offshore structures, international legal proceedings,
sanctions exposure, and connections that may not be visible in US records alone.

### Sources

**Corporate Registries (key jurisdictions):**
- UK: Companies House — https://www.gov.uk/get-information-about-a-company (free, excellent)
- EU: European Business Register — https://www.ebr.org/
- Hong Kong: https://www.icris.cr.gov.hk/
- Singapore: https://www.acra.gov.sg/
- Cayman Islands: https://www.ciipa.ky/ (limited)
- BVI: Very limited public access

**Sanctions & Watchlists:**
- OFAC (US Treasury): https://sanctionssearch.ofac.treas.gov/
- EU Sanctions Map: https://www.sanctionsmap.eu/
- UN Sanctions: https://www.un.org/securitycouncil/sanctions
- Query: `"[Target Name]" sanctions OFAC SDN list`

**Offshore Leaks Database (ICIJ):**
- URL: https://offshoreleaks.icij.org/
- Covers: Panama Papers, Paradise Papers, Pandora Papers, etc.
- Search by name for offshore entities, intermediaries, beneficiaries
- Query: `site:offshoreleaks.icij.org "[Target Name]"`

**International Court Records:**
- ICC: https://www.icc-cpi.int/
- ECHR: https://hudoc.echr.coe.int/
- WTO disputes: https://www.wto.org/english/tratop_e/dispu_e/dispu_e.htm

### What to Look For
- **Offshore entities** — legitimate tax planning or opacity?
- **Sanctions proximity** — do they do business with sanctioned entities?
- **Multi-jurisdictional structures** — why are entities in specific jurisdictions?
- **International litigation** — disputes that don't show up in US courts

---

## 10. Primary Document Retrieval

### Technique: Go to the Source

When web_search surfaces a reference to a primary document (court filing, SEC form,
congressional testimony, speech transcript), **always** attempt to retrieve the
actual document using web_fetch. Third-party summaries introduce interpretation drift.

### Priority Documents to Retrieve

| Document Type | Why It Matters | How to Fetch |
|--------------|----------------|-------------|
| Confirmation hearing transcript | Target's own words under oath | congress.gov or committee website |
| FOMC/board meeting transcripts | What they actually said vs. public messaging | federalreserve.gov (5-year delay) |
| SEC filings (DEF 14A, 13F, Form 4) | Financial interests, compensation, trades | EDGAR full-text search |
| Court complaints/opinions | Specific allegations and judicial findings | CourtListener / PACER |
| Authored speeches (full text) | Their intellectual framework unfiltered | Institutional websites |
| Op-eds (full text) | Carefully composed public positions | Publication archives |
| Financial disclosures | Assets, income, potential conflicts | OGE or congressional disclosure sites |
| IRS 990 forms | Foundation/nonprofit financial activity | ProPublica Nonprofit Explorer |
| FEC contribution records | Actual political spending | FEC data portal |
| Patent filings | Actual inventive work | Google Patents / USPTO |

### Retrieval Protocol
1. Identify the primary source URL from web_search results or known databases
2. Use `web_fetch` to retrieve the full document
3. Extract the key factual claims — dates, amounts, names, relationships
4. Record these as **primary-sourced** position entries in the dossier
   (tag source type as "primary" — higher trust than journalistic sources)

---

## 11. Investigation Playbooks by Target Type

### Financial Professional (Banker, Fund Manager, Trader)
```
Priority Sources:
1. FINRA BrokerCheck — full employment and disciplinary history
2. SEC EDGAR — Form ADV (adviser), 13F (holdings), Form 4 (insider trades)
3. SEC enforcement actions — any regulatory trouble
4. Court records — investor lawsuits, SEC actions
5. FEC — political donation patterns
6. OpenSecrets — lobbying activity
7. Corporate registries — entities they control
8. Proxy statements — compensation at public companies

Key Questions:
- What is their actual investment track record vs. claimed?
- Any regulatory actions or customer complaints?
- Insider trading patterns — buying/selling before major events?
- What entities do they control and how are they structured?
```

### Attorney / Legal Professional
```
Priority Sources:
1. State bar records — disciplinary history, active status
2. Court records (CourtListener) — cases they've litigated
3. SEC filings — if they advise public companies
4. Lobbying disclosures — if they lobby
5. Published opinions/articles — legal scholarship
6. FEC — political donations (often aligned with client interests)

Key Questions:
- Win/loss record in significant cases?
- Any bar disciplinary actions?
- Pattern in client representation — who do they repeatedly serve?
- Any conflicts between public positions and client interests?
```

### Tech Executive / Founder
```
Priority Sources:
1. SEC EDGAR — if public company (10-K, proxy, insider trades)
2. Patent filings — actual inventive contribution
3. Crunchbase / PitchBook — funding history, board seats, investments
4. GitHub / open-source contributions — actual technical work (if applicable)
5. Court records — IP lawsuits, employment disputes, antitrust
6. FEC / lobbying — political spending and lobbying priorities
7. H-1B employer data — hiring patterns (if relevant)

Key Questions:
- Is their technical reputation backed by actual patents/code/publications?
- Insider trading patterns — selling before bad quarters?
- How is their compensation structured relative to shareholder returns?
- What has been litigated — IP theft, employment, antitrust?
```

### Military / Intelligence Official
```
Priority Sources:
1. Congressional testimony transcripts — statements under oath
2. Financial disclosures (if senior) — OGE filings
3. Inspector General reports — any investigations involving them
4. FOIA releases — declassified documents related to their activities
5. Published writings — war college papers, journal articles, doctrinal contributions
6. Medal/award citations — official recognition of what they actually did
7. Post-service employment — revolving door to defense contractors

Key Questions:
- What did they actually do vs. what their biography claims?
- Any IG investigations?
- Post-service employer — conflict with decisions made while in service?
- Congressional testimony — did subsequent events contradict their testimony?
```

### Politician / Government Official
```
Priority Sources:
1. FEC — all contributions (given and received)
2. Financial disclosures — assets, income, outside positions
3. Voting record — congress.gov (compare votes to stated positions)
4. Lobbying disclosures — who lobbies them, and on what
5. Committee assignments — do they oversee industries they're connected to
6. Earmarks / directed spending — who benefits
7. Post-office employment — where do they go after leaving government
8. Court records — any legal issues

Key Questions:
- Do their votes match their stated positions?
- Who donates to them, and do their votes align with donor interests?
- Financial disclosure anomalies — unexplained wealth changes?
- Revolving door — did they regulate industries they later joined?
```

### Scientist / Academic
```
Priority Sources:
1. Publication record — Google Scholar, Semantic Scholar, PubMed
2. Funding sources — NIH RePORTER, NSF award search, grant acknowledgments
3. Patent filings — commercial applications of research
4. Retraction Watch — any retracted or corrected papers
5. Conflict of interest disclosures — in published papers
6. University records — title, tenure status, departmental affiliations
7. Expert witness history — court records (Daubert challenges)

Key Questions:
- Is their citation count genuine or self-citation inflated?
- Funding sources — do they create conflicts with research conclusions?
- Any retractions, corrections, or reproducibility failures?
- Industry consulting — do they advise companies their research evaluates?
```

---

## 12. Analytical Techniques for Primary Data

### Technique: Follow the Money
For any target with financial records, trace the capital flow:
1. Where does their income come from? (salary, investments, board fees, speaking fees)
2. Where does their money go? (donations, investments, entities they control)
3. Do the inflows and outflows tell a different story than their public narrative?

### Technique: Timeline Juxtaposition
Place primary source events on the same timeline as public statements:
```
[Date] Target says "I believe in X" (speech)
[Date + 2 weeks] Target's company files Form 4 showing stock sale (SEC filing)
[Date + 1 month] Bad news emerges about the company (press)
```
This reveals gaps between words and actions that journalistic sources may not catch.

### Technique: Entity Web Mapping
For targets with complex corporate structures:
1. Start with known entities (from SEC filings, business registrations)
2. Look up each entity's registered agent and address
3. Search for OTHER entities at the same address or with the same agent
4. Map the full web — often reveals entities not publicly associated with the target

### Technique: Peer Comparison
Compare the target's primary records against peers in the same role:
- Is their insider selling pattern unusual for their industry?
- Is their compensation higher/lower than comparable executives?
- Is their litigation frequency normal for their profession?
- Is their donation pattern typical for their wealth level?
Without peer comparison, isolated data points lack meaning.

### Technique: Absence Detection
Sometimes the most revealing finding is what's MISSING:
- A financial professional with no FINRA record — why not?
- A published scholar with no citations — why not?
- A government official whose financial disclosure is late — why?
- A company with no 10-K filed on time — what's happening?
- A target who claims expertise in X but has zero publications — really?

---

## 13. Ethical Boundaries

### Always
- Use only **publicly accessible** records and databases
- Attribute sources clearly in the dossier
- Present findings neutrally — raw data before interpretation
- Note when records are absent (could mean "clean" OR "not yet found")
- Distinguish between allegations (lawsuit filed) and findings (court ruled)

### Never
- Access password-protected systems without authorization
- Misrepresent identity to obtain records
- Conflate accusations with proven facts
- Use personal information (home address, family members' private details)
  in ways that could endanger the target
- Make legal conclusions — "this might be illegal" is for lawyers, not analysts

### Always Flag
- When a record is an **allegation** vs. a **finding** (sued vs. found liable)
- When a record is **sealed** or **expunged** and referenced only indirectly
- When absence of records could mean "clean" or "records not digitized"
- When a data source has known limitations or biases
