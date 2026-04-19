import nextPlugin from "@next/eslint-plugin-next";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

const projectFiles = ["**/*.{js,jsx,mjs,cjs,ts,tsx,mts,cts}"];
const ignorePatterns = [
  ".next/**",
  "out/**",
  "build/**",
  "next-env.d.ts",
  "eslint.config.mjs",
  "tsconfig.tsbuildinfo",
  "*.log",
];

export default [
  {
    files: projectFiles,
    ignores: ignorePatterns,
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
        sourceType: "module",
      },
    },
    plugins: {
      "@next/next": nextPlugin,
      "react-hooks": reactHooksPlugin,
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
];
