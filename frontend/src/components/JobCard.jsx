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
    className: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  },
  processing: {
    label: 'Processing',
    icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
    className: 'bg-violet-500/15 text-violet-400 border-violet-500/20',
  },
  pending: {
    label: 'Pending',
    icon: <Clock className="w-3.5 h-3.5" />,
    className: 'bg-slate-500/15 text-slate-400 border-slate-500/20',
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
      className={[
        'bg-dark-surface border border-dark-border rounded-2xl overflow-hidden transition-all duration-200',
        isClickable
          ? 'cursor-pointer hover:border-violet-500/40 hover:shadow-[0_0_20px_-5px_rgba(124,58,237,0.3)] hover:scale-[1.01]'
          : 'opacity-70',
      ].join(' ')}
    >
      {/* Thumbnail */}
      <div className="aspect-video bg-dark-base flex items-center justify-center overflow-hidden">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={job.filename}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-slate-600">
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
        <p className="text-sm font-medium text-slate-200 truncate mb-2" title={job.filename}>
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
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(job.processingTime)}
            </span>
          ) : null}
        </div>

        {/* Created date */}
        <p className="text-xs text-slate-600 mt-2">{formatDate(job.createdAt)}</p>
      </div>
    </div>
  );
}
