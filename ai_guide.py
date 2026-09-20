"""Optional Gemini-powered next-step guides with a deterministic fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from typing import Any


SUPPORTED_LANGUAGES = ("English", "Spanish", "Haitian Creole")
DEFAULT_MODEL = "gemini-3.8-flash"
CACHE_TTL_SECONDS = 3_600
CACHE_MAX_ENTRIES = 128

LOGGER = logging.getLogger(__name__)
_GUIDE_CACHE: dict[str, tuple[float, str]] = {}
_GUIDE_CACHE_LOCK = threading.Lock()

SYSTEM_INSTRUCTION = """
You organize and translate a deterministic list of public resources.

Include every supplied program exactly once. Order the programs by the most
immediate and concrete action the user can take, not by likelihood of
eligibility. Use only the supplied facts and write every user-facing string in
the requested language.

Do not add or remove programs. Do not determine, promise, or imply eligibility.
Do not recalculate income limits. Do not invent requirements, documents,
deadlines, contacts, phone numbers, or URLs. Do not give legal or financial
advice. Do not describe the ordering as an eligibility ranking.

For each program, provide one specific practical next action that is meaningfully
different from the other steps and one program-specific question for the
administering agency. Refer to the supplied verification notes when useful. Do
not use generic filler such as "review the next steps" or repeat the same
question for multiple programs. End with a reminder that only the administering
agencies can determine eligibility and current availability.
""".strip()

FALLBACK_TEXT = {
    "English": {
        "introduction": "Use this checklist to investigate each resource. The order does not indicate eligibility.",
        "apply_action": "Open the official application or contact page and review the next steps.",
        "source_action": "Review the official program page and contact the agency about next steps.",
        "question": "Which current requirements, documents, and services apply to my situation?",
        "reminder": "Only the administering agencies can determine eligibility and current availability.",
    },
    "Spanish": {
        "introduction": "Use esta lista para investigar cada recurso. El orden no indica elegibilidad.",
        "apply_action": "Abra la página oficial de solicitud o contacto y revise los próximos pasos.",
        "source_action": "Revise la página oficial del programa y comuníquese con la agencia sobre los próximos pasos.",
        "question": "¿Qué requisitos, documentos y servicios actuales corresponden a mi situación?",
        "reminder": "Solo las agencias administradoras pueden determinar la elegibilidad y disponibilidad actual.",
    },
    "Haitian Creole": {
        "introduction": "Sèvi ak lis sa a pou verifye chak resous. Lòd la pa vle di ou kalifye.",
        "apply_action": "Louvri paj aplikasyon oswa kontak ofisyèl la epi verifye pwochen etap yo.",
        "source_action": "Revize paj ofisyèl pwogram nan epi kontakte ajans lan pou pwochen etap yo.",
        "question": "Ki kondisyon, dokiman, ak sèvis ki disponib kounye a ki aplike nan sitiyasyon mwen?",
        "reminder": "Se sèlman ajans ki administre pwogram yo ki ka detèmine kalifikasyon ak disponiblite aktyèl.",
    },
}

FALLBACK_PROGRAM_TEXT = {
    "English": {
        "florida-snap": {
            "action": "Use the official MyACCESS link to begin or review a SNAP application, and be ready to describe your household members and income.",
            "question": "Which deductions, work rules, or student rules should be reviewed for my household?",
        },
        "florida-wic": {
            "action": "Contact the local WIC office to request an appointment for its income and nutritional-risk assessment.",
            "question": "How should unborn babies be counted in my household size, and what happens at the nutritional-risk assessment?",
        },
        "alachua-county-veteran-services": {
            "action": "Contact an Alachua County Veteran Service Officer to review the benefits connected to your service.",
            "question": "Which benefits should we investigate based on my service, discharge, and dependent or survivor status?",
        },
        "florida-kidcare": {
            "action": "Open the Florida KidCare application and review coverage options for each dependent child.",
            "question": "Which KidCare program could cover my child based on age, current insurance, household size, and income?",
        },
        "alachua-county-social-services": {
            "action": "Complete the county's official application screener to identify currently available assistance and referral options.",
            "question": "Which temporary-assistance or referral programs are currently available for my household circumstances?",
        },
        "gainesville-housing-community-development": {
            "action": "Review the city's housing program page and contact the department to learn which programs are currently open.",
            "question": "Which open program fits my housing situation, location, and renter or homeowner status?",
        },
    },
    "Spanish": {
        "florida-snap": {
            "action": "Use el enlace oficial de MyACCESS para iniciar o revisar una solicitud de SNAP y prepárese para describir los miembros e ingresos de su hogar.",
            "question": "¿Qué deducciones y reglas de trabajo o de estudiantes deben revisarse para mi hogar?",
        },
        "florida-wic": {
            "action": "Comuníquese con la oficina local de WIC para solicitar una cita para la evaluación de ingresos y riesgo nutricional.",
            "question": "¿Cómo se cuentan los bebés por nacer en el tamaño de mi hogar y qué ocurre durante la evaluación de riesgo nutricional?",
        },
        "alachua-county-veteran-services": {
            "action": "Comuníquese con un oficial de Servicios para Veteranos del condado de Alachua para revisar los beneficios relacionados con su servicio.",
            "question": "¿Qué beneficios debemos investigar según mi servicio, baja y condición de dependiente o sobreviviente?",
        },
        "florida-kidcare": {
            "action": "Abra la solicitud de Florida KidCare y revise las opciones de cobertura para cada menor dependiente.",
            "question": "¿Qué programa de KidCare podría cubrir a mi hijo según su edad, seguro actual, tamaño del hogar e ingresos?",
        },
        "alachua-county-social-services": {
            "action": "Complete el evaluador oficial de solicitudes del condado para identificar opciones actuales de asistencia y referidos.",
            "question": "¿Qué programas de asistencia temporal o referidos están disponibles actualmente para las circunstancias de mi hogar?",
        },
        "gainesville-housing-community-development": {
            "action": "Revise la página de programas de vivienda de la ciudad y comuníquese con el departamento para saber cuáles están abiertos.",
            "question": "¿Qué programa abierto corresponde a mi situación de vivienda, ubicación y condición de inquilino o propietario?",
        },
    },
    "Haitian Creole": {
        "florida-snap": {
            "action": "Sèvi ak lyen ofisyèl MyACCESS la pou kòmanse oswa revize yon aplikasyon SNAP, epi prepare enfòmasyon sou moun ak revni nan kay la.",
            "question": "Ki dediksyon ak règ travay oswa etidyan yo dwe revize pou kay mwen an?",
        },
        "florida-wic": {
            "action": "Kontakte biwo WIC lokal la pou mande yon randevou pou evalyasyon revni ak risk nitrisyonèl la.",
            "question": "Kijan tibebe ki poko fèt konte nan kantite moun nan kay la, epi kisa ki fèt nan evalyasyon risk nitrisyonèl la?",
        },
        "alachua-county-veteran-services": {
            "action": "Kontakte yon ajan Sèvis Veteran Konte Alachua pou revize avantaj ki gen rapò ak sèvis ou.",
            "question": "Ki avantaj nou ta dwe verifye selon sèvis mwen, kalite separasyon mwen, ak estati depandan oswa sivivan?",
        },
        "florida-kidcare": {
            "action": "Louvri aplikasyon Florida KidCare la epi revize chwa kouvèti pou chak timoun depandan.",
            "question": "Ki pwogram KidCare ki ta ka kouvri pitit mwen selon laj, asirans aktyèl, kantite moun nan kay la, ak revni?",
        },
        "alachua-county-social-services": {
            "action": "Ranpli zouti evalyasyon aplikasyon ofisyèl konte a pou idantifye asistans ak referans ki disponib kounye a.",
            "question": "Ki pwogram asistans tanporè oswa referans ki disponib kounye a pou sitiyasyon kay mwen an?",
        },
        "gainesville-housing-community-development": {
            "action": "Revize paj pwogram lojman vil la epi kontakte depatman an pou konnen ki pwogram ki ouvè kounye a.",
            "question": "Ki pwogram ouvè ki koresponn ak sitiyasyon lojman mwen, kote mwen rete, ak estati lokatè oswa pwopriyetè mwen?",
        },
    },
}


def _normalize_language(language: str) -> str:
    return language if language in SUPPORTED_LANGUAGES else "English"


def build_fallback_guide(
    matches: list[dict[str, Any]], language: str = "English"
) -> dict[str, Any]:
    """Build a useful guide without an external service."""
    selected_language = _normalize_language(language)
    text = FALLBACK_TEXT[selected_language]
    program_text = FALLBACK_PROGRAM_TEXT[selected_language]
    return {
        "introduction": text["introduction"],
        "steps": [
            {
                "program_id": str(match.get("program_id", "")),
                "action": program_text.get(str(match.get("program_id")), {}).get(
                    "action",
                    text["apply_action"] if match.get("apply_url") else text["source_action"],
                ),
                "question_to_ask": program_text.get(
                    str(match.get("program_id")), {}
                ).get("question", text["question"]),
            }
            for match in matches
            if match.get("program_id")
        ],
        "reminder": text["reminder"],
    }


def _safe_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Minimize data sent externally and deliberately omit profiles and URLs."""
    return [
        {
            "program_id": str(match.get("program_id", "")),
            "name": str(match.get("name", "Resource")),
            "description": str(match.get("description", "")),
            "needs_verification": [
                str(note) for note in match.get("needs_verification", [])
            ],
            "has_application_link": bool(match.get("apply_url")),
        }
        for match in matches
        if match.get("program_id")
    ]


