import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Using CSS variables for theme support
        surface: "var(--surface)",
        "surface-dim": "var(--surface-dim)",
        "surface-bright": "var(--surface-bright)",
        "surface-container-lowest": "var(--surface-container-lowest)",
        "surface-container-low": "var(--surface-container-low)",
        "surface-container": "var(--surface-container)",
        "surface-container-high": "var(--surface-container-high)",
        "surface-container-highest": "var(--surface-container-highest)",
        "surface-variant": "var(--surface-variant)",
        background: "var(--background)",

        // Primary colors
        primary: "var(--primary)",
        "primary-container": "var(--primary-container)",
        "primary-fixed": "var(--primary-fixed)",
        "primary-fixed-dim": "var(--primary-fixed-dim)",
        "on-primary": "var(--on-primary)",
        "on-primary-container": "var(--on-primary-container)",
        "on-primary-fixed": "var(--on-primary-fixed)",
        "on-primary-fixed-variant": "var(--on-primary-fixed-variant)",
        "inverse-primary": "var(--inverse-primary)",

        // Secondary colors
        secondary: "var(--secondary)",
        "secondary-container": "var(--secondary-container)",
        "secondary-fixed": "var(--secondary-fixed)",
        "secondary-fixed-dim": "var(--secondary-fixed-dim)",
        "on-secondary": "var(--on-secondary)",
        "on-secondary-container": "var(--on-secondary-container)",
        "on-secondary-fixed": "var(--on-secondary-fixed)",
        "on-secondary-fixed-variant": "var(--on-secondary-fixed-variant)",

        // Tertiary colors (warnings/alerts)
        tertiary: "var(--tertiary)",
        "tertiary-container": "var(--tertiary-container)",
        "tertiary-fixed": "var(--tertiary-fixed)",
        "tertiary-fixed-dim": "var(--tertiary-fixed-dim)",
        "on-tertiary": "var(--on-tertiary)",
        "on-tertiary-container": "var(--on-tertiary-container)",
        "on-tertiary-fixed": "var(--on-tertiary-fixed)",
        "on-tertiary-fixed-variant": "var(--on-tertiary-fixed-variant)",

        // Error colors
        error: "var(--error)",
        "error-container": "var(--error-container)",
        "on-error": "var(--on-error)",
        "on-error-container": "var(--on-error-container)",

        // Surface text colors
        "on-surface": "var(--on-surface)",
        "on-surface-variant": "var(--on-surface-variant)",
        "on-background": "var(--on-background)",
        "inverse-surface": "var(--inverse-surface)",
        "inverse-on-surface": "var(--inverse-on-surface)",

        // Outline colors
        outline: "var(--outline)",
        "outline-variant": "var(--outline-variant)",

        // Surface tint
        "surface-tint": "var(--surface-tint)",

        // Legacy brand colors (for backward compatibility)
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
        // Manrope para design editorial
        nav: ["Manrope", "Inter", "sans-serif"],
        main: ["Manrope", "Poppins", "sans-serif"],
        headline: ["Manrope", "Poppins", "sans-serif"],
        body: ["Manrope", "Poppins", "sans-serif"],
        label: ["Manrope", "Inter", "sans-serif"],
        sans: ["Manrope", "Poppins", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        lg: "0.5rem",
        xl: "0.75rem",
        "2xl": "1rem",
        "3xl": "1.5rem",
        full: "9999px",
      },
      boxShadow: {
        soft: "0 16px 32px -16px rgba(9, 60, 68, 0.15)",
        ambient: "var(--shadow-ambient)",
      },
    },
  },
  plugins: [],
};

export default config;
