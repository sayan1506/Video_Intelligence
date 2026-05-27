import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Zap, AlertTriangle, FileQuestion, LogIn } from 'lucide-react';
import { getResult, getVideoUrl } from '../services/api';

import VideoPlayer from '../components/VideoPlayer';
import SummaryCard from '../components/SummaryCard';
import TranscriptPanel from '../components/TranscriptPanel';
import ScenePanel from '../components/ScenePanel';

const FETCH_TIMEOUT_MS = 30000;

const SkeletonCard = ({ className }) => (
  <div className={`bg-white/5 border border-white/10 rounded-2xl animate-pulse ${className}`} />
);

export default function SharePage() {
  const { jobId } = useParams();

  const [result, setResult] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);
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

  useEffect(() => {
    if (!jobId) return;

    const controller = new AbortController();
    let timeoutId;

    const fetchData = async () => {
      try {
        // Set up a 30s timeout
        const timeoutPromise = new Promise((_, reject) => {
          timeoutId = setTimeout(() => {
            controller.abort();
            reject(new Error('Request timed out'));
          }, FETCH_TIMEOUT_MS);
        });

        const dataPromise = Promise.all([
          getResult(jobId),
          getVideoUrl(jobId),
        ]);

        const [data, freshVideoUrl] = await Promise.race([dataPromise, timeoutPromise]);

        clearTimeout(timeoutId);
        setResult(data);
        setVideoUrl(freshVideoUrl);
      } catch (err) {
        clearTimeout(timeoutId);

        if (err?.response?.status === 404) {
          setNotFound(true);
        } else if (err.message === 'Request timed out') {
          setError('The request timed out. Please try again later.');
        } else {
          setError('Could not load the shared content. Please try again later.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [jobId]);

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-dark-base text-slate-100 font-sans">
        <ShareNavHeader />
        <div className="flex items-center justify-center py-8">
          <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-slate-400 text-sm">Loading shared content...</p>
          </div>
        </div>
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

  // 404 Not Found state
  if (notFound) {
    return (
      <div className="min-h-screen bg-dark-base text-slate-100 font-sans flex flex-col">
        <ShareNavHeader />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="text-center max-w-md p-8 bg-white/5 border border-white/10 rounded-2xl">
            <FileQuestion className="w-12 h-12 text-slate-400 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-slate-100 mb-2">Not Found</h2>
            <p className="text-slate-400 text-sm mb-6">
              This shared content is no longer available or does not exist.
            </p>
            <Link
              to="/"
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-sm transition-colors inline-block"
            >
              Go to Home
            </Link>
          </div>
        </main>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-dark-base text-slate-100 font-sans flex flex-col">
        <ShareNavHeader />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="text-center max-w-md p-8 bg-white/5 border border-white/10 rounded-2xl">
            <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-slate-100 mb-2">Failed to load content</h2>
            <p className="text-slate-400 text-sm mb-6">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-sm transition-colors"
            >
              Retry
            </button>
          </div>
        </main>
      </div>
    );
  }

  // Success — render read-only content
  return (
    <div className="min-h-screen bg-dark-base text-slate-100 font-sans flex flex-col overflow-hidden">
      <ShareNavHeader />

      <main className="flex-1 p-4 md:p-6 overflow-y-auto">
        <div className="max-w-[1600px] mx-auto h-full flex flex-col gap-4 md:gap-6">
          <div className="flex flex-col md:flex-row gap-4 md:gap-6 flex-1 min-h-0">

            {/* Left Column */}
            <div className="w-full md:w-1/2 flex flex-col gap-4 md:gap-6 min-h-0">
              <div className="flex-[0_0_auto]">
                <VideoPlayer
                  videoUrl={videoUrl}
                  scenes={result?.scenes ?? []}
                  highlights={result?.highlights ?? []}
                  currentTime={currentTime}
                  seekTo={seekTo}
                  onPlayerReady={handlePlayerReady}
                />
              </div>
              <div className="flex-[1_1_auto] overflow-hidden">
                <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
                  {result?.summary !== null && result?.summary !== undefined && (
                    <SummaryCard
                      summary={result.summary}
                      sentiment={result?.sentiment}
                      chapters={result?.chapters ?? []}
                      highlights={result?.highlights ?? []}
                      actionItems={result?.actionItems ?? []}
                      seekTo={seekTo}
                      hideExports
                    />
                  )}
                </div>
              </div>
            </div>

            {/* Right Column */}
            <div className="w-full md:w-1/2 flex flex-col gap-4 md:gap-6 min-h-0">
              {result?.transcript !== null && result?.transcript !== undefined && (
                <div className="flex-[1_1_auto] h-1/2 overflow-hidden">
                  <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
                    <TranscriptPanel
                      transcript={result.transcript}
                      translatedTranscript={result?.translatedTranscript}
                      currentTime={currentTime}
                      seekTo={seekTo}
                      hideExports
                    />
                  </div>
                </div>
              )}
              {result?.scenes !== null && result?.scenes !== undefined && (
                <div className="flex-[1_1_auto] h-1/2 overflow-hidden">
                  <div className="h-full overflow-y-auto pr-2 custom-scrollbar">
                    <ScenePanel
                      scenes={result.scenes}
                      labels={result?.labels ?? []}
                      seekTo={seekTo}
                      currentTime={currentTime}
                    />
                  </div>
                </div>
              )}
            </div>

          </div>

          {/* CTA — Sign in to analyse your own videos */}
          <div className="border-t border-white/10 pt-6 pb-4 text-center">
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-6 py-3 bg-violet-600 hover:bg-violet-500 text-white rounded-xl font-medium transition-colors"
            >
              <LogIn className="w-4 h-4" />
              Sign in to analyse your own videos
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

function ShareNavHeader() {
  return (
    <nav className="border-b border-white/5 px-6 py-4 flex items-center justify-between bg-dark-base shrink-0">
      <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
        <Zap className="w-6 h-6 text-violet-500" fill="currentColor" />
        <span>VidIQ</span>
      </Link>
      <Link
        to="/"
        className="text-sm text-slate-400 hover:text-white transition-colors"
      >
        Sign in
      </Link>
    </nav>
  );
}