def _guide_cache_key(language: str, safe_matches: list[dict[str, Any]]) -> str:
    """Hash only the language and privacy-minimized program data."""
    payload = json.dumps(
        {"language": language, "matches": safe_matches},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_cached_guide(cache_key: str) -> dict[str, Any] | None:
    now = time.monotonic()
    with _GUIDE_CACHE_LOCK:
        cached = _GUIDE_CACHE.get(cache_key)
        if cached is None:
            return None
        created_at, serialized_guide = cached
        if now - created_at > CACHE_TTL_SECONDS:
            del _GUIDE_CACHE[cache_key]
            return None
    return json.loads(serialized_guide)


def _cache_guide(cache_key: str, guide: dict[str, Any]) -> None:
    serialized_guide = json.dumps(guide, ensure_ascii=False)
    with _GUIDE_CACHE_LOCK:
        if len(_GUIDE_CACHE) >= CACHE_MAX_ENTRIES:
            oldest_key = min(_GUIDE_CACHE, key=lambda key: _GUIDE_CACHE[key][0])
            del _GUIDE_CACHE[oldest_key]
        _GUIDE_CACHE[cache_key] = (time.monotonic(), serialized_guide)


def _log_gemini_exception(error: Exception) -> None:
    """Log a bounded status summary without request or credential data."""
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(error, "code", None)
    message = getattr(error, "message", None)
    if not message and isinstance(error, TimeoutError):
        message = "Request timed out."
    elif not message and isinstance(error, json.JSONDecodeError):
        message = "Model response was not valid JSON."
    elif not message and isinstance(error, ValueError):
        message = str(error)
    elif not message:
        message = "No safe message available."
    safe_message = " ".join(str(message).split())[:500]
    LOGGER.warning(
        "Gemini guide request failed: type=%s status=%s message=%s",
        type(error).__name__,
        status if status is not None else "unknown",
        safe_message,
    )


def _response_schema(program_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "introduction": {"type": "string"},
            "steps": {
                "type": "array",
                "minItems": len(program_ids),
                "maxItems": len(program_ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "program_id": {"type": "string", "enum": program_ids},
                        "action": {"type": "string"},
                        "question_to_ask": {"type": "string"},
                    },
                    "required": ["program_id", "action", "question_to_ask"],
                },
            },
            "reminder": {"type": "string"},
        },
        "required": ["introduction", "steps", "reminder"],
    }


