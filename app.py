"""Gainesville Resource Navigator Streamlit application."""

from __future__ import annotations

import html
import json
from collections import defaultdict
from importlib import import_module
from pathlib import Path
from typing import Any

import streamlit as st


ROOT = Path(__file__).parent
DISCLAIMER = (
    "This tool provides general information and does not determine eligibility or "
    "provide legal or financial advice. Requirements and program availability may "
    "change. Confirm details with the administering agency."
)


def inject_styles() -> None:
    """Load the shared visual system without requiring a separate build step."""
    stylesheet = ROOT / "styles.css"
    if stylesheet.exists():
        st.markdown(
            f"<style>{stylesheet.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def demo_matches(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Provide a deterministic UI fixture until Developer B supplies the matcher."""
    matches = [
        {
            "program_id": "snap-demo",
            "name": "Supplemental Nutrition Assistance Program (SNAP)",
            "category": "Food",
            "description": "Monthly food assistance for eligible households through Florida DCF.",
            "status": "potential_match",
            "score": 4 if profile["annual_income"] < 40000 else 2,
            "matched_reasons": [
                "You live in Florida and reported a household size of "
                f"{profile['household_size'] }.",
                "Your reported income is worth checking against current SNAP limits.",
            ],
            "needs_verification": [
                "Student, work, and household-income rules may affect the final decision.",
            ],
            "source_name": "Florida Department of Children and Families",
            "source_url": "https://www.myflfamilies.com/assistance-services/food-stamp-program-snap",
            "apply_url": "https://www.myflorida.com/accessflorida/",
            "last_checked": "2026-09-20",
        },
        {
            "program_id": "kidcare-demo",
            "name": "Florida KidCare",
            "category": "Health",
            "description": "Low-cost health and dental coverage options for children.",
            "status": "potential_match" if profile["dependent_children"] else "possible_match",
            "score": 3 if profile["dependent_children"] else 1,
            "matched_reasons": [
                "Your profile indicates a household with children." if profile["dependent_children"] else "Florida KidCare is a broad resource for households to investigate.",
            ],
            "needs_verification": [
                "Coverage and premiums depend on child age, household income, and program availability.",
            ],
            "source_name": "Florida KidCare",
            "source_url": "https://www.floridakidcare.org/",
            "apply_url": "https://www.floridakidcare.org/apply",
            "last_checked": "2026-09-20",
        },
        {
            "program_id": "alachua-social-services-demo",
            "name": "Alachua County Social Services",
            "category": "Local support",
            "description": "A local starting point for county assistance and service referrals.",
            "status": "possible_match",
            "score": 2,
            "matched_reasons": ["You reported a Gainesville-area ZIP code."],
            "needs_verification": [
                "A county staff member will confirm which services fit your situation.",
            ],
            "source_name": "Alachua County",
            "source_url": "https://alachuacounty.us/Depts/CommunitySupportServices/SocialServices/Pages/SocialServices.aspx",
            "apply_url": "https://alachuacounty.us/Depts/CommunitySupportServices/Pages/CommunitySupportServices.aspx",
            "last_checked": "2026-09-20",
        },
    ]
    return matches


def get_matches(profile: dict[str, Any]) -> tuple[list[dict[str, Any]], bool, str | None]:
    """Call Developer B's contract when available, with a local UI fixture as fallback."""
    try:
        matcher = import_module("matcher")
        programs = matcher.load_programs(str(ROOT / "programs.json"))
        return matcher.find_matches(profile, programs), False, None
    except ModuleNotFoundError as error:
        if error.name != "matcher":
            raise
        return demo_matches(profile), True, None
    except FileNotFoundError:
        return demo_matches(profile), True, "Add programs.json to enable the curated program database."
    except Exception as error:  # Keep a data failure from taking down the demo.
        return [], False, f"The resource data could not be loaded: {error}"


def validate_profile(raw_profile: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    zip_code = str(raw_profile["zip_code"]).strip()
    if len(zip_code) != 5 or not zip_code.isdigit():
        errors.append("Enter a five-digit ZIP code.")
    if raw_profile["household_size"] < 1:
        errors.append("Household size must be at least 1.")
    if raw_profile["annual_income"] < 0:
        errors.append("Annual household income cannot be negative.")
    if raw_profile["dependent_children"] < 0:
        errors.append("Dependent children cannot be negative.")
    if raw_profile["dependent_children"] > raw_profile["household_size"]:
        errors.append("Dependent children cannot exceed household size.")
    if errors:
        return None, errors
    raw_profile["zip_code"] = zip_code
    return raw_profile, []


def render_header() -> None:
    st.markdown(
        """
        <div class="topline"><span class="mark">GR</span><span>Gainesville Resource Navigator</span><span class="topline-note">Civic tech prototype</span></div>
        <div class="hero">
            <div class="eyebrow">A clearer place to begin</div>
            <h1>Find support that may be waiting for you.</h1>
            <p>Answer a few practical questions. We will surface public programs worth investigating and show you where to verify the details.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_questionnaire() -> None:
    st.markdown('<div class="section-kicker">01 / Your situation</div>', unsafe_allow_html=True)
    st.markdown("### A short, private questionnaire")
    st.caption("No names, documents, Social Security numbers, or accounts are needed.")
    with st.form("resource_questionnaire"):
        first, second = st.columns(2)
        with first:
            zip_code = st.text_input("ZIP code", placeholder="32601", max_chars=5)
            age = st.number_input("Your age", min_value=0, max_value=120, value=29)
            annual_income = st.number_input("Annual household income (USD)", min_value=0, value=27000, step=1000, format="%d")
            household_size = st.number_input("Household size", min_value=1, max_value=20, value=3)
        with second:
            dependent_children = st.number_input("Dependent children", min_value=0, max_value=20, value=2)
            student_status = st.radio("Are you currently a student?", ["No", "Yes"], horizontal=True)
            employment_status = st.selectbox("Employment status", ["Employed", "Unemployed", "Part-time", "Not currently working", "Prefer not to say"])
            disability_status = st.radio("Do you have a disability?", ["No", "Yes", "Prefer not to say"], horizontal=True)
            veteran_status = st.radio("Are you a veteran?", ["No", "Yes"], horizontal=True)
        submitted = st.form_submit_button("Find resources", type="primary", use_container_width=True)

    if submitted:
        raw_profile = {
            "zip_code": zip_code,
            "age": age,
            "annual_income": annual_income,
            "household_size": household_size,
            "dependent_children": dependent_children,
            "student": student_status == "Yes",
            "employment_status": employment_status,
            "disability": disability_status == "Yes",
            "veteran": veteran_status == "Yes",
        }
        profile, errors = validate_profile(raw_profile)
        if errors:
            for error in errors:
                st.error(error)
            return
        st.session_state["profile"] = profile
        st.session_state["show_results"] = True


def normalize_match(match: dict[str, Any]) -> dict[str, Any]:
    """Accept either a flat result or a result containing a program payload."""
    program = match.get("program", {}) if isinstance(match.get("program"), dict) else {}
    merged = {**program, **match}
    return merged


def render_result_card(match: dict[str, Any]) -> None:
    match = normalize_match(match)
    status = "Potential match" if match.get("status") == "potential_match" else "Worth investigating"
    reasons = match.get("matched_reasons", [])
    notes = match.get("needs_verification", match.get("verification_notes", []))
    source_url = match.get("source_url", "#")
    apply_url = match.get("apply_url")
    name = html.escape(str(match.get("name", "Resource")))
    category = html.escape(str(match.get("category", "Resource")).title())
    description = html.escape(str(match.get("description", "A public resource you may want to investigate.")))
    reason_html = "".join(f"<li>{html.escape(str(reason))}</li>" for reason in reasons)
    note_html = "".join(f"<li>{html.escape(str(note))}</li>" for note in notes)
    st.markdown(
        f"""
        <article class="resource-card">
            <div class="card-meta"><span class="category">{category}</span><span class="status">{status}</span></div>
            <h3>{name}</h3>
            <p class="description">{description}</p>
            <details><summary>Why am I seeing this?</summary>
                <div class="explanation"><strong>Matched from your answers</strong><ul>{reason_html}</ul>
                <strong>Still needs verification</strong><ul>{note_html}</ul></div>
            </details>
            <div class="card-links"><a href="{html.escape(source_url)}" target="_blank">Official source &#8599;</a>
            {f'<a class="secondary-link" href="{html.escape(apply_url)}" target="_blank">Apply or contact &#8599;</a>' if apply_url else ''}</div>
            <div class="checked">Checked {html.escape(str(match.get('last_checked', 'date not provided')))}</div>
        </article>
        """,
        unsafe_allow_html=True,
    )


def render_results() -> None:
    profile = st.session_state.get("profile")
    if not profile:
        return
    st.markdown('<div class="section-kicker">02 / Your report</div>', unsafe_allow_html=True)
    matches, using_demo, load_error = get_matches(profile)
    if load_error:
        st.error(load_error)
    if using_demo:
        st.info("Showing prepared demo resources while the curated matcher is being added.")
    st.markdown("### Resources worth investigating")
    if not matches:
        st.markdown('<div class="empty-state"><strong>No clear matches yet.</strong><br>This does not mean you are ineligible for assistance. Try an official resource directory or contact a local service provider.</div>', unsafe_allow_html=True)
        return
    st.write(f"We found {len(matches)} resource{'s' if len(matches) != 1 else ''} that may be relevant to your situation.")
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for match in sorted(matches, key=lambda item: item.get("score", 0), reverse=True):
        grouped[str(normalize_match(match).get("category", "Other")).title()].append(match)
    for category, category_matches in grouped.items():
        st.markdown(f'<div class="category-heading">{html.escape(category)}</div>', unsafe_allow_html=True)
        for match in category_matches:
            render_result_card(match)


def main() -> None:
    st.set_page_config(page_title="Gainesville Resource Navigator", page_icon="GR", layout="wide", initial_sidebar_state="collapsed")
    inject_styles()
    render_header()
    render_questionnaire()
    if st.session_state.get("show_results"):
        st.divider()
        render_results()
        st.markdown(f'<div class="disclaimer"><strong>Please verify before relying on this information.</strong><br>{DISCLAIMER}</div>', unsafe_allow_html=True)
        if st.button("Start over"):
            st.session_state.clear()
            st.rerun()
    else:
        st.markdown('<div class="trust-row"><span>Private by design</span><span>Official sources</span><span>Plain-language explanations</span></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()