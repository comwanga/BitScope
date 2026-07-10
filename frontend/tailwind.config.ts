import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        paper: "rgb(var(--color-paper) / <alpha-value>)",
        panel: "rgb(var(--color-panel) / <alpha-value>)",
        brass: "rgb(var(--color-brass) / <alpha-value>)",
        forest: "rgb(var(--color-forest) / <alpha-value>)",
        rust: "rgb(var(--color-rust) / <alpha-value>)"
      }
    }
  },
  plugins: []
};

export default config;
