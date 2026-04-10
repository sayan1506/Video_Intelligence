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
    <div className="bg-dark-surface border border-dark-border rounded-2xl h-full flex flex-col min-h-0 relative">
      
      {/* Sticky Header with Label Badges */}
      <div className="sticky top-0 z-10 bg-dark-surface/90 backdrop-blur-md border-b border-dark-border p-4 rounded-t-2xl">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-bold text-white">Scene Analysis</h3>
          <span className="text-xs text-slate-500 font-medium">
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
          <p className="text-slate-500 italic text-sm text-center mt-6">No scene data available.</p>
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
                      ? 'bg-violet-500/10 border-l-2 border-violet-500 shadow-sm' 
                      : 'hover:bg-white/5 border-l-2 border-transparent'
                    }
                  `}
                >
                  {/* Scene number */}
                  <span className="text-xs font-mono text-slate-500 w-5 shrink-0 text-center">{i + 1}</span>

                  {/* Time range */}
                  <span className="text-xs font-mono text-violet-400 shrink-0 tabular-nums">
                    {formatTime(scene.startTime)} → {formatTime(scene.endTime)}
                  </span>

                  {/* Top Label chips for this scene */}
                  <div className="flex flex-wrap gap-1.5">
                    {scene.labels?.slice(0, 4).map((label, j) => (
                      <span key={j} className="text-[10px] px-1.5 py-0.5 rounded text-slate-300 bg-white/5 border border-white/10 group-hover:bg-white/10 transition-colors">
                        {label}
                      </span>
                    ))}
                    {scene.labels?.length > 4 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded text-slate-500 bg-transparent">
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
