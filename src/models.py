from dataclasses import dataclass, field, asdict
import re


@dataclass
class Job:
    source: str            # "adzuna", "jsearch" or "demo"
    source_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted_at: str = ""    # ISO date string
    salary: str = ""
    # filled in by the scorer
    score: int | None = None
    verdict: str = ""
    reason: str = ""
    matching_skills: list = field(default_factory=list)
    missing_skills: list = field(default_factory=list)
    resume_version: str = ""

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def dedupe_key(self) -> str:
        """Same company + same title = same job, even if found on two sites."""
        norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        return f"{norm(self.company)}|{norm(self.title)}"

    def to_dict(self) -> dict:
        return asdict(self)
