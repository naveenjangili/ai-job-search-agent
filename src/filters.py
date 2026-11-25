"""Cheap rule-based filters that run before the LLM, to save API calls."""
import re

from . import settings
from .models import Job

# matches "2+ years", "3-5 yrs", "2 to 4 years", "minimum 3 years"
_EXP = re.compile(r"(\d{1,2})\s*(?:\+|-|–|to)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)", re.I)


def min_years_required(text: str) -> int | None:
    """Smallest 'N years' mentioned near experience words, or None if not stated."""
    best = None
    for m in _EXP.finditer(text):
        window = text[max(0, m.start() - 60): m.end() + 40].lower()
        if "experience" not in window and "exp" not in window:
            continue
        n = int(m.group(1))
        if n > 20:
            continue
        best = n if best is None else min(best, n)
    return best


def is_senior_title(title: str) -> bool:
    t = f" {title.lower()} "
    return any(w in t for w in settings.SENIOR_TITLE_WORDS)


def passes_prefilter(job: Job) -> tuple[bool, str]:
    if not job.url:
        return False, "no apply link"
    if is_senior_title(job.title):
        return False, "senior title"
    years = min_years_required(f"{job.title}. {job.description}")
    if years is not None and years > settings.MAX_YEARS_EXPERIENCE:
        return False, "too much experience"
    return True, ""


def dedupe(jobs: list[Job]) -> list[Job]:
    seen_uid, seen_key, out = set(), set(), []
    for j in jobs:
        if j.uid in seen_uid or j.dedupe_key in seen_key:
            continue
        seen_uid.add(j.uid)
        seen_key.add(j.dedupe_key)
        out.append(j)
    return out
