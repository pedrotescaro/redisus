import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#edf9f8",
          100: "#c9f0eb",
          200: "#9fe3dc",
          300: "#6ccfc7",
          400: "#38b4ae",
          500: "#1f9995",
          600: "#157a78",
          700: "#135f5e",
          800: "#144d4d",
          900: "#153f40",
        },
      },
      fontFamily: {
        sans: ["Segoe UI", "Tahoma", "Verdana", "sans-serif"],
      },
      boxShadow: {
        soft: "0 16px 32px -16px rgba(9, 60, 68, 0.35)",
      },
    },
  },
  plugins: [],
};

export default config;
