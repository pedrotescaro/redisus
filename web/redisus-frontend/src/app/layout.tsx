import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/contexts/theme-context";

export const metadata: Metadata = {
  title: "Redisus | Heal+",
  description:
    "Plataforma clínica para gestão de pacientes e avaliação de feridas com IA.",
  icons: {
    icon: "/images/logo.svg",
  },
};

type RootLayoutProps = {
  children: React.ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <meta charSet="UTF-8" />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var key = "healplus-theme";
                  var a11yKey = "healplus-accessibility-preferences";
                  var stored = localStorage.getItem(key) || "dark";
                  var isDark = stored === "dark" || (stored === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
                  if (isDark) {
                    document.documentElement.classList.add("dark");
                    document.documentElement.style.colorScheme = "dark";
                  } else {
                    document.documentElement.classList.remove("dark");
                    document.documentElement.style.colorScheme = "light";
                  }
                  var raw = localStorage.getItem(a11yKey);
                  if (raw) {
                    var prefs = JSON.parse(raw);
                    if (prefs.largeText) document.documentElement.classList.add("a11y-large-text");
                    if (prefs.highContrast) document.documentElement.classList.add("a11y-high-contrast");
                    if (prefs.reducedMotion) document.documentElement.classList.add("a11y-reduced-motion");
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body
        suppressHydrationWarning
        className="font-body antialiased bg-background text-on-surface"
      >
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
