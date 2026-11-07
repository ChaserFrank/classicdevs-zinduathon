import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "hero" | "glass" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  // In the app: flare pill with black text.
  primary: "bg-flare text-black hover:bg-flare-hot shadow-[0_0_24px_-6px_rgb(var(--flare)/0.8)]",
  // On dark heroes: the reference's white pill with black text.
  hero: "bg-ink text-black hover:bg-white",
  glass: "glass-pill text-ink hover:bg-white/10",
  ghost: "text-mist hover:text-ink hover:bg-white/5",
  danger: "bg-bad/90 text-black hover:bg-bad",
};
const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm gap-1.5",
  md: "h-10 px-5 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, disabled, className, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex select-none items-center justify-center rounded-full font-semibold transition",
        "duration-200 active:scale-[0.98] active:shadow-[inset_0_0_12px_rgba(0,0,0,0.35)]",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 aria-hidden className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
});
