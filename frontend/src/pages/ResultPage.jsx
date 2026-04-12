import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Zap, AlertTriangle, ArrowLeft } from 'lucide-react';
import { getResult } from '../services/api';

import VideoPlayer from '../components/VideoPlayer';
import SummaryCard from '../components/SummaryCard';
import TranscriptPanel from '../components/TranscriptPanel';
import ScenePanel from '../components/ScenePanel';

const SkeletonCard = ({ className }) => (
  <div className={`bg-white/5 border border-white/10 rounded-2xl animate-pulse ${className}`} />
);

export default function ResultPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);

  const videoPlayerRef = useRef(null);

  const seekTo = useCallback((seconds) => {
    if (videoPlayerRef.current) {
      videoPlayerRef.current.currentTime(seconds);
    }
  }, []);

  const handlePlayerReady = useCallback((player) => {
    videoPlayerRef.current = player;
    player.on('timeupdate', () => {
      setCurrentTime(player.currentTime());
    });
  }, []);

  const formatDuration = (seconds) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  };

  useEffect(() => {
    if (!jobId) return;
    
    const fetchResult = async () => {
      try {
        const data = await getResult(jobId);
        setResult(data);
      } catch (err) {
        console.error(err);
        setError("Failed to load result.");
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchResult();
  }, [jobId]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-dark-base text-slate-100 font-sans">
        <NavHeader />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-4">
          <div className="flex flex-col gap-4">
            <SkeletonCard className="h-72" />
            <SkeletonCard className="h-64" />
          </div>
          <div className="flex flex-col gap-4">
            <SkeletonCard className="h-80" />
            <SkeletonCard className="h-64" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-dark-base flex items-center justify-center">
        <div className="text-center max-w-md p-8 bg-white/5 border border-white/10 rounded-2xl">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-100 mb-2">Failed to load results</h2>
          <p className="text-slate-400 text-sm mb-6">{error}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => navigate('/upload')}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-sm transition-colors"
            >
              New Upload
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-white/10 hover:bg-white/20 text-slate-300 rounded-xl text-sm transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (result && result.status !== 'completed') {
    return (
      <div className="min-h-screen bg-dark-base text-slate-100 font-sans flex flex-col">
        <NavHeader />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-[500px] bg-dark-surface border border-yellow-500/20 rounded-3xl p-8 text-center text-yellow-100">
            <h2 className="text-xl font-bold mb-2">Analysis Not Complete</h2>
            <p className="text-yellow-100/70 mb-8 mt-2 text-sm leading-relaxed">
              This job is not yet complete. Please check the status page.
            </p>
            <Link 
              to={`/status/${jobId}`}
              className="px-6 py-3 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-300 rounded-xl font-medium transition-colors inline-block"
            >
              Go to Status
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-dark-base text-slate-100 font-sans flex flex-col overflow-hidden">
      <header className="border-b border-white/5 px-6 py-4 flex flex-wrap items-center justify-between bg-dark-base shrink-0">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
             <Zap className="w-6 h-6 text-violet-500" fill="currentColor" />
             <span>VidIQ</span>
          </Link>
          <div className="hidden md:flex items-center gap-2 text-sm text-slate-400 border-l border-white/10 pl-6">
            <span className="font-mono bg-white/5 px-2 py-1 rounded truncate max-w-[150px] sm:max-w-none">Job: {jobId}</span>
            {result?.processingTime && (
              <span>{" \u00B7 "} Processed in {formatDuration(result.processingTime)}</span>
            )}
          </div>
        </div>
        <Link to="/upload" className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" /> New Upload
        </Link>
      </header>

      <main className="flex-1 p-4 md:p-6 overflow-y-auto">
        <div className="max-w-[1600px] mx-auto h-full flex flex-col md:flex-row gap-4 md:gap-6">
          
          {/* Left Column */}
          <div className="w-full md:w-1/2 flex flex-col gap-4 md:gap-6 min-h-0">
            <div className="flex-[0_0_auto]">
              <VideoPlayer 
                videoUrl={result?.videoUrl} 
                scenes={result?.scenes ?? []} 
                highlights={result?.highlights ?? []}
                currentTime={currentTime}
                seekTo={seekTo}
                onPlayerReady={handlePlayerReady}
              />
            </div>
            <div className="flex-[1_1_auto] overflow-hidden">
              <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
                <SummaryCard 
                  summary={result?.summary}
                  sentiment={result?.sentiment}
                  chapters={result?.chapters ?? []}
                  highlights={result?.highlights ?? []}
                  actionItems={result?.actionItems ?? []}
                  seekTo={seekTo}
                />
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className="w-full md:w-1/2 flex flex-col gap-4 md:gap-6 min-h-0">
            <div className="flex-[1_1_auto] h-1/2 overflow-hidden">
              <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
                <TranscriptPanel 
                  transcript={result?.transcript ?? []}
                  currentTime={currentTime} 
                  seekTo={seekTo}
                />
              </div>
            </div>
            <div className="flex-[1_1_auto] h-1/2 overflow-hidden">
              <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
                <ScenePanel 
                  scenes={result?.scenes ?? []}
                  labels={result?.labels ?? []}
                  seekTo={seekTo}
                  currentTime={currentTime}
                />
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}

function NavHeader() {
  return (
    <nav className="border-b border-white/5 px-6 py-4 flex items-center justify-between bg-dark-base shrink-0">
      <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
        <Zap className="w-6 h-6 text-violet-500" fill="currentColor" />
        <span>VidIQ</span>
      </Link>
    </nav>
  );
}