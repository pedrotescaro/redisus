import { useState } from "react";
import { Sidebar } from "../../components/layout/sidebar";
import { Topbar } from "../../components/layout/Topbar";
import { AnalyzerWorkbench } from "../../components/heal-analyzer/analyzer-workbench";

function AnalyzerPageWithSidebar() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false); // starts false (sidebar enabled/visible by default)

  return (
    <div className="flex h-screen bg-heal-canvas text-heal-ink dark:bg-[#060606] text-heal-ink dark:text-white antialiased overflow-hidden w-full">
      {!isFullscreen && (
        <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />
      )}

      <div
        className={`flex-grow flex flex-col min-h-0 min-w-0 bg-heal-canvas dark:bg-[#060606] relative overflow-hidden transition-all duration-300 ${
          !isFullscreen ? 'lg:pl-[280px] border-l border-heal-line dark:border-[#1f1f23]/40' : ''
        }`}
      >
        {!isFullscreen && (
          <div className="lg:hidden shrink-0">
            <Topbar onMenuClick={() => setIsSidebarOpen(true)} />
          </div>
        )}

        <div className="flex flex-col flex-grow min-h-0 relative overflow-hidden bg-heal-canvas dark:bg-[#060606]">
          <AnalyzerWorkbench
            showSidebarToggle={true}
            isSidebarCollapsed={isFullscreen}
            onToggleSidebar={() => setIsFullscreen(!isFullscreen)}
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
