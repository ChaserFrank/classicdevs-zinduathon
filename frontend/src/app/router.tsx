import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { env } from "@/lib/env";

import { AppShell } from "./layouts/AppShell";
import { AuthLayout } from "./layouts/AuthLayout";
import { PublicLayout } from "./layouts/PublicLayout";
import { NotFound, RouteError } from "./pages/SystemPages";

/** Each section is its own chunk (React Router `lazy`), so the landing page stays small. */
const routes: RouteObject[] = [
  {
    element: <PublicLayout />,
    errorElement: <RouteError />,
    children: [
      {
        index: true,
        lazy: async () => ({ Component: (await import("@/features/landing/LandingPage")).LandingPage }),
      },
    ],
  },
  {
    element: <AuthLayout />,
    errorElement: <RouteError />,
    children: [
      {
        path: "login",
        lazy: async () => ({ Component: (await import("./pages/Placeholder")).AuthPlaceholder }),
      },
      {
        path: "register",
        lazy: async () => ({ Component: (await import("./pages/Placeholder")).AuthPlaceholder }),
      },
    ],
  },
  {
    path: "app",
    element: <AppShell area="job_seeker" />,
    errorElement: <RouteError />,
    children: [
      {
        index: true,
        lazy: async () => ({ Component: (await import("./pages/Placeholder")).AppPlaceholder }),
      },
    ],
  },
  ...(env.includeDevRoutes
    ? [
        { path: "dev/ui", lazy: async () => ({ Component: (await import("@/dev/DevUiPage")).DevUiPage }) },
        {
          path: "dev/planet-capture",
          lazy: async () => ({ Component: (await import("@/dev/PlanetCapturePage")).PlanetCapturePage }),
        },
      ]
    : []),
  { path: "*", element: <NotFound /> },
];

export const router = createBrowserRouter(routes, {
  future: {
    v7_relativeSplatPath: true,
    v7_fetcherPersist: true,
    v7_normalizeFormMethod: true,
    v7_partialHydration: true,
    v7_skipActionErrorRevalidation: true,
  },
});
