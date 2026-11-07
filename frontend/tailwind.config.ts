import type { Config } from "tailwindcss";

// Colours come from CSS variables in src/styles/tokens.css so glass, charts and the 3D scene share one palette.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: token("void"),
        "void-2": token("void-2"),
        planet: token("planet"),
        "planet-2": token("planet-2"),
        flare: token("flare"),
        "flare-hot": token("flare-hot"),
        ember: token("ember"),
        ink: token("ink"),
        mist: token("mist"),
        ok: token("ok"),
        warn: token("warn"),
        bad: token("bad"),
      },
      borderColor: { line: "rgba(255,255,255,0.10)" },
      fontFamily: { sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"] },
      borderRadius: { glass: "24px", card: "16px" },
      letterSpacing: { tightest: "-0.02em" },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "dialog-in": {
          from: { opacity: "0", transform: "translate(-50%, -48%) scale(0.96)" },
          to: { opacity: "1", transform: "translate(-50%, -50%) scale(1)" },
        },
      },
      boxShadow: {
        float: "0 24px 60px -12px rgba(0,0,0,0.65), 0 8px 24px -8px rgba(0,0,0,0.5)",
        "inner-hi": "inset 0 1px 0 0 rgba(255,255,255,0.08)",
      },
    },
  },
  plugins: [],
} satisfies Config;
