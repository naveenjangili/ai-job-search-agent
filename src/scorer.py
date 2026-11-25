"""Score each job against your profile with Gemini (falls back to keyword matching without a key)."""
import json
import logging
import re
import time

from . import settings
from .models import Job

log = logging.getLogger(__name__)

PROMPT = """You are a career assistant helping an Indian fresher decide which jobs to apply for.

CANDIDATE PROFILE:
{profile}

JOB POSTING:
Title: {title}
Company: {company}
Location: {location}
Description:
{description}

Judge how well this job fits the candidate. Be strict about experience: a job needing 2+ years is a poor fit.
Return ONLY valid JSON with exactly these keys:
{{
  "score": <integer 0-100>,
  "verdict": "<one of: strong match, good match, weak match, not a fit>",
  "experience_ok": <true or false>,
  "matching_skills": [<skills from the posting the candidate has, max 6>],
  "missing_skills": [<important skills the posting asks for that the candidate lacks, max 4>],
  "resume_version": "<'Data Analyst' or 'AI/ML' — which resume version to send>",
  "reason": "<one short sentence explaining the score>"
}}"""

# Used when no Gemini key is set.
KEYWORDS = {
    "sql": 10, "power bi": 10, "excel": 8, "python": 10, "pandas": 6, "tableau": 3, "dax": 5,
    "statistics": 4, "machine learning": 6, "scikit": 5, "dashboard": 6, "data visualization": 6,
    "fresher": 10, "entry level": 8, "graduate": 6, "0-1": 8, "trainee": 6, "generative ai": 6,
    "llm": 5, "rag": 5, "streamlit": 3, "etl": 3,
}
AI_WORDS = ("machine learning", "ml ", "ai ", "llm", "generative", "nlp", "deep learning", "data scientist")


class Scorer:
    def __init__(self):
        self.profile = settings.PROFILE_PATH.read_text(encoding="utf-8")
        self.client = None
        self.errors: list[str] = []
        if settings.GEMINI_API_KEY:
            from google import genai
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    @property
    def mode(self) -> str:
        return f"Gemini ({settings.GEMINI_MODEL})" if self.client else "keyword fallback"

    def score(self, job: Job) -> Job:
        result = self._gemini(job) if self.client else None
        if result is None:
            result = self._keywords(job)
        job.score = int(result.get("score", 0))
        if result.get("experience_ok") is False:
            job.score = min(job.score, 30)
        job.verdict = result.get("verdict", "")
        job.reason = result.get("reason", "")
        job.matching_skills = result.get("matching_skills", [])[:6]
        job.missing_skills = result.get("missing_skills", [])[:4]
        job.resume_version = result.get("resume_version", "Data Analyst")
        return job

    def _gemini(self, job: Job, retries: int = 3) -> dict | None:
        from google.genai import types
        prompt = PROMPT.format(profile=self.profile, title=job.title, company=job.company,
                               location=job.location, description=job.description[:6000])
        for attempt in range(retries):
            try:
                resp = self.client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
                )
                return json.loads(resp.text)
            except Exception as e:  # rate limits, bad JSON, network, bad key
                text = str(e)
                fatal = any(w in text for w in ("API_KEY", "API key", "PERMISSION_DENIED", "UNAUTHENTICATED",
                                                "401", "403", "not found", "NOT_FOUND"))
                if fatal or attempt == retries - 1:
                    self.errors.append(text[:300])
                    log.warning("Gemini disabled for this run: %s", text[:300])
                    self.client = None          # stop trying; keyword scoring for the rest
                    return None
                wait = 5 * (attempt + 1)
                log.warning("Gemini scoring failed (%s); retrying in %ss", text[:200], wait)
                time.sleep(wait)
        return None

    def _keywords(self, job: Job) -> dict:
        text = f" {job.title} {job.description} ".lower()
        hits = [k for k in KEYWORDS if k in text]
        score = min(100, 20 + sum(KEYWORDS[k] for k in hits))
        is_ai = any(w in text for w in AI_WORDS)
        return {
            "score": score,
            "verdict": "good match" if score >= 65 else "weak match",
            "matching_skills": [k.title() for k in hits if k not in ("fresher", "entry level", "graduate", "0-1", "trainee")],
            "missing_skills": [],
            "resume_version": "AI/ML" if is_ai else "Data Analyst",
            "reason": f"Keyword match on {len(hits)} terms (add a Gemini key for smarter scoring).",
        }


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "")
