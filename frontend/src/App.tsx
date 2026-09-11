import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { Job } from './api/types';
import { useJobs } from './hooks/useQueries';
import { useTheme } from './hooks/useTheme';
import { useToast } from './hooks/useToast';
import { ToastViewport } from './components/ui/ToastViewport';
import { FlowLauncher } from './components/launcher/FlowLauncher';
import type { FlowId } from './components/launcher/FlowLauncher';
import { JobGrid } from './components/jobs/JobGrid';
import { JobDrawer } from './components/jobs/JobDrawer';
import { SystemMonitor } from './components/SystemMonitor';

function App() {
  useTheme();
  const queryClient = useQueryClient();
  const { data: jobs = [], isLoading } = useJobs();
  const { toasts, push, dismiss } = useToast();
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [activeFlow, setActiveFlow] = useState<FlowId | null>(null);
  const [maxResources, setMaxResources] = useState(false);

  return (
    <div className="min-h-screen bg-bg-page text-text-primary transition-colors duration-200">
      <div className="max-w-[1200px] mx-auto px-8 py-8 w-full animate-fadeIn">
        <header className="mb-10 flex justify-between items-start gap-6 border-b border-border pb-6">
          <div className="flex flex-col gap-1.5">
            <h1 className="text-3xl font-bold tracking-tight text-text-primary">BIMOS</h1>
            <p className="text-[0.8rem] text-text-secondary font-mono tracking-widest uppercase opacity-80">
              Biomolecular Modeling Suite
            </p>
          </div>
          <SystemMonitor />
        </header>

        <main className="flex flex-col gap-8">
          <FlowLauncher
            activeFlow={activeFlow}
            onActiveFlowChange={setActiveFlow}
            maxResources={maxResources}
            onMaxResourcesChange={setMaxResources}
            onJobStarted={async () => {
              await queryClient.invalidateQueries({ queryKey: ['jobs'] });
            }}
            notify={push}
          />

          <section aria-label="Job history">
            <JobGrid
              jobs={jobs}
              loading={isLoading}
              onOpen={setSelectedJob}
            />
          </section>
        </main>
      </div>

      {selectedJob && (
        <JobDrawer
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onMutated={() => {
            /* grid auto-refreshes via react-query */
          }}
          notify={push}
        />
      )}

      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}

export default App;