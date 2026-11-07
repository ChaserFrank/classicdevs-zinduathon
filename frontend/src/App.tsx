import { RouterProvider } from "react-router-dom";

import { Providers } from "@/app/providers";
import { router } from "@/app/router";
import { AuthProvider } from "@/lib/auth/AuthProvider";

const toLogin = (next: string) => router.navigate(`/login?next=${encodeURIComponent(next)}`);

export function App() {
  return (
    <Providers>
      <AuthProvider onSessionEnded={toLogin}>
        <RouterProvider router={router} future={{ v7_startTransition: true }} />
      </AuthProvider>
    </Providers>
  );
}
