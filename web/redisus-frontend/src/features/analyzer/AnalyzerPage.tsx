import { AnalyzerWorkbench } from "../../components/heal-analyzer/analyzer-workbench";

export function AnalyzerPage() {
  return <AnalyzerWorkbench />;
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
