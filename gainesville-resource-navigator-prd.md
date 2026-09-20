# Gainesville Resource Navigator — Product Requirements Document

**Hackathon:** Gainesville Civic Tech  
**Build time:** 5 hours  
**Team:** 2 developers  
**Status:** Hackathon MVP  
**Working name:** Gainesville Resource Navigator

## 1. Product summary

Gainesville Resource Navigator helps Gainesville and Alachua County residents discover public assistance programs they may want to investigate.

Users answer a short questionnaire about their household, income, location, and circumstances. The app compares those answers with a small, curated database of government and nonprofit programs, then produces a personalized resource report explaining:

- Which programs may be relevant
- Why each program appeared
- What the program provides
- What the user should do next
- Where to verify eligibility or apply through an official source

The product does **not** make final eligibility decisions. It helps residents narrow a fragmented search into a clear, trustworthy action plan.

## 2. Problem

Assistance programs already exist, but residents often must:

- Know which agency or program to search for
- Navigate multiple city, county, state, and federal websites
- Interpret complicated eligibility language
- Determine which details apply to their circumstances
- Find the correct application or contact page

As a result, people may miss useful programs even when information is publicly available.

## 3. Goal

Within five hours, build and deploy a credible end-to-end prototype that lets a Gainesville resident:

1. Enter basic household information.
2. Receive several potentially relevant resource matches.
3. Understand why each result appeared.
4. Follow an official link to verify eligibility or take the next step.

### Success criteria

The MVP is successful if:

- A user can complete the questionnaire in under two minutes.
- The app returns results for at least three prepared test personas.
- Every result includes a plain-language explanation and official source.
- Changing a meaningful answer, such as income or student status, changes the results.
- The deployed demo can complete the full flow without errors.

## 4. Target user

### Primary user

A Gainesville or Alachua County resident who needs help but does not know which programs or agencies to investigate.

### Example persona

**Maria** is 29, lives in ZIP code 32601, earns $27,000 annually, and has a household of three with two children. She knows some assistance may exist but does not know whether to search city, county, state, or federal websites.

## 5. Product principles

1. **Helpful, not definitive:** Say “Potential match” or “You may want to investigate,” never “You qualify.”
2. **Transparent:** Explain exactly which answers caused a result to appear.
3. **Source-first:** Link every program to an authoritative page and show when its information was checked.
4. **Privacy-conscious:** Do not request names, Social Security numbers, documents, or accounts.
5. **Action-oriented:** Give the user a next step, not merely a list of program names.
6. **Deterministic core:** The rules engine selects programs. Any AI feature may explain results but must not invent or decide eligibility.

## 6. MVP scope

### User inputs

The initial form will collect:

- ZIP code
- Age
- Annual household income
- Household size
- Number of dependent children
- Student status
- Employment status
- Disability status
- Veteran status

If implementation time becomes tight, employment, disability, and veteran status may be removed unless an included program uses them.

### Program database

The MVP will contain **6–8 curated programs** across several categories. The final list depends on which programs the team can verify fastest from authoritative sources.

Candidate categories and programs:

| Category | Candidate program/resource |
| --- | --- |
| Food | SNAP |
| Children/families | WIC or Temporary Cash Assistance |
| Health | Medicaid or Florida KidCare |
| Utilities | LIHEAP or a local utility-assistance resource |
| Housing | Gainesville or Alachua County housing assistance |
| Local support | Alachua County Social Services |
| Education | Student-focused assistance resource |
| Veterans/disability | One official local, state, or federal resource if time permits |

Program data must be manually reviewed before inclusion. The team will not guess current income thresholds.

### Results

Each result card will show:

- Program name and category
- “Potential match” label
- One-sentence description
- “Why this appeared” explanation
- Criteria that matched
- Important conditions still requiring verification
- Official source link
- Application or contact link, when available
- Date last checked

### Disclaimer

Display this near the results:

> This tool provides general information and does not determine eligibility or provide legal or financial advice. Requirements and program availability may change. Confirm details with the administering agency.

## 7. Core user flow

1. User opens the landing page.
2. User reads a one-sentence explanation of the product.
3. User completes the questionnaire.
4. User selects **Find Resources**.
5. The matching engine evaluates the profile against curated rules.
6. The app displays a personalized resource report grouped by category.
7. User expands **Why am I seeing this?** for matched and uncertain criteria.
8. User follows an official source, application, or contact link.

## 8. Functional requirements

### FR-1: Questionnaire

