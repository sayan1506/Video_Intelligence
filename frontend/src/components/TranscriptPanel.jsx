import { useState, useMemo, useRef, useEffect } from 'react';
import { Search, FileX, Download } from 'lucide-react';
import { exportSrt, exportVtt } from '../lib/exporters.js';

const isActiveWord = (wordObj, currentTime) => {
  return currentTime >= wordObj.startTime && currentTime <= wordObj.endTime;
};

export default function TranscriptPanel({ transcript, translatedTranscript, detectedLanguage = null, currentTime, seekTo, filenameBase = 'transcript', hideExports = false }) {
  const [query, setQuery] = useState('');
  const [activeView, setActiveView] = useState('original'); // 'original' | 'english'
  const activeWordRef = useRef(null);
  const scrollContainerRef = useRef(null);

  const showToggle = translatedTranscript != null && translatedTranscript.length > 0;

  // Switch displayed transcript based on active view
  const displayedTranscript = activeView === 'english' && showToggle
    ? translatedTranscript
    : transcript;

  // Clear search query when user switches between views
  useEffect(() => {
    setQuery('');
  }, [activeView]);

  const SPEAKER_COLORS = [
    '',                        // 0 = unknown / chunked path — no colour
    'text-violet-400',         // Speaker 1
    'text-emerald-400',        // Speaker 2
    'text-amber-400',          // Speaker 3
    'text-sky-400',            // Speaker 4
    'text-rose-400',           // Speaker 5
    'text-orange-400',         // Speaker 6
  ];

  const filteredTranscriptIds = useMemo(() => {
    if (!query) return null; // null means no search is active
    const lowerQuery = query.toLowerCase();
    const matches = new Set();
    displayedTranscript.forEach((w, i) => {
      if (w.word.toLowerCase().includes(lowerQuery)) {
        matches.add(i);
      }
    });
    return matches;
  }, [displayedTranscript, query]);

  useEffect(() => {
    if (!activeWordRef.current || !scrollContainerRef.current) return;
    
    const container = scrollContainerRef.current;
    const word = activeWordRef.current;
    
    const containerTop = container.scrollTop;
    const containerBottom = containerTop + container.clientHeight;
    const wordTop = word.offsetTop;
    const wordBottom = wordTop + word.offsetHeight;
    
    // Only scroll if word is outside visible area
    if (wordTop < containerTop || wordBottom > containerBottom) {
      container.scrollTop = wordTop - container.clientHeight / 2;
    }
  }, [currentTime]);

  const isEmpty = !displayedTranscript || displayedTranscript.length === 0;

  return (
    <div className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border-t-2 border-t-gold-light-accent dark:border-t-gold-accent border border-gold-light-border dark:border-gold-border rounded-lg h-full flex flex-col min-h-0 relative">
      
      {/* Sticky Header */}
      <div className="sticky top-0 z-10 bg-gold-light-bg-secondary/90 dark:bg-gold-bg-secondary/90 backdrop-blur-md border-b border-gold-light-border dark:border-gold-border p-4 rounded-t-lg flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gold-light-text-muted dark:text-gold-text-muted" />
          <input 
            type="text"
            placeholder="Search transcript..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded-lg pl-10 pr-4 py-2 text-sm text-gold-light-text-primary dark:text-gold-text-primary placeholder:text-gold-light-text-muted dark:placeholder:text-gold-text-muted focus:outline-none focus:border-gold-light-accent dark:focus:border-gold-accent focus:ring-1 focus:ring-gold-light-accent dark:focus:ring-gold-accent transition-all font-sans"
          />
        </div>
        {showToggle && (
          <div className="flex items-center bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded-lg p-0.5">
            <button
              onClick={() => setActiveView('original')}
              title={`Show original${detectedLanguage ? ` (${detectedLanguage})` : ''}`}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                activeView === 'original'
                  ? 'bg-gold-light-accent dark:bg-gold-accent text-white shadow-sm'
                  : 'text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-text-primary dark:hover:text-gold-text-primary'
              }`}
            >
              Original
            </button>
            <button
              onClick={() => setActiveView('english')}
              title="Show English translation"
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                activeView === 'english'
                  ? 'bg-gold-light-accent dark:bg-gold-accent text-white shadow-sm'
                  : 'text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-text-primary dark:hover:text-gold-text-primary'
              }`}
            >
              English
            </button>
          </div>
        )}
        <div className="text-xs text-gold-light-text-muted dark:text-gold-text-muted font-medium whitespace-nowrap">
          {displayedTranscript?.length || 0} words
        </div>
        {!hideExports && displayedTranscript && displayedTranscript.length > 0 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => exportSrt(displayedTranscript, filenameBase)}
              title="Download SRT subtitles"
              className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-text-primary dark:hover:text-gold-text-primary bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary hover:bg-gold-light-border dark:hover:bg-gold-border border border-gold-light-border dark:border-gold-border rounded-md transition-colors"
            >
              <Download className="w-3 h-3" />
              SRT
            </button>
            <button
              onClick={() => exportVtt(displayedTranscript, filenameBase)}
              title="Download VTT subtitles"
              className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-text-primary dark:hover:text-gold-text-primary bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary hover:bg-gold-light-border dark:hover:bg-gold-border border border-gold-light-border dark:border-gold-border rounded-md transition-colors"
            >
              <Download className="w-3 h-3" />
              VTT
            </button>
          </div>
        )}
      </div>

      {/* Transcript Text Flow */}
      <div ref={scrollContainerRef} className="p-5 overflow-y-auto relative flex-1 custom-scrollbar">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-64 text-gold-light-text-muted dark:text-gold-text-muted">
            <FileX className="w-10 h-10 mb-3 opacity-50" />
            <p className="text-sm">No transcript available.</p>
            <p className="text-xs mt-1 text-gold-light-text-muted dark:text-gold-text-muted">Audio may not have been detected.</p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-x-1 gap-y-1 content-start font-sans leading-relaxed">
            {displayedTranscript.map((wordObj, i) => {
              const isActive = isActiveWord(wordObj, currentTime);
              const isSearchMatch = filteredTranscriptIds && filteredTranscriptIds.has(i);
              const prevWord = i > 0 ? displayedTranscript[i - 1] : null;
              const speakerChanged = wordObj.speaker > 0 && (!prevWord || prevWord.speaker !== wordObj.speaker);

              return (
                <span key={i}>
                  {speakerChanged && (
                    <span className={`basis-full block text-xs font-semibold mt-3 mb-1 ${SPEAKER_COLORS[wordObj.speaker] || 'text-slate-400'}`}>
                      Speaker {wordObj.speaker}
                    </span>
                  )}
                  <span
                    ref={isActive ? activeWordRef : null}
                    onClick={() => seekTo(wordObj.startTime)}
                    className={`
                      cursor-pointer rounded px-0.5 py-0.5 text-sm transition-colors duration-150 inline-block
                      ${isActive
                        ? 'bg-gold-light-accent dark:bg-gold-accent text-white font-medium shadow-sm'
                        : isSearchMatch
                        ? 'bg-amber-500/40 text-amber-100 font-medium'
                        : wordObj.speaker > 0
                        ? `${SPEAKER_COLORS[wordObj.speaker] || ''} hover:bg-gold-light-border dark:hover:bg-gold-border`
                        : 'text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-text-primary dark:hover:text-gold-text-primary hover:bg-gold-light-border dark:hover:bg-gold-border'
                      }
                    `}
                  >
                    {wordObj.word}
                  </span>
                </span>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}
