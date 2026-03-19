import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Redisus | Heal+",
  description: "Plataforma clinica para gestao de pacientes e avaliacao de feridas com IA.",
};

type RootLayoutProps = {
  children: React.ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="pt-BR">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
