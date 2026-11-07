import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Glass dialog: scale-and-fade in, focus trapped, Esc and outside click close it. */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-[fade-in_200ms_ease-out]" />
        <RadixDialog.Content
          className={cn(
            "glass-panel glass-scrim fixed left-1/2 top-1/2 z-50 w-[min(92vw,460px)] -translate-x-1/2 -translate-y-1/2 rounded-glass p-6 shadow-float",
            "data-[state=open]:animate-[dialog-in_220ms_cubic-bezier(0.22,1,0.36,1)]",
            className,
          )}
        >
          <RadixDialog.Title className="pr-8 text-xl font-bold">{title}</RadixDialog.Title>
          {description && <RadixDialog.Description className="mt-1 text-sm text-mist">{description}</RadixDialog.Description>}
          <div className="mt-5">{children}</div>
          <RadixDialog.Close
            aria-label="Close"
            className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full text-mist hover:bg-white/10 hover:text-ink"
          >
            <X className="h-4 w-4" />
          </RadixDialog.Close>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
