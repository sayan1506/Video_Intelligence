import { useEffect, useRef, useState } from 'react';
import videojs from 'video.js';
import 'video.js/dist/video-js.css';

export default function VideoPlayer({ videoUrl, scenes, highlights, currentTime, seekTo, onPlayerReady }) {
  const videoRef = useRef(null);
  const playerRef = useRef(null);
  const [duration, setDuration] = useState(0);
  console.log('VideoPlayer render — videoUrl:', videoUrl);
  useEffect(() => {
    // Wait for next tick to ensure DOM element is fully mounted
    const timer = setTimeout(() => {
      if (playerRef.current) return;
      if (!videoRef.current) return;

      const player = videojs(videoRef.current, {
        controls: true,
        fluid: true,
        preload: 'auto',
        aspectRatio: '16:9',
        sources: [{ src: videoUrl, type: 'video/mp4' }],
      });

      playerRef.current = player;

      player.on('loadedmetadata', () => {
        setDuration(player.duration());
      });

      if (onPlayerReady) onPlayerReady(player);
    }, 0);

    return () => {
      clearTimeout(timer);
      if (playerRef.current && !playerRef.current.isDisposed()) {
        playerRef.current.dispose();
        playerRef.current = null;
      }
    };
  }, [videoUrl]);

  return (
    <div className="bg-dark-surface border border-dark-border rounded-2xl p-4 md:p-6 w-full">
      <div data-vjs-player className="w-full aspect-video">
        <video ref={videoRef} className="video-js vjs-big-play-centered rounded-lg overflow-hidden" />
      </div>
      
      {/* Custom Timeline Bar */}
      <div className="relative h-8 bg-white/5 rounded-full mt-3 overflow-hidden">
        {/* Playhead progress */}
        <div
          className="absolute top-0 left-0 h-full bg-violet-500/20 transition-all duration-100"
          style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
        />
        {/* Scene boundary ticks */}
        {scenes?.map((scene, i) => (
          <div
            key={i}
            className="absolute top-0 w-0.5 h-full bg-violet-400/60 cursor-pointer hover:bg-violet-300 transition-colors"
            style={{ left: `${duration ? (scene.startTime / duration) * 100 : 0}%` }}
            onClick={() => seekTo(scene.startTime)}
            title={scene.labels?.[0] ?? `Scene ${i + 1}`}
          />
        ))}
        {/* Highlight dots */}
        {highlights?.map((h, i) => (
          <div
            key={i}
            className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-amber-400 cursor-pointer hover:scale-150 transition-transform"
            style={{ left: `${duration ? (h.timestamp / duration) * 100 : 0}%` }}
            onClick={() => seekTo(h.timestamp)}
            title={h.description}
          />
        ))}
      </div>
    </div>
  );
}
