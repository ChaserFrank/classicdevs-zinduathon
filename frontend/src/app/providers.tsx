import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { useState, type ReactNode } from "react";
import { Toaster } from "sonner";

import { ProgressGlowProvider } from "@/components/space/SpaceBackdrop";
import { env } from "@/lib/env";

import { makeQueryClient } from "./query-client";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={250}>
        <ProgressGlowProvider>
          {children}
          {/* Toasts slide in from the top centre as glass pills (DESIGN.md §Motion). */}
          <Toaster
            position="top-center"
            toastOptions={{
              classNames: {
                toast:
                  "glass-pill !rounded-full !border-line !bg-[rgba(20,20,26,0.85)] !text-ink !shadow-float",
                description: "!text-mist",
              },
            }}
          />
        </ProgressGlowProvider>
      </TooltipProvider>
      {/* Hidden for automated browsers (screenshots/e2e) and the planet capture page. */}
      {env.isDev && !navigator.webdriver && !window.location.pathname.startsWith("/dev/planet") && (
        <ReactQueryDevtools buttonPosition="bottom-left" />
      )}
    </QueryClientProvider>
  );
}