- The app must validate required values.
- Household size must be at least 1.
- Income and dependent count cannot be negative.
- ZIP code must contain five digits.
- The form must not collect personally identifying information.

### FR-2: Geographic filtering

- Gainesville-only resources must appear only for configured Gainesville ZIP codes.
- Alachua County resources must appear only for configured county ZIP codes.
- Florida programs may appear for all supported local ZIP codes.

### FR-3: Rules-based matching

- The matcher must evaluate structured rules rather than keywords.
- It must return matched reasons, unmet rules, and rules requiring external verification.
- Programs may have three outcomes: `potential_match`, `possible_match`, or `not_shown`.
- A missing or unimplemented criterion must not be treated as proof of eligibility.

### FR-4: Explainable results

- Every displayed result must identify at least one matched user attribute.
- Uncertain criteria must be labeled separately from matched criteria.
- The wording must avoid guarantees of eligibility.

### FR-5: Sources and next steps

- Every program must include an authoritative source URL.
- When available, every program should include a separate application or contact URL.
- Every program must include a `last_checked` date.

### FR-6: Empty and error states

- If there are no matches, the app must explain that no result is not a denial of eligibility.
- If program data fails to load, the app must show a friendly error rather than crash.

## 9. Data model

Recommended `programs.json` structure:

```json
[
  {
    "id": "program_id",
    "name": "Program Name",
    "category": "food",
    "level": "state",
    "description": "Short plain-language description.",
    "service_area": ["Florida"],
    "rules": [
      {
        "field": "annual_income",
        "operator": "lte_by_household_size",
        "values": {
          "1": 0,
          "2": 0,
          "3": 0
        },
        "reason": "Your reported income appears within the listed range."
      }
    ],
    "verification_notes": [
      "The administering agency may apply additional requirements or deductions."
    ],
    "source_name": "Official Agency Name",
    "source_url": "https://official-source.example",
    "apply_url": "https://official-application.example",
    "last_checked": "2026-09-20"
  }
]
```

Only replace placeholder values with verified figures. If a rule is too complicated to model safely during the hackathon, use it as an uncertainty note rather than pretending the app has evaluated it.

## 10. Matching logic

For each program:

1. Check geography.
2. Evaluate every rule supported by the questionnaire.
3. Record each satisfied rule as a match reason.
4. Record complex or unavailable conditions as verification notes.
5. Do not display programs that clearly fail a required rule.
6. Rank stronger matches above broad informational resources.

Recommended result object:

```json
{
  "program_id": "program_id",
  "status": "potential_match",
  "score": 3,
  "matched_reasons": [
    "You live in the program's service area.",
    "Your household size was considered.",
    "Your reported income appears within the listed range."
  ],
  "needs_verification": [
    "The agency must verify income and other program-specific requirements."
  ]
}
```

The score is used only to order results. It must not be presented as an eligibility probability.

## 11. Screens and UX

### Screen 1: Welcome and questionnaire

**Headline:** Find Gainesville resources you may be missing  
**Supporting text:** Answer a few questions to discover public programs worth investigating.  
**Primary action:** Find Resources

### Screen 2: Resource report

**Headline:** Your Gainesville Resource Report  
**Summary:** We found X resources you may want to investigate.

Cards should be grouped by category and prioritize scanability. Each card contains:

- Category icon
- Program name
- Potential-match badge
- Short description
- Expandable explanation
- Official source button
- Apply or Contact button

### Empty state

> We did not find a clear match in our small resource database. This does not mean that you are ineligible for assistance. Check the listed official resource directories or contact a local service provider.

## 12. Technical approach

### Recommended stack

- **App and UI:** Streamlit
- **Language:** Python
- **Data:** Local JSON
- **Matching:** Plain Python functions
- **Deployment:** Streamlit Community Cloud
- **Version control:** GitHub

### Architecture

```text
Questionnaire
    ↓
Validated user profile
    ↓
Python rules engine ← programs.json
    ↓
Structured matches
    ↓
Explainable result cards + official links
```

No separate API or database is required for the MVP.

### Optional AI use

If the complete flow is already stable, an LLM may rewrite structured match reasons into friendlier language. The prompt must receive only verified program data and the rule engine's output. The app must still function if the AI call fails.

## 13. Two-person execution plan

To minimize merge conflicts, each person should own separate files.

### Developer A — App and experience

Primary files: `app.py`, styling/assets, `README.md`

- Create the Streamlit shell.
- Build and validate the questionnaire.
- Build result cards and category grouping.
- Add disclaimer, loading, empty, and error states.
- Deploy the app.
- Own final visual polish and demo flow.

