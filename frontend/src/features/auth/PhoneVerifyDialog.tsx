import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Field, Input } from "@/components/ui/Field";
import { OtpInput } from "@/components/ui/OtpInput";
import { api, unwrap } from "@/lib/api/client";
import { ApiError, fieldErrors, userMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { formatPhone, toE164 } from "@/lib/phone";

const RESEND_SECONDS = 60;

/**
 * Verify a phone by SMS code: (optionally) set the number, send a 6-digit code, enter it.
 * SMS feedback is only ever sent to verified phones.
 */
export function PhoneVerifyDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { user, refreshMe } = useAuth();
  const [phone, setPhone] = useState(user?.phone ? formatPhone(user.phone) : "");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = window.setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => window.clearTimeout(t);
  }, [cooldown]);

  const send = async () => {
    setError(null);
    const e164 = toE164(phone);
    if (!e164) {
      setError("Enter a valid phone number, e.g. 0712 345 678.");
      return;
    }
    setBusy(true);
    try {
      const result = await unwrap(api.POST("/api/v1/auth/phone/send-code", { body: { phone: e164 } }));
      setSentTo(result.phone);
      setDevCode(result.devCode ?? null); // only in local development while SMS is dry-run
      setCooldown(RESEND_SECONDS);
      setCode("");
      toast("Code sent by SMS");
    } catch (e) {
      setError(fieldErrors(e).phone ?? userMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setError(null);
    try {
      await unwrap(api.POST("/api/v1/auth/phone/verify", { body: { code } }));
      await refreshMe();
      toast("Phone verified");
      onOpenChange(false);
    } catch (e) {
      setError(
        e instanceof ApiError && e.code === "code_attempts_exceeded"
          ? "Too many wrong codes. Send a new one."
          : e instanceof ApiError && e.code === "code_invalid"
            ? "That code is wrong or has expired."
            : userMessage(e),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Verify your phone"
      description="We text feedback only to verified numbers. Standard SMS rates may apply."
    >
      {!sentTo ? (
        <div className="space-y-4">
          <Field label="Phone number" hint="Kenyan numbers: 07…, 01… or +254…" error={error ?? undefined}>
            {({ id, describedBy, invalid }) => (
              <Input id={id} aria-describedby={describedBy} invalid={invalid} type="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
            )}
          </Field>
          <Button className="w-full" loading={busy} onClick={send}>
            Send code
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-mist">
            Enter the 6-digit code sent to <span className="text-ink">{formatPhone(sentTo)}</span>.
          </p>
          <OtpInput value={code} onChange={setCode} invalid={Boolean(error)} />
          {error && (
            <p role="alert" className="text-sm text-bad">
              {error}
            </p>
          )}
          {devCode && <p className="text-xs text-mist">Development only (SMS dry run): code {devCode}</p>}
          <Button className="w-full" loading={busy} disabled={code.length !== 6} onClick={verify}>
            Verify phone
          </Button>
          <Button variant="ghost" className="w-full" disabled={cooldown > 0 || busy} onClick={send}>
            {cooldown > 0 ? `Send a new code in ${cooldown}s` : "Send a new code"}
          </Button>
        </div>
      )}
    </Dialog>
  );
}
