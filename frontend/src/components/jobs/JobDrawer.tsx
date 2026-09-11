import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useJob } from '../../hooks/useQueries';
import { cancelJob, deleteJob } from '../../api/client';
import type { Job } from '../../api/types';
import { jobLabel, kindDisplay } from '../../utils/results';
import { formatDuration } from '../../utils/format';
import { Drawer } from '../ui/Drawer';
import { StatusBadge } from '../ui/StatusBadge';
import { Button } from '../ui/Button';
import { JobTimeline } from './JobTimeline';
import { JobResults } from './JobResults';
import { JobLogs } from './JobLogs';
import { PanelLabel } from '../ui/primitives';

interface JobDrawerProps {
  job: Job;
  onClose: () => void;
  onMutated: () => void;
  notify: (t: 'success' | 'error' | 'info', m: string) => void;
}

export function JobDrawer({ job, onClose, onMutated, notify }: JobDrawerProps) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<'cancel' | 'delete' | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const { data: liveJob } = useJob(job.id);
  const current = liveJob ?? job;

  const refreshJobs = async () => {
    await queryClient.invalidateQueries({ queryKey: ['jobs'] });
  };

  const doCancel = async () => {
    setBusy('cancel');
    try {
      await cancelJob(current.id);
      notify('success', `Job ${current.id} canceled.`);
      onMutated();
      await refreshJobs();
    } catch (err) {
      notify('error', `Cancel failed: ${(err as Error).message}`);
    } finally {
      setBusy(null);
    }
  };

  const doDelete = async () => {
    if (!confirmingDelete) {
      setConfirmingDelete(true);
      return;
    }
    setBusy('delete');
    try {
      await deleteJob(current.id);
      notify('success', `Job ${current.id} deleted.`);
      onClose();
      onMutated();
      await refreshJobs();
    } catch (err) {
      notify('error', `Delete failed: ${(err as Error).message}`);
    } finally {
      setBusy(null);
      setConfirmingDelete(false);
    }
  };

  const running = current.status === 'running' || current.status === 'pending';
  const terminal = current.status === 'completed' || current.status === 'failed' || current.status === 'canceled';

  return (
    <Drawer
      open
      onClose={onClose}
      title={
        <div className="flex items-center gap-3">
          <h2 className="text-base font-bold text-text-primary truncate">
            {kindDisplay(current.kind)} — {jobLabel(current)}
          </h2>
          <StatusBadge status={current.status} />
        </div>
      }
      maxWidth="680px"
      footer={
        <div className="flex items-center gap-2">
          {running && (
            <Button variant="outline" size="sm" onClick={doCancel} loading={busy === 'cancel'}>
              Cancel job
            </Button>
          )}
          {terminal && (
            <Button variant="danger" size="sm" onClick={doDelete} loading={busy === 'delete'}>
              {confirmingDelete ? 'Confirm delete?' : 'Delete job'}
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
          <span className="ml-auto text-[0.7rem] font-mono text-text-secondary">
            ID_{current.id.toUpperCase()}
          </span>
        </div>
      }
    >
      <div className="flex flex-col gap-6 h-full">
        <div className="flex flex-col gap-2">
          <PanelLabel>Timeline</PanelLabel>
          <JobTimeline job={current} />
          {current.started_at && (
            <div className="text-[0.72rem] font-mono text-text-secondary opacity-80 mt-1">
              {terminal
                ? `Total run time: ${formatDuration(current.created_at, current.finished_at)}`
                : `Elapsed: ${formatDuration(current.started_at)}`}
            </div>
          )}
          {current.error && (
            <p className="text-[0.8rem] font-mono text-danger border border-danger/40 rounded-md px-3 py-2 mt-1">
              {current.error}
            </p>
          )}
        </div>

        <JobResults job={current} />
        <JobLogs key={current.id} job={current} />
      </div>
    </Drawer>
  );
}