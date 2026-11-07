"""Make SMS fit one GSM-7 part (160 characters). Pure.

A single non-GSM character (a smart quote, an en dash, an emoji) switches the whole message to
UCS-2, where one part holds only 70 characters, so the message would be split and cost 2–3 SMS.
We replace look-alikes, drop the rest, and shorten the message part, never the link or opt-out.
"""

SINGLE_PART = 160

_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
_EXTENDED = set("^{}\\[~]|€")  # count as 2 (escape + char)
_REPLACEMENTS = {
    "‘": "'",
    "’": "'",
    "‚": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "–": "-",
    "—": "-",
    "−": "-",
    "…": "...",
    "•": "*",
    " ": " ",
    "\t": " ",
    "×": "x",
}


def to_gsm(text: str) -> str:
    out = []
    for char in text:
        char = _REPLACEMENTS.get(char, char)
        out.append("".join(c for c in char if c in _BASIC or c in _EXTENDED))
    return " ".join("".join(out).split())  # SMS is one line; collapse whitespace


def gsm_length(text: str) -> int:
    return sum(2 if c in _EXTENDED else 1 for c in text)


def compose(message: str, *, link: str = "", footer: str = "", limit: int = SINGLE_PART) -> str:
    """message + link + footer in one part. Only `message` is shortened (with "...")."""
    message, link, footer = to_gsm(message), to_gsm(link), to_gsm(footer)
    tail = " ".join(p for p in (link, footer) if p)
    budget = limit - gsm_length(tail) - (1 if tail else 0)
    if gsm_length(message) > budget:
        trimmed = message
        while trimmed and gsm_length(trimmed) + 3 > budget:
            trimmed = trimmed[:-1]
        message = trimmed.rstrip() + "..." if trimmed else ""
    return " ".join(p for p in (message, tail) if p)
