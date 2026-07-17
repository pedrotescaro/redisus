import { useState } from "react";
import { Sidebar } from "../../components/layout/sidebar";
import { Topbar } from "../../components/layout/Topbar";
import { AnalyzerWorkbench } from "../../components/heal-analyzer/analyzer-workbench";

function AnalyzerPageWithSidebar() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-heal-canvas text-heal-ink antialiased dark:bg-[#060606] dark:text-white">
      {!isSidebarCollapsed ? <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} /> : null}

      <div
        className={`relative flex min-h-0 min-w-0 flex-grow flex-col overflow-hidden bg-heal-canvas transition-[padding] duration-300 dark:bg-[#060606] ${
          isSidebarCollapsed ? '' : 'border-l border-heal-line lg:pl-[280px] dark:border-[#1f1f23]/40'
        }`}
      >
        <div className={`shrink-0 lg:hidden ${isSidebarCollapsed ? 'hidden' : ''}`}>
          <Topbar onMenuClick={() => setIsSidebarOpen(true)} />
        </div>

        <div className="relative flex min-h-0 flex-grow flex-col overflow-hidden bg-heal-canvas dark:bg-[#060606]">
          <AnalyzerWorkbench
            showSidebarToggle
            isSidebarCollapsed={isSidebarCollapsed}
            onToggleSidebar={() => setIsSidebarCollapsed(current => !current)}
          />
        </div>
      </div>
    </div>
  );
}

export function AnalyzerPage() {
  return <AnalyzerPageWithSidebar />;
}

export function StandaloneAnalyzerPage() {
  return <AnalyzerPageWithSidebar />;
}
