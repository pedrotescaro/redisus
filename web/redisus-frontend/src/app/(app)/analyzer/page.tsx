import type { Metadata } from "next";
import { AnalyzerWorkbench } from "@/components/heal-analyzer/analyzer-workbench";

export const metadata: Metadata = {
  title: "HEAL Analyzer",
  description:
    "Painel de analise de feridas com foco em imagem, resultado clinico e explicabilidade.",
};

export default function AnalyzerPage() {
  return <AnalyzerWorkbench />;
}
