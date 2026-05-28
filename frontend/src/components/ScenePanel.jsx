import { Film } from 'lucide-react';

const formatTime = (seconds) => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const chipColors = [
  'bg-violet-500/20 text-violet-300 border-violet-500/30',
  'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  'bg-amber-500/20 text-amber-300 border-amber-500/30',
];

const isActiveScene = (scene, currentTime) => {
  return currentTime >= scene.startTime && currentTime <= scene.endTime;
};

export default function ScenePanel({ scenes, labels, seekTo, currentTime }) {
  const hasScenes = scenes && scenes.length > 0;
  
  return (
    <div className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border-t-2 border-t-gold-light-accent dark:border-t-gold-accent border border-gold-light-border dark:border-gold-border rounded-lg h-full flex flex-col min-h-0 relative">
      
      {/* Sticky Header with Label Badges */}
      <div className="sticky top-0 z-10 bg-gold-light-bg-secondary/90 dark:bg-gold-bg-secondary/90 backdrop-blur-md border-b border-gold-light-border dark:border-gold-border p-4 rounded-t-lg">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-bold text-gold-light-text-primary dark:text-gold-text-primary">Scene Analysis</h3>
          <span className="text-xs text-gold-light-text-muted dark:text-gold-text-muted font-medium">
            {scenes?.length || 0} scenes · {labels?.length || 0} labels
          </span>
        </div>
        
        <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto custom-scrollbar pr-2">
          {labels?.map((label, i) => {
            const colorClass = chipColors[i % chipColors.length];
            return (
              <span 
                key={i} 
                className={`text-[10px] px-2 py-0.5 rounded-full border ${colorClass} uppercase tracking-wider font-semibold shadow-sm`}
              >
                {label}
              </span>
            );
          })}
        </div>
      </div>

      {/* Scene List scrollable content */}
      <div className="p-3 overflow-y-auto flex-1 custom-scrollbar">
        {!hasScenes ? (
          <div className="flex flex-col items-center justify-center h-48 text-gold-light-text-muted dark:text-gold-text-muted">
            <Film className="w-10 h-10 mb-3 opacity-50" />
            <p className="text-sm">No scenes detected.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {scenes.map((scene, i) => {
              const active = isActiveScene(scene, currentTime);
              return (
                <div
                  key={i}
                  onClick={() => seekTo(scene.startTime)}
                  className={`
                    flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all group
                    ${active 
                      ? 'bg-gold-accent-muted border-l-2 border-gold-light-accent dark:border-gold-accent shadow-sm' 
                      : 'hover:bg-gold-light-bg-tertiary dark:hover:bg-gold-bg-tertiary border-l-2 border-transparent'
                    }
                  `}
                >
                  {/* Scene number */}
                  <span className="text-xs font-mono text-gold-light-text-muted dark:text-gold-text-muted w-5 shrink-0 text-center">{i + 1}</span>

                  {/* Time range */}
                  <span className="text-xs font-mono text-gold-light-accent dark:text-gold-accent shrink-0 tabular-nums">
                    {formatTime(scene.startTime)} → {formatTime(scene.endTime)}
                  </span>

                  {/* Top Label chips for this scene */}
                  <div className="flex flex-wrap gap-1.5">
                    {scene.labels?.slice(0, 4).map((label, j) => (
                      <span key={j} className="text-[10px] px-1.5 py-0.5 rounded text-gold-light-text-secondary dark:text-gold-text-secondary bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border group-hover:bg-gold-light-border dark:group-hover:bg-gold-border transition-colors">
                        {label}
                      </span>
                    ))}
                    {scene.labels?.length > 4 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded text-gold-light-text-muted dark:text-gold-text-muted bg-transparent">
                        +{scene.labels.length - 4}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}
