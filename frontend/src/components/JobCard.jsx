import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Film, Clock, CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react';
import { getThumbnailUrl } from '../services/api';

/**
 * Status badge colours and icons.
 */
const STATUS_CONFIG = {
  completed: {
    label: 'Completed',
    icon: <CheckCircle className="w-3.5 h-3.5" />,
    className: 'bg-gold-accent-muted text-gold-light-accent dark:text-gold-accent border-gold-light-border dark:border-gold-border',
  },
  processing: {
    label: 'Processing',
    icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
    className: 'bg-gold-accent-muted text-gold-light-accent dark:text-gold-accent border-gold-light-border dark:border-gold-border',
  },
  pending: {
    label: 'Pending',
    icon: <Clock className="w-3.5 h-3.5" />,
    className: 'bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary text-gold-light-text-secondary dark:text-gold-text-secondary border-gold-light-border dark:border-gold-border',
  },
  failed: {
    label: 'Failed',
    icon: <XCircle className="w-3.5 h-3.5" />,
    className: 'bg-red-500/15 text-red-400 border-red-500/20',
  },
};

function formatDate(ts) {
  if (!ts) return '—';
  // Firestore timestamps arrive as { _seconds, _nanoseconds } or as ISO strings
  const date = ts._seconds
    ? new Date(ts._seconds * 1000)
    : new Date(ts);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDuration(seconds) {
  if (!seconds) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/**
 * JobCard — displays a single job in the dashboard grid.
 *
 * Props:
 *   job  — Firestore job document dict
 */
export default function JobCard({ job }) {
  const navigate = useNavigate();
  const [thumbnailUrl, setThumbnailUrl] = useState(null);

  const statusCfg = STATUS_CONFIG[job.status] ?? STATUS_CONFIG.pending;

  // Fetch thumbnail URL on mount — best-effort, no error surfaced to user
  useEffect(() => {
    if (!job.thumbnailGcsPath) return;
    let cancelled = false;
    getThumbnailUrl(job.jobId)
      .then((url) => { if (!cancelled) setThumbnailUrl(url); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [job.jobId, job.thumbnailGcsPath]);

  const handleClick = () => {
    if (job.status === 'completed') {
      navigate(`/result/${job.jobId}`);
    } else if (job.status === 'processing' || job.status === 'pending') {
      navigate(`/status/${job.jobId}`);
    }
    // failed jobs — no navigation (card is still visible but not clickable)
  };

  const isClickable = job.status === 'completed' || job.status === 'processing' || job.status === 'pending';

  return (
    <div
      onClick={isClickable ? handleClick : undefined}
      tabIndex={isClickable ? 0 : undefined}
      role={isClickable ? 'button' : undefined}
      aria-label={isClickable ? `View ${job.filename} — ${statusCfg.label}` : undefined}
      className={[
        'bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border-t-2 border-t-gold-light-accent dark:border-t-gold-accent border border-gold-light-border dark:border-gold-border rounded-lg overflow-hidden transition-all duration-200',
        isClickable
          ? 'cursor-pointer hover:border-gold-light-accent-hover dark:hover:border-gold-accent-hover hover:shadow-[0_0_20px_-5px_rgba(212,175,55,0.2)] hover:scale-[1.01] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-light-accent dark:focus-visible:ring-gold-accent'
          : 'opacity-70',
      ].join(' ')}
    >
      {/* Thumbnail */}
      <div className="aspect-video bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary flex items-center justify-center overflow-hidden">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={job.filename}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-gold-light-text-muted dark:text-gold-text-muted">
            <Film className="w-10 h-10" />
            {job.status === 'processing' || job.status === 'pending' ? (
              <span className="text-xs">Processing…</span>
            ) : null}
          </div>
        )}
      </div>

      {/* Card body */}
      <div className="p-4">
        {/* Filename */}
        <p className="text-sm font-medium text-gold-light-text-primary dark:text-gold-text-primary truncate mb-2" title={job.filename}>
          {job.filename}
        </p>

        {/* Status badge */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <span
            className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${statusCfg.className}`}
          >
            {statusCfg.icon}
            {statusCfg.label}
          </span>

          {/* Processing time (completed only) */}
          {job.processingTime ? (
            <span className="text-xs text-gold-light-text-muted dark:text-gold-text-muted flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(job.processingTime)}
            </span>
          ) : null}
        </div>

        {/* Created date */}
        <p className="text-xs text-gold-light-text-muted dark:text-gold-text-muted mt-2">{formatDate(job.createdAt)}</p>
      </div>
    </div>
  );
}
