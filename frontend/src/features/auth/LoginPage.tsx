import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { api, unwrap } from "@/lib/api/client";
import { ApiError, userMessage } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { homeFor, safeNext } from "@/lib/auth/redirects";

import { AuthCard, Divider, FormError, GithubButton } from "./parts";

const schema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
type Values = z.infer<typeof schema>;

export function LoginPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      const result = await unwrap(api.POST("/api/v1/auth/login", { body: values }));
      signIn(result);
      navigate(next ?? homeFor(result.user), { replace: true });
    } catch (e) {
      setError(
        e instanceof ApiError && e.code === "invalid_credentials"
          ? "Email or password is incorrect."
          : userMessage(e),
      );
    }
  });

  return (
    <AuthCard
      title="Sign in"
      subtitle="Welcome back. Your evidence is where you left it."
      footer={
        <>
          New to SkillProof?{" "}
          <Link to="/register" className="font-medium text-flare-hot hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <FormError message={error} />
      <form onSubmit={onSubmit} noValidate className="space-y-4">
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
        <Field label="Password" error={formState.errors.password?.message}>
          {({ id, describedBy, invalid }) => (
            <Input
              id={id}
              aria-describedby={describedBy}
              invalid={invalid}
              type="password"
              autoComplete="current-password"
              {...register("password")}
            />
          )}
        </Field>
        <div className="flex justify-end">
          <Link to="/forgot-password" className="text-sm text-mist hover:text-ink">
            Forgot password?
          </Link>
        </div>
        <Button type="submit" className="w-full" size="lg" loading={formState.isSubmitting}>
          Sign in
        </Button>
      </form>
      <Divider />
      <GithubButton options={{ next }} onError={setError} />
    </AuthCard>
  );
}
