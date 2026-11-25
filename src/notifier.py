"""Send the top new matches to your phone on Telegram (optional)."""
import html
import logging

import requests

from . import settings
from .models import Job

log = logging.getLogger(__name__)


def format_message(jobs: list[Job]) -> str:
    lines = [f"<b>🎯 {len(jobs)} new job matches</b>\n"]
    for i, j in enumerate(jobs, 1):
        lines.append(
            f"<b>{i}. {html.escape(j.title)} — {html.escape(j.company)}</b>\n"
            f"📍 {html.escape(j.location)} · ⭐ {j.score}/100 · 📄 {html.escape(j.resume_version)} resume\n"
            f"✅ {html.escape(j.reason)}\n"
            f"🔗 {html.escape(j.url)}\n"
        )
    return "\n".join(lines)


def send_telegram(jobs: list[Job]) -> bool:
    if not jobs or not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": format_message(jobs),
               "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload, timeout=30).raise_for_status()
        return True
    except requests.RequestException as e:
        log.warning("Telegram send failed: %s", e)
        return False
