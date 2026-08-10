"""
LinkedIn Job Scraper with Resume Matching
Uses Ollama LLM to analyze job matches against your resume
"""

import requests  #Sert à envoyer des requêtes HTTP (GET) vers LinkedIn
from bs4 import BeautifulSoup #Sert à parser le HTML (extraire titres, dates, entreprises…)
import time #Pour sleep() → éviter les bans LinkedIn
import json #Lire / écrire du JSON (LLM + fichiers)
from urllib.parse import quote #Encode les paramètres d’URL (AI Engineer → AI%20Engineer)
from datetime import datetime #Gérer les dates (scraping, affichage, sauvegarde)
import hashlib #Génère un identifiant unique pour chaque job
import pandas as pd #Créer le fichier CSV facilement
import pdfplumber #Lire le texte contenu dans ton CV PDF
from ollama import chat #Appeler le modèle IA local Ollama

# Import configuration
import config


# ------------------ PDF ------------------
def extract_text_from_pdf(pdf_path):
    """Extract text from PDF resume"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except FileNotFoundError:
        print(f"❌ Resume not found: {pdf_path}")
    except Exception as e:
        print(f"❌ Error reading resume: {e}")
    
    return text


# ------------------ JOB DETAILS FETCHER ------------------
def fetch_job_description(job_url):
    """Fetch full job description from LinkedIn job page"""
    try:
        response = requests.get(
            job_url, 
            headers=config.REQUEST_HEADERS, 
            timeout=config.REQUEST_TIMEOUT
        )
        
        if response.status_code != 200:
            return ""
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try to find job description
        description_elem = soup.find('div', class_='show-more-less-html__markup')
        if not description_elem:
            description_elem = soup.find('div', class_='description__text')
        if not description_elem:
            # Fallback: look for any div with description-related class
            description_elem = soup.find('div', class_=lambda x: x and 'description' in x.lower())
        
        if description_elem:
            return description_elem.get_text(strip=True, separator='\n')
        
        return ""
        
    except Exception as e:
        if config.DEBUG_MODE:
            print(f"  ⚠️ Error fetching job description: {e}")
        return ""


# ------------------ LLM ------------------
def compare_resume_with_job(resume_text, job_data):
    """
    Use Ollama to compare resume with job posting
    
    Args:
        resume_text: Full resume text
        job_data: Dictionary containing job info (title, company, location, description)
    """
    # Build job context
    job_context = f"""
Job Title: {job_data.get('title', 'Unknown')}
Company: {job_data.get('company', 'Unknown')}
Location: {job_data.get('location', 'Unknown')}

Job Description:
{job_data.get('description', 'No description available')}
"""
    
    if not job_context.strip() or job_data.get('description', '').strip() == '':
        return {
            "match_score": 0,
            "recommendation": "Don't Apply",
            "matched_skills": [],
            "missing_skills": [],
            "job_benefits": [],
            "analysis": "No job description available"
        }

    prompt = f"""
You are an expert career advisor and recruiter. Compare this resume with the job posting and provide a detailed analysis.

RESUME:
{resume_text}

JOB POSTING:
{job_context}

Analyze the match between the resume and job posting. Return ONLY a valid JSON object with this exact structure (no markdown, no code blocks, just raw JSON):

{{
  "match_score": <number 0-10>,
  "recommendation": "<Apply/Don't Apply/Maybe Apply>",
  "matched_skills": ["skill1", "skill2", "skill3"],
  "missing_skills": ["skill1", "skill2"],
  "job_benefits": ["benefit1", "benefit2"],
  "analysis": "<2-3 sentence summary of the match>"
}}

