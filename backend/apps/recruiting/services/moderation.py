"""Feedback hygiene (brief section 10). Pure.

- HTML is stripped (we render feedback as text in emails and the app).
- Max 1,000 characters after cleaning.
- Links must be https (no http://, javascript: or other schemes).
- A small abuse word list holds the message for admin review instead of sending it. It's a
  safety net for a demo, not a content-moderation system; the list lives in ABUSE_WORDS.
"""

import re
from dataclasses import dataclass

from django.utils.html import strip_tags

MAX_LENGTH = 1000
_URL = re.compile(r"\b([a-z][a-z0-9+.-]*):(//)?[^\s<>\"']+", re.IGNORECASE)
_SAFE_PREFIXES = ("https://",)
ABUSE_WORDS = {
    "idiot",
    "stupid",
    "useless",
    "moron",
    "dumb",
    "loser",
    "trash",
    "garbage",
    "shut up",
    "fuck",
    "shit",
    "bitch",
    "bastard",
    "asshole",
    "crap",
    "wtf",
    "mjinga",
    "pumbavu",
    "mavi",
    "malaya",
    "fala",  # common Swahili/Sheng insults
}
_ABUSE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(ABUSE_WORDS)) + r")\b", re.IGNORECASE
)


class FeedbackRejected(ValueError):
    pass


@dataclass(frozen=True)
class CleanFeedback:
    message: str
    hold_reason: str  # "" when the message can be sent


def clean(raw: str) -> CleanFeedback:
    text = strip_tags(raw or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise FeedbackRejected("Write a message.")
    if len(text) > MAX_LENGTH:
        raise FeedbackRejected(f"Keep feedback under {MAX_LENGTH} characters.")
    for match in _URL.finditer(text):
        url = match.group(0)
        if match.group(1).lower() in {
            "http",
            "https",
            "javascript",
            "data",
            "ftp",
            "file",
            "mailto",
        } and not url.lower().startswith(_SAFE_PREFIXES):
            raise FeedbackRejected("Only https:// links are allowed.")
    found = _ABUSE.search(text)
    reason = f"Contains flagged language ({found.group(1).lower()})" if found else ""
    return CleanFeedback(text, reason)
