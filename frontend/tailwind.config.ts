import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          900: "#08070d",
          800: "#0e0c18",
          700: "#15121f",
          600: "#1d1930",
          500: "#272140",
        },
        melo: {
          DEFAULT: "#a78bfa",
          dim: "#7c3aed",
          glow: "#c4b5fd",
          neon: "#22d3ee",
          pink: "#ec4899",
        },
      },
      fontFamily: {
        display: ["Inter", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "melo-grad": "radial-gradient(circle at 20% 10%, rgba(124,58,237,0.35), transparent 55%), radial-gradient(circle at 80% 30%, rgba(34,211,238,0.22), transparent 50%), radial-gradient(circle at 50% 95%, rgba(236,72,153,0.18), transparent 60%)",
      },
      animation: {
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [],
};
export default config;
