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
        ink: "#17201b",
        paper: "#f7f5ef",
        panel: "#ffffff",
        brass: "#b9802d",
        forest: "#1f6b55",
        rust: "#a34d32"
      }
    }
  },
  plugins: []
};

export default config;
