import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, DollarSign, Clock, AlertTriangle,
  CheckCircle, XCircle, Loader2, Zap, RefreshCw, TrendingUp,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { getAdminStats, getAllJobs } from '../services/api';

const ADMIN_UID = import.meta.env.VITE_ADMIN_UID;

function StatCard({ icon: Icon, label, value, sub, color = 'text-violet-400' }) {
  return (
    <div className="bg-dark-surface border border-dark-border rounded-xl p-5">
      <div className="flex items-center gap-3 mb-3">
        <Icon className={`w-5 h-5 ${color}`} />
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    completed: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    failed:    'bg-red-500/15 text-red-400 border-red-500/20',
    processing: 'bg-violet-500/15 text-violet-400 border-violet-500/20',
    pending:   'bg-slate-500/15 text-slate-400 border-slate-500/20',
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
      <div className="min-h-screen bg-dark-base flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-dark-base flex items-center justify-center text-red-400">
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
    <div className="min-h-screen bg-dark-base text-slate-100 font-sans">
      {/* Navbar */}
      <nav className="border-b border-dark-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold">
            <Zap className="w-5 h-5 text-violet-500" fill="currentColor" />
            VidIQ
          </Link>
          <span className="text-xs font-semibold text-violet-400 bg-violet-500/15 border border-violet-500/20 px-2 py-0.5 rounded-full">
            Admin
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-200 bg-white/5 border border-dark-border hover:border-violet-500/30 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link
            to="/dashboard"
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            ← User Dashboard
          </Link>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold mb-1">Admin Dashboard</h1>
        <p className="text-slate-400 text-sm mb-8">All users · All jobs · Real-time from Firestore</p>

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
            color={failedCount > 0 ? 'text-amber-400' : 'text-emerald-400'}
          />
          <StatCard
            icon={DollarSign}
            label="Total API Cost"
            value={`$${(stats?.totalEstimatedCostUsd ?? 0).toFixed(4)}`}
            sub={stats?.totalJobs > 0
              ? `~$${((stats.totalEstimatedCostUsd ?? 0) / stats.totalJobs).toFixed(4)}/job avg`
              : 'No jobs yet'}
            color="text-amber-400"
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
          <div className="flex items-start gap-3 bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 mb-8">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-400">Unit economics warning</p>
              <p className="text-xs text-slate-400 mt-1">
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
          <div className="bg-dark-surface border border-dark-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-300 mb-4">Jobs by Status</h2>
            <div className="space-y-3">
              {Object.entries(stats?.byStatus || {}).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <StatusBadge status={status} />
                  <div className="flex items-center gap-3 flex-1 mx-4">
                    <div className="flex-1 bg-white/5 rounded-full h-1.5">
                      <div
                        className="h-1.5 rounded-full bg-violet-500/60"
                        style={{ width: `${(count / (stats?.totalJobs || 1)) * 100}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-slate-300">{count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Top users */}
          <div className="bg-dark-surface border border-dark-border rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-300 mb-4">Top Users by Job Count</h2>
            <div className="space-y-3">
              {(stats?.topUsers || []).slice(0, 8).map((u) => (
                <div key={u.userId} className="flex items-center justify-between gap-3">
                  <p className="text-xs text-slate-400 truncate flex-1">{u.email}</p>
                  <span className="text-xs font-semibold text-slate-300 shrink-0">
                    {u.jobCount} jobs
                  </span>
                  <span className="text-xs text-amber-400 shrink-0">
                    ${u.totalCost.toFixed(3)}
                  </span>
                </div>
              ))}
              {(stats?.topUsers || []).length === 0 && (
                <p className="text-xs text-slate-500">No users yet.</p>
              )}
            </div>
          </div>
        </div>

        {/* Jobs table */}
        <div className="bg-dark-surface border border-dark-border rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-dark-border flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-300">Recent Jobs (All Users)</h2>
            <span className="text-xs text-slate-500">{jobs.length} shown</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-dark-border text-slate-500">
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
              <tbody className="divide-y divide-dark-border">
                {jobs.map((job) => (
                  <tr
                    key={job.jobId}
                    className="hover:bg-white/3 cursor-pointer transition-colors"
                    onClick={() => navigate(`/result/${job.jobId}`)}
                  >
                    <td className="px-5 py-3 text-slate-300 max-w-[180px] truncate">
                      {job.filename || '—'}
                    </td>
                    <td className="px-5 py-3 text-slate-400 max-w-[150px] truncate">
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
                    <td className="px-5 py-3 text-right text-slate-400">
                      {job.sttEstimatedCostUsd != null ? `$${job.sttEstimatedCostUsd.toFixed(4)}` : '—'}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-400">
                      {job.viEstimatedCostUsd != null ? `$${job.viEstimatedCostUsd.toFixed(4)}` : '—'}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-400">
                      {job.geminiEstimatedCostUsd != null ? `$${job.geminiEstimatedCostUsd.toFixed(4)}` : '—'}
                    </td>
                    <td className={`px-5 py-3 text-right font-semibold ${
                      (job.totalEstimatedCostUsd ?? 0) > 0.10 ? 'text-amber-400' : 'text-slate-300'
                    }`}>
                      {job.totalEstimatedCostUsd != null ? `$${job.totalEstimatedCostUsd.toFixed(4)}` : '—'}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-400">
                      {job.processingTime ? `${job.processingTime}s` : '—'}
                    </td>
                    <td className="px-5 py-3 text-right text-slate-500">
                      {job.createdAt
                        ? new Date(job.createdAt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
                        : '—'}
                    </td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-5 py-8 text-center text-slate-500">
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
