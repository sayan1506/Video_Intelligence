import { useState, useEffect, useCallback } from 'react';
import { Globe, Lock } from 'lucide-react';
import { toggleJobShare } from '../services/api';

/**
 * ShareToggle — toggle switch for public/private job visibility.
 *
 * Renders a toggle control showing "Private" or "Public" label based on
 * the current share state. Disables during API calls and reverts on failure
 * with an auto-dismissing error toast (5 seconds).
 *
 * Only rendered by the parent when the user is the job owner.
 *
 * Props:
 *   jobId    — the job identifier
 *   isPublic — current public visibility state
 *   onToggle — callback invoked with the new boolean value on successful toggle
 */
export default function ShareToggle({ jobId, isPublic, onToggle }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Auto-dismiss error toast after 5 seconds
  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(timer);
  }, [error]);

  const handleToggle = useCallback(async () => {
    if (loading) return;

    const newValue = !isPublic;
    setLoading(true);
    setError(null);

    try {
      await toggleJobShare(jobId, newValue);
      onToggle(newValue);
    } catch (err) {
      // Revert: the parent state stays unchanged since onToggle was not called
      setError('Failed to update share setting. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [jobId, isPublic, loading, onToggle]);

  return (
    <div className="relative flex items-center gap-3">
      {/* Toggle switch */}
      <button
        type="button"
        role="switch"
        aria-checked={isPublic}
        aria-label={isPublic ? 'Disable public sharing' : 'Enable public sharing'}
        disabled={loading}
        onClick={handleToggle}
        className={[
          'relative inline-flex min-h-[44px] min-w-[44px] h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-gold-light-accent dark:focus-visible:ring-gold-accent focus-visible:ring-offset-2 focus-visible:ring-offset-gold-light-bg-primary dark:focus-visible:ring-offset-gold-bg-primary',
          isPublic ? 'bg-gold-light-accent dark:bg-gold-accent' : 'bg-gold-light-border dark:bg-gold-border',
          loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
        ].join(' ')}
      >
        <span
          className={[
            'inline-block h-4 w-4 rounded-full bg-white transition-transform duration-200',
            isPublic ? 'translate-x-6' : 'translate-x-1',
          ].join(' ')}
        />
      </button>

      {/* Label with icon */}
      <span className="flex items-center gap-1.5 text-sm text-gold-light-text-secondary dark:text-gold-text-secondary">
        {isPublic ? (
          <>
            <Globe className="w-3.5 h-3.5 text-gold-light-accent dark:text-gold-accent" />
            <span>Public</span>
          </>
        ) : (
          <>
            <Lock className="w-3.5 h-3.5 text-gold-light-text-muted dark:text-gold-text-muted" />
            <span>Private</span>
          </>
        )}
      </span>

      {/* Error toast */}
      {error && (
        <div
          role="alert"
          className="absolute top-full left-0 mt-2 z-50 px-3 py-2 bg-red-500/90 text-gold-text-primary text-xs rounded-lg shadow-lg whitespace-nowrap animate-fade-in"
        >
          {error}
        </div>
      )}
    </div>
  );
}
