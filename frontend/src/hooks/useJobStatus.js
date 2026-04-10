import { useState, useEffect } from 'react';
import { getStatus } from '../services/api';

export default function useJobStatus(jobId) {
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(null);
  const [stage, setStage] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!jobId) return;

    let isMounted = true;
    let pollInterval = null;

    const fetchStatus = async () => {
      try {
        const data = await getStatus(jobId);
        if (isMounted) {
          setStatus(data.status);
          setProgress(data.progress);
          setStage(data.stage);
          setVideoUrl(data.videoUrl);
          setIsLoading(false);

          if (data.status === 'completed' || data.status === 'failed') {
            if (pollInterval) clearInterval(pollInterval);
          }
        }
      } catch (err) {
        if (isMounted) {
          if (err.response && err.response.status === 404) {
             setError("Job not found");
          } else {
             setError("Failed to fetch status");
          }
          setIsLoading(false);
          if (pollInterval) clearInterval(pollInterval);
        }
      }
    };

    // Initial fetch immediately
    fetchStatus();

    const intervalMs = parseInt(import.meta.env.VITE_POLL_INTERVAL_MS) || 3000;
    
    pollInterval = setInterval(fetchStatus, intervalMs);

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [jobId]);

  return { status, progress, stage, videoUrl, error, isLoading };
}
