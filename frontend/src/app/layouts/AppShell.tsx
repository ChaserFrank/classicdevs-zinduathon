import { Bell, Briefcase, FileBarChart2, Inbox, LayoutDashboard, Settings, Sparkles } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { Wordmark } from "@/components/brand/Logo";
import { SpaceBackdrop } from "@/components/space/SpaceBackdrop";
import { cn } from "@/lib/utils";

type Role = "job_seeker" | "recruiter" | "admin";

const NAV: Record<Role, { to: string; label: string; icon: typeof LayoutDashboard }[]> = {
  job_seeker: [
    { to: "/app", label: "Dashboard", icon: LayoutDashboard },
    { to: "/app/analyse", label: "Analyse", icon: Sparkles },
    { to: "/app/card", label: "My card", icon: FileBarChart2 },
    { to: "/app/inbox", label: "Inbox", icon: Inbox },
    { to: "/app/jobs", label: "Jobs", icon: Briefcase },
    { to: "/app/settings", label: "Settings", icon: Settings },
  ],
  recruiter: [{ to: "/recruiter", label: "Dashboard", icon: LayoutDashboard }],
  admin: [{ to: "/admin", label: "Overview", icon: LayoutDashboard }],
};

/**
 * Floating glass sidebar + top bar over the SpaceBackdrop (role-specific items arrive with each
 * role's phase). Bottom bar on small screens.
 */
export function AppShell({ area }: { area: Role }) {
  const items = NAV[area];
  return (
    <div className="relative min-h-screen">
      <SpaceBackdrop />
      <aside className="glass-panel fixed bottom-4 left-4 top-4 z-40 hidden w-60 flex-col rounded-glass p-3 lg:flex">
        <div className="px-3 py-3">
          <Wordmark />
        </div>
        <nav aria-label="App" className="mt-4 flex flex-col gap-1">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-mist transition hover:bg-white/5 hover:text-ink",
                  isActive &&
                    "bg-flare/10 text-ink shadow-[inset_0_0_0_1px_rgb(var(--flare)/0.35),0_0_24px_-8px_rgb(var(--flare)/0.6)]",
                )
              }
            >
              <Icon aria-hidden className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="lg:pl-[17rem]">
        <header className="glass-panel sticky top-4 z-30 mx-4 mt-4 flex h-14 items-center justify-between rounded-glass px-5">
          <h1 className="text-base font-semibold">Dashboard</h1>
          <button
            type="button"
            aria-label="Notifications"
            className="grid h-9 w-9 place-items-center rounded-full text-mist hover:bg-white/10 hover:text-ink"
          >
            <Bell className="h-4 w-4" />
          </button>
        </header>
        <main id="main" className="p-4 pb-24 lg:pb-8">
          <Outlet />
        </main>
      </div>
      <nav
        aria-label="App"
        className="glass-panel fixed inset-x-3 bottom-3 z-40 flex justify-around rounded-glass p-2 lg:hidden"
      >
        {items.slice(0, 5).map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-1 rounded-xl px-3 py-1.5 text-[11px] text-mist",
                isActive && "text-flare-hot",
              )
            }
          >
            <Icon aria-hidden className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
