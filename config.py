"""
Configuration — LinkedIn Job Scraper
Toutes les valeurs sensibles sont lues depuis .env (python-dotenv)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Charger le fichier .env situé dans le même dossier que ce script
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ==================== FICHIERS ====================
RESUME_PATH = os.getenv(
    "LINKEDIN_RESUME_PATH",
    r"C:\Users\MSI\Desktop\cv pour candidature\iovision\cv_zaineb_zouari.pdf"
)
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "linkedin_jobs_scraper/output")
DEFAULT_OUTPUT_PREFIX = "linkedin_jobs_analyzed"

# ==================== RECHERCHE ====================
DEFAULT_JOB_TITLES = [
    "AI Engineer",
    # "Machine Learning Engineer",
    # "MLOps Engineer",
    # "Data Scientist",
    # "Computer Vision Engineer",
]

DEFAULT_LOCATIONS = [
    "Tunisie",
    "France",
    # "Germany",
    # "Remote",
]

# ==================== LIMITES ====================
MAX_PAGES_PER_LOCATION = 3
MAX_JOBS_TOTAL = 20          # augmenté pour les tests réels
DELAY_BETWEEN_REQUESTS = 3
DELAY_BETWEEN_LOCATIONS = 5
DELAY_AFTER_DESCRIPTION_FETCH = 2

# ==================== LLM ====================
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

ENABLE_LLM_ANALYSIS = True
FETCH_JOB_DESCRIPTIONS = True

# Seuils de score (sur 10 pour Ollama, sur 100 pour CrewAI)
EXCELLENT_MATCH_THRESHOLD = 80   # >= 80/100
GOOD_MATCH_THRESHOLD = 50        # >= 50/100
POOR_MATCH_THRESHOLD = 30        # <  30/100

# ==================== HTTP ====================
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
REQUEST_TIMEOUT = 15

# ==================== URLS LINKEDIN ====================
LINKEDIN_JOBS_API_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)
LINKEDIN_BASE_URL = "https://www.linkedin.com"

# ==================== SOURCES SUPPORTÉES ====================
# Utilisé par ScraperManager dans scraper.py
SUPPORTED_SOURCES = ["LinkedIn", "Indeed", "WelcomeToTheJungle"]

# ==================== SORTIE ====================
CSV_ENCODING = "utf-8-sig"   # BOM pour Excel
JSON_INDENT = 2
JSON_ENSURE_ASCII = False

# ==================== DEBUG ====================
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
SAVE_HTML_RESPONSES = False
DEBUG_LAST_RESPONSE = "last_response.html"
DEBUG_LAST_SEARCH_PAGE = "last_search_page.html"

# ==================== FILTRES ====================
EXCLUDE_KEYWORDS: list[str] = []   # ex. ["intern", "unpaid"]
REQUIRE_KEYWORDS: list[str] = []   # ex. ["remote", "senior"]
MAX_JOB_AGE_DAYS: int | None = 30  # None = pas de limite

# ==================== EMAIL (optionnel) ====================
ENABLE_EMAIL_NOTIFICATIONS = False
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")


# ==================== HELPERS ====================
def get_output_path(filename: str) -> str:
    """Retourne le chemin complet vers un fichier de sortie."""
    if OUTPUT_DIR:
        return str(Path(OUTPUT_DIR) / filename)
    return filename


def validate_config() -> bool:
    """Vérifie la configuration avant le lancement."""
    errors: list[str] = []

    if not Path(RESUME_PATH).exists():
        errors.append(f"CV introuvable : {RESUME_PATH}")

    if OUTPUT_DIR:
        try:
            Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            errors.append(f"Impossible de créer {OUTPUT_DIR} : {exc}")

    if ENABLE_EMAIL_NOTIFICATIONS and not EMAIL_PASSWORD:
        errors.append("Notifications email activées mais EMAIL_PASSWORD absent.")

    if errors:
        print("⚠️  Erreurs de configuration :")
        for err in errors:
            print(f"   • {err}")
        return False

    return True


def print_config() -> None:
    """Affiche la configuration courante (debug)."""
    print("=" * 70)
    print("CONFIGURATION")
    print("=" * 70)
    print(f"CV             : {RESUME_PATH}")
    print(f"Dossier sortie : {OUTPUT_DIR}")
    print(f"Modèle Ollama  : {OLLAMA_MODEL}")
    print(f"Analyse LLM    : {ENABLE_LLM_ANALYSIS}")
    print(f"Fetch desc.    : {FETCH_JOB_DESCRIPTIONS}")
    print(f"Debug          : {DEBUG_MODE}")
    print("=" * 70)


if __name__ == "__main__":
    print_config()
    result = validate_config()
    print("\n✅ Configuration valide !" if result else "\n❌ Erreurs détectées !")