def _validate_guide(
    guide: Any, matches: list[dict[str, Any]]
) -> dict[str, Any]:
    """Reject reordered, incomplete, malformed, or URL-bearing model output."""
    expected_ids = [
        str(match["program_id"]) for match in matches if match.get("program_id")
    ]
    if not isinstance(guide, dict):
        raise ValueError("Guide must be an object.")
    if set(guide) != {"introduction", "steps", "reminder"}:
        raise ValueError("Guide has unexpected fields.")
    if not all(
        isinstance(guide.get(field), str) and guide[field].strip()
        for field in ("introduction", "reminder")
    ):
        raise ValueError("Guide text must not be empty.")

    steps = guide.get("steps")
    if not isinstance(steps, list) or len(steps) != len(expected_ids):
        raise ValueError("Guide must contain exactly one step per program.")

    actual_ids: list[str] = []
    for step in steps:
        if not isinstance(step, dict) or set(step) != {
            "program_id",
            "action",
            "question_to_ask",
        }:
            raise ValueError("Guide step has unexpected fields.")
        if not all(
            isinstance(step.get(field), str) and step[field].strip()
            for field in ("program_id", "action", "question_to_ask")
        ):
            raise ValueError("Guide step text must not be empty.")
        generated_text = f"{step['action']} {step['question_to_ask']}".lower()
        if any(
            marker in generated_text
            for marker in (
                "http://",
                "https://",
                "www.",
                "mailto:",
                "tel:",
                "](",
                "<a",
            )
        ):
            raise ValueError("Gemini must not generate links.")
        actual_ids.append(step["program_id"])

    if len(set(actual_ids)) != len(actual_ids) or set(actual_ids) != set(expected_ids):
        raise ValueError("Guide changed the program membership.")
    return guide


