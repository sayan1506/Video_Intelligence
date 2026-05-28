import { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Zap, Plus, LogOut, RefreshCw, Film, AlertCircle, Crown } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { getJobs, getQuota } from '../services/api';
import JobCard from '../components/JobCard';
import ThemeToggle from '../components/ThemeToggle';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();

  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [quota, setQuota] = useState({ plan: 'free', jobsThisMonth: 0, monthlyLimit: 5, resetDate: null });
  const [quotaError, setQuotaError] = useState(false);

  const fetchJobs = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const data = await getJobs(20);
      setJobs(data);
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
      setError('Could not load your videos. Please try again.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  useEffect(() => {
    getQuota()
      .then(q => setQuota(q))
      .catch(() => setQuotaError(true));
  }, []);

  const handleSignOut = async () => {
    await signOut();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary text-gold-light-text-primary dark:text-gold-text-primary font-sans transition-colors">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-gold-light-bg-primary/80 dark:bg-gold-bg-primary/80 border-b border-gold-light-border dark:border-gold-border px-6 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
          <span className="font-display text-2xl text-gold-light-text-primary dark:text-gold-text-primary">VidIQ</span>
        </Link>

        <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
          {/* User avatar / email */}
          <div className="hidden sm:flex items-center gap-2 text-sm text-gold-light-text-secondary dark:text-gold-text-secondary">
            {user?.photoURL ? (
              <img
                src={user.photoURL}
                alt={user.displayName ?? 'User'}
                className="w-7 h-7 rounded-full border border-gold-light-border dark:border-gold-border"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-gold-accent-muted dark:bg-gold-accent-muted border border-gold-light-accent dark:border-gold-accent flex items-center justify-center text-xs font-bold text-gold-light-accent dark:text-gold-accent">
                {(user?.displayName ?? user?.email ?? '?')[0].toUpperCase()}
              </div>
            )}
            <span className="max-w-[160px] truncate">{user?.displayName ?? user?.email}</span>
            {quota.plan === 'pro' ? (
              <span className="flex items-center gap-1 text-xs font-semibold text-gold-light-accent dark:text-gold-accent bg-gold-accent-muted border border-gold-light-border dark:border-gold-border px-2 py-0.5 rounded-full">
                <Crown className="w-3 h-3" /> Pro
              </span>
            ) : (
              <Link
                to="/pricing"
                className="text-xs font-semibold text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-accent dark:hover:text-gold-accent bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border hover:border-gold-light-accent dark:hover:border-gold-accent px-2 py-0.5 rounded-full transition-colors"
              >
                Upgrade
              </Link>
            )}
            {user?.uid === import.meta.env.VITE_ADMIN_UID && (
              <Link
                to="/admin"
                className="text-xs font-semibold text-gold-light-text-muted dark:text-gold-text-muted hover:text-gold-light-accent dark:hover:text-gold-accent transition-colors"
              >
                Admin ↗
              </Link>
            )}
          </div>

          <ThemeToggle />

          <button
            onClick={() => navigate('/upload')}
            className="flex items-center gap-2 bg-gold-light-accent dark:bg-gold-accent hover:bg-gold-light-accent-hover dark:hover:bg-gold-accent-hover active:scale-95 transition-all text-white dark:text-gold-bg-primary px-3 sm:px-4 py-2 rounded-full text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-light-accent dark:focus-visible:ring-gold-accent focus-visible:ring-offset-2 focus-visible:ring-offset-gold-light-bg-primary dark:focus-visible:ring-offset-gold-bg-primary"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">New Video</span>
          </button>

          <button
            onClick={handleSignOut}
            title="Sign out"
            aria-label="Sign out"
            className="w-11 h-11 flex items-center justify-center text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-text-primary dark:hover:text-gold-text-primary hover:bg-gold-light-bg-tertiary dark:hover:bg-gold-bg-tertiary rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-light-accent dark:focus-visible:ring-gold-accent"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-10 animate-fade-in">
        {/* Page header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">My Videos</h1>
            <p className="text-gold-light-text-secondary dark:text-gold-text-secondary text-sm mt-1">
              {jobs.length > 0 ? `${jobs.length} video${jobs.length !== 1 ? 's' : ''}` : 'No videos yet'}
            </p>
            {quota.plan === 'free' && (
              <p className="text-gold-light-text-muted dark:text-gold-text-muted text-xs mt-1">
                {quotaError ? (
                  <>Could not load quota — try refreshing.</>
                ) : (
                  <>
                    {Math.max(0, quota.monthlyLimit - quota.jobsThisMonth)} of {quota.monthlyLimit} free video{quota.monthlyLimit !== 1 ? 's' : ''} remaining this month
                    {quota.resetDate && (
                      <> · resets {new Date(quota.resetDate).toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}</>
                    )}
                  </>
                )}
                {' · '}
                <Link to="/pricing" className="text-gold-light-accent dark:text-gold-accent hover:underline">Upgrade to Pro</Link>
              </p>
            )}
          </div>

          <button
            onClick={() => fetchJobs(true)}
            disabled={refreshing}
            title="Refresh"
            aria-label="Refresh"
            className="w-11 h-11 flex items-center justify-center text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-text-primary dark:hover:text-gold-text-primary hover:bg-gold-light-bg-tertiary dark:hover:bg-gold-bg-tertiary rounded-lg transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-light-accent dark:focus-visible:ring-gold-accent"
          >
            <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Gold string separator */}
        <div className="h-px w-full bg-gold-light-accent dark:bg-gold-accent mb-8" />

        {/* Error state */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3 text-red-400 text-sm">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <p>{error}</p>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border border-gold-light-border dark:border-gold-border border-t-2 border-t-gold-light-accent dark:border-t-gold-accent rounded-2xl overflow-hidden animate-pulse">
                <div className="aspect-video bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary" />
                <div className="p-4 space-y-2">
                  <div className="h-3 bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary rounded w-3/4" />
                  <div className="h-3 bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && jobs.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-20 h-20 rounded-full bg-gold-accent-muted flex items-center justify-center mb-6">
              <Film className="w-10 h-10 text-gold-light-accent dark:text-gold-accent" />
            </div>
            <h2 className="text-xl font-bold text-gold-light-text-primary dark:text-gold-text-primary mb-2">No videos yet</h2>
            <p className="text-gold-light-text-secondary dark:text-gold-text-secondary mb-8 max-w-sm">
              Upload your first video and VidIQ will generate a full transcript, AI summary, and scene analysis.
            </p>
            <button
              onClick={() => navigate('/upload')}
              className="flex items-center gap-2 bg-gold-light-accent dark:bg-gold-accent hover:bg-gold-light-accent-hover dark:hover:bg-gold-accent-hover active:scale-95 transition-all text-white dark:text-gold-bg-primary px-6 py-3 rounded-full font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-light-accent dark:focus-visible:ring-gold-accent focus-visible:ring-offset-2 focus-visible:ring-offset-gold-light-bg-primary dark:focus-visible:ring-offset-gold-bg-primary"
            >
              <Plus className="w-5 h-5" />
              Upload your first video
            </button>
          </div>
        )}

        {/* Job grid */}
        {!loading && jobs.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {jobs.map((job) => (
              <JobCard key={job.jobId} job={job} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
