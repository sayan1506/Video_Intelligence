import { useState, useMemo, useRef, useEffect } from 'react';
import { Search, FileX, Download } from 'lucide-react';
import { exportSrt, exportVtt } from '../lib/exporters.js';

const isActiveWord = (wordObj, currentTime) => {
  return currentTime >= wordObj.startTime && currentTime <= wordObj.endTime;
};

export default function TranscriptPanel({ transcript, currentTime, seekTo, filenameBase = 'transcript' }) {
  const [query, setQuery] = useState('');
  const activeWordRef = useRef(null);
  const scrollContainerRef = useRef(null);

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
    transcript.forEach((w, i) => {
      if (w.word.toLowerCase().includes(lowerQuery)) {
        matches.add(i);
      }
    });
    return matches;
  }, [transcript, query]);

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

  const isEmpty = !transcript || transcript.length === 0;

  return (
    <div className="bg-dark-surface border border-dark-border rounded-2xl h-full flex flex-col min-h-0 relative">
      
      {/* Sticky Header */}
      <div className="sticky top-0 z-10 bg-dark-surface/90 backdrop-blur-md border-b border-dark-border p-4 rounded-t-2xl flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text"
            placeholder="Search transcript..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-black/40 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all font-sans"
          />
        </div>
        <div className="text-xs text-slate-500 font-medium whitespace-nowrap">
          {transcript?.length || 0} words
        </div>
        {transcript && transcript.length > 0 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => exportSrt(transcript, filenameBase)}
              title="Download SRT subtitles"
              className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-slate-400 hover:text-white bg-black/30 hover:bg-white/10 border border-white/10 rounded-md transition-colors"
            >
              <Download className="w-3 h-3" />
              SRT
            </button>
            <button
              onClick={() => exportVtt(transcript, filenameBase)}
              title="Download VTT subtitles"
              className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-slate-400 hover:text-white bg-black/30 hover:bg-white/10 border border-white/10 rounded-md transition-colors"
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
          <div className="flex flex-col items-center justify-center h-64 text-slate-500">
            <FileX className="w-10 h-10 mb-3 opacity-50" />
            <p className="text-sm">No transcript available.</p>
            <p className="text-xs mt-1 text-slate-600">Audio may not have been detected.</p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-x-1 gap-y-1 content-start font-sans leading-relaxed">
            {transcript.map((wordObj, i) => {
              const isActive = isActiveWord(wordObj, currentTime);
              const isSearchMatch = filteredTranscriptIds && filteredTranscriptIds.has(i);
              const prevWord = i > 0 ? transcript[i - 1] : null;
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
                        ? 'bg-violet-500/80 text-white font-medium shadow-sm'
                        : isSearchMatch
                        ? 'bg-amber-500/40 text-amber-100 font-medium'
                        : wordObj.speaker > 0
                        ? `${SPEAKER_COLORS[wordObj.speaker] || ''} hover:bg-white/10`
                        : 'text-slate-300 hover:text-white hover:bg-white/10'
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
