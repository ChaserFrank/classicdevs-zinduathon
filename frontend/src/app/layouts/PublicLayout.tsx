import { ChevronDown, Menu, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";

import { Wordmark } from "@/components/brand/Logo";
import { HealthDot } from "@/components/HealthDot";
import { env } from "@/lib/env";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/#how", label: "How it works" },
  { to: "/#scoring", label: "Scoring", menu: true },
  { to: "/#recruiters", label: "For recruiters" },
  { to: "/#privacy", label: "Privacy" },
];

/** The reference's floating pill nav, centred at the top; collapses under 768px. */
function PillNav() {
  const [open, setOpen] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  return (
    <header className="fixed inset-x-0 top-4 z-50 flex justify-center px-4">
      <nav
        aria-label="Main"
        className="glass-pill relative flex h-12 items-center gap-1 rounded-full py-1.5 pl-2 pr-1.5 shadow-float"
      >
        <Link to="/" className="mr-2 rounded-full px-1" aria-label="SkillProof home">
          <Wordmark className="text-[15px]" />
        </Link>
        <ul className="hidden items-center md:flex" onMouseLeave={() => setHover(null)}>
          {LINKS.map((link, i) => (
            <li key={link.to} className="relative" onMouseEnter={() => setHover(i)}>
              {hover === i && (
                <span aria-hidden className="absolute inset-0 rounded-full bg-white/[0.07] transition-all" />
              )}
              <a
                href={link.to}
                className="relative flex items-center gap-1 rounded-full px-3 py-1.5 text-sm text-mist transition hover:text-ink"
              >
                {link.label}
                {link.menu && <ChevronDown aria-hidden className="h-3.5 w-3.5" />}
              </a>
            </li>
          ))}
        </ul>
        <NavLink
          to="/login"
          className="ml-1 hidden rounded-full px-3 py-1.5 text-sm text-mist hover:text-ink md:block"
        >
          Sign in
        </NavLink>
        <Link
          to="/register?role=job_seeker"
          className="ml-1 hidden h-9 items-center rounded-full bg-ink px-4 text-sm font-semibold text-black transition hover:bg-white sm:flex"
        >
          Get your skill card
        </Link>
        <button
          type="button"
          className="ml-1 grid h-9 w-9 place-items-center rounded-full text-ink hover:bg-white/10 md:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <div
          id="mobile-menu"
          hidden={!open}
          className={cn("glass-panel absolute left-0 right-0 top-14 rounded-glass p-2 md:hidden")}
        >
          {[...LINKS, { to: "/login", label: "Sign in" }].map((link) => (
            <a
              key={link.to}
              href={link.to}
              onClick={() => setOpen(false)}
              className="block rounded-xl px-4 py-3 text-ink hover:bg-white/5"
            >
              {link.label}
            </a>
          ))}
          <Link
            to="/register?role=job_seeker"
            className="mt-1 block rounded-full bg-ink px-4 py-3 text-center font-semibold text-black"
          >
            Get your skill card
          </Link>
        </div>
      </nav>
    </header>
  );
}

export function PublicLayout() {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-void">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-black"
      >
        Skip to content
      </a>
      <PillNav />
      <main id="main">
        <Outlet />
      </main>
      <footer className="relative border-t border-line px-6 py-10 text-sm text-mist">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <Wordmark className="text-ink" />
          <p>Built for Zinduathon 3.0 · Nairobi</p>
          <div className="flex items-center gap-4">
            <a href={env.apiDocsUrl} className="hover:text-ink">
              API docs
            </a>
            <Link to="/terms" className="hover:text-ink">
              Terms
            </Link>
            <Link to="/privacy" className="hover:text-ink">
              Privacy
            </Link>
            {env.isDev && <HealthDot />}
          </div>
        </div>
      </footer>
    </div>
  );
}