Be honest and specific. Match score:
- 8-10: Excellent match, highly qualified
- 5-7: Good match, meets most requirements
- 3-4: Partial match, missing key skills
- 0-2: Poor match, not qualified
"""
    
    try:
        if config.DEBUG_MODE:
            print("  🤖 Analyzing with Ollama...")
        
        response = chat(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        ) #appel a ollama 
        
        response_text = response.message.content.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        result = json.loads(response_text) #Transforme le JSON texte en dictionnaire Python
        
        # Validate structure
        required_keys = ['match_score', 'recommendation', 'matched_skills', 'missing_skills', 'job_benefits', 'analysis']
        for key in required_keys:
            if key not in result:
                result[key] = [] if key.endswith('skills') or key.endswith('benefits') else ("Unknown" if key == 'recommendation' else 0)
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON parsing error: {e}")
        if config.DEBUG_MODE:
            print(f"  Response was: {response_text[:200]}...")
        return {
            "match_score": 0,
            "recommendation": "Error",
            "matched_skills": [],
            "missing_skills": [],
            "job_benefits": [],
            "analysis": f"Error parsing LLM response: {str(e)}"
        }
    except Exception as e:
        print(f"  ⚠️ LLM Error: {e}")
        return {
            "match_score": 0,
            "recommendation": "Error",
            "matched_skills": [],
            "missing_skills": [],
            "job_benefits": [],
            "analysis": f"Error: {str(e)}"
        }


# ------------------ SCRAPER ------------------
class LinkedInJobScraper:
    def __init__(self, analyze_with_llm=None, fetch_descriptions=None):
        """
        Initialize scraper
        
        Args:
            analyze_with_llm: Enable LLM analysis (default from config)
            fetch_descriptions: Fetch full job descriptions (default from config)
        """
        self.base_url = config.LINKEDIN_JOBS_API_URL
        self.session = requests.Session()
        self.session.headers.update(config.REQUEST_HEADERS)
        
        # Load configuration
        self.analyze_with_llm = analyze_with_llm if analyze_with_llm is not None else config.ENABLE_LLM_ANALYSIS
        self.fetch_descriptions = fetch_descriptions if fetch_descriptions is not None else config.FETCH_JOB_DESCRIPTIONS
        
        # Load resume
        self.resume_text = extract_text_from_pdf(config.RESUME_PATH)
        self.jobs = []
        
        if self.analyze_with_llm and not self.resume_text:
            print("⚠️ Warning: LLM analysis enabled but no resume found!")
            print(f"   Resume path: {config.RESUME_PATH}")

    def build_search_url(self, job_title, location, start=0):
        """Build LinkedIn search URL"""
        params = {
            'keywords': job_title,
            'location': location,
            'start': start
        }
        return f"{self.base_url}?{'&'.join([f'{k}={quote(str(v))}' for k,v in params.items()])}"

    def scrape_job_listings(self, url, current_job_count=0, max_jobs=None):
        """Scrape job listings from a single page"""
        try:
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)

            if response.status_code != 200:
                print(f"❌ Request failed with status {response.status_code}")
                return []

            # Save response for debugging
            if config.SAVE_HTML_RESPONSES:
                with open(config.DEBUG_LAST_RESPONSE, 'w', encoding='utf-8') as f:
                    f.write(response.text)

            soup = BeautifulSoup(response.content, 'html.parser')
            job_cards = soup.find_all('li')

            jobs = []

            for li in job_cards:
                # Check if we've reached max_jobs limit
                if max_jobs and (current_job_count + len(jobs)) >= max_jobs:
                    print(f"  ⏹️ Reached max jobs limit ({max_jobs}), stopping...")
                    break
                
                try:
                    card = li.find('div', class_='base-card')
                    if not card:
                        continue

                    job_link = card.find('a', class_='base-card__full-link')
                    if not job_link:
                        continue

                    job_url = job_link.get('href')
                    if not job_url:
                        continue
                    
                    # Clean URL
                    if '?' in job_url:
                        job_url = job_url.split('?')[0]

                    job_id = hashlib.md5(job_url.encode()).hexdigest()

                    # Extract title
                    title_elem = card.find('h3', class_='base-search-card__title')
                    if not title_elem:
                        title_elem = card.find('h3')
                    title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"

                    # Extract company
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    if not company_elem:
                        company_elem = card.find('h4')
                    
                    if company_elem:
                        company_link = company_elem.find('a', class_='hidden-nested-link')
                        company = company_link.get_text(strip=True) if company_link else company_elem.get_text(strip=True)
                    else:
                        company = "Unknown Company"

                    # Extract location
                    location_elem = card.find('span', class_='job-search-card__location')
                    location = location_elem.get_text(strip=True) if location_elem else "Unknown"

                    # Extract posted date
                    date_elem = card.find('time', class_='job-search-card__listdate')
                    posted_date = date_elem.get('datetime') if date_elem else None
                    posted_text = date_elem.get_text(strip=True) if date_elem else "Unknown"

                    job = {
                        "job_id": job_id,
                        "title": title,
                        "company": company,
                        "location": location,
                        "link": job_url,
                        "posted_date": posted_date,
                        "posted_text": posted_text,
                        "scraped_at": datetime.now().isoformat()
                    }

                    # Optionally fetch full description
                    if self.fetch_descriptions:
                        print(f"  📄 Fetching description for: {title}")
                        job['description'] = fetch_job_description(job_url)
                        time.sleep(config.DELAY_AFTER_DESCRIPTION_FETCH)
                    else:
                        job['description'] = ""

                    # Optionally analyze with LLM
                    if self.analyze_with_llm and self.resume_text:
                        analysis = compare_resume_with_job(self.resume_text, job)
                        job['llm_analysis'] = analysis
                        
                        # Show quick summary
                        score = analysis.get('match_score', 0)
                        rec = analysis.get('recommendation', 'Unknown')
                        print(f"  ✓ {title} at {company} | Score: {score}/10 | {rec}")
                    else:
                        print(f"  ✓ {title} at {company}")

                    jobs.append(job)
                    
                except Exception as e:
                    if config.DEBUG_MODE:
                        print(f"  ⚠️ Error parsing card: {e}")
                    continue

            return jobs
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return []

    def scrape(self, job_titles=None, locations=None, max_pages=None, max_jobs=None):
        """
        Main scraping method
        
        Args:
            job_titles: List of job titles to search (default from config)
            locations: List of locations to search (default from config)
            max_pages: Max pages per location (default from config)
            max_jobs: Max total jobs to scrape (default from config)
        """
        # Use config defaults if not provided
        if job_titles is None:
            job_titles = config.DEFAULT_JOB_TITLES
        if locations is None:
            locations = config.DEFAULT_LOCATIONS
        if max_pages is None:
            max_pages = config.MAX_PAGES_PER_LOCATION
        if max_jobs is None:
            max_jobs = config.MAX_JOBS_TOTAL
        
        # Ensure lists
        if isinstance(job_titles, str):
            job_titles = [job_titles]
        if isinstance(locations, str):
            locations = [locations]
        
        all_jobs = []
        total_searches = len(job_titles) * len(locations)
        current_search = 0

        print(f"\n{'='*80}")
        print(f"🔍 SEARCH CONFIGURATION")
        print(f"{'='*80}")
        print(f"Job Titles: {', '.join(job_titles)}")
        print(f"Locations: {', '.join(locations)}")
        print(f"Max Pages per Location: {max_pages}")
        print(f"Max Jobs Total: {max_jobs if max_jobs else 'Unlimited'}")
        print(f"Fetch Descriptions: {self.fetch_descriptions}")
        print(f"LLM Analysis: {self.analyze_with_llm}")
        print(f"Ollama Model: {config.OLLAMA_MODEL}")
        print(f"{'='*80}\n")

        for job_title in job_titles:
            for location in locations:
                current_search += 1
                
                # Check if we've reached max_jobs
                if max_jobs and len(all_jobs) >= max_jobs:
                    print(f"✅ Reached max jobs limit ({max_jobs})")
                    break
                
                print(f"\n[{current_search}/{total_searches}] 🔍 Searching: '{job_title}' in '{location}'")
                
                for page in range(max_pages):
                    if max_jobs and len(all_jobs) >= max_jobs:
                        break

                    start = page * 25
                    url = self.build_search_url(job_title, location, start)
                    
                    print(f"\n🔎 Page {page + 1}/{max_pages}")
                    jobs = self.scrape_job_listings(url, current_job_count=len(all_jobs), max_jobs=max_jobs)

                    if not jobs:
                        if page == 0:
                            print("  ⚠️ No jobs found")
                        break

                    # Add unique jobs
                    new_jobs = 0
                    for job in jobs:
                        if max_jobs and len(all_jobs) >= max_jobs:
                            break
                        if not any(j['job_id'] == job['job_id'] for j in all_jobs):
                            all_jobs.append(job)
                            new_jobs += 1

                    print(f"📊 Found {len(jobs)} jobs ({new_jobs} new) | Total: {len(all_jobs)}")

                    # Delay between pages
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                
                # Delay between locations
                if current_search < total_searches:
                    time.sleep(config.DELAY_BETWEEN_LOCATIONS)

        self.jobs = all_jobs
        
        # Print results
        print(f"\n{'='*80}")
        print(f"✅ SCRAPING COMPLETE")
        print(f"{'='*80}")
        print(f"Total jobs scraped: {len(self.jobs)}")
        
        # Show top matches if LLM analysis was done
        if self.analyze_with_llm:
            jobs_with_scores = [j for j in self.jobs if 'llm_analysis' in j]
            if jobs_with_scores:
                jobs_with_scores.sort(key=lambda x: x.get('llm_analysis', {}).get('match_score', 0), reverse=True)
                print(f"\n🏆 TOP 5 MATCHES:")
                for i, job in enumerate(jobs_with_scores[:5], 1):
                    analysis = job.get('llm_analysis', {})
                    score = analysis.get('match_score', 0)
                    rec = analysis.get('recommendation', 'Unknown')
                    print(f"  {i}. {job['title']} at {job['company']}")
                    print(f"     Score: {score}/10 | {rec}")
        
        print(f"{'='*80}\n")

    def save(self, filename_prefix=None):
        """Save results to JSON and CSV"""
        if not self.jobs:
            print("❌ No jobs to save.")
            return

        # Use config default if not provided
        if filename_prefix is None:
            filename_prefix = config.DEFAULT_OUTPUT_PREFIX

        # Prepare output
        output = {
            "metadata": {
                "scrape_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_jobs": len(self.jobs),
                "llm_analysis_enabled": self.analyze_with_llm,
                "descriptions_fetched": self.fetch_descriptions,
                "ollama_model": config.OLLAMA_MODEL
            },
            "items": self.jobs
        }

        # Save JSON
        json_file = config.get_output_path(f"{filename_prefix}.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=config.JSON_INDENT, ensure_ascii=config.JSON_ENSURE_ASCII)

        # Save CSV
        csv_data = []
        for job in self.jobs:
            row = {
                'job_id': job.get('job_id'),
                'title': job.get('title'),
                'company': job.get('company'),
                'location': job.get('location'),
                'link': job.get('link'),
                'posted_date': job.get('posted_date'),
                'posted_text': job.get('posted_text'),
                'scraped_at': job.get('scraped_at')
            }
            
            # Add LLM analysis columns if available
            if 'llm_analysis' in job:
                analysis = job['llm_analysis']
                row['match_score'] = analysis.get('match_score', 0)
                row['recommendation'] = analysis.get('recommendation', 'Unknown')
                row['matched_skills'] = ', '.join(analysis.get('matched_skills', []))
                row['missing_skills'] = ', '.join(analysis.get('missing_skills', []))
                row['job_benefits'] = ', '.join(analysis.get('job_benefits', []))
                row['analysis'] = analysis.get('analysis', '')
            
            csv_data.append(row)

        csv_file = config.get_output_path(f"{filename_prefix}.csv")
        df = pd.DataFrame(csv_data)
        df.to_csv(csv_file, index=False, encoding=config.CSV_ENCODING)

        print(f"\n💾 FILES SAVED:")
        print(f"   - {json_file} ({len(self.jobs)} jobs)")
        print(f"   - {csv_file} ({len(self.jobs)} jobs)")
        
        # Print summary stats
        print(f"\n📊 SUMMARY:")
        print(f"   - Total jobs: {len(self.jobs)}")
        print(f"   - Unique companies: {len(set(j['company'] for j in self.jobs))}")
        print(f"   - Unique locations: {len(set(j['location'] for j in self.jobs))}")
        
        if self.analyze_with_llm:
            jobs_with_analysis = [j for j in self.jobs if 'llm_analysis' in j]
            if jobs_with_analysis:
                avg_score = sum(j.get('llm_analysis', {}).get('match_score', 0) for j in jobs_with_analysis) / len(jobs_with_analysis)
                apply_count = sum(1 for j in jobs_with_analysis if j.get('llm_analysis', {}).get('recommendation') == 'Apply')
                print(f"   - Average match score: {avg_score:.1f}/10")
                print(f"   - Recommended to apply: {apply_count} jobs")


# ------------------ MAIN ------------------
def main():
    """Main entry point"""
    
    # Validate configuration
    if not config.validate_config():
        print("\n❌ Please fix configuration errors in config.py")
        return
    
    # Optional: print configuration
    if config.DEBUG_MODE:
        config.print_config()
    
    # Initialize scraper
    scraper = LinkedInJobScraper()
    
    # Run scraper with config defaults
    scraper.scrape()
    
    # Save results
    scraper.save()
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()