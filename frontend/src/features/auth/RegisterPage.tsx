import { zodResolver } from "@hookform/resolvers/zod";
import { Briefcase, Code2 } from "lucide-react";
import { useState } from "react";
import { Controller, useForm, type Path } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { GlassCard } from "@/components/glass/Glass";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Field, Input } from "@/components/ui/Field";
import { PasswordStrength } from "@/components/ui/PasswordStrength";
import { api, unwrap } from "@/lib/api/client";
import { ApiError, userMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { homeFor } from "@/lib/auth/redirects";
import { toE164 } from "@/lib/phone";
import { cn } from "@/lib/utils";

import { AuthCard, Divider, FormError, GithubButton } from "./parts";

type RoleChoice = "job_seeker" | "recruiter";

export const registerSchema = z
  .object({
    role: z.enum(["job_seeker", "recruiter"]),
    fullName: z.string().trim().min(1, "Enter your name.").max(150),
    email: z.string().trim().email("Enter a valid email address."),
    password: z.string().min(8, "Use at least 8 characters."),
    phone: z.string().trim().optional().default(""),
    companyName: z.string().trim().max(120).optional().default(""),
    jobTitle: z.string().trim().max(120).optional().default(""),
    consents: z.object({
      terms: z.boolean().refine((v) => v, "Accept the terms and privacy policy to continue."),
      emailFeedback: z.boolean(),
      smsFeedback: z.boolean(),
    }),
  })
  .superRefine((v, ctx) => {
    if (v.role === "recruiter" && !v.companyName)
      ctx.addIssue({ code: "custom", path: ["companyName"], message: "Enter your company's name." });
    if (v.consents.smsFeedback && !v.phone)
      ctx.addIssue({ code: "custom", path: ["phone"], message: "Add a phone number to get feedback by SMS." });
    if (v.phone && !toE164(v.phone))
      ctx.addIssue({ code: "custom", path: ["phone"], message: "Enter a valid phone number, e.g. 0712 345 678." });
  });
export type RegisterValues = z.infer<typeof registerSchema>;

function RoleStep({ onPick }: { onPick: (role: RoleChoice) => void }) {
  const choices = [
    { role: "job_seeker" as const, icon: Code2, title: "I'm looking for work", body: "Turn your public GitHub work into a skill card recruiters trust." },
    { role: "recruiter" as const, icon: Briefcase, title: "I'm hiring", body: "Search developers by proven skill and send them feedback." },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {choices.map(({ role, icon: Icon, title, body }) => (
        <button key={role} type="button" onClick={() => onPick(role)} className="group text-left">
          <GlassCard className="h-full p-5 transition group-hover:border-flare/50 group-hover:bg-white/[0.06] group-focus-visible:border-flare">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-flare/15 text-flare-hot">
              <Icon aria-hidden className="h-5 w-5" />
            </span>
            <span className="mt-4 block text-lg font-bold">{title}</span>
            <span className="mt-1 block text-sm text-mist">{body}</span>
          </GlassCard>
        </button>
      ))}
    </div>
  );
}

export function RegisterPage() {
  const [params, setParams] = useSearchParams();
  const roleParam = params.get("role");
  const role: RoleChoice | null = roleParam === "job_seeker" || roleParam === "recruiter" ? roleParam : null;
  const pick = (r: RoleChoice) => setParams({ role: r });

  if (!role) {
    return (
      <AuthCard
        title="Create your account"
        subtitle="Who are you here as?"
        footer={
          <>
            Already have an account?{" "}
            <Link to="/login" className="font-medium text-flare-hot hover:underline">
              Sign in
            </Link>
          </>
        }
      >
        <RoleStep onPick={pick} />
      </AuthCard>
    );
  }
  return <RegisterForm role={role} onChangeRole={() => setParams({})} />;
}

function RegisterForm({ role, onChangeRole }: { role: RoleChoice; onChangeRole: () => void }) {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, control, watch, setError: setFieldError, formState } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      role,
      fullName: "",
      email: "",
      password: "",
      phone: "",
      companyName: "",
      jobTitle: "",
      consents: { terms: false, emailFeedback: true, smsFeedback: false },
    },
  });
  const sms = watch("consents.smsFeedback");
  const password = watch("password");
  const recruiter = role === "recruiter";

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      const result = await unwrap(
        api.POST("/api/v1/auth/register", {
          body: {
            role: values.role,
            fullName: values.fullName,
            email: values.email,
            password: values.password,
            phone: values.phone ? toE164(values.phone) : null,
            ...(recruiter ? { companyName: values.companyName, jobTitle: values.jobTitle } : {}),
            consents: values.consents,
          },
        }),
      );
      signIn(result);
      // Job seekers who chose SMS verify their phone right away (the dashboard opens the dialog).
      navigate(homeFor(result.user), { replace: true, state: { verifyPhone: values.consents.smsFeedback && !recruiter } });
    } catch (e) {
      if (e instanceof ApiError && e.fields) {
        Object.entries(e.fields).forEach(([field, messages]) =>
          setFieldError(field as Path<RegisterValues>, { message: messages.join(" ") }),
        );
        setError("Check the highlighted fields.");
      } else setError(userMessage(e));
    }
  });

  const err = formState.errors;
  return (
    <AuthCard
      title={recruiter ? "Create a recruiter account" : "Create your skill card"}
      subtitle={
        <>
          {recruiter ? "An admin approves recruiter accounts before you can search." : "Free. We only ever read public repositories."}{" "}
          <button type="button" onClick={onChangeRole} className="text-flare-hot hover:underline">
            Change
          </button>
        </>
      }
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-flare-hot hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <FormError message={error} />
      {!recruiter && (
        <>
          <GithubButton
            label="Sign up with GitHub"
            options={{ role, acceptTerms: true, emailFeedback: true, smsFeedback: false }}
            onError={setError}
          />
          <p className="mt-2 text-center text-xs text-mist">
            By continuing with GitHub you accept the <Link to="/terms" className="underline">terms</Link> and{" "}
            <Link to="/privacy" className="underline">privacy policy</Link>.
          </p>
          <Divider label="or with email" />
        </>
      )}
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <Field label="Full name" error={err.fullName?.message}>
          {({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} invalid={invalid} autoComplete="name" {...register("fullName")} />}
        </Field>
        <Field label={recruiter ? "Work email" : "Email"} error={err.email?.message}>
          {({ id, describedBy, invalid }) => (
            <Input id={id} aria-describedby={describedBy} invalid={invalid} type="email" autoComplete="email" {...register("email")} />
          )}
        </Field>
        <Field label="Password" error={err.password?.message} hint="At least 8 characters; avoid common passwords.">
          {({ id, describedBy, invalid }) => (
            <>
              <Input id={id} aria-describedby={describedBy} invalid={invalid} type="password" autoComplete="new-password" {...register("password")} />
              <PasswordStrength value={password} />
            </>
          )}
        </Field>
        {recruiter && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Company" error={err.companyName?.message} hint="We reuse an existing company with the same name.">
              {({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} invalid={invalid} autoComplete="organization" {...register("companyName")} />}
            </Field>
            <Field label="Job title" error={err.jobTitle?.message}>
              {({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} invalid={invalid} autoComplete="organization-title" {...register("jobTitle")} />}
            </Field>
          </div>
        )}
        <Field
          label={sms ? "Phone (required for SMS)" : "Phone (optional)"}
          error={err.phone?.message}
          hint="Kenyan numbers: 07…, 01… or +254…"
        >
          {({ id, describedBy, invalid }) => (
            <Input id={id} aria-describedby={describedBy} invalid={invalid} type="tel" autoComplete="tel" {...register("phone")} />
          )}
        </Field>
        <div className="space-y-3 pt-1">
          <Controller
            control={control}
            name="consents.terms"
            render={({ field }) => (
              <Checkbox
                checked={field.value}
                onCheckedChange={field.onChange}
                error={err.consents?.terms?.message}
                label={
                  <>
                    I accept the <Link to="/terms" className="text-flare-hot underline">terms</Link> and{" "}
                    <Link to="/privacy" className="text-flare-hot underline">privacy policy</Link>
                  </>
                }
              />
            )}
          />
          <Controller
            control={control}
            name="consents.emailFeedback"
            render={({ field }) => (
              <Checkbox checked={field.value} onCheckedChange={field.onChange} label={recruiter ? "Email me about my account and candidates" : "Send me recruiter feedback by email"} />
            )}
          />
          <Controller
            control={control}
            name="consents.smsFeedback"
            render={({ field }) => (
              <Checkbox
                checked={field.value}
                onCheckedChange={field.onChange}
                label={recruiter ? "Text me about my approval" : "Send me recruiter feedback by SMS"}
                description={field.value ? "From SkillProof. Reply STOP to opt out at any time; standard SMS opt-out applies." : undefined}
              />
            )}
          />
        </div>
        <Button type="submit" size="lg" className={cn("w-full")} loading={formState.isSubmitting}>
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}