### Developer B — Data and matching

Primary files: `programs.json`, `matcher.py`, `test_matcher.py`

- Research and verify 6–8 programs.
- Record official links and `last_checked` dates.
- Define the JSON schema.
- Implement geographic and program-rule checks.
- Return structured reasons and verification notes.
- Test the three demo personas.

### Shared interface contract

Agree on these two function shapes during the first 10 minutes:

```python
def find_matches(user_profile: dict, programs: list[dict]) -> list[dict]:
    ...

def load_programs(path: str = "programs.json") -> list[dict]:
    ...
```

Developer B should provide one hard-coded sample result immediately so Developer A can build the UI before the real matcher is complete.

## 14. Five-hour timeline

| Time | Developer A: App/UI | Developer B: Data/logic | Integration checkpoint |
| --- | --- | --- | --- |
| 0:00–0:15 | Create Streamlit layout and inputs | Create schema and candidate-program list | Agree on data fields, function contract, and Git ownership |
| 0:15–1:00 | Complete form and validation | Verify first 3–4 programs | App renders a mocked result |
| 1:00–2:00 | Build result cards and explanations | Finish 6–8 programs and basic matcher | First real result returned in app |
| 2:00–3:00 | Add grouping, disclaimer, empty/error states | Add geography, ranking, and test personas | Full happy path works locally |
| 3:00–3:45 | Visual polish and mobile check | Fix matching/data issues; verify every link | Feature freeze at 3:45 |
| 3:45–4:20 | Deploy and test public URL | Run persona tests on deployed build | Deployment stable |
| 4:20–5:00 | Rehearse demo and prepare pitch | Rehearse demo and prepare fallback screenshots | No new features; demo ready |

## 15. Test personas and acceptance results

### Persona A: Low-income family

- ZIP: 32601
- Age: 29
- Income: $27,000
- Household size: 3
- Dependents: 2
- Student: No

Expected behavior: multiple food, family/health, utility, housing, or local-support resources appear, depending on verified rules.

### Persona B: Student

- ZIP: 32608
- Age: 21
- Income: $8,000
- Household size: 1
- Dependents: 0
- Student: Yes

Expected behavior: student-relevant resources appear. Any SNAP result clearly states that separate student rules require verification.

### Persona C: Higher-income comparison

- Same profile as Persona A, but income changed to $55,000

Expected behavior: at least one income-based program disappears or moves to a weaker `possible_match` state. This profile powers the before-and-after demo.

## 16. Non-goals

The hackathon MVP will not include:

- A general government-web crawler
- Automated changes to eligibility rules
- A vector database or document-RAG system
- User accounts or saved profiles
- Collection of sensitive identifiers or documents
- Definitive eligibility determinations
- Automatic government-form submission
- Every available city, state, or federal program
- A mobile app
- A complex backend or production database

## 17. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Incorrect or outdated eligibility rules | Use authoritative sources, show `last_checked`, and model uncertain rules as verification notes |
| Overpromising eligibility | Use careful language and a visible disclaimer |
| Research consumes the build window | Cap the database at 6–8 well-sourced programs |
| Merge conflicts between two developers | Own different files and integrate through a fixed function contract |
| AI integration breaks the demo | Keep AI optional and retain deterministic explanations as the fallback |
| Deployment fails late | Deploy a minimal version by hour 3, then update it |
| Official site or link fails during judging | Keep one backup screenshot or recorded flow and verify links before feature freeze |

## 18. Demo plan

1. Introduce Maria and the difficulty of searching fragmented agency websites.
2. Complete the short questionnaire using her prepared profile.
3. Select **Find Resources**.
4. Show the personalized report and open **Why am I seeing this?**
5. Point out the official source, next step, and verification warning.
6. Change Maria's income from $27,000 to $55,000.
7. Rerun the matcher and show how the report changes.
8. Close with the product's purpose: discovery and navigation, not automated eligibility decisions.

## 19. One-sentence pitch

Gainesville Resource Navigator asks residents a few simple questions, identifies public programs worth investigating, explains why each one may be relevant, and connects users directly to trusted official sources.

## 20. Definition of done

Stop building when all of the following are true:

- The questionnaire submits successfully.
- At least 6 verified programs exist in `programs.json`.
- The matcher returns structured explanations.
- All three personas have been tested.
- Every result has an official source and `last_checked` date.
- The disclaimer is visible.
- The public demo URL works on a second device or incognito window.
- Both teammates can deliver the three-minute demo without relying on live coding.

