import { forwardRef, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type Props = HTMLAttributes<HTMLDivElement> & {
  /** One orange bloom per screen: behind the element that matters most (login card, score, filters). */
  glow?: boolean;
  /** Darker glass for surfaces that can float over the planet's bright rim (keeps text AA). */
  scrim?: boolean;
  as?: "div" | "section" | "aside" | "article" | "nav" | "header" | "form";
  children?: ReactNode;
};

/** The orange bloom + 1px lit edge, placed behind a glass surface. */
export function LitEdge({ className }: { className?: string }) {
  return (
    <>
      <span
        aria-hidden
        className={cn(
          "pointer-events-none absolute -inset-10 -z-10 rounded-[inherit] opacity-30 blur-3xl",
          "bg-[radial-gradient(closest-side,rgb(var(--flare)/0.9),transparent)]",
          className,
        )}
      />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[inherit] p-px [mask:linear-gradient(#000_0_0)_content-box_exclude,linear-gradient(#000_0_0)]"
        style={{ background: "linear-gradient(160deg, rgb(var(--flare-hot) / 0.7), transparent 45%)" }}
      />
    </>
  );
}

/** Large floating surface (24px radius, strong blur). The main container on every screen. */
export const GlassPanel = forwardRef<HTMLDivElement, Props>(function GlassPanel(
  { glow, scrim, as = "div", className, children, ...rest },
  ref,
) {
  // Typing boundary: every allowed tag is a block element with the same attributes as <div>,
  // so we narrow to "div" for the ref type. The rendered tag is still `as`.
  const Tag = as as "div";
  return (
    <Tag
      ref={ref}
      className={cn("glass-panel relative isolate rounded-glass", scrim && "glass-scrim", className)}
      {...rest}
    >
      {glow && <LitEdge />}
      {children}
    </Tag>
  );
});

/** Smaller surface inside panels (16px radius, lighter blur). */
export const GlassCard = forwardRef<HTMLDivElement, Props>(function GlassCard(
  { glow, as = "div", className, children, ...rest },
  ref,
) {
  // Typing boundary: every allowed tag is a block element with the same attributes as <div>,
  // so we narrow to "div" for the ref type. The rendered tag is still `as`.
  const Tag = as as "div";
  return (
    <Tag ref={ref} className={cn("glass-card relative isolate rounded-card", className)} {...rest}>
      {glow && <LitEdge />}
      {children}
    </Tag>
  );
});

/** Fully rounded pill: the reference's nav bar and badge. Also chips and segmented controls. */
export function GlassPill({ className, children, ...rest }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn("glass-pill inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm", className)}
      {...rest}
    >
      {children}
    </span>
  );
}
