import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, DollarSign, Clock, AlertTriangle,
  CheckCircle, XCircle, Loader2, Zap, RefreshCw, TrendingUp,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { getAdminStats, getAllJobs } from '../services/api';
import ThemeToggle from '../components/ThemeToggle';

const ADMIN_UID = import.meta.env.VITE_ADMIN_UID;

function StatCard({ icon: Icon, label, value, sub, color = 'text-gold-accent dark:text-gold-accent' }) {
  return (
    <div className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded-xl p-5 border-l-[3px] border-l-gold-light-accent dark:border-l-gold-accent">
      <div className="flex items-center gap-3 mb-3">
        <Icon className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />
        <span className="text-xs font-semibold text-gold-light-text-secondary dark:text-gold-text-secondary uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-2xl font-bold text-gold-light-accent dark:text-gold-accent">{value}</p>
      {sub && <p className="text-xs text-gold-light-text-muted dark:text-gold-text-muted mt-1">{sub}</p>}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    completed: 'bg-gold-accent-muted dark:bg-gold-accent-muted text-gold-light-accent dark:text-gold-accent border-gold-light-accent/20 dark:border-gold-accent/20',
    failed:    'bg-red-500/15 text-red-400 border-red-500/20',
    processing: 'bg-gold-accent-muted dark:bg-gold-accent-muted text-gold-light-accent dark:text-gold-accent border-gold-light-accent/20 dark:border-gold-accent/20',
    pending:   'bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary text-gold-light-text-muted dark:text-gold-text-muted border-gold-light-border dark:border-gold-border',
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${map[status] || map.pending}`}>
      {status}
    </span>
  );
}

export default function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // UID guard — redirect non-admins immediately
  useEffect(() => {
    if (user && user.uid !== ADMIN_UID) {
      navigate('/dashboard');
    }
  }, [user, navigate]);

  const fetchData = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const [statsData, jobsData] = await Promise.all([
        getAdminStats(),
        getAllJobs(50),
      ]);
      setStats(statsData);
      setJobs(jobsData);
    } catch (err) {
      setError(err.response?.status === 403
        ? 'Access denied. Admin only.'
        : 'Failed to load admin data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (user?.uid === ADMIN_UID) {
      fetchData();
    }
  }, [user]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-gold-light-accent dark:text-gold-accent animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary flex items-center justify-center text-red-400">
        {error}
      </div>
    );
  }

  const completedCount = stats?.byStatus?.completed || 0;
  const failedCount = stats?.byStatus?.failed || 0;
  const processingCount = stats?.byStatus?.processing || 0;
  const failRate = stats?.totalJobs > 0
    ? ((failedCount / stats.totalJobs) * 100).toFixed(1)
    : '0.0';

  return (
    <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary text-gold-light-text-primary dark:text-gold-text-primary font-sans transition-colors">
      {/* Navbar */}
      <nav className="border-b border-gold-light-border dark:border-gold-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 text-lg font-display font-bold text-gold-light-text-primary dark:text-gold-text-primary">
            VidIQ
          </Link>
          <span className="text-xs font-semibold text-gold-light-accent dark:text-gold-accent bg-gold-accent-muted dark:bg-gold-accent-muted border border-gold-light-accent/20 dark:border-gold-accent/20 px-2 py-0.5 rounded-full">
            Admin
          </span>
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="flex items-center gap-2 text-xs text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-accent dark:hover:text-gold-accent bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border hover:border-gold-light-accent/30 dark:hover:border-gold-accent/30 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
          <Link
            to="/dashboard"
            className="hidden sm:inline text-xs text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-accent dark:hover:text-gold-accent transition-colors"
          >
            ← User Dashboard
          </Link>
          <ThemeToggle />
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold mb-1 text-gold-light-text-primary dark:text-gold-text-primary">Admin Dashboard</h1>
        <p className="text-gold-light-text-secondary dark:text-gold-text-secondary text-sm mb-8">All users · All jobs · Real-time from Firestore</p>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={LayoutDashboard}
            label="Total Jobs"
            value={stats?.totalJobs ?? 0}
            sub={`${processingCount} active`}
          />
          <StatCard
            icon={CheckCircle}
            label="Completed"
            value={completedCount}
            sub={`${failedCount} failed (${failRate}%)`}
          />
          <StatCard
            icon={DollarSign}
            label="Total API Cost"
            value={`$${(stats?.totalEstimatedCostUsd ?? 0).toFixed(4)}`}
            sub={stats?.totalJobs > 0
              ? `~$${((stats.totalEstimatedCostUsd ?? 0) / stats.totalJobs).toFixed(4)}/job avg`
              : 'No jobs yet'}
          />
          <StatCard
            icon={Clock}
            label="Avg Processing"
            value={`${stats?.avgProcessingTimeSeconds ?? 0}s`}
            sub={`${Math.round((stats?.avgProcessingTimeSeconds ?? 0) / 60 * 10) / 10} min avg`}
          />
        </div>

        {/* Unit economics warning */}
        {stats?.totalJobs > 0 && stats.totalEstimatedCostUsd / stats.totalJobs > 0.10 && (
          <div className="flex items-start gap-3 bg-gold-accent-muted dark:bg-gold-accent-muted border border-gold-light-accent/20 dark:border-gold-accent/20 rounded-xl p-4 mb-8">
            <AlertTriangle className="w-5 h-5 text-gold-light-accent dark:text-gold-accent shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-gold-light-accent dark:text-gold-accent">Unit economics warning</p>
              <p className="text-xs text-gold-light-text-secondary dark:text-gold-text-secondary mt-1">
                Average cost per job is ${(stats.totalEstimatedCostUsd / stats.totalJobs).toFixed(4)},
                which exceeds sustainable levels for a ₹9/month (~$0.11) plan.
                Consider making Video Intelligence API optional or Pro-only to reduce per-job cost.
              </p>
            </div>
          </div>
        )}

        {/* Status breakdown */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Status counts */}
          <div className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border border-gold-light-border dark:border-gold-border border-t-2 border-t-gold-light-accent dark:border-t-gold-accent rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gold-light-text-primary dark:text-gold-text-primary mb-4">Jobs by Status</h2>
            <div className="space-y-3">
              {Object.entries(stats?.byStatus || {}).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <StatusBadge status={status} />
                  <div className="flex items-center gap-3 flex-1 mx-4">
                    <div className="flex-1 bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary rounded-full h-1.5">
                      <div
                        className="h-1.5 rounded-full bg-gold-light-accent/60 dark:bg-gold-accent/60"
                        style={{ width: `${(count / (stats?.totalJobs || 1)) * 100}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-gold-light-text-primary dark:text-gold-text-primary">{count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Top users */}
          <div className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border border-gold-light-border dark:border-gold-border border-t-2 border-t-gold-light-accent dark:border-t-gold-accent rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gold-light-text-primary dark:text-gold-text-primary mb-4">Top Users by Job Count</h2>
            <div className="space-y-3">
              {(stats?.topUsers || []).slice(0, 8).map((u) => (
                <div key={u.userId} className="flex items-center justify-between gap-3">
                  <p className="text-xs text-gold-light-text-secondary dark:text-gold-text-secondary truncate flex-1">{u.email}</p>
                  <span className="text-xs font-semibold text-gold-light-text-primary dark:text-gold-text-primary shrink-0">
                    {u.jobCount} jobs
                  </span>
                  <span className="text-xs text-gold-light-accent dark:text-gold-accent shrink-0">
                    ${u.totalCost.toFixed(3)}
                  </span>
                </div>
              ))}
              {(stats?.topUsers || []).length === 0 && (
                <p className="text-xs text-gold-light-text-muted dark:text-gold-text-muted">No users yet.</p>
              )}
            </div>
          </div>
        </div>

        {/* Jobs table */}
        <div className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border border-gold-light-border dark:border-gold-border border-t-2 border-t-gold-light-accent dark:border-t-gold-accent rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gold-light-border dark:border-gold-border flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gold-light-text-primary dark:text-gold-text-primary">Recent Jobs (All Users)</h2>
            <span className="text-xs text-gold-light-text-muted dark:text-gold-text-muted">{jobs.length} shown</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gold-light-border dark:border-gold-border text-gold-light-accent dark:text-gold-accent">
                  <th className="text-left px-5 py-3 font-medium">File</th>
                  <th className="text-left px-5 py-3 font-medium">User</th>
                  <th className="text-left px-5 py-3 font-medium">Status</th>
                  <th className="text-right px-5 py-3 font-medium">STT</th>
                  <th className="text-right px-5 py-3 font-medium">VI</th>
                  <th className="text-right px-5 py-3 font-medium">Gemini</th>
                  <th className="text-right px-5 py-3 font-medium">Total</th>
                  <th className="text-right px-5 py-3 font-medium">Time</th>
                  <th className="text-right px-5 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gold-light-border dark:divide-gold-border">
                {jobs.map((job) => (
                  <tr
                    key={job.jobId}
                    className="hover:bg-[rgba(184,150,12,0.1)] dark:hover:bg-gold-accent-muted cursor-pointer transition-colors"
                    onClick={() => navigate(`/result/${job.jobId}`)}
                  >
                    <td className="px-5 py-3 text-gold-light-text-primary dark:text-gold-text-primary max-w-[180px] truncate">
                      {job.filename || '—'}
                    </td>
                    <td className="px-5 py-3 text-gold-light-text-secondary dark:text-gold-text-secondary max-w-[150px] truncate">
                      {job.userEmail || job.userId?.slice(0, 8) || 'anon'}
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={job.status} />
                      {job.status === 'failed' && job.errorMessage && (
                        <p className="text-red-400 text-xs mt-1 max-w-[200px] truncate">
                          {job.errorMessage}
                        </p>
                      )}
                    </td>
                    <td className="px-5 py-3 text-right text-gold-light-text-secondary dark:text-gold-text-secondary">
                      {job.sttEstimatedCostUsd != null ? `$${job.sttEstimatedCostUsd.toFixed(4)}` : '—'}
                    </td>
                    <td className="px-5 py-3 text-right text-gold-light-text-secondary dark:text-gold-text-secondary">
                      {job.viEstimatedCostUsd != null ? `$${job.viEstimatedCostUsd.toFixed(4)}` : '—'}
                    </td>
                    <td className="px-5 py-3 text-right text-gold-light-text-secondary dark:text-gold-text-secondary">
                      {job.geminiEstimatedCostUsd != null ? `$${job.geminiEstimatedCostUsd.toFixed(4)}` : '—'}
                    </td>
                    <td className={`px-5 py-3 text-right font-semibold ${
                      (job.totalEstimatedCostUsd ?? 0) > 0.10 ? 'text-gold-light-accent dark:text-gold-accent' : 'text-gold-light-text-primary dark:text-gold-text-primary'
                    }`}>
                      {job.totalEstimatedCostUsd != null ? `$${job.totalEstimatedCostUsd.toFixed(4)}` : '—'}
                    </td>
                    <td className="px-5 py-3 text-right text-gold-light-text-secondary dark:text-gold-text-secondary">
                      {job.processingTime ? `${job.processingTime}s` : '—'}
                    </td>
                    <td className="px-5 py-3 text-right text-gold-light-text-muted dark:text-gold-text-muted">
                      {job.createdAt
                        ? new Date(job.createdAt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
                        : '—'}
                    </td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-5 py-8 text-center text-gold-light-text-muted dark:text-gold-text-muted">
                      No jobs yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
