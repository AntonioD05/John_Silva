# Gainesville Resource Navigator

A civic-resource discovery tool that helps Gainesville, Alachua County, and
Florida residents identify public programs worth investigating.

**[Open the live application](https://gainesville-resource-navigator.streamlit.app/)**

> This application provides general information and potential matches. It does
> not determine eligibility or provide legal or financial advice. Requirements
> and program availability may change; confirm all details with the administering
> agency.

## What it does

Users complete a short questionnaire about their household and circumstances.
The application then:

1. Runs the answers through a deterministic, explainable rules engine.
2. Returns only resources that pass the configured prescreen rules.
3. Explains which reported facts produced each potential match.
4. Lists conditions that still require verification by the agency.
5. Links directly to reviewed official source and application pages.
6. Optionally uses Gemini to organize the matches into a multilingual
   next-step guide.

The rules engine, not Gemini, decides which programs appear.

```text
Questionnaire
     |
     v
Deterministic matcher + reviewed program data
     |
     v
Explainable potential matches and official links
     |
     v
Optional Gemini organization/translation
```

## Included resources

- Supplemental Nutrition Assistance Program (SNAP)
- Florida Women, Infants, and Children (WIC)
- Florida KidCare
- Alachua County Veteran Services
- Alachua County Social Services
- Gainesville Housing & Community Development

SNAP and WIC use limited income and household prescreens based on the reviewed
data in `programs.json`. Other complex requirements remain clearly marked for
agency verification. ZIP matching is only a service-area prescreen; it does not
prove residency, jurisdiction, program availability, or eligibility.

## Explainable and responsible matching

Every returned result has a `possible_match` status and includes:

- A score based on matched prescreen signals
- Reasons derived from the user's answers
- Conditions that still need agency verification
- An official source URL
- An official application or contact URL when one is available
- The date the program information was last reviewed

The matcher never converts a prescreen result into a guarantee of eligibility.
Student rules, work requirements, deductions, assets, citizenship or qualified
noncitizen status, identity, insurance status, nutritional risk, program
availability, and other complex conditions remain with the administering agency.

## Optional Gemini next-step guide

After matches are displayed, users can request a guide in:

- English
- Spanish
- Haitian Creole

Gemini may organize the existing matches, suggest one concrete action per
resource, and generate a useful question for the agency. It cannot add or remove
programs, change official links, recalculate thresholds, or determine
eligibility. Generated output is validated before display.

Only program names, descriptions, verification notes, and whether an application
link exists are sent to Gemini. Raw questionnaire answers, exact income, ZIP
codes, and official URLs are not sent. If Gemini is unavailable or returns an
invalid response, the application uses a deterministic local fallback.

## Run locally

### Requirements

- Python 3.10 or newer
- A Gemini API key only if you want AI-generated guides

### Installation

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

The deterministic matcher and local next-step guide work without an API key.

To enable Gemini locally, create `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "replace-with-your-key"
```

Never commit this file or paste a real key into documentation. For deployment,
set `GEMINI_API_KEY` through Streamlit Community Cloud's Secrets settings.

## Run the tests

```powershell
python -m unittest discover -v
```

The test suite covers SNAP and WIC prescreens, larger and incomplete households,
service-area filtering, KidCare and veteran conditions, program-data validation,
Gemini response validation, privacy boundaries, and deterministic fallbacks.

## Project structure

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit questionnaire, result cards, and guide interface |
| `matcher.py` | Deterministic program loading, validation, and matching |
| `programs.json` | Reviewed program descriptions, rules, notes, and official links |
| `ai_guide.py` | Constrained Gemini integration and multilingual fallback |
| `styles.css` | Application styling |
| `test_matcher.py` | Matcher and program integration tests |
| `test_ai_guide.py` | Gemini safety, validation, and fallback tests |
| `.streamlit/config.toml` | Streamlit theme and server configuration |

## Design limitations

- The catalog is intentionally small and is not a complete directory of public
  assistance.
- Income checks are general prescreens, not official benefit calculations.
- ZIP-code checks approximate service areas and cannot verify residence or city
  and county jurisdiction.
- Program rules and availability can change after their recorded review date.
- Only the administering agency can make an eligibility decision.

## Technology

- Python
- Streamlit
- Google GenAI SDK
- JSON-based program definitions
- Python `unittest`
