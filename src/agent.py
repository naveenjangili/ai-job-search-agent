"""The agent pipeline: fetch → filter → dedupe → score → store → notify.

Run it:
    python -m src.agent            # real search (needs API keys in .env)
    python -m src.agent --demo     # offline sample data, no keys needed
"""
import argparse
import logging

from . import db, fetchers, notifier, settings
from .filters import dedupe, passes_prefilter
from .models import Job
from .scorer import Scorer, clean_html

log = logging.getLogger("agent")


def run(demo: bool = False, notify: bool = True, progress=None) -> dict:
    """Run one search cycle. `progress` is an optional callback(str) for the Streamlit UI."""
    say = progress or (lambda msg: log.info(msg))
    con = db.connect()
    scorer = Scorer()

    if demo:
        say("⚠️ DEMO MODE: using sample jobs, not real ones.")
        raw = fetchers.fetch_demo()
    else:
        removed = db.delete_demo_jobs(con)
        if removed:
            say(f"Removed {removed} old demo jobs from the database.")
        say("Fetching real jobs from job APIs…")
        raw = fetchers.fetch_all()
        for source, count in fetchers.STATS.items():
            say(f"• {source}: {count}" + (" jobs" if isinstance(count, int) else ""))
        for err in fetchers.ERRORS[:5]:
            say(f"❌ {err}")
        if not raw and not fetchers.ERRORS:
            say("No jobs returned by the APIs. Try shorter SEARCH_QUERIES or a bigger MAX_DAYS_OLD in src/settings.py.")
    for j in raw:
        j.description = clean_html(j.description)

    unique = dedupe(raw)
    new = [j for j in unique if not db.is_known(con, j)]
    say(f"{len(raw)} postings → {len(unique)} unique → {len(new)} not seen before")

    kept, dropped = [], {}
    for j in new:
        ok, why = passes_prefilter(j)
        if ok:
            kept.append(j)
        else:
            dropped[why] = dropped.get(why, 0) + 1
            j.score, j.reason = 0, f"Filtered out: {why}"
            db.save(con, j, status="filtered")   # remember it so it is not re-checked next run
    say(f"{len(kept)} pass the fresher filter (dropped: {dropped or 'none'})")

    say(f"Scoring {len(kept)} jobs with {scorer.mode}…")
    scored: list[Job] = []
    for i, j in enumerate(kept, 1):
        scorer.score(j)
        db.save(con, j)
        scored.append(j)
        if progress:
            progress(f"Scored {i}/{len(kept)}: {j.title} — {j.company} ({j.score})")

    top = sorted([j for j in scored if (j.score or 0) >= settings.MIN_SCORE_TO_NOTIFY],
                 key=lambda j: j.score, reverse=True)[: settings.TOP_N_TO_NOTIFY]
    sent = False
    if notify and top:
        sent = notifier.send_telegram(top)
        if sent:
            db.mark_notified(con, [j.uid for j in top])

    summary = {"fetched": len(raw), "new": len(new), "scored": len(scored),
               "top_matches": len(top), "telegram_sent": sent, "scorer": scorer.mode,
               "errors": list(fetchers.ERRORS) + scorer.errors}
    if scorer.errors:
        say(f"❌ Gemini problem: {scorer.errors[0]}  (used keyword scoring instead)")
    say(f"Done: {summary}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="AI job-search agent")
    parser.add_argument("--demo", action="store_true", help="use offline sample jobs instead of real APIs")
    parser.add_argument("--no-notify", action="store_true", help="skip the Telegram message")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not args.demo and not (settings.ADZUNA_APP_ID or settings.RAPIDAPI_KEY):
        raise SystemExit("No job API keys found. Add ADZUNA_* or RAPIDAPI_KEY to .env, or try --demo.")
    run(demo=args.demo, notify=not args.no_notify)


if __name__ == "__main__":
    main()
