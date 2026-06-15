import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowLeft } from 'lucide-react';
import { getResult, getVideoUrl } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

import VideoPlayer from '../components/VideoPlayer';
import SummaryCard from '../components/SummaryCard';
import TranscriptPanel from '../components/TranscriptPanel';
import ScenePanel from '../components/ScenePanel';
import ProcessingStats from '../components/ProcessingStats';
import QAPanel from '../components/QAPanel';
import ShareToggle from '../components/ShareToggle';
import CopyLinkButton from '../components/CopyLinkButton';
import ThemeToggle from '../components/ThemeToggle';

const SkeletonCard = ({ className }) => (
  <div className={`bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border border-gold-light-border dark:border-gold-border rounded-2xl animate-pulse ${className}`} />
);

export default function ResultPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  
  const [result, setResult] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPublic, setIsPublic] = useState(false);
  const [shareUrl, setShareUrl] = useState(null);

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
        setIsPublic(data.isPublic ?? false);
        setShareUrl(data.shareUrl ?? null);

        // Fetch video URL separately — a 404 (deleted raw video) must not
        // block the transcript, summary, and all other result data.
        try {
          const freshVideoUrl = await getVideoUrl(jobId);
          setVideoUrl(freshVideoUrl);
        } catch (videoErr) {
          // 404 = raw video was deleted after processing (Phase 9 behaviour).
          // VideoPlayer.jsx renders "Video unavailable" when videoUrl is null.
          const status = videoErr?.response?.status;
          if (status === 404) {
            setVideoUrl(null);
          } else {
            // Non-404 errors (network, 5xx) — also degrade gracefully.
            console.warn("getVideoUrl failed:", videoErr);
            setVideoUrl(null);
          }
        }
      } catch (err) {
        console.error(err);
        setError("Failed to load result.");
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchResult();
  }, [jobId]);

  const handleShareToggle = useCallback((newValue) => {
    setIsPublic(newValue);
    // When toggled to public, construct the share URL; when private, clear it
    if (newValue) {
      setShareUrl(`${window.location.origin}/share/${jobId}`);
    } else {
      setShareUrl(null);
    }
  }, [jobId]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary text-gold-light-text-primary dark:text-gold-text-primary font-sans">
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
      <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary flex items-center justify-center">
        <div className="text-center max-w-md p-8 bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border border-gold-light-border dark:border-gold-border rounded-2xl">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-gold-light-text-primary dark:text-gold-text-primary mb-2">Failed to load results</h2>
          <p className="text-gold-light-text-secondary dark:text-gold-text-secondary text-sm mb-6">{error}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => navigate('/upload')}
              className="px-4 py-2 bg-gold-light-accent dark:bg-gold-accent hover:bg-gold-light-accent-hover dark:hover:bg-gold-accent-hover text-white rounded-xl text-sm transition-colors"
            >
              New Upload
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary hover:bg-gold-light-border dark:hover:bg-gold-border text-gold-light-text-secondary dark:text-gold-text-secondary rounded-xl text-sm transition-colors"
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
      <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary text-gold-light-text-primary dark:text-gold-text-primary font-sans flex flex-col">
        <NavHeader />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-[500px] bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border border-gold-light-border dark:border-gold-border rounded-3xl p-8 text-center">
            <h2 className="text-xl font-bold text-gold-light-accent dark:text-gold-accent mb-2">Analysis Not Complete</h2>
            <p className="text-gold-light-text-secondary dark:text-gold-text-secondary mb-8 mt-2 text-sm leading-relaxed">
              This job is not yet complete. Please check the status page.
            </p>
            <Link 
              to={`/status/${jobId}`}
              className="px-6 py-3 bg-gold-accent-muted hover:bg-gold-light-accent dark:hover:bg-gold-accent text-gold-light-accent dark:text-gold-accent hover:text-white rounded-xl font-medium transition-colors inline-block"
            >
              Go to Status
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary text-gold-light-text-primary dark:text-gold-text-primary font-sans flex flex-col overflow-hidden">
      <header className="border-b border-gold-light-border dark:border-gold-border px-6 py-4 flex flex-wrap items-center justify-between bg-gold-light-bg-primary dark:bg-gold-bg-primary shrink-0">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
             <span className="font-display text-gold-light-text-primary dark:text-gold-text-primary">VidIQ</span>
          </Link>
          <div className="hidden md:flex items-center gap-2 text-sm text-gold-light-text-secondary dark:text-gold-text-secondary border-l border-gold-light-border dark:border-gold-border pl-6">
            <span className="font-mono bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary px-2 py-1 rounded truncate max-w-[150px] sm:max-w-none">Job: {jobId}</span>
            {result?.processingTime && (
              <span>{" \u00B7 "} Processed in {formatDuration(result.processingTime)}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4">
          {user && result?.status === 'completed' && user.uid === result?.userId && (
            <div className="flex items-center gap-3">
              <ShareToggle jobId={jobId} isPublic={isPublic} onToggle={handleShareToggle} />
              <CopyLinkButton shareUrl={shareUrl} isPublic={isPublic} />
            </div>
          )}
          <Link to="/upload" className="hidden sm:flex items-center gap-2 text-sm text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-accent dark:hover:text-gold-accent transition-colors">
            <ArrowLeft className="w-4 h-4" /> New Upload
          </Link>
          <ThemeToggle />
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6 overflow-y-auto">
        <div className="max-w-[1600px] mx-auto flex flex-col gap-4 md:gap-6">
        <div className="flex flex-col md:flex-row gap-4 md:gap-6 md:items-start">

          {/* Left Column */}
          <div className="w-full md:w-1/2 flex flex-col gap-4 md:gap-6">
            <VideoPlayer
              videoUrl={videoUrl}
              scenes={result?.scenes ?? []}
              highlights={result?.highlights ?? []}
              currentTime={currentTime}
              seekTo={seekTo}
              onPlayerReady={handlePlayerReady}
            />
            <div>
              <SummaryCard
                summary={result?.summary}
                sentiment={result?.sentiment}
                chapters={result?.chapters ?? []}
                highlights={result?.highlights ?? []}
                actionItems={result?.actionItems ?? []}
                seekTo={seekTo}
                filenameBase={jobId}
              />
              <QAPanel jobId={jobId} onSeek={seekTo} />
            </div>
          </div>

          {/* Right Column */}
          <div className="w-full md:w-1/2 flex flex-col gap-4 md:gap-6">
            <TranscriptPanel
              transcript={result?.transcript ?? []}
              translatedTranscript={result?.translatedTranscript}
              detectedLanguage={result?.detectedLanguage}
              currentTime={currentTime}
              seekTo={seekTo}
              filenameBase={jobId}
            />
            <ScenePanel
              scenes={result?.scenes ?? []}
              labels={result?.labels ?? []}
              seekTo={seekTo}
              currentTime={currentTime}
            />
          </div>

        </div>

          {/* Processing Stats — collapsible, bottom */}
          <ProcessingStats result={result} />
        </div>
      </main>
    </div>
  );
}

function NavHeader() {
  return (
    <nav className="border-b border-gold-light-border dark:border-gold-border px-6 py-4 flex items-center justify-between bg-gold-light-bg-primary dark:bg-gold-bg-primary shrink-0">
      <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
        <span className="font-display text-gold-light-text-primary dark:text-gold-text-primary">VidIQ</span>
      </Link>
      <ThemeToggle />
    </nav>
  );
}