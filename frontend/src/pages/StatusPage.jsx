import { useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, Loader2, Zap } from 'lucide-react';
import useJobStatus from '../hooks/useJobStatus';

export default function StatusPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const { status, progress, stage, error, isLoading } = useJobStatus(jobId);

  useEffect(() => {
    if (status === 'completed') {
      const timer = setTimeout(() => {
        navigate('/result/' + jobId);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [status, jobId, navigate]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-dark-base text-slate-100 flex flex-col font-sans">
        <NavHeader />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-[560px] bg-dark-surface border border-dark-border rounded-3xl p-8 animate-pulse-slow">
            <div className="h-8 bg-white/5 rounded-lg w-1/2 mx-auto mb-2"></div>
            <div className="h-4 bg-white/5 rounded-lg w-1/3 mx-auto mb-10"></div>
            <div className="w-48 h-48 rounded-full bg-white/5 mx-auto mb-8"></div>
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className="h-6 bg-white/5 rounded w-full"></div>
              ))}
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (status === 'failed' || error) {
    return (
      <div className="min-h-screen bg-dark-base text-slate-100 flex flex-col font-sans">
        <NavHeader />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-[560px] bg-dark-surface border border-red-500/20 rounded-3xl p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4 text-red-500">
              <AlertTriangle className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold mb-2">Processing Failed</h2>
            <p className="text-slate-400 mb-8">{error || "An error occurred during processing."}</p>
            <button 
              onClick={() => navigate('/upload')}
              className="px-6 py-3 bg-red-500 hover:bg-red-600 text-white rounded-xl font-medium transition-colors"
            >
              Try Again
            </button>
          </div>
        </main>
      </div>
    );
  }

  // Calculate steps for checklist
  const safeProgress = progress || 0;
  
  const steps = [
    { label: "Video uploaded", isComplete: true, isActive: false },
    { label: "Transcribing audio...", isComplete: safeProgress >= 50, isActive: safeProgress >= 10 && safeProgress < 50 },
    { label: "Detecting scenes...", isComplete: safeProgress >= 75, isActive: safeProgress >= 50 && safeProgress < 75 },
    { label: "Generating summary...", isComplete: safeProgress >= 90, isActive: safeProgress >= 75 && safeProgress < 90 },
    { label: "Complete", isComplete: status === 'completed', isActive: safeProgress >= 90 && status !== 'completed' },
  ];

  const radius = 80;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - ((safeProgress || 0) / 100) * circumference;

  return (
    <div className="min-h-screen bg-dark-base text-slate-100 flex flex-col font-sans">
      <NavHeader />
      <main className="flex-1 flex items-center justify-center p-6 animate-fade-in">
        <div className="w-full max-w-[560px] bg-dark-surface border border-dark-border rounded-3xl p-8 shadow-2xl relative overflow-hidden">
          
          {status === 'completed' && (
            <div className="absolute inset-x-0 top-0 bg-emerald-500/90 text-white text-center py-2 font-medium text-sm animate-slide-up z-10 flex items-center justify-center gap-2">
              <CheckCircle2 className="w-4 h-4" /> Analysis complete! Redirecting...
            </div>
          )}

          <div className="text-center mb-10 mt-2">
            <h1 className="text-2xl font-bold tracking-tight mb-2">Processing Your Video</h1>
            <p className="font-mono text-xs text-slate-500 bg-white/5 inline-block px-3 py-1 rounded-full">
              ID: {jobId}
            </p>
          </div>

          <div className="relative flex justify-center mb-8">
            {/* SVG Ring */}
            <svg viewBox="0 0 200 200" className="transform -rotate-90 w-32 h-32 sm:w-48 sm:h-48">
              <circle
                cx="100"
                cy="100"
                r={radius}
                className="stroke-white/5"
                strokeWidth="12"
                fill="none"
              />
              <circle
                cx="100"
                cy="100"
                r={radius}
                className="stroke-violet-500 transition-all duration-500 ease-out"
                strokeWidth="12"
                fill="none"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center flex-col">
              <span className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-violet-400 to-indigo-400">
                {safeProgress}%
              </span>
            </div>
          </div>

          <div className="text-center mb-8 flex items-center justify-center gap-2 text-indigo-400 font-medium">
            {status !== 'completed' && <Loader2 className="w-4 h-4 animate-spin" />}
            {stage || (safeProgress === 100 ? "Finalising..." : "Processing...")}
          </div>

          <div className="bg-white/5 border border-white/10 rounded-2xl p-6 mb-6">
            <ul className="space-y-4">
              {steps.map((step, idx) => (
                <li key={idx} className={`flex items-center gap-3 text-sm ${step.isComplete ? 'text-slate-200' : step.isActive ? 'text-indigo-300 font-medium' : 'text-slate-500'}`}>
                  {step.isComplete ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                  ) : step.isActive ? (
                    <Loader2 className="w-5 h-5 animate-spin text-indigo-400 shrink-0" />
                  ) : (
                    <div className="w-5 h-5 rounded-full border-2 border-slate-600 shrink-0" />
                  )}
                  <span>{step.label}</span>
                </li>
              ))}
            </ul>
          </div>

          <p className="text-center text-xs text-slate-500">
            Processing usually takes 1-3 minutes depending on video length.
          </p>

        </div>
      </main>
    </div>
  );
}

function NavHeader() {
  return (
    <nav className="border-b border-white/5 px-6 py-4 flex items-center justify-between bg-dark-base">
      <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
        <Zap className="w-6 h-6 text-violet-500" fill="currentColor" />
        <span>VidIQ</span>
      </Link>
    </nav>
  );
}