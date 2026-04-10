import { BookOpen, Star, CheckSquare } from 'lucide-react';

const formatTime = (seconds) => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const sentimentConfig = {
  positive: { label: 'Positive', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
  neutral:  { label: 'Neutral',  color: 'bg-slate-500/20 text-slate-400 border-slate-500/30' },
  negative: { label: 'Negative', color: 'bg-red-500/20 text-red-400 border-red-500/30' },
};

export default function SummaryCard({ summary, sentiment, chapters, highlights, actionItems, seekTo }) {
  const badge = sentimentConfig[sentiment ?? 'neutral'];

  return (
    <div className="bg-dark-surface border border-dark-border rounded-2xl p-6 flex flex-col gap-6">
      
      {/* Sentiment Badge */}
      <div className="flex items-start">
        <span className={`px-3 py-1 rounded-full text-xs font-medium border ${badge.color}`}>
          Sentiment: {badge.label}
        </span>
      </div>

      {/* Summary Paragraph */}
      <div>
        <h3 className="text-lg font-bold mb-2">Summary</h3>
        {summary ? (
          <p className="text-slate-300 leading-relaxed text-sm">{summary}</p>
        ) : (
          <p className="text-slate-500 italic text-sm">No summary available</p>
        )}
      </div>

      {/* Chapters (if any) */}
      {chapters && chapters.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-5 h-5 text-violet-400" />
            <h3 className="text-lg font-bold">Chapters</h3>
          </div>
          <div className="flex flex-col gap-2">
            {chapters.map((chapter, i) => (
              <button
                key={i}
                onClick={() => seekTo(chapter.startTime)}
                className="flex items-center gap-4 p-3 rounded-lg bg-white/5 hover:bg-white/10 hover:border-l-2 hover:border-violet-500 transition-all text-left group border border-transparent"
              >
                <span className="font-mono text-sm text-violet-400 group-hover:text-violet-300 shrink-0">
                  {formatTime(chapter.startTime)}
                </span>
                <span className="text-sm font-medium text-slate-200">{chapter.title}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Highlights (if any) */}
      {highlights && highlights.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Star className="w-5 h-5 text-amber-400" />
            <h3 className="text-lg font-bold">Key Highlights</h3>
          </div>
          <div className="flex flex-col gap-3">
            {highlights.map((highlight, i) => (
              <div 
                key={i}
                onClick={() => seekTo(highlight.timestamp)}
                className="flex items-start gap-4 p-3 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
              >
                <span className="shrink-0 mt-0.5 px-2 py-1 rounded-md bg-amber-500/20 text-amber-300 text-xs font-mono">
                  {formatTime(highlight.timestamp)}
                </span>
                <p className="text-sm text-slate-300 leading-relaxed">{highlight.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Items (if any) */}
      {actionItems && actionItems.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <CheckSquare className="w-5 h-5 text-emerald-400" />
            <h3 className="text-lg font-bold">Action Items</h3>
          </div>
          <ul className="list-disc list-inside flex flex-col gap-2 text-sm text-slate-300 pl-1">
            {actionItems.map((item, i) => (
              <li key={i} className="leading-relaxed">{item}</li>
            ))}
          </ul>
        </div>
      )}

    </div>
  );
}
