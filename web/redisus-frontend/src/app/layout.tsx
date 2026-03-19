import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/contexts/theme-context";

export const metadata: Metadata = {
  title: "Redisus | Heal+",
  description:
    "Plataforma clínica para gestão de pacientes e avaliação de feridas com IA.",
};

type RootLayoutProps = {
  children: React.ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className="font-body antialiased bg-background text-on-surface">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
