import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

/** Six separate boxes with paste support; value is the joined digits. */
export function OtpInput({
  value,
  onChange,
  invalid,
  label = "Verification code",
  length = 6,
}: {
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  label?: string;
  length?: number;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = Array.from({ length }, (_, i) => value[i] ?? "");

  const set = (index: number, digit: string) => {
    const next = digits.slice();
    next[index] = digit;
    onChange(next.join("").slice(0, length));
  };

  const onKey = (i: number) => (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) refs.current[i - 1]?.focus();
    if (e.key === "ArrowLeft" && i > 0) refs.current[i - 1]?.focus();
    if (e.key === "ArrowRight" && i < length - 1) refs.current[i + 1]?.focus();
  };

  const onPaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (!pasted) return;
    e.preventDefault();
    onChange(pasted);
    refs.current[Math.min(pasted.length, length - 1)]?.focus();
  };

  return (
    <fieldset>
      <legend className="sr-only">{label}</legend>
      <div className="flex justify-between gap-2">
        {digits.map((digit, i) => (
          <input
            key={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            aria-label={`Digit ${i + 1} of ${length}`}
            aria-invalid={invalid || undefined}
            inputMode="numeric"
            autoComplete={i === 0 ? "one-time-code" : "off"}
            maxLength={1}
            value={digit}
            onPaste={onPaste}
            onKeyDown={onKey(i)}
            onChange={(e) => {
              const d = e.target.value.replace(/\D/g, "").slice(-1);
              set(i, d);
              if (d && i < length - 1) refs.current[i + 1]?.focus();
            }}
            className={cn(
              "tabular h-14 w-12 rounded-xl border border-line bg-black/40 text-center text-xl font-semibold text-ink outline-none",
              "focus:border-flare/70 focus:ring-2 focus:ring-flare/30",
              invalid && "border-bad/70",
            )}
          />
        ))}
      </div>
    </fieldset>
  );
}
