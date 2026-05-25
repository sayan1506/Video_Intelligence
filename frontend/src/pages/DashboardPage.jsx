import { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Zap, Plus, LogOut, RefreshCw, Film, AlertCircle, Crown } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { getJobs, getBillingStatus } from '../services/api';
import JobCard from '../components/JobCard';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();

  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [plan, setPlan] = useState('free');

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
    getBillingStatus()
      .then(({ plan }) => setPlan(plan))
      .catch(() => {});
  }, []);

  const handleSignOut = async () => {
    await signOut();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-dark-base text-slate-100 font-sans">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-dark-base/80 border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
          <Zap className="w-6 h-6 text-violet-500" fill="currentColor" />
          <span>VidIQ</span>
        </Link>

        <div className="flex items-center gap-3">
          {/* User avatar / email */}
          <div className="hidden sm:flex items-center gap-2 text-sm text-slate-400">
            {user?.photoURL ? (
              <img
                src={user.photoURL}
                alt={user.displayName ?? 'User'}
                className="w-7 h-7 rounded-full border border-white/10"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-violet-500/20 border border-violet-500/30 flex items-center justify-center text-xs font-bold text-violet-400">
                {(user?.displayName ?? user?.email ?? '?')[0].toUpperCase()}
              </div>
            )}
            <span className="max-w-[160px] truncate">{user?.displayName ?? user?.email}</span>
            {plan === 'pro' ? (
              <span className="flex items-center gap-1 text-xs font-semibold text-violet-400 bg-violet-500/15 border border-violet-500/20 px-2 py-0.5 rounded-full">
                <Crown className="w-3 h-3" /> Pro
              </span>
            ) : (
              <Link
                to="/pricing"
                className="text-xs font-semibold text-slate-400 hover:text-violet-400 bg-white/5 border border-dark-border hover:border-violet-500/30 px-2 py-0.5 rounded-full transition-colors"
              >
                Upgrade
              </Link>
            )}
          </div>

          <button
            onClick={() => navigate('/upload')}
            className="flex items-center gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 active:scale-95 transition-all text-white px-4 py-2 rounded-full text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Video
          </button>

          <button
            onClick={handleSignOut}
            title="Sign out"
            className="p-2 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors"
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
            <p className="text-slate-400 text-sm mt-1">
              {jobs.length > 0 ? `${jobs.length} video${jobs.length !== 1 ? 's' : ''}` : 'No videos yet'}
            </p>
            {plan === 'free' && jobs.length > 0 && (
              <p className="text-slate-500 text-xs mt-1">
                {Math.max(0, 5 - jobs.length)} free video{Math.max(0, 5 - jobs.length) !== 1 ? 's' : ''} remaining this month ·{' '}
                <Link to="/pricing" className="text-violet-400 hover:underline">Upgrade to Pro</Link>
              </p>
            )}
          </div>

          <button
            onClick={() => fetchJobs(true)}
            disabled={refreshing}
            title="Refresh"
            className="p-2 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>

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
              <div key={i} className="bg-dark-surface border border-dark-border rounded-2xl overflow-hidden animate-pulse">
                <div className="aspect-video bg-white/5" />
                <div className="p-4 space-y-2">
                  <div className="h-3 bg-white/5 rounded w-3/4" />
                  <div className="h-3 bg-white/5 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && jobs.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-20 h-20 rounded-full bg-white/5 flex items-center justify-center mb-6">
              <Film className="w-10 h-10 text-slate-600" />
            </div>
            <h2 className="text-xl font-bold text-slate-300 mb-2">No videos yet</h2>
            <p className="text-slate-500 mb-8 max-w-sm">
              Upload your first video and VidIQ will generate a full transcript, AI summary, and scene analysis.
            </p>
            <button
              onClick={() => navigate('/upload')}
              className="flex items-center gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 active:scale-95 transition-all text-white px-6 py-3 rounded-full font-medium"
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