def generate_action_guide(
    matches: list[dict[str, Any]],
    language: str = "English",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Generate a constrained guide, falling back safely on every failure."""
    guide, _ = generate_action_guide_with_status(matches, language, api_key)
    return guide


def generate_action_guide_with_status(
    matches: list[dict[str, Any]],
    language: str = "English",
    api_key: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Return a guide and whether the deterministic fallback was used."""
    selected_language = _normalize_language(language)
    fallback = build_fallback_guide(matches, selected_language)
    safe_matches = _safe_matches(matches)
    if not safe_matches:
        return fallback, True

    key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    if not key:
        return fallback, True

    cache_key = _guide_cache_key(selected_language, safe_matches)
    cached_guide = _get_cached_guide(cache_key)
    if cached_guide is not None:
        return cached_guide, False

    try:
        from google import genai
        from google.genai import types as genai_types

        http_options = genai_types.HttpOptions(
            timeout=15_000,
            retry_options=genai_types.HttpRetryOptions(attempts=1),
        )
        with genai.Client(api_key=key, http_options=http_options) as client:
            interaction = client.interactions.create(
                model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
                store=False,
                system_instruction=SYSTEM_INSTRUCTION,
                input=json.dumps(
                    {
                        "language": selected_language,
                        "programs_in_required_order": safe_matches,
                    },
                    ensure_ascii=False,
                ),
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": _response_schema(
                        [match["program_id"] for match in safe_matches]
                    ),
                },
            )
        guide = json.loads(interaction.output_text)
        validated_guide = _validate_guide(guide, matches)
        _cache_guide(cache_key, validated_guide)
        return validated_guide, False
    except Exception as error:
        _log_gemini_exception(error)
        return fallback, True
