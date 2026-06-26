import { AnalyzerWorkbench } from "../../components/heal-analyzer/analyzer-workbench";

export function AnalyzerPage() {
  return (
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      <div className="flex-grow max-w-6xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
        <AnalyzerWorkbench />
      </div>
    </div>
  );
}

export function StandaloneAnalyzerPage() {
  return (
    <main className="min-h-screen bg-background px-4 py-6 text-on-surface sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-[1800px]">
        <AnalyzerWorkbench />
      </div>
    </main>
  );
}
