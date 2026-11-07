import { parsePhoneNumberFromString } from "libphonenumber-js";

/** Kenyan formats people type (07…, 01…, +254…, 254…) → E.164, matching the backend's rule. */
export function toE164(raw: string): string | null {
  const text = raw.trim().startsWith("254") ? `+${raw.trim()}` : raw.trim();
  const parsed = parsePhoneNumberFromString(text, "KE");
  return parsed?.isValid() ? parsed.number : null;
}

export function formatPhone(e164: string | null | undefined): string {
  if (!e164) return "";
  return parsePhoneNumberFromString(e164)?.formatInternational() ?? e164;
}
