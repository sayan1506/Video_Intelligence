import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Zap, AlertTriangle, ArrowLeft } from 'lucide-react';
import { getResult } from '../services/api';

import VideoPlayer from '../components/VideoPlayer';
import SummaryCard from '../components/SummaryCard';
import TranscriptPanel from '../components/TranscriptPanel';
import ScenePanel from '../components/ScenePanel';

export default function ResultPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const videoPlayerRef = useRef(null);

  const seekTo = useCallback((seconds) => {
    if (videoPlayerRef.current) {
      videoPlayerRef.current.seekTo(seconds);
    }
  }, []);

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
        <main className="p-6 max-w-7xl mx-auto flex flex-col md:flex-row gap-6 animate-pulse-slow">
           <div className="w-full md:w-1/2 flex flex-col gap-6">
              <div className="h-[400px] bg-dark-surface rounded-2xl"></div>
              <div className="h-[400px] bg-dark-surface rounded-2xl"></div>
           </div>
           <div className="w-full md:w-1/2 flex flex-col gap-6">
              <div className="h-[500px] bg-dark-surface rounded-2xl"></div>
              <div className="h-[300px] bg-dark-surface rounded-2xl"></div>
           </div>
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-dark-base text-slate-100 font-sans flex flex-col">
        <NavHeader />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-[500px] bg-dark-surface border border-red-500/20 rounded-3xl p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4 text-red-500">
              <AlertTriangle className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold mb-2">Error Loading Result</h2>
            <p className="text-slate-400 mb-8">{error}</p>
            <button 
              onClick={() => navigate('/upload')}
              className="px-6 py-3 bg-white/10 hover:bg-white/20 text-white rounded-xl font-medium transition-colors"
            >
              Back to Upload
            </button>
          </div>
        </main>
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
      <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between bg-dark-base shrink-0">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
             <Zap className="w-6 h-6 text-violet-500" fill="currentColor" />
             <span>VidIQ</span>
          </Link>
          <div className="hidden md:flex items-center gap-2 text-sm text-slate-400 border-l border-white/10 pl-6">
            <span className="font-mono bg-white/5 px-2 py-1 rounded">Job: {jobId}</span>
            {result?.processingTime && (
              <span>{" \u00B7 "} Processed in {result.processingTime.toFixed(1)}s</span>
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
                scenes={result?.scenes} 
                highlights={result?.highlights}
                onPlayerReady={(player) => { videoPlayerRef.current = player; }}
              />
            </div>
            <div className="flex-[1_1_auto] overflow-hidden">
              <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
                <SummaryCard 
                  summary={result?.summary}
                  sentiment={result?.sentiment}
                  chapters={result?.chapters}
                  highlights={result?.highlights}
                  actionItems={result?.actionItems}
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
                  transcript={result?.transcript}
                  currentTime={0} 
                  seekTo={seekTo}
                />
              </div>
            </div>
            <div className="flex-[1_1_auto] h-1/2 overflow-hidden">
              <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
                <ScenePanel 
                  scenes={result?.scenes}
                  labels={result?.labels}
                  seekTo={seekTo}
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