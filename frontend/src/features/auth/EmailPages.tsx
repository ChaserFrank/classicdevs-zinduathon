import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { PasswordStrength } from "@/components/ui/PasswordStrength";
import { SkeletonBlock } from "@/components/ui/States";
import { api, unwrap } from "@/lib/api/client";
import { ApiError, fieldErrors, userMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { homeFor } from "@/lib/auth/redirects";

import { AuthCard, FormError } from "./parts";

/** /verify-email?token= — the link from the verification email. */
export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const { status, user, refreshMe } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [message, setMessage] = useState("");
  const once = useRef(false);

  useEffect(() => {
    if (once.current) return;
    once.current = true;
    const token = params.get("token");
    if (!token) {
      setState("error");
      setMessage("This link is missing its token. Open the link from the email again.");
      return;
    }
    unwrap(api.POST("/api/v1/auth/email/verify", { body: { token } }))
      .then(async () => {
        setState("done");
        if (status === "signed-in") await refreshMe();
      })
      .catch((e: unknown) => {
        setState("error");
        setMessage(
          e instanceof ApiError && e.code === "token_invalid"
            ? "This link is invalid or has expired. Request a new one from your account."
            : userMessage(e),
        );
      });
  }, [params, status, refreshMe]);

  return (
    <AuthCard
      title={
        state === "done"
          ? "Email verified"
          : state === "error"
            ? "We couldn't verify your email"
            : "Verifying your email"
      }
    >
      {state === "working" && <SkeletonBlock lines={2} label="Verifying" />}
      {state === "done" && (
        <div className="space-y-5">
          <p className="flex items-center gap-2 text-ok">
            <CheckCircle2 aria-hidden className="h-5 w-5" /> Thanks, your address is confirmed.
          </p>
          <Button
            className="w-full"
            onClick={() => navigate(user ? homeFor(user) : "/login", { replace: true })}
          >
            {user ? "Go to your dashboard" : "Sign in"}
          </Button>
        </div>
      )}
      {state === "error" && (
        <div className="space-y-5">
          <p role="alert" className="text-mist">
            {message}
          </p>
          <Link to={user ? homeFor(user) : "/login"}>
            <Button variant="glass" className="w-full">
              {user ? "Back to your account" : "Sign in"}
            </Button>
          </Link>
        </div>
      )}
    </AuthCard>
  );
}

const forgotSchema = z.object({ email: z.string().trim().email("Enter a valid email address.") });

export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<z.infer<typeof forgotSchema>>({
    resolver: zodResolver(forgotSchema),
  });
  const onSubmit = handleSubmit(async ({ email }) => {
    setError(null);
    try {
      await unwrap(api.POST("/api/v1/auth/password/reset", { body: { email } }));
      setSent(true);
    } catch (e) {
      setError(userMessage(e));
    }
  });
  return (
    <AuthCard
      title="Reset your password"
      subtitle="We'll email you a link that works once, for one hour."
      footer={
        <Link to="/login" className="text-flare-hot hover:underline">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <p role="status" className="text-ink">
          If an account exists for that address, we've sent a link. Check your inbox (and spam).
        </p>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <FormError message={error} />
          <Field label="Email" error={formState.errors.email?.message}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                type="email"
                autoComplete="email"
                {...register("email")}
              />
            )}
          </Field>
          <Button type="submit" className="w-full" loading={formState.isSubmitting}>
            Send reset link
          </Button>
        </form>
      )}
    </AuthCard>
  );
}

const resetSchema = z
  .object({ password: z.string().min(8, "Use at least 8 characters."), confirm: z.string() })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "The passwords don't match." });

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    watch,
    setError: setFieldError,
    formState,
  } = useForm<z.infer<typeof resetSchema>>({
    resolver: zodResolver(resetSchema),
  });
  const onSubmit = handleSubmit(async ({ password }) => {
    setError(null);
    try {
      await unwrap(
        api.POST("/api/v1/auth/password/reset/confirm", { body: { token, newPassword: password } }),
      );
      setDone(true);
    } catch (e) {
      const fields = fieldErrors(e);
      if (fields.newPassword) setFieldError("password", { message: fields.newPassword });
      else
        setError(
          e instanceof ApiError && e.code === "token_invalid"
            ? "This link is invalid, already used or expired. Request a new one."
            : userMessage(e),
        );
    }
  });
  return (
    <AuthCard title={done ? "Password changed" : "Choose a new password"}>
      {done ? (
        <div className="space-y-5">
          <p className="text-ink">You're signed out everywhere. Sign in with your new password.</p>
          <Link to="/login">
            <Button className="w-full">Sign in</Button>
          </Link>
        </div>
      ) : !token ? (
        <p role="alert" className="text-mist">
          This link is missing its token.{" "}
          <Link to="/forgot-password" className="text-flare-hot underline">
            Request a new one
          </Link>
          .
        </p>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <FormError message={error} />
          <Field label="New password" error={formState.errors.password?.message}>
            {({ id, describedBy, invalid }) => (
              <>
                <Input
                  id={id}
                  aria-describedby={describedBy}
                  invalid={invalid}
                  type="password"
                  autoComplete="new-password"
                  {...register("password")}
                />
                <PasswordStrength value={watch("password") ?? ""} />
              </>
            )}
          </Field>
          <Field label="Confirm new password" error={formState.errors.confirm?.message}>
            {({ id, describedBy, invalid }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                invalid={invalid}
                type="password"
                autoComplete="new-password"
                {...register("confirm")}
              />
            )}
          </Field>
          <Button type="submit" className="w-full" loading={formState.isSubmitting}>
            Set new password
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
