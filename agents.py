"""
agents.py — Analyse CV × Offres via CrewAI + Ollama local
Améliorations :
  - Chaque offre est analysée dans un appel LLM ISOLÉ (jamais plusieurs
    offres dans le même prompt) pour éviter que le modèle mélange les
    entreprises/titres entre offres — bug observé avec le prompt combiné.
  - Titre/Entreprise/Localisation du rapport proviennent TOUJOURS des
    données scrapées, jamais de ce que le LLM répète, donc jamais faux.
  - Score sur 100 (cohérent avec les seuils config.py)
  - Rapport structuré avec tableau récapitulatif
  - Gestion d'erreur + retry automatique
"""

import re
import os
import json
import time
import logging
from typing import Any, Callable

from crewai import Agent, Task, Crew, Process, LLM

import config

logger = logging.getLogger(__name__)

# Bypass de la vérification OpenAI imposée par CrewAI
os.environ["OPENAI_API_KEY"] = "NA"

# LLM local via LiteLLM → Ollama
_llm = LLM(
    model=f"ollama/{config.OLLAMA_MODEL}",
    base_url=config.OLLAMA_BASE_URL,
)


# ---------------------------------------------------------------------------
# Helper JSON — parsing robuste des sorties LLM
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict[str, Any] | None:
    """Extrait le premier bloc JSON valide d'une réponse LLM, même si le
    modèle a ajouté du texte autour (fréquent avec les petits modèles locaux)."""
    raw = str(raw).strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


# ---------------------------------------------------------------------------
# Analyse d'UNE offre — jamais de mélange possible entre offres
# ---------------------------------------------------------------------------

def _analyze_single_job(cv_text: str, job: dict[str, Any], max_retries: int = 2) -> dict[str, Any]:
    """Analyse une seule offre. Ne retourne JAMAIS le titre/l'entreprise —
    ces champs viennent toujours des données scrapées (source de vérité)."""
    desc = (job.get("description") or "").strip()[:2000]

    matcher = Agent(
        role="Analyste de Carrière Senior",
        goal="Évaluer objectivement la compatibilité entre un CV et UNE offre d'emploi.",
        backstory=(
            "Expert en recrutement technique (IA, Data, Software). Tu analyses "
            "une seule offre à la fois, avec rigueur, sans jamais confondre "
            "avec d'autres postes. Tu réponds UNIQUEMENT en JSON valide."
        ),
        llm=_llm,
        allow_delegation=False,
        verbose=config.DEBUG_MODE,
    )

    task_description = f"""
CV du candidat :
{cv_text}

Offre à évaluer (titre : {job.get('title', 'N/A')}, entreprise : {job.get('company', 'N/A')}) :
{desc if desc else "Description non disponible — évalue à partir du titre uniquement."}

Réponds STRICTEMENT avec un objet JSON respectant ce schéma (aucun texte
avant/après, aucun markdown) :

{{
  "score": <entier 0-100>,
  "recommendation": "<Candidater | À considérer | Ne pas candidater>",
  "strengths": ["<point fort concret basé sur le CV>", "..."],
  "improvements": ["<compétence manquante ou point de vigilance>", "..."],
  "advice": "<une phrase de conseil stratégique et actionnable>"
}}

Entre 2 et 4 éléments par liste. N'invente aucune compétence absente du CV.
"""

    task = Task(
        description=task_description,
        expected_output="Un objet JSON valide respectant exactement le schéma demandé.",
        agent=matcher,
    )
    crew = Crew(agents=[matcher], tasks=[task], process=Process.sequential, verbose=config.DEBUG_MODE)

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            result = crew.kickoff()
            parsed = _extract_json(str(result))
            if parsed is None:
                raise ValueError("Réponse LLM non parsable en JSON")
            parsed["score"] = max(0, min(100, int(parsed.get("score", 0))))
            parsed.setdefault("recommendation", "À considérer")
            parsed.setdefault("strengths", [])
            parsed.setdefault("improvements", [])
            parsed.setdefault("advice", "")
            return parsed
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "Analyse offre '%s' — tentative %d/%d échouée : %s",
                job.get("title", "?"), attempt, max_retries, exc,
            )
            if attempt < max_retries:
                time.sleep(2 * attempt)

    return {
        "score": 0, "recommendation": "Analyse indisponible",
        "strengths": [], "improvements": [], "advice": "",
        "error": str(last_error),
    }


# ---------------------------------------------------------------------------
# Entrée principale — assemble le rapport à partir d'analyses individuelles
# ---------------------------------------------------------------------------

