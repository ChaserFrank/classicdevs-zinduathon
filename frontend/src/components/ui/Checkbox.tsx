import * as RadixCheckbox from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Checkbox({
  checked,
  onCheckedChange,
  label,
  description,
  error,
  name,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: ReactNode;
  description?: ReactNode;
  error?: string;
  name?: string;
}) {
  const id = useId();
  return (
    <div>
      <div className="flex items-start gap-3">
        <RadixCheckbox.Root
          id={id}
          name={name}
          checked={checked}
          onCheckedChange={(v) => onCheckedChange(v === true)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          className={cn(
            "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md border border-line bg-black/40 transition",
            "data-[state=checked]:border-flare data-[state=checked]:bg-flare",
            error && "border-bad/70",
          )}
        >
          <RadixCheckbox.Indicator>
            <Check aria-hidden className="h-3.5 w-3.5 text-black" strokeWidth={3} />
          </RadixCheckbox.Indicator>
        </RadixCheckbox.Root>
        <label htmlFor={id} className="text-sm leading-5 text-ink">
          {label}
          {description && <span className="mt-0.5 block text-mist">{description}</span>}
        </label>
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="ml-8 mt-1 text-sm text-bad">
          {error}
        </p>
      )}
    </div>
  );
}
