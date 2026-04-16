"""
LLM Service (Ollama / Qwen)
============================
Verbindet sich mit einem Ollama-Server über die OpenAI-kompatible API.
Fallback: Gibt Rohdaten ohne Interpretation zurück, wenn kein LLM erreichbar.

Konfiguration über Umgebungsvariablen:
  OLLAMA_URL   = http://IP:11434   (default: http://localhost:11434)
  OLLAMA_MODEL = qwen3:8b          (default)
"""

import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
DEFAULT_TIMEOUT = 60  # LLM braucht mehr Zeit als eine API


def is_available():
    """Quick health check — is Ollama reachable?"""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def chat(prompt, system=None, temperature=0.3, max_tokens=1000):
    """
    Send a prompt to Ollama, return the response text.

    Returns:
        str: LLM response, or None if unavailable.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/v1/chat/completions",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[llm] Request failed: {e}")
        return None


# ── Spezialisierte Prompts pro Modul ────────────────────────

SYSTEM_HEALTH = """Du bist ein medizinischer Wissensassistent für Health Professionals im deutschsprachigen Raum.
Antworte immer auf Deutsch. Sei präzise, evidenzbasiert und praxisnah.
Keine Floskeln, keine Einleitungen. Direkt zur Sache."""


def summarize_study(title, abstract, journal=""):
    """Generiere eine Praxisrelevanz-Zusammenfassung für eine Studie."""
    prompt = f"""Studie: "{title}"
Journal: {journal}
Abstract: {abstract}

Beantworte in maximal 2-3 Sätzen:
Was ändert diese Studie konkret für den Behandlungsalltag einer Physiotherapie-Praxis?"""
    return chat(prompt, system=SYSTEM_HEALTH, max_tokens=200)


def explain_guideline_change(title, summary=""):
    """Erkläre eine Leitlinien-Änderung für die Praxis."""
    prompt = f"""Leitlinien-Update: "{title}"
{('Details: ' + summary) if summary else ''}

Beantworte kurz:
1. Was hat sich geändert?
2. Was muss ich in der Praxis ab sofort anders machen?"""
    return chat(prompt, system=SYSTEM_HEALTH, max_tokens=250)


def assess_privacy_relevance(title, summary=""):
    """Bewerte ob eine Datenschutz-Meldung praxisrelevant ist."""
    prompt = f"""Datenschutz-Meldung: "{title}"
{('Details: ' + summary) if summary else ''}

Bewerte in 1-2 Sätzen: Betrifft das eine Gesundheits-Praxis? Ja/Nein/Möglicherweise — und warum."""
    return chat(prompt, system=SYSTEM_HEALTH, max_tokens=150)


def patient_explainer(topic_title, summary=""):
    """Formuliere eine Patientenantwort zu einem Medienthema."""
    prompt = f"""Medienthema: "{topic_title}"
{('Kontext: ' + summary) if summary else ''}

Formuliere in 2-3 einfachen Sätzen, wie du einem Patienten erklärst, was daran stimmt und was nicht.
Verständlich, nicht belehrend."""
    return chat(prompt, system=SYSTEM_HEALTH, max_tokens=200)
