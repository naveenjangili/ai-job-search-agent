"""Fetch real job postings from job APIs (no scraping).

- Adzuna:  free key at https://developer.adzuna.com  (has India listings, country code "in")
- JSearch: free tier on RapidAPI, pulls from Google for Jobs (LinkedIn, Indeed, Naukri, company sites...)
"""
import json
import logging

import requests

from . import settings
from .models import Job

log = logging.getLogger(__name__)
TIMEOUT = 30

# Filled during fetch_all() so the dashboard can show what happened.
STATS: dict = {}
ERRORS: list[str] = []


def _record_error(source: str, query: str, where: str, e: Exception) -> None:
    detail = str(e)
    resp = getattr(e, "response", None)
    if resp is not None:
        detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
    msg = f"{source} error for '{query}' in {where}: {detail}"
    log.warning(msg)
    if msg not in ERRORS:
        ERRORS.append(msg)


def _auth_failed(source: str) -> bool:
    return any(e.startswith(source) and ("HTTP 401" in e or "HTTP 403" in e) for e in ERRORS)


def fetch_adzuna(query: str, location: str) -> list[Job]:
    if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
        return []
    url = "https://api.adzuna.com/v1/api/jobs/in/search/1"
    params = {
        "app_id": settings.ADZUNA_APP_ID,
        "app_key": settings.ADZUNA_APP_KEY,
        "what": query,
        "where": location,
        "results_per_page": settings.RESULTS_PER_QUERY,
        "max_days_old": settings.MAX_DAYS_OLD,
        "what_exclude": settings.ADZUNA_EXCLUDE,
        "sort_by": "date",
        "content-type": "application/json",
    }
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        _record_error("Adzuna", query, location, e)
        return []

    jobs = []
    for item in r.json().get("results", []):
        salary = ""
        if item.get("salary_min"):
            salary = f"₹{int(item['salary_min']):,}" + (f" – ₹{int(item['salary_max']):,}" if item.get("salary_max") else "")
        jobs.append(Job(
            source="adzuna",
            source_id=str(item.get("id")),
            title=item.get("title", "").strip(),
            company=(item.get("company") or {}).get("display_name", "Unknown"),
            location=(item.get("location") or {}).get("display_name", location),
            url=item.get("redirect_url", ""),
            description=item.get("description", ""),
            posted_at=(item.get("created") or "")[:10],
            salary=salary,
        ))
    return jobs


def fetch_jsearch(query: str, location: str) -> list[Job]:
    if not settings.RAPIDAPI_KEY:
        return []
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {"X-RapidAPI-Key": settings.RAPIDAPI_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    q = f"{query} remote" if location.lower() == "remote" else f"{query} in {location}"
    params = {
        "query": q,
        "page": 1,
        "num_pages": 1,
        "country": "in",
        "date_posted": "month" if settings.MAX_DAYS_OLD > 7 else "week" if settings.MAX_DAYS_OLD > 3 else "3days",
    }
    if location.lower() == "remote":
        params["work_from_home"] = "true"
    try:
        r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        _record_error("JSearch", query, location, e)
        return []

    jobs = []
    for item in r.json().get("data", []):
        city = item.get("job_city") or ""
        loc = "Remote" if item.get("job_is_remote") else (city or item.get("job_country") or location)
        jobs.append(Job(
            source="jsearch",
            source_id=str(item.get("job_id")),
            title=(item.get("job_title") or "").strip(),
            company=item.get("employer_name") or "Unknown",
            location=loc,
            url=item.get("job_apply_link") or item.get("job_google_link") or "",
            description=item.get("job_description") or "",
            posted_at=(item.get("job_posted_at_datetime_utc") or "")[:10],
        ))
    return jobs


def fetch_demo() -> list[Job]:
    """Offline sample data so you can try the app before getting API keys."""
    with open(settings.DEMO_JOBS_PATH, encoding="utf-8") as f:
        return [Job(source="demo", **j) for j in json.load(f)]


def fetch_all() -> list[Job]:
    STATS.clear(); ERRORS.clear()
    jobs: list[Job] = []
    if settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY:
        n = 0
        for query in settings.SEARCH_QUERIES:      # Adzuna: all queries x all cities
            for loc in settings.LOCATIONS:
                found = fetch_adzuna(query, loc)
                n += len(found); jobs += found
                if _auth_failed("Adzuna"):
                    break
            if _auth_failed("Adzuna"):
                STATS["Adzuna"] = "stopped: the API rejected your keys (check ADZUNA_APP_ID / ADZUNA_APP_KEY)"
                break
        else:
            STATS["Adzuna"] = n
    else:
        STATS["Adzuna"] = "skipped (no ADZUNA_APP_ID / ADZUNA_APP_KEY in .env)"
    if settings.RAPIDAPI_KEY:
        n = 0
        for query in settings.JSEARCH_QUERIES:     # JSearch: smaller set (free-tier limit)
            for loc in settings.JSEARCH_LOCATIONS:
                found = fetch_jsearch(query, loc)
                n += len(found); jobs += found
                if _auth_failed("JSearch"):
                    break
            if _auth_failed("JSearch"):
                STATS["JSearch"] = "stopped: RapidAPI rejected your key or you are not subscribed to JSearch"
                break
        else:
            STATS["JSearch"] = n
    else:
        STATS["JSearch"] = "skipped (no RAPIDAPI_KEY in .env)"
    log.info("Fetched %d raw postings: %s", len(jobs), STATS)
    return jobs
