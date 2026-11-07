"""Phone numbers: accept what Kenyans type (07…, 01…, +254…, 254…) and store E.164."""

import phonenumbers


class InvalidPhone(ValueError):
    pass


def normalise(raw: str, region: str = "KE") -> str:
    """Return E.164 (e.g. +254712345678) or raise InvalidPhone."""
    text = (raw or "").strip()
    if text.startswith("254"):  # people often drop the plus
        text = f"+{text}"
    try:
        number = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhone("Enter a valid phone number, e.g. 0712 345 678.") from exc
    if not phonenumbers.is_valid_number(number):
        raise InvalidPhone("Enter a valid phone number, e.g. 0712 345 678.")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def mask(e164: str) -> str:
    """+254712345678 → +2547*****678, for logs."""
    if not e164 or len(e164) < 8:
        return "***"
    return f"{e164[:5]}{'*' * (len(e164) - 8)}{e164[-3:]}"
