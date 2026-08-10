"""
app.py — Elite AI Career Agent
Interface Streamlit : thème sobre, filtres avancés (dont date), cache,
onglets, métriques, export CSV/JSON/Markdown et lettres de motivation en PDF.
"""

import io
import json
import logging

import pandas as pd
import pdfplumber
import streamlit as st
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from agents import run_agency_workflow, generate_cover_letter
from scraper import ScraperManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Elite AI Career Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# DESIGN SYSTEM
# Palette indigo/violet, typographie Space Grotesk (titres) + Inter (corps).
# Couleurs de texte fixées explicitement (indépendantes du thème Streamlit)
# pour éviter tout texte invisible.
# ---------------------------------------------------------------------------
st.markdown(
    """
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
    --primary: #1D4ED8;
    --primary-dark: #1E3A8A;
    --primary-light: #3B82F6;
    --sky: #0EA5E9;
    --sky-soft: #E0F2FE;
    --green: #059669;
    --green-dark: #047857;
    --green-soft: #ECFDF5;
    --warn: #D97706;
    --warn-soft: #FFFBEB;
    --bad: #DC2626;
    --bad-soft: #FEF2F2;
    --ink: #0F172A;
    --ink-soft: #475569;
    --ink-faint: #94A3B8;
    --bg: #F5F8FC;
    --surface: #FFFFFF;
    --border: #E2E8F0;
    --shadow: 0 1px 2px rgba(15,23,42,0.04), 0 4px 14px rgba(15,23,42,0.07);
    --shadow-lg: 0 10px 30px rgba(15,23,42,0.12);
    --shadow-glow: 0 8px 24px rgba(29,78,216,0.22);
}
.stApp {
    background: var(--bg);
}
[data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] span, [data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] li, [data-testid="stAppViewContainer"] div {
    color: var(--ink);
    font-family: 'Inter', sans-serif;
}
[data-testid="stIconMaterial"], [data-testid="stIconMaterial"] *,
[data-testid="stAppViewContainer"] [data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons', sans-serif !important;
}
h1, h2, h3, h4, .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 700 !important;
    color: var(--ink) !important;
}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
    color: var(--ink-soft) !important;
}
@keyframes gradientFlow {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeInScale {
    from { opacity: 0; transform: scale(0.97); }
    to { opacity: 1; transform: scale(1); }
}
@keyframes pulseDot {
    0% { box-shadow: 0 0 0 0 rgba(52,211,153,0.5); }
    70% { box-shadow: 0 0 0 8px rgba(52,211,153,0); }
    100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
}
@keyframes shimmer {
    0% { background-position: -200px 0; }
    100% { background-position: 200px 0; }
}
.fade-in {
    animation: fadeInUp 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.app-header {
    background: linear-gradient(120deg, var(--primary-dark) 0%, var(--primary) 45%, var(--sky) 75%, var(--green) 100%);
    background-size: 260% 260%;
    animation: gradientFlow 14s ease infinite;
    border-radius: 22px;
    padding: 30px 34px;
    margin-bottom: 28px;
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
}
.app-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    position: relative;
    z-index: 1;
}
.app-brand, .app-brand * {
    color: #FFFFFF !important;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.65rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.01em;
    animation: fadeInUp 0.5s ease both;
}
.app-tagline, .app-tagline * {
    color: rgba(255,255,255,0.86) !important;
    font-size: 0.94rem;
    margin-top: 5px;
    max-width: 540px;
    animation: fadeInUp 0.6s ease both;
}
.app-status-pill, .app-status-pill * {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255,255,255,0.14);
    border: 1px solid rgba(255,255,255,0.28);
    backdrop-filter: blur(6px);
    color: #FFFFFF !important;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 999px;
    white-space: nowrap;
    animation: fadeInUp 0.7s ease both;
}
.status-dot-live {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #34D399;
    animation: pulseDot 2s ease infinite;
}
.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: var(--shadow);
    transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.22s ease, border-color 0.22s ease;
    position: relative;
    overflow: hidden;
    animation: fadeInScale 0.4s ease both;
}
.metric-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--primary), var(--green));
}
.metric-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
    border-color: var(--primary-light);
}
.metric-icon {
    font-size: 1.25rem;
    opacity: 0.9;
    margin-bottom: 6px;
}
.metric-value, .metric-value * {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--ink) !important;
    line-height: 1.1;
}
.metric-label, .metric-label * {
    color: var(--ink-soft) !important;
    font-size: 0.74rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 4px;
}
.job-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 17px 19px;
    margin-bottom: 12px;
    box-shadow: var(--shadow);
    transition: border-color 0.2s ease, transform 0.2s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.2s ease;
    animation: fadeInUp 0.35s ease both;
}
.job-card:hover {
    border-color: var(--primary);
    transform: translateY(-3px) translateX(2px);
    box-shadow: var(--shadow-glow);
}
.job-title, .job-title * {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    color: var(--ink) !important;
    font-size: 1.04rem;
}
.job-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 9px;
}
.job-meta-text, .job-meta-text * {
    color: var(--ink-soft) !important;
    font-size: 0.85rem;
}
.job-badge {
    display: inline-block;
    background: var(--sky-soft);
    color: var(--primary);
    font-size: 0.72rem;
    font-weight: 700;
    padding: 3px 11px;
    border-radius: 999px;
    transition: transform 0.15s ease;
}
.job-badge-success {
    background: var(--green-soft);
    color: var(--green);
}
.job-badge-warn {
    background: var(--warn-soft);
    color: var(--warn);
}
.stButton > button {
    border-radius: 11px !important;
    border: none !important;
    background: linear-gradient(135deg, var(--primary), var(--primary-light)) !important;
    color: #FFFFFF !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 600 !important;
    padding: 0.6em 1.4em !important;
    box-shadow: 0 2px 6px rgba(29,78,216,0.25) !important;
    transition: transform 0.18s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.18s ease !important;
}
.stButton > button *  {
    color: #FFFFFF !important;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-glow) !important;
}
.stButton > button:active {
    transform: translateY(0px);
}
.stDownloadButton > button {
    border-radius: 11px !important;
    border: none !important;
    background: linear-gradient(135deg, var(--green), var(--green-dark)) !important;
    color: #FFFFFF !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 600 !important;
    padding: 0.6em 1.4em !important;
    box-shadow: 0 2px 6px rgba(5,150,105,0.25) !important;
    transition: transform 0.18s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.18s ease !important;
}
.stDownloadButton > button * {
    color: #FFFFFF !important;
}
.stDownloadButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 24px rgba(5,150,105,0.3) !important;
}
button[kind="primary"], button[kind="primaryFormSubmit"] {
    background: linear-gradient(135deg, var(--primary-dark), var(--primary), var(--green)) !important;
    background-size: 220% 220% !important;
    animation: gradientFlow 6s ease infinite !important;
}
section[data-testid="stSidebar"] {
    background: var(--ink);
}
section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div {
    color: #F1F5F9 !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"],
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] *,
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"],
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] *,
section[data-testid="stSidebar"] [data-baseweb="select"],
section[data-testid="stSidebar"] [data-baseweb="select"] *,
section[data-testid="stSidebar"] [data-baseweb="input"],
section[data-testid="stSidebar"] [data-baseweb="input"] *,
section[data-testid="stSidebar"] [data-baseweb="base-input"],
section[data-testid="stSidebar"] [data-baseweb="base-input"] *,
section[data-testid="stSidebar"] [data-baseweb="popover"],
section[data-testid="stSidebar"] [data-baseweb="popover"] * {
    color: var(--ink) !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
    background: #EDF2F7 !important;
}
section[data-testid="stSidebar"] h3 {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #7DD3FC !important;
    margin-top: 8px;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.1);
    margin: 18px 0;
}
section[data-testid="stSidebar"] [data-baseweb="select"],
section[data-testid="stSidebar"] [data-baseweb="input"] {
    transition: box-shadow 0.18s ease;
}
section[data-testid="stSidebar"] [data-baseweb="select"]:hover,
section[data-testid="stSidebar"] [data-baseweb="input"]:hover {
    box-shadow: 0 0 0 1px var(--sky);
}
.sidebar-brand, .sidebar-brand * {
    color: #FFFFFF !important;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 1.08rem;
    margin: 0;
}
.sidebar-brand-mark {
    color: var(--sky) !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #EAF2FB;
    padding: 4px;
    border-radius: 13px;
    display: inline-flex;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    background: transparent;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    padding: 8px 18px;
    transition: background 0.2s ease;
}
.stTabs [data-baseweb="tab"] p {
    color: var(--ink-soft) !important;
    transition: color 0.2s ease;
}
.stTabs [aria-selected="true"] {
    background: var(--surface) !important;
    box-shadow: var(--shadow);
}
.stTabs [aria-selected="true"] p {
    color: var(--primary) !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: var(--primary) !important;
}
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--primary), var(--sky), var(--green), var(--sky), var(--primary)) !important;
    background-size: 400px 100% !important;
    animation: shimmer 2.2s linear infinite !important;
}
[data-testid="stAlert"] {
    border-radius: 13px !important;
    animation: fadeInUp 0.3s ease both;
}
.letter-box, .letter-box * {
    background: var(--surface);
    border-radius: 16px;
    padding: 26px 30px;
    box-shadow: var(--shadow);
    border-left: 4px solid var(--green);
    white-space: pre-wrap;
    line-height: 1.65;
    color: var(--ink) !important;
    font-size: 0.95rem;
    animation: fadeInUp 0.35s ease both;
}
.step-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 24px 22px;
    box-shadow: var(--shadow);
    text-align: left;
    height: 100%;
    transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.22s ease;
    animation: fadeInUp 0.4s ease both;
}
.step-card:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-lg);
}
.step-icon-badge {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--primary), var(--green));
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    margin-bottom: 13px;
    box-shadow: 0 4px 10px rgba(29,78,216,0.25);
}
.step-title, .step-title * {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    color: var(--ink) !important;
    font-size: 1rem;
}
.step-desc, .step-desc * {
    color: var(--ink-soft) !important;
    font-size: 0.85rem;
    margin-top: 5px;
}
.welcome-eyebrow, .welcome-eyebrow * {
    display: inline-block;
    background: var(--sky-soft);
    color: var(--primary) !important;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 5px 13px;
    border-radius: 999px;
    margin-bottom: 12px;
    animation: fadeInUp 0.3s ease both;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
for key, default in {
    "all_jobs": [],
    "report_md": "",
    "cv_text": "",
    "cover_letter": "",
    "cover_letter_job": None,
    "sources_used": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# PDF helper
# ---------------------------------------------------------------------------
def _sanitize_for_pdf(text: str) -> str:
    """Remplace les caractères typographiques non supportés par les polices
    de base (latin-1) et neutralise le reste plutôt que de planter."""
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def letter_to_pdf_bytes(text: str, job_title: str, company: str) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(
        0, 8, _sanitize_for_pdf(f"Candidature - {job_title}"),
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(
        0, 6, _sanitize_for_pdf(company),
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 11)
    for paragraph in text.split("\n"):
        pdf.multi_cell(
            0, 6, _sanitize_for_pdf(paragraph),
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.ln(1)

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<p class="sidebar-brand"><span class="sidebar-brand-mark">◆</span> Elite AI Career Agent</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    uploaded_cv = st.file_uploader("📄 Votre CV (PDF)", type="pdf")

    st.subheader("Postes visés")
    job_titles = st.multiselect(
        "Titres de poste",
        ["AI Engineer", "Machine Learning Engineer", "Data Scientist",
         "MLOps Engineer", "Computer Vision Engineer", "NLP Engineer"],
        default=["AI Engineer"],
    )

    st.subheader("Localisations")
    locations = st.multiselect(
        "Pays / villes",
        ["Tunisie", "France", "Germany", "Remote", "Paris", "Lyon"],
        default=["Tunisie", "France"],
    )

    st.subheader("Filtres")
    job_type = st.radio(
        "Type de poste",
        ["Tous", "Remote", "Présentiel", "Hybride"],
        horizontal=True,
    )
    date_filter = st.selectbox(
        "Date de publication",
        ["Toutes", "24 heures", "Semaine", "Mois"],
        index=0,
    )

    st.subheader("Plateformes")
    sources = st.multiselect(
        "Sources",
        ["LinkedIn", "Indeed", "WelcomeToTheJungle"],
        default=["LinkedIn"],
    )

    max_per_combo = st.slider("Jobs max par recherche", 3, 15, 5)

    st.subheader("Lettre de motivation")
    letter_language = st.radio("Langue", ["Français", "English"], horizontal=True)

    st.markdown("---")
    search_button = st.button("🔍 Lancer l'analyse", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Header (always visible)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <div class="app-header-row">
            <div>
                <p class="app-brand">Elite AI Career Agent</p>
                <p class="app-tagline">Découvre les meilleures offres pour ton profil, obtiens une analyse de compatibilité détaillée et génère une lettre de motivation sur mesure — en toute confidentialité.</p>
            </div>
            <div class="app-status-pill"><span class="status-dot-live"></span> Assistant IA actif</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Validation + run
# ---------------------------------------------------------------------------
if search_button:
    errors = []
    if not uploaded_cv:
        errors.append("Veuillez uploader votre CV (PDF).")
    if not job_titles:
        errors.append("Sélectionnez au moins un titre de poste.")
    if not locations:
        errors.append("Sélectionnez au moins une localisation.")
    if not sources:
        errors.append("Sélectionnez au moins une plateforme.")

    if errors:
        for err in errors:
            st.error(err)
        st.stop()

    # Extraction CV
    with pdfplumber.open(uploaded_cv) as pdf:
        cv_text = "\n".join(
            page.extract_text() or "" for page in pdf.pages
        ).strip()

    if not cv_text:
        st.error("Impossible d'extraire le texte du CV. Vérifiez que le PDF n'est pas scanné.")
        st.stop()

    # Recherche des offres (+ récupération des descriptions complètes)
    progress = st.progress(0, text="🌐 Recherche des offres en cours…")
    status_placeholder = st.empty()

    manager = ScraperManager()
    all_jobs: list[dict] = []

    def _on_progress(msg: str) -> None:
        status_placeholder.caption(msg)

    try:
        all_jobs = manager.get_all_jobs(
            titles=job_titles,
            locations=locations,
            sources=sources,
            job_type=job_type,
            max_per_combo=max_per_combo,
            date_filter=date_filter,
            progress_callback=_on_progress,
        )
    except Exception:
        logger.exception("Erreur pendant la recherche des offres")
        st.error("Une erreur est survenue pendant la recherche des offres. Réessaie dans quelques instants ou modifie tes critères.")
        st.stop()

    status_placeholder.empty()
    progress.progress(60, text=f"✅ {len(all_jobs)} offres collectées. Analyse en cours…")

    if not all_jobs:
        st.warning("Aucune offre trouvée avec ces filtres. Essayez d'élargir la recherche.")
        st.stop()

    # Analyse — une offre à la fois, jamais plusieurs offres dans la même
    # analyse (pour garantir la fiabilité du résultat)
    def _on_analysis_progress(i: int, total: int, title: str) -> None:
        progress.progress(
            60 + int(38 * i / total),
            text=f"🧠 Analyse {i}/{total} — {title[:50]}",
        )

    report_md: str = ""
    try:
        report_md = run_agency_workflow(cv_text, all_jobs, progress_callback=_on_analysis_progress)
    except Exception:
        logger.exception("Erreur pendant l'analyse des offres")
        st.error("Une erreur est survenue pendant l'analyse. Réessaie dans quelques instants.")
        report_md = "L'analyse n'a pas pu être générée pour cette recherche."

    progress.progress(100, text="🎉 Analyse terminée !")

    # Persist in session state so later interactions (cover letter button)
    # don't require re-scraping / re-analyzing everything.
    st.session_state.all_jobs = all_jobs
    st.session_state.report_md = report_md
    st.session_state.cv_text = cv_text
    st.session_state.sources_used = sources
    st.session_state.cover_letter = ""
    st.session_state.cover_letter_job = None

# ---------------------------------------------------------------------------
# Résultats (persistants via session_state)
# ---------------------------------------------------------------------------
if st.session_state.all_jobs:
    all_jobs = st.session_state.all_jobs
    report_md = st.session_state.report_md
    cv_text = st.session_state.cv_text
    sources_used = st.session_state.sources_used

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-icon">🗂️</div><div class="metric-value">{len(all_jobs)}</div>
            <div class="metric-label">Offres collectées</div></div>""",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""<div class="metric-card"><div class="metric-icon">🌐</div><div class="metric-value">{len(sources_used)}</div>
            <div class="metric-label">Plateformes</div></div>""",
            unsafe_allow_html=True,
        )
    with col3:
        n_companies = len(set(j.get("company", "") for j in all_jobs))
        st.markdown(
            f"""<div class="metric-card"><div class="metric-icon">🏢</div><div class="metric-value">{n_companies}</div>
            <div class="metric-label">Entreprises uniques</div></div>""",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    tab_report, tab_jobs, tab_letter, tab_export = st.tabs(
        ["📋 Rapport d'expertise", "🗂️ Offres brutes", "✉️ Lettre de motivation", "📥 Export"]
    )

    with tab_report:
        st.subheader("Rapport de matching IA")
        st.markdown(f'<div class="fade-in">{report_md}</div>', unsafe_allow_html=True)

    with tab_jobs:
        st.subheader("Toutes les offres collectées")
        for j in all_jobs:
            desc_badge = (
                '<span class="job-badge job-badge-success">✓ Description récupérée</span>'
                if j.get("description")
                else '<span class="job-badge job-badge-warn">⚠ Description indisponible</span>'
            )
            st.markdown(
                f"""
                <div class="job-card">
                    <div class="job-title">{j.get('title', 'N/A')}</div>
                    <div class="job-meta">
                        <span class="job-meta-text">🏢 {j.get('company', 'N/A')} · 📍 {j.get('location', 'N/A')}</span>
                        <span class="job-badge">{j.get('source', 'N/A')}</span>
                        {desc_badge}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        df = pd.DataFrame(all_jobs)
        with st.expander("Voir en tableau"):
            def _col(name: str) -> pd.Series:
                if name in df.columns:
                    return df[name].fillna("")
                return pd.Series([""] * len(df))

            def _preview(d: str) -> str:
                if not isinstance(d, str) or not d:
                    return "—"
                if len(d) <= 110:
                    return d
                return d[:110].rsplit(" ", 1)[0] + " …"

            table_df = pd.DataFrame({
                "Titre": _col("title").replace("", "—"),
                "Entreprise": _col("company").replace("", "—"),
                "Localisation": _col("location").replace("", "—"),
                "Source": _col("source").replace("", "—"),
                "Aperçu description": _col("description").apply(_preview),
                "Lien": _col("link"),
            })
            st.dataframe(
                table_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Titre": st.column_config.TextColumn("Titre", width="medium"),
                    "Entreprise": st.column_config.TextColumn("Entreprise", width="small"),
                    "Localisation": st.column_config.TextColumn("Localisation", width="small"),
                    "Source": st.column_config.TextColumn("Source", width="small"),
                    "Aperçu description": st.column_config.TextColumn("Aperçu description", width="large"),
                    "Lien": st.column_config.LinkColumn("Offre", display_text="Voir ↗", width="small"),
                },
            )

    with tab_letter:
        st.subheader("✉️ Générer une lettre de motivation")
        st.caption("La lettre est générée à partir de ton CV et de la description complète du poste sélectionné.")

        job_options = {
            f"{j.get('title', 'N/A')} — {j.get('company', 'N/A')}": idx
            for idx, j in enumerate(all_jobs)
        }
        selected_label = st.selectbox("Offre visée", list(job_options.keys()))
        selected_job = all_jobs[job_options[selected_label]]

        if not selected_job.get("description"):
            st.warning(
                "⚠️ La description complète de cette offre n'a pas pu être récupérée "
                "(page bloquée ou introuvable). La lettre sera générée avec moins de "
                "contexte (titre, entreprise, localisation uniquement)."
            )

        gen_col, _ = st.columns([1, 3])
        with gen_col:
            generate_clicked = st.button("✨ Générer la lettre", use_container_width=True)

        if generate_clicked:
            with st.spinner("Rédaction de la lettre en cours…"):
                letter = generate_cover_letter(
                    cv_text, selected_job, language=letter_language
                )
            st.session_state.cover_letter = letter
            st.session_state.cover_letter_job = selected_label

        if st.session_state.cover_letter and st.session_state.cover_letter_job == selected_label:
            st.markdown(
                f'<div class="letter-box">{st.session_state.cover_letter}</div>',
                unsafe_allow_html=True,
            )

            pdf_bytes = letter_to_pdf_bytes(
                st.session_state.cover_letter,
                selected_job.get("title", "Poste"),
                selected_job.get("company", "Entreprise"),
            )
            safe_company = "".join(
                c if c.isalnum() else "_" for c in selected_job.get("company", "entreprise")
            )
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    "⬇️ Télécharger en PDF",
                    data=pdf_bytes,
                    file_name=f"lettre_motivation_{safe_company}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            with dl_col2:
                st.download_button(
                    "⬇️ Télécharger en .txt",
                    data=st.session_state.cover_letter.encode("utf-8"),
                    file_name=f"lettre_motivation_{safe_company}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

    with tab_export:
        st.subheader("Télécharger les résultats")

        df_export = pd.DataFrame(all_jobs)
        csv_bytes = df_export.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "⬇️ Télécharger CSV",
            data=csv_bytes,
            file_name="jobs_results.csv",
            mime="text/csv",
        )

        json_bytes = json.dumps(all_jobs, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            "⬇️ Télécharger JSON",
            data=json_bytes,
            file_name="jobs_results.json",
            mime="application/json",
        )

        st.download_button(
            "⬇️ Télécharger rapport Markdown",
            data=report_md.encode("utf-8"),
            file_name="rapport_matching.md",
            mime="text/markdown",
        )

# ---------------------------------------------------------------------------
# Page d'accueil (aucune action lancée)
# ---------------------------------------------------------------------------
else:
    st.markdown(
        """
        <div class="fade-in">
        <span class="welcome-eyebrow">Comment ça marche</span>
        <h3 style="margin-top:6px;">Bienvenue sur ton copilote de recherche d'emploi 👋</h3>
        <p style="color:var(--ink-soft);max-width:620px;">Cet agent IA analyse des offres d'emploi, les compare à ton CV et peut rédiger
        une lettre de motivation sur mesure pour l'offre de ton choix — sans jamais quitter ta machine.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    step_cols = st.columns(3)
    steps = [
        ("1", "Upload ton CV", "Dépose ton CV en PDF dans la barre latérale."),
        ("2", "Filtre tes critères", "Titres, localisations, date, plateformes."),
        ("3", "Lance l'analyse", "Score de matching + rapport + lettre de motivation."),
    ]
    for col, (num, title, desc) in zip(step_cols, steps):
        with col:
            st.markdown(
                f"""
                <div class="step-card">
                    <div class="step-icon-badge">{num}</div>
                    <div class="step-title">{title}</div>
                    <div class="step-desc">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)