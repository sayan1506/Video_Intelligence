import { BookOpen, Star, CheckSquare, FileDown } from 'lucide-react';
import { exportPdf } from '../lib/exporters.js';

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

export default function SummaryCard({ summary, sentiment, chapters, highlights, actionItems, seekTo, filenameBase = 'summary', hideExports = false }) {
  const badge = sentimentConfig[sentiment ?? 'neutral'];

  return (
    <div className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border-t-2 border-t-gold-light-accent dark:border-t-gold-accent border border-gold-light-border dark:border-gold-border rounded-lg p-6 flex flex-col gap-6">
      
      {/* Sentiment Badge */}
      <div className="flex items-center justify-between">
        <span className={`px-3 py-1 rounded-full text-xs font-medium border ${badge.color}`}>
          Sentiment: {badge.label}
        </span>
        {!hideExports && summary && summary.length > 0 && (
          <button
            title="Export PDF summary"
            onClick={() => exportPdf({ summary, chapters, highlights, actionItems, sentiment }, filenameBase)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-text-primary dark:hover:text-gold-text-primary bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary hover:bg-gold-light-border dark:hover:bg-gold-border border border-gold-light-border dark:border-gold-border hover:border-gold-light-accent dark:hover:border-gold-accent transition-all"
          >
            <FileDown className="w-4 h-4" />
            Export PDF
          </button>
        )}
      </div>

      {/* Summary Paragraph */}
      <div>
        <h3 className="text-lg font-bold mb-2 text-gold-light-text-primary dark:text-gold-text-primary">Summary</h3>
        {summary ? (
          <p className="text-gold-light-text-secondary dark:text-gold-text-secondary leading-relaxed text-sm">{summary}</p>
        ) : (
          <p className="text-gold-light-text-muted dark:text-gold-text-muted italic text-sm">No summary available.</p>
        )}
      </div>

      {/* Chapters */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <BookOpen className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />
          <h3 className="text-lg font-bold text-gold-light-text-primary dark:text-gold-text-primary">Chapters</h3>
        </div>
        {chapters && chapters.length > 0 ? (
          <div className="flex flex-col gap-2">
            {chapters.map((chapter, i) => (
              <button
                key={i}
                onClick={() => seekTo(chapter.startTime)}
                className="flex items-center gap-4 p-3 rounded-lg bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary hover:bg-gold-light-border dark:hover:bg-gold-border hover:border-l-2 hover:border-gold-light-accent dark:hover:border-gold-accent transition-all text-left group border border-transparent"
              >
                <span className="font-mono text-sm text-gold-light-accent dark:text-gold-accent group-hover:text-gold-light-accent-hover dark:group-hover:text-gold-accent-hover shrink-0">
                  {formatTime(chapter.startTime)}
                </span>
                <span className="text-sm font-medium text-gold-light-text-primary dark:text-gold-text-primary">{chapter.title}</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="text-gold-light-text-muted dark:text-gold-text-muted text-sm">No chapters detected.</p>
        )}
      </div>

      {/* Highlights */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Star className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />
          <h3 className="text-lg font-bold text-gold-light-text-primary dark:text-gold-text-primary">Key Highlights</h3>
        </div>
        {highlights && highlights.length > 0 ? (
          <div className="flex flex-col gap-3">
            {highlights.map((highlight, i) => (
              <div 
                key={i}
                onClick={() => seekTo(highlight.timestamp)}
                className="flex items-start gap-4 p-3 rounded-lg hover:bg-gold-light-bg-tertiary dark:hover:bg-gold-bg-tertiary transition-colors cursor-pointer"
              >
              <span className="shrink-0 mt-0.5 px-2 py-1 rounded-md bg-gold-accent-muted text-gold-light-accent dark:text-gold-accent text-xs font-mono">
                {formatTime(highlight.timestamp)}
              </span>
              <p className="text-sm text-gold-light-text-secondary dark:text-gold-text-secondary leading-relaxed">{highlight.description}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gold-light-text-muted dark:text-gold-text-muted text-sm">No highlights detected.</p>
        )}
      </div>

      {/* Action Items (only render if non-empty) */}
      {actionItems && actionItems.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <CheckSquare className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />
            <h3 className="text-lg font-bold text-gold-light-text-primary dark:text-gold-text-primary">Action Items</h3>
          </div>
          <ul className="list-disc list-inside flex flex-col gap-2 text-sm text-gold-light-text-secondary dark:text-gold-text-secondary pl-1">
            {actionItems.map((item, i) => (
              <li key={i} className="leading-relaxed">{item}</li>
            ))}
          </ul>
        </div>
      )}

    </div>
  );
}
