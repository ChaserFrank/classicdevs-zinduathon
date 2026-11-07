import { cn } from "@/lib/utils";

/** Rough guide only; the backend's password validators make the final call. */
export function passwordScore(value: string): 0 | 1 | 2 | 3 | 4 {
  if (!value) return 0;
  let score = 0;
  if (value.length >= 8) score++;
  if (value.length >= 12) score++;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score++;
  if (/\d/.test(value) && /[^A-Za-z0-9]/.test(value)) score++;
  if (/^(.)\1+$/.test(value) || /^(password|12345678|qwerty)/i.test(value)) score = 1;
  return Math.min(4, Math.max(1, score)) as 1 | 2 | 3 | 4;
}

const LABELS = ["", "Weak", "Fair", "Good", "Strong"];

export function PasswordStrength({ value }: { value: string }) {
  const score = passwordScore(value);
  if (!value) return null;
  return (
    <div className="mt-2" aria-live="polite">
      <div className="flex gap-1" aria-hidden>
        {[1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className={cn(
              "h-1 flex-1 rounded-full bg-white/10 transition-colors",
              i <= score && (score <= 1 ? "bg-bad" : score === 2 ? "bg-warn" : "bg-ok"),
            )}
          />
        ))}
      </div>
      <p className="mt-1 text-xs text-mist">Password strength: {LABELS[score]}</p>
    </div>
  );
}
