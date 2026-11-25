"""Turn an uploaded resume (PDF, TXT or MD) into the profile the AI scores jobs against."""
import io

from . import settings


def extract_text(filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    return data.decode("utf-8", errors="ignore").strip()


def save_profile(text: str) -> None:
    settings.PROFILE_PATH.write_text(text, encoding="utf-8")


def load_profile() -> str:
    try:
        return settings.PROFILE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
