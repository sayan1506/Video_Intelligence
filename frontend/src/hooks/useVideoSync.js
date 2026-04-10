import { useState, useEffect } from 'react';

export default function useVideoSync(playerRef) {
  const [currentTime, setCurrentTime] = useState(0);

  useEffect(() => {
    const player = playerRef.current;
    if (!player) return;

    const handleTimeUpdate = () => {
      setCurrentTime(player.currentTime());
    };

    player.on("timeupdate", handleTimeUpdate);

    return () => {
      player.off("timeupdate", handleTimeUpdate);
    };
  }, [playerRef]);

  return currentTime;
}