def run_agency_workflow(
    cv_text: str,
    jobs_list: list[dict[str, Any]],
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> str:
    """
    Analyse chaque offre séparément puis assemble un rapport Markdown.
    Le titre/l'entreprise/la localisation de chaque fiche et du tableau
    proviennent TOUJOURS de jobs_list (jamais du LLM), donc ne peuvent
    jamais être erronés ou mélangés entre deux offres.

    Args:
        cv_text: Texte brut extrait du CV (PDF).
        jobs_list: Liste de dicts produits par ScraperManager.
        progress_callback: Callable(i, total, title) optionnel, appelé
            avant l'analyse de chaque offre (utile pour l'UI Streamlit).

    Returns:
        Rapport Markdown structuré.
    """
    if not cv_text.strip():
        return "❌ Erreur : le texte du CV est vide."
    if not jobs_list:
        return "❌ Erreur : aucune offre à analyser."

    analyses: list[dict[str, Any]] = []
    for i, job in enumerate(jobs_list, 1):
        if progress_callback:
            progress_callback(i, len(jobs_list), job.get("title", "N/A"))
        analyses.append(_analyze_single_job(cv_text, job))

    # --- Tableau récapitulatif (données scrapées, jamais le LLM) ---
    table_lines = ["| # | Titre | Entreprise | Score | Recommandation |", "|---|-------|-----------|-------|---------------|"]
    for i, (job, a) in enumerate(zip(jobs_list, analyses), 1):
        title = job.get("title") or "N/A"
        company = job.get("company") or "N/A"
        table_lines.append(f"| {i} | {title} | {company} | {a['score']} | {a['recommendation']} |")

    # --- Fiches détaillées ---
    fiches = []
    for i, (job, a) in enumerate(zip(jobs_list, analyses), 1):
        title = job.get("title") or "N/A"
        company = job.get("company") or "N/A"
        location = job.get("location") or "Non précisée"
        strengths = "\n".join(f"   * {s}" for s in a["strengths"]) or "   * —"
        improvements = "\n".join(f"   * {s}" for s in a["improvements"]) or "   * —"
        error_note = f"\n> ⚠️ Analyse partielle : {a['error']}" if "error" in a else ""
        fiches.append(
            f"### Offre {i} : {title} chez {company}\n"
            f"📍 {location}\n\n"
            f"* **Score de compatibilité** : {a['score']}\n"
            f"* **Recommandation** : {a['recommendation']}\n"
            f"* **Points forts** :\n{strengths}\n"
            f"* **Points à améliorer** :\n{improvements}\n"
            f"* **Conseil stratégique** : {a['advice']}"
            f"{error_note}"
        )

    report = (
        "## Tableau récapitulatif\n\n" + "\n".join(table_lines) +
        "\n\n## Fiches d'analyse\n\n" + "\n\n".join(fiches)
    )
    return report


# ---------------------------------------------------------------------------
# Lettre de motivation
# ---------------------------------------------------------------------------

def generate_cover_letter(
    cv_text: str,
    job: dict[str, Any],
    language: str = "Français",
    max_retries: int = 2,
) -> str:
    """
    Génère une lettre de motivation personnalisée pour une offre précise,
    en s'appuyant sur le CV et la description complète du poste.

    Args:
        cv_text: Texte brut extrait du CV.
        job: Dict décrivant l'offre (title, company, location, description, ...).
        language: Langue de rédaction ("Français" ou "English").
        max_retries: Nombre de tentatives en cas d'erreur LLM.

    Returns:
        Texte de la lettre de motivation (ou message d'erreur).
    """
    if not cv_text.strip():
        return "❌ Erreur : le texte du CV est vide."
    if not job:
        return "❌ Erreur : aucune offre sélectionnée."

    desc = (job.get("description") or "").strip()[:2500]

    writer = Agent(
        role="Coach en candidature et rédaction professionnelle",
        goal=(
            "Rédiger une lettre de motivation percutante, personnalisée et "
            "prête à l'emploi, qui met en évidence l'adéquation réelle entre "
            "le profil du candidat et l'offre visée."
        ),
        backstory=(
            "Tu es rédacteur professionnel spécialisé dans les candidatures "
            "tech (IA, Data, Software). Tu évites le remplissage générique : "
            "chaque phrase s'appuie sur un élément concret du CV ou de l'offre. "
            "Ton style est naturel, confiant, sans formules toutes faites."
        ),
        llm=_llm,
        allow_delegation=False,
        verbose=config.DEBUG_MODE,
    )

    task_description = f"""
Voici le CV du candidat :
{cv_text}

Voici l'offre visée :
Titre : {job.get('title', 'N/A')}
Entreprise : {job.get('company', 'N/A')}
Localisation : {job.get('location', 'N/A')}
Description :
{desc if desc else "Non disponible — appuie-toi sur le titre et l'entreprise."}

Rédige une lettre de motivation en {language}, longueur 280-400 mots, structurée
en 3-4 paragraphes (accroche, adéquation profil/poste avec exemples concrets du
CV, motivation pour l'entreprise, conclusion avec appel à l'action).
Contraintes :
- Aucune formule générique creuse ("je suis très motivé", "je suis rigoureux
  et dynamique" sans preuve).
- Personnalise avec de vrais éléments du CV (compétences, projets, expériences).
- Ne mentionne pas de compétences absentes du CV.
- Texte brut prêt à copier-coller, sans markdown (pas de **, #, listes à puces).
- Pas d'en-tête/adresse postale factice ; commence directement par la formule
  d'appel (ex. "Madame, Monsieur," ou équivalent selon la langue).
"""

    task = Task(
        description=task_description,
        expected_output="Une lettre de motivation complète, en texte brut, prête à l'emploi.",
        agent=writer,
    )

    crew = Crew(
        agents=[writer],
        tasks=[task],
        process=Process.sequential,
        verbose=config.DEBUG_MODE,
    )

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            result = crew.kickoff()
            return str(result).strip()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "Lettre de motivation — tentative %d/%d échouée : %s",
                attempt, max_retries, exc,
            )
            if attempt < max_retries:
                time.sleep(3 * attempt)

    return f"❌ Génération impossible après {max_retries} tentatives. Dernière erreur : {last_error}"