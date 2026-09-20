# Gainesville Resource Navigator

Streamlit MVP for helping Gainesville and Alachua County residents discover public resources worth investigating.

## Run locally

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

The app includes a small prepared demo fixture so Developer A can build and rehearse the experience before the data and matching lane is integrated.

## Developer B integration

Add `matcher.py` and `programs.json` beside `app.py` with the shared contract from the PRD:

```python
def load_programs(path: str = "programs.json") -> list[dict]: ...
def find_matches(user_profile: dict, programs: list[dict]) -> list[dict]: ...
```

The UI accepts either flat match objects or objects with a nested `program` payload. Each displayed result should include `name`, `category`, `description`, `status`, `score`, `matched_reasons`, `needs_verification`, `source_url`, and `last_checked`; `apply_url` is optional.

## Ownership

- Developer A: `app.py`, `styles.css`, `.streamlit/config.toml`, and the demo experience.
- Developer B: `matcher.py`, `programs.json`, and matcher tests.