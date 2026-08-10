"""
scraper.py — ScraperManager multi-sources (LinkedIn, Indeed, WelcomeToTheJungle)
Utilise Selenium en mode headless avec gestion d'erreurs améliorée.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Literal

import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager

import config

logger = logging.getLogger(__name__)

JobType = Literal["Tous", "Remote", "Présentiel", "Hybride"]
DateFilter = Literal["Toutes", "24 heures", "Semaine", "Mois"]

# Paramètre LinkedIn f_TPR (Time Posted Range, en secondes)
LINKEDIN_DATE_PARAMS: dict[str, str] = {
    "Toutes": "",
    "24 heures": "&f_TPR=r86400",
    "Semaine": "&f_TPR=r604800",
    "Mois": "&f_TPR=r2592000",
}

# Paramètre Indeed fromage (en jours)
INDEED_DATE_PARAMS: dict[str, str] = {
    "Toutes": "",
    "24 heures": "&fromage=1",
    "Semaine": "&fromage=7",
    "Mois": "&fromage=14",  # Indeed ne propose pas 30j exact, 14 est le max courant
}

# Mots trop génériques pour servir de signal de pertinence à eux seuls
_GENERIC_TITLE_WORDS = {
    "engineer", "scientist", "developer", "specialist", "expert",
    "senior", "junior", "lead", "intern", "stagiaire", "and", "et",
}


def _title_matches_query(job_title: str, queried_titles: list[str]) -> bool:
    """Vérifie que le titre d'une offre scrapée a un lien réel avec au moins
    un des titres recherchés, pour filtrer les recommandations hors-sujet que
    LinkedIn/Indeed injectent parfois dans les résultats de recherche."""
    job_title_l = (job_title or "").lower()
    if not job_title_l:
        return False
    for query in queried_titles:
        query_l = query.lower()
        if query_l in job_title_l:
            return True
        significant_words = {
            w for w in query_l.split() if w not in _GENERIC_TITLE_WORDS and len(w) >= 2
        }
        if significant_words and any(w in job_title_l for w in significant_words):
            return True
    return False


# Paramètres LinkedIn pour le type de poste
JOB_TYPE_PARAMS: dict[str, str] = {
    "Remote": "&f_WT=2",
    "Présentiel": "&f_WT=1",
    "Hybride": "&f_WT=3",
    "Tous": "",
}


@dataclass
class Job:
    title: str
    company: str
    link: str
    source: str
    location: str = ""
    posted_text: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "link": self.link,
            "source": self.source,
            "location": self.location,
            "posted_text": self.posted_text,
            "description": self.description,
        }


def _build_driver() -> webdriver.Chrome:
    """Crée un driver Chrome headless configuré pour éviter la détection."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(f"user-agent={config.USER_AGENT}")
    opts.add_argument("--window-size=1920,1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


class ScraperManager:
    """Agrège les résultats de plusieurs plateformes d'emploi."""

    def __init__(self) -> None:
        self._driver: webdriver.Chrome | None = None

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def get_all_jobs(
        self,
        titles: list[str],
        locations: list[str],
        sources: list[str],
        job_type: JobType = "Tous",
        max_per_combo: int = 5,
        date_filter: DateFilter = "Toutes",
        fetch_descriptions: bool | None = None,
        progress_callback=None,
    ) -> list[dict]:
        """
        Lance le scraping sur toutes les combinaisons titre × location × source.

        Args:
            titles: Titres de poste à rechercher.
            locations: Localisations cibles.
            sources: Plateformes ("LinkedIn", "Indeed", "WelcomeToTheJungle").
            job_type: Filtre de mode de travail.
            max_per_combo: Nombre max de jobs par combinaison.
            date_filter: Ancienneté max des offres ("Toutes", "24 heures", "Semaine", "Mois").
            fetch_descriptions: Récupérer la description complète de chaque offre
                (défaut : config.FETCH_JOB_DESCRIPTIONS).
            progress_callback: Callable(str) optionnel appelé avec un message de
                progression (utile pour mettre à jour l'UI Streamlit).

        Returns:
            Liste de dicts (clés : title, company, link, source, location, description, …).
        """
        aggregated: list[Job] = []

        try:
            self._driver = _build_driver()

            for source in sources:
                for title in titles:
                    for location in locations:
                        try:
                            jobs = self._dispatch(
                                source, title, location, job_type, max_per_combo, date_filter
                            )
                            aggregated.extend(jobs)
                            logger.info(
                                "[%s] '%s' @ '%s' → %d résultats",
                                source, title, location, len(jobs),
                            )
                            if progress_callback:
                                progress_callback(
                                    f"[{source}] '{title}' @ '{location}' → {len(jobs)} résultats"
                                )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(
                                "Erreur scraping %s/%s/%s : %s",
                                source, title, location, exc,
                            )
                        time.sleep(config.DELAY_BETWEEN_REQUESTS)

        finally:
            if self._driver:
                self._driver.quit()
                self._driver = None

        # Dédoublonnage par lien
        seen: set[str] = set()
        unique: list[Job] = []
        for job in aggregated:
            key = job.link.split("?")[0]
            if key not in seen:
                seen.add(key)
                unique.append(job)

        # Filtrage de pertinence : LinkedIn/Indeed injectent parfois des offres
        # "recommandées" sans rapport avec la recherche dans la même structure
        # HTML que les vrais résultats (ex. "Quality Engineer" pour une
        # recherche "AI Engineer"). On ne garde que les offres dont le titre a
        # un mot significatif en commun avec au moins un des titres recherchés.
        unique = [job for job in unique if _title_matches_query(job.title, titles)]

        # Récupération des descriptions complètes (nécessaire pour un matching
        # et des lettres de motivation pertinents)
        should_fetch = (
            fetch_descriptions
            if fetch_descriptions is not None
            else config.FETCH_JOB_DESCRIPTIONS
        )
        if should_fetch:
            for i, job in enumerate(unique, 1):
                job.description = self._fetch_description(job.link)
                if progress_callback:
                    progress_callback(
                        f"📄 Description {i}/{len(unique)} récupérée ({job.title[:40]})"
                    )
                time.sleep(config.DELAY_AFTER_DESCRIPTION_FETCH)

        return [j.to_dict() for j in unique]

    # ------------------------------------------------------------------
    # Récupération de la description complète d'une offre
    # ------------------------------------------------------------------

    def _fetch_description(self, url: str) -> str:
        """Récupère et nettoie la description complète d'une offre via requests."""
        if not url:
            return ""
        try:
            response = requests.get(
                url, headers=config.REQUEST_HEADERS, timeout=config.REQUEST_TIMEOUT
            )
            if response.status_code != 200:
                return ""

            soup = BeautifulSoup(response.content, "html.parser")

            # LinkedIn
            desc_elem = soup.find("div", class_="show-more-less-html__markup")
            if not desc_elem:
                desc_elem = soup.find("div", class_="description__text")
            # Indeed
            if not desc_elem:
                desc_elem = soup.find("div", id="jobDescriptionText")
            # Fallback générique
            if not desc_elem:
                desc_elem = soup.find(
                    "div", class_=lambda x: x and "description" in x.lower()
                )

            if desc_elem:
                return desc_elem.get_text(strip=True, separator="\n")
            return ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erreur récupération description (%s) : %s", url, exc)
            return ""

    # ------------------------------------------------------------------
    # Dispatch interne
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        source: str,
        title: str,
        location: str,
        job_type: JobType,
        max_per_combo: int,
        date_filter: DateFilter = "Toutes",
    ) -> list[Job]:
        if source == "LinkedIn":
            return self._scrape_linkedin(title, location, job_type, max_per_combo, date_filter)
        if source == "Indeed":
            return self._scrape_indeed(title, location, job_type, max_per_combo, date_filter)
        if source == "WelcomeToTheJungle":
            return self._scrape_wttj(title, location, max_per_combo)
        logger.warning("Source inconnue : %s", source)
        return []

    # ------------------------------------------------------------------
    # LinkedIn
    # ------------------------------------------------------------------

    def _scrape_linkedin(
        self,
        title: str,
        location: str,
        job_type: JobType,
        max_results: int,
        date_filter: DateFilter = "Toutes",
    ) -> list[Job]:
        type_param = JOB_TYPE_PARAMS.get(job_type, "")
        date_param = LINKEDIN_DATE_PARAMS.get(date_filter, "")
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={title.replace(' ', '%20')}"
            f"&location={location.replace(' ', '%20')}"
            f"{type_param}{date_param}"
        )
        assert self._driver is not None
        self._driver.get(url)

        try:
            WebDriverWait(self._driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "base-card"))
            )
        except TimeoutException:
            logger.warning("LinkedIn : timeout sur '%s' @ '%s'", title, location)
            return []

        jobs: list[Job] = []
        cards = self._driver.find_elements(By.CLASS_NAME, "base-card")

        for card in cards[:max_results]:
            try:
                t = card.find_element(
                    By.CLASS_NAME, "base-search-card__title"
                ).text.strip()
                c = card.find_element(
                    By.CLASS_NAME, "base-search-card__subtitle"
                ).text.strip()
                link_elem = card.find_element(By.TAG_NAME, "a")
                href = link_elem.get_attribute("href") or ""
                loc_text = ""
                try:
                    loc_text = card.find_element(
                        By.CLASS_NAME, "job-search-card__location"
                    ).text.strip()
                except NoSuchElementException:
                    pass

                jobs.append(
                    Job(
                        title=t,
                        company=c,
                        link=href.split("?")[0],
                        source="LinkedIn",
                        location=loc_text,
                    )
                )
            except NoSuchElementException:
                continue

        return jobs

    # ------------------------------------------------------------------
    # Indeed (squelette — à compléter selon les besoins)
    # ------------------------------------------------------------------

    def _scrape_indeed(
        self,
        title: str,
        location: str,
        job_type: JobType,
        max_results: int,
        date_filter: DateFilter = "Toutes",
    ) -> list[Job]:
        url = (
            f"https://fr.indeed.com/jobs"
            f"?q={title.replace(' ', '+')}"
            f"&l={location.replace(' ', '+')}"
            f"{INDEED_DATE_PARAMS.get(date_filter, '')}"
        )
        if job_type == "Remote":
            url += "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11"

        assert self._driver is not None
        self._driver.get(url)
        time.sleep(3)

        jobs: list[Job] = []
        try:
            cards = self._driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
            for card in cards[:max_results]:
                try:
                    t = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span").text.strip()
                    c = card.find_element(
                        By.CSS_SELECTOR, "[data-testid='company-name']"
                    ).text.strip()
                    href = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a").get_attribute(
                        "href"
                    ) or ""
                    loc_text = ""
                    try:
                        loc_text = card.find_element(
                            By.CSS_SELECTOR, "[data-testid='text-location']"
                        ).text.strip()
                    except NoSuchElementException:
                        pass
                    jobs.append(
                        Job(
                            title=t,
                            company=c,
                            link=href,
                            source="Indeed",
                            location=loc_text,
                        )
                    )
                except NoSuchElementException:
                    continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("Indeed scraping error: %s", exc)

        return jobs

    # ------------------------------------------------------------------
    # WelcomeToTheJungle (squelette)
    # ------------------------------------------------------------------

    def _scrape_wttj(
        self, title: str, location: str, max_results: int
    ) -> list[Job]:
        url = (
            f"https://www.welcometothejungle.com/fr/jobs"
            f"?query={title.replace(' ', '%20')}"
            f"&refinementList%5Boffice.country_code%5D%5B%5D=FR"
        )
        assert self._driver is not None
        self._driver.get(url)
        time.sleep(4)

        jobs: list[Job] = []
        try:
            cards = self._driver.find_elements(
                By.CSS_SELECTOR, "li[data-testid='search-results-list-item-wrapper']"
            )
            for card in cards[:max_results]:
                try:
                    t = card.find_element(By.CSS_SELECTOR, "h4").text.strip()
                    c = card.find_element(By.CSS_SELECTOR, "span.sc-1vudcrq-5").text.strip()
                    href = card.find_element(By.TAG_NAME, "a").get_attribute("href") or ""
                    jobs.append(
                        Job(title=t, company=c, link=href, source="WelcomeToTheJungle")
                    )
                except NoSuchElementException:
                    continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("WTTJ scraping error: %s", exc)

        return jobs