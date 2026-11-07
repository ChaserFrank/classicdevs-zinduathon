import { createContext, useContext } from "react";

/** 0 = idle, 1–4 = analysis steps, 5 = card revealed. Drives the backdrop glow. */
export type ProgressGlow = { step: number; setStep: (step: number) => void };
export const ProgressGlowContext = createContext<ProgressGlow>({ step: 0, setStep: () => undefined });
export const useProgressGlow = () => useContext(ProgressGlowContext);
