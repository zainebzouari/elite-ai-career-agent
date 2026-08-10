# 🚀 Elite AI Career Agent

Un assistant IA qui recherche des offres d'emploi, les compare à ton CV et génère des lettres de motivation personnalisées — le tout via un pipeline d'agents IA exécuté en local (aucune API cloud payante).

## ✨ Fonctionnalités

- **Analyse de CV** : extraction automatique du contenu de ton CV (PDF)
- **Recherche d'offres** : LinkedIn (fonctionnel), Indeed (partiel), WelcomeToTheJungle (expérimental)
- **Filtres avancés** : titres de poste, localisation, type de contrat, date de publication, plateformes
- **Matching IA** : chaque offre est analysée individuellement pour un score de compatibilité fiable (0-100), avec points forts, points à améliorer et conseil stratégique
- **Lettres de motivation** : génération sur mesure à partir de ton CV et de la description réelle du poste, export PDF et TXT
- **Export des résultats** : CSV, JSON, rapport Markdown

## 🛠️ Stack technique

| Domaine | Outil |
|---|---|
| Interface | [Streamlit](https://streamlit.io) |
| Scraping | Selenium (pages dynamiques) + Requests/BeautifulSoup (descriptions) |
| Extraction CV | pdfplumber |
| Orchestration IA | [CrewAI](https://www.crewai.com) |
| Modèle de langage | [Ollama](https://ollama.com) en local, via LiteLLM |
| Export PDF | fpdf2 |
| Données | pandas |
| Configuration | python-dotenv |

## 📋 Prérequis

- **Python 3.10+**
- **[Ollama](https://ollama.com/download)** installé et démarré localement
- **Google Chrome** installé (utilisé par Selenium pour le scraping)

## ⚙️ Installation

1. **Cloner le dépôt**
   ```bash
   git clone https://github.com/<ton-utilisateur>/elite-ai-career-agent.git
   cd elite-ai-career-agent
   ```

2. **Créer un environnement virtuel** (recommandé)
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS / Linux
   source venv/bin/activate
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurer les variables d'environnement**

   Copie `.env.example` vers `.env` et ajuste les valeurs si besoin :
   ```bash
   cp .env.example .env
   ```

5. **Télécharger un modèle Ollama** (si ce n'est pas déjà fait)
   ```bash
   ollama pull qwen2.5:7b
   ollama serve
   ```

## ▶️ Lancer l'application

```bash
streamlit run app.py
```

L'application s'ouvre automatiquement sur `http://localhost:8501`.

## 📁 Structure du projet

```
elite-ai-career-agent/
├── app.py              # Interface Streamlit (UI, filtres, onglets, session state)
├── agents.py           # Agents IA (matching CV × offres, lettre de motivation)
├── scraper.py           # Scraping des plateformes d'offres d'emploi
├── config.py            # Configuration centralisée (lue depuis .env)
├── requirements.txt      # Dépendances Python
├── .env.example          # Exemple de variables d'environnement
├── .gitignore
└── README.md
```