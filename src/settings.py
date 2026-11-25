"""All settings in one place. Secrets come from the .env file; search preferences live here."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ---- API keys (put them in .env, never commit them) ----
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")          # for JSearch
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---- What to search for ----
# Adzuna needs EVERY word to appear in the posting, so keep queries short and don't add
# "fresher" (most Indian job ads never use that word). The fresher filter and Gemini
# remove senior jobs afterwards.
SEARCH_QUERIES = [
    "data analyst",
    "business analyst",
    "power bi",
    "data scientist",
    "machine learning",
    "python sql",
]
LOCATIONS = ["Hyderabad", "Bangalore", "Pune", "Chennai"]
# JSearch's free plan allows only ~200 requests a month, so it gets a smaller set:
# 3 queries x 2 locations = 6 calls per run = ~180 a month if you run it daily.
JSEARCH_QUERIES = ["data analyst fresher", "entry level data analyst", "machine learning engineer fresher"]
JSEARCH_LOCATIONS = ["Hyderabad", "remote"]
MAX_DAYS_OLD = 14            # ignore postings older than this
RESULTS_PER_QUERY = 20

# ---- Filtering and scoring ----
MAX_YEARS_EXPERIENCE = 1     # drop jobs whose minimum experience is above this
MIN_SCORE_TO_NOTIFY = 65     # only send Telegram alerts for jobs at or above this score
TOP_N_TO_NOTIFY = 10
SENIOR_TITLE_WORDS = ["senior", "sr.", "sr ", "lead", "principal", "manager", "head of", "architect", "director"]

# Words that remove senior postings at the source (Adzuna)
ADZUNA_EXCLUDE = "senior lead manager principal architect director head"

# ---- Files ----
DB_PATH = ROOT / "data" / "jobs.db"
PROFILE_PATH = ROOT / "profile.md"
DEMO_JOBS_PATH = ROOT / "data" / "demo_jobs.json"
