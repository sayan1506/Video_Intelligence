import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import fc from 'fast-check';
import { formatSrtTimecode, formatVttTimecode, groupWordsToCues, generateSrtContent, generateVttContent, downloadTextFile, exportSrt, exportVtt, exportPdf } from './exporters.js';

/**
 * Property 6: Timecode formatting round-trip
 * Validates: Requirements 5.1, 5.2, 5.3
 *
 * For any non-negative numeric time value, formatting it as an SRT timecode
 * (HH:MM:SS,mmm) or VTT timecode (HH:MM:SS.mmm) and then parsing the resulting
 * string back to seconds SHALL yield the original value within a 1-millisecond tolerance.
 */

/**
 * Parses an SRT timecode string (HH:MM:SS,mmm) back to seconds.
 */
function parseSrtTimecode(timecode) {
  const [timePart, msPart] = timecode.split(',');
  const [h, m, s] = timePart.split(':').map(Number);
  const ms = Number(msPart);
  return h * 3600 + m * 60 + s + ms / 1000;
}

/**
 * Parses a VTT timecode string (HH:MM:SS.mmm) back to seconds.
 */
function parseVttTimecode(timecode) {
  const [timePart, msPart] = timecode.split('.');
  const [h, m, s] = timePart.split(':').map(Number);
  const ms = Number(msPart);
  return h * 3600 + m * 60 + s + ms / 1000;
}

describe('Property 6: Timecode formatting round-trip', () => {
  it('SRT timecode format→parse round-trip yields original value within 1ms tolerance', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0, max: 86400, noNaN: true }),
        (seconds) => {
          const formatted = formatSrtTimecode(seconds);
          const parsed = parseSrtTimecode(formatted);
          expect(Math.abs(parsed - seconds)).toBeLessThanOrEqual(0.001);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('VTT timecode format→parse round-trip yields original value within 1ms tolerance', () => {
    fc.assert(
      fc.property(
        fc.double({ min: 0, max: 86400, noNaN: true }),
        (seconds) => {
          const formatted = formatVttTimecode(seconds);
          const parsed = parseVttTimecode(formatted);
          expect(Math.abs(parsed - seconds)).toBeLessThanOrEqual(0.001);
        }
      ),
      { numRuns: 100 }
    );
  });
});


/**
 * Property 1: Cue word count invariant
 * Validates: Requirements 4.1, 1.2
 *
 * For any valid non-empty WordTimestamp array, every Cue produced by the
 * Cue_Grouping_Algorithm SHALL contain between 1 and 10 words (inclusive).
 */

/**
 * Generator for a valid ordered WordTimestamp array (Property 1).
 * Each word has: { word: string, startTime: number, endTime: number, speaker: number }
 * Words are ordered: each word's startTime >= previous word's endTime
 * endTime >= startTime for each word
 */
function arbitraryWordTimestampArrayP1(minLen = 1, maxLen = 50) {
  return fc.integer({ min: minLen, max: maxLen }).chain((len) =>
    fc.array(
      fc.record({
        duration: fc.double({ min: 0.01, max: 5.0, noNaN: true }),
        gap: fc.double({ min: 0, max: 5.0, noNaN: true }),
        word: fc.stringMatching(/^[a-z]{1,10}$/),
        speaker: fc.integer({ min: 0, max: 5 }),
      }),
      { minLength: len, maxLength: len }
    ).map((items) => {
      let currentTime = 0;
      return items.map((item) => {
        const startTime = currentTime + item.gap;
        const endTime = startTime + item.duration;
        currentTime = endTime;
        return {
          word: item.word || 'w',
          startTime,
          endTime,
          speaker: item.speaker,
        };
      });
    })
  );
}

describe('Property 1: Cue word count invariant', () => {
  it('every cue contains between 1 and 10 words inclusive for any valid WordTimestamp array', () => {
    fc.assert(
      fc.property(
        arbitraryWordTimestampArrayP1(1, 50),
        (words) => {
          const cues = groupWordsToCues(words);
          expect(cues.length).toBeGreaterThanOrEqual(1);
          for (const cue of cues) {
            expect(cue.words.length).toBeGreaterThanOrEqual(1);
            expect(cue.words.length).toBeLessThanOrEqual(10);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Property 2: Cue timing correctness
 * Validates: Requirements 4.2
 *
 * For any valid non-empty WordTimestamp array, every Cue produced by the
 * Cue_Grouping_Algorithm SHALL have its startTime equal to the first word's
 * startTime and its endTime equal to the last word's endTime within that Cue.
 */

/**
 * Generates a non-empty array of valid WordTimestamp objects where words are
 * ordered (each word's startTime >= previous word's endTime, endTime >= startTime).
 */
function arbitraryWordTimestampArrayP2(minLen = 1, maxLen = 50) {
  return fc.integer({ min: minLen, max: maxLen }).chain((len) =>
    fc.array(
      fc.record({
        duration: fc.double({ min: 0.01, max: 5.0, noNaN: true }),
        gap: fc.double({ min: 0, max: 5.0, noNaN: true }),
        word: fc.stringMatching(/^[a-z]{1,10}$/),
        speaker: fc.integer({ min: 0, max: 5 }),
      }),
      { minLength: len, maxLength: len }
    ).map((items) => {
      let currentTime = 0;
      return items.map((item) => {
        const startTime = currentTime + item.gap;
        const endTime = startTime + item.duration;
        currentTime = endTime;
        return {
          word: item.word || 'w',
          startTime,
          endTime,
          speaker: item.speaker,
        };
      });
    })
  );
}

describe('Property 2: Cue timing correctness', () => {
  it('each cue startTime equals its first word startTime and endTime equals its last word endTime', () => {
    fc.assert(
      fc.property(
        arbitraryWordTimestampArrayP2(1, 50),
        (words) => {
          const cues = groupWordsToCues(words);
          for (const cue of cues) {
            expect(cue.startTime).toBe(cue.words[0].startTime);
            expect(cue.endTime).toBe(cue.words[cue.words.length - 1].endTime);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Property 3: Word conservation and order preservation
 * Validates: Requirements 4.3, 4.4
 *
 * For any valid non-empty WordTimestamp array, concatenating the word sequences
 * from all Cues produced by groupWordsToCues SHALL reproduce the original input
 * array in the same order, with no words omitted or duplicated (total word count
 * across all Cues equals input array length).
 */

/**
 * Generator for a valid ordered WordTimestamp array (Property 3).
 * Each word has: { word: string, startTime: number, endTime: number, speaker: number }
 * Words are ordered: each word's startTime >= previous word's endTime
 */
function arbitraryWordTimestampArrayP3(minLen = 1, maxLen = 50) {
  return fc.integer({ min: minLen, max: maxLen }).chain((len) =>
    fc.array(
      fc.record({
        duration: fc.double({ min: 0.01, max: 5.0, noNaN: true }),
        gap: fc.double({ min: 0, max: 5.0, noNaN: true }),
        word: fc.string({ minLength: 1, maxLength: 10 }).filter(w => w.trim().length > 0),
        speaker: fc.integer({ min: 0, max: 5 }),
      }),
      { minLength: len, maxLength: len }
    ).map((items) => {
      let currentTime = 0;
      return items.map((item) => {
        const startTime = currentTime + item.gap;
        const endTime = startTime + item.duration;
        currentTime = endTime;
        return {
          word: item.word,
          startTime,
          endTime,
          speaker: item.speaker,
        };
      });
    })
  );
}

describe('Property 3: Word conservation and order preservation', () => {
  it('concatenating all cue word sequences reproduces the original input array in order', () => {
    fc.assert(
      fc.property(
        arbitraryWordTimestampArrayP3(1, 50),
        (words) => {
          const cues = groupWordsToCues(words);
          const concatenated = cues.flatMap(c => c.words);

          // Same length — no omissions or duplicates
          expect(concatenated.length).toBe(words.length);

          // Same elements in same order
          expect(concatenated).toEqual(words);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('total word count across all cues equals input array length', () => {
    fc.assert(
      fc.property(
        arbitraryWordTimestampArrayP3(1, 50),
        (words) => {
          const cues = groupWordsToCues(words);
          const totalWordCount = cues.reduce((sum, c) => sum + c.words.length, 0);

          expect(totalWordCount).toBe(words.length);
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Property 5: Uniform splitting without gaps
 * Validates: Requirements 4.5
 *
 * For any valid WordTimestamp array containing more than 10 words where no gap
 * between consecutive words exceeds 2 seconds, the Cue_Grouping_Algorithm SHALL
 * produce Cues of exactly 10 words each, except the last Cue which SHALL contain
 * between 1 and 10 words (inclusive).
 */

/**
 * Generator for a valid ordered WordTimestamp array with >10 words and all gaps ≤ 2s.
 * Each word has: { word: string, startTime: number, endTime: number, speaker: number }
 * Words are ordered: each word's startTime >= previous word's endTime
 * All gaps between consecutive words are between 0 and 2 seconds (inclusive).
 */
const arbitraryWordTimestampArrayNoGaps = fc.array(
  fc.record({
    word: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0),
    duration: fc.double({ min: 0.01, max: 5, noNaN: true }),
    gap: fc.double({ min: 0, max: 1.99, noNaN: true }),
    speaker: fc.integer({ min: 0, max: 5 }),
  }),
  { minLength: 11, maxLength: 50 }
).map(records => {
  let currentTime = 0;
  return records.map(r => {
    const startTime = currentTime + r.gap;
    const endTime = startTime + r.duration;
    currentTime = endTime;
    return { word: r.word, startTime, endTime, speaker: r.speaker };
  });
});

describe('Property 5: Uniform splitting without gaps', () => {
  it('all cues except the last have exactly 10 words when no gaps exceed 2s and input has >10 words', () => {
    fc.assert(
      fc.property(
        arbitraryWordTimestampArrayNoGaps,
        (words) => {
          const cues = groupWordsToCues(words);
          expect(cues.length).toBeGreaterThanOrEqual(2);

          // All cues except the last must have exactly 10 words
          for (let i = 0; i < cues.length - 1; i++) {
            expect(cues[i].words.length).toBe(10);
          }

          // The last cue must have between 1 and 10 words
          const lastCue = cues[cues.length - 1];
          expect(lastCue.words.length).toBeGreaterThanOrEqual(1);
          expect(lastCue.words.length).toBeLessThanOrEqual(10);
        }
      ),
      { numRuns: 100 }
    );
  });
});

/**
 * Property 4: Gap-based cue splitting
 * Validates: Requirements 4.6, 1.3
 *
 * For any valid WordTimestamp array where the gap between two consecutive words
 * (word[n].startTime − word[n−1].endTime) exceeds 2 seconds, the Cue_Grouping_Algorithm
 * SHALL place those two words in different Cues, with word[n] starting a new Cue.
 */
describe('Property 4: Gap-based cue splitting', () => {
  /**
   * Generator: creates a valid WordTimestamp array with sequential, non-overlapping times,
   * then injects a gap > 2s at a random position to guarantee at least one split point.
   */
  const arbitraryWordsWithGap = fc.nat({ max: 18 }).chain((len) => {
    const arrayLen = len + 2; // at least 2 words so we can have a gap between them
    return fc.tuple(
      fc.array(
        fc.record({
          word: fc.stringMatching(/^[a-z]{1,8}$/),
          duration: fc.double({ min: 0.1, max: 1.5, noNaN: true }),
          gap: fc.double({ min: 0.0, max: 1.9, noNaN: true }), // normal gap ≤ 2s
        }),
        { minLength: arrayLen, maxLength: arrayLen }
      ),
      fc.nat({ max: arrayLen - 2 }), // position to inject the large gap
      fc.double({ min: 2.01, max: 10.0, noNaN: true }) // the large gap value (> 2s)
    ).map(([wordSpecs, gapPosition, largeGap]) => {
      // Build the WordTimestamp array with sequential times
      const words = [];
      let currentTime = 0;
      for (let i = 0; i < wordSpecs.length; i++) {
        const spec = wordSpecs[i];
        const startTime = currentTime;
        const endTime = startTime + spec.duration;
        words.push({
          word: spec.word || 'w',
          startTime,
          endTime,
          speaker: 1,
        });
        // Use the normal gap, except at the injection position use the large gap
        if (i < wordSpecs.length - 1) {
          currentTime = endTime + (i === gapPosition ? largeGap : spec.gap);
        }
      }
      return { words, gapPosition };
    });
  });

  it('words separated by a gap > 2s are placed in different cues', () => {
    fc.assert(
      fc.property(
        arbitraryWordsWithGap,
        ({ words, gapPosition }) => {
          const cues = groupWordsToCues(words);

          // For every pair of consecutive words where gap > 2s, they must be in different cues
          for (let n = 1; n < words.length; n++) {
            const gap = words[n].startTime - words[n - 1].endTime;
            if (gap > 2) {
              // word[n-1] should be the last word of one cue
              // word[n] should be the first word of the next cue
              let foundPrevInCue = -1;
              let foundCurrInCue = -1;

              for (let c = 0; c < cues.length; c++) {
                const cueWords = cues[c].words;
                if (cueWords[cueWords.length - 1] === words[n - 1]) {
                  foundPrevInCue = c;
                }
                if (cueWords[0] === words[n]) {
                  foundCurrInCue = c;
                }
              }

              // word[n-1] must be the last word of some cue
              expect(foundPrevInCue).toBeGreaterThanOrEqual(0);
              // word[n] must be the first word of some cue
              expect(foundCurrInCue).toBeGreaterThanOrEqual(0);
              // They must be in different (consecutive) cues
              expect(foundCurrInCue).toBe(foundPrevInCue + 1);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});

describe('groupWordsToCues', () => {
  it('returns empty array for empty input', () => {
    expect(groupWordsToCues([])).toEqual([]);
  });

  it('returns empty array for null/undefined input', () => {
    expect(groupWordsToCues(null)).toEqual([]);
    expect(groupWordsToCues(undefined)).toEqual([]);
  });

  it('handles single-word input as a valid single cue', () => {
    const words = [{ word: 'hello', startTime: 1.0, endTime: 1.5, speaker: 1 }];
    const cues = groupWordsToCues(words);
    expect(cues).toHaveLength(1);
    expect(cues[0].startTime).toBe(1.0);
    expect(cues[0].endTime).toBe(1.5);
    expect(cues[0].text).toBe('hello');
    expect(cues[0].words).toEqual(words);
  });

  it('splits at 10-word boundary', () => {
    const words = Array.from({ length: 12 }, (_, i) => ({
      word: `word${i}`,
      startTime: i * 0.5,
      endTime: i * 0.5 + 0.4,
      speaker: 1,
    }));
    const cues = groupWordsToCues(words);
    expect(cues).toHaveLength(2);
    expect(cues[0].words).toHaveLength(10);
    expect(cues[1].words).toHaveLength(2);
  });

  it('splits when gap between consecutive words exceeds 2 seconds', () => {
    const words = [
      { word: 'hello', startTime: 0, endTime: 0.5, speaker: 1 },
      { word: 'world', startTime: 0.6, endTime: 1.0, speaker: 1 },
      { word: 'foo', startTime: 3.1, endTime: 3.5, speaker: 1 }, // gap of 2.1s > 2s
    ];
    const cues = groupWordsToCues(words);
    expect(cues).toHaveLength(2);
    expect(cues[0].text).toBe('hello world');
    expect(cues[1].text).toBe('foo');
  });

  it('does NOT split when gap is exactly 2 seconds (uses strictly greater than)', () => {
    const words = [
      { word: 'hello', startTime: 0, endTime: 1.0, speaker: 1 },
      { word: 'world', startTime: 3.0, endTime: 3.5, speaker: 1 }, // gap of exactly 2s
    ];
    const cues = groupWordsToCues(words);
    expect(cues).toHaveLength(1);
    expect(cues[0].text).toBe('hello world');
  });

  it('preserves word order across all cues', () => {
    const words = Array.from({ length: 25 }, (_, i) => ({
      word: `w${i}`,
      startTime: i * 0.5,
      endTime: i * 0.5 + 0.4,
      speaker: 1,
    }));
    const cues = groupWordsToCues(words);
    const allWords = cues.flatMap(c => c.words);
    expect(allWords).toEqual(words);
  });

  it('sets correct startTime and endTime on each cue', () => {
    const words = [
      { word: 'a', startTime: 1.0, endTime: 1.5, speaker: 1 },
      { word: 'b', startTime: 2.0, endTime: 2.5, speaker: 1 },
      { word: 'c', startTime: 3.0, endTime: 3.5, speaker: 1 },
    ];
    const cues = groupWordsToCues(words);
    expect(cues[0].startTime).toBe(1.0);
    expect(cues[0].endTime).toBe(3.5);
  });
});


/**
 * Property 7: SRT output structure
 * Validates: Requirements 1.4, 1.5
 *
 * For any valid non-empty WordTimestamp array, the generated SRT content SHALL
 * consist of sequentially numbered Cue blocks (starting at 1) where each block
 * contains a numeric index line, a timecode line matching HH:MM:SS,mmm --> HH:MM:SS,mmm,
 * and a text line, with blocks separated by exactly one blank line and the file
 * ending with a trailing newline.
 */

/**
 * Generator for a non-empty array of valid WordTimestamp objects (Property 7).
 * Words are ordered: each word's startTime >= previous word's endTime.
 */
function arbitraryWordTimestampArrayP7(minLen = 1, maxLen = 50) {
  return fc.integer({ min: minLen, max: maxLen }).chain((len) =>
    fc.array(
      fc.record({
        duration: fc.double({ min: 0.01, max: 5.0, noNaN: true }),
        gap: fc.double({ min: 0, max: 5.0, noNaN: true }),
        word: fc.stringMatching(/^[a-z]{1,10}$/),
        speaker: fc.integer({ min: 0, max: 5 }),
      }),
      { minLength: len, maxLength: len }
    ).map((items) => {
      let currentTime = 0;
      return items.map((item) => {
        const startTime = currentTime + item.gap;
        const endTime = startTime + item.duration;
        currentTime = endTime;
        return {
          word: item.word || 'w',
          startTime,
          endTime,
          speaker: item.speaker,
        };
      });
    })
  );
}

describe('Property 7: SRT output structure', () => {
  const SRT_TIMECODE_REGEX = /^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$/;

  it('output has sequentially numbered cue blocks with correct structure and formatting', () => {
    fc.assert(
      fc.property(
        arbitraryWordTimestampArrayP7(1, 50),
        (words) => {
          const srtContent = generateSrtContent(words);

          // Output must end with a trailing newline
          expect(srtContent.endsWith('\n')).toBe(true);

          // Split by double newline to get blocks (remove trailing newline first)
          const trimmed = srtContent.slice(0, -1);
          const blocks = trimmed.split('\n\n');

          // Must have at least one block
          expect(blocks.length).toBeGreaterThanOrEqual(1);

          for (let i = 0; i < blocks.length; i++) {
            const lines = blocks[i].split('\n');

            // Each block must have exactly 3 lines: index, timecode, text
            expect(lines.length).toBe(3);

            // Line 1: numeric index, sequential starting at 1
            const index = Number(lines[0]);
            expect(index).toBe(i + 1);

            // Line 2: timecode line matching SRT format
            expect(lines[1]).toMatch(SRT_TIMECODE_REGEX);

            // Line 3: text line must be non-empty
            expect(lines[2].length).toBeGreaterThan(0);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});


/**
 * Property 8: VTT output structure
 * Validates: Requirements 2.2, 2.3, 2.4, 2.5
 *
 * For any valid non-empty WordTimestamp array, the generated VTT content SHALL
 * begin with a "WEBVTT" header followed by one blank line, contain Cue blocks
 * each consisting of a timecode line matching HH:MM:SS.mmm --> HH:MM:SS.mmm
 * followed by a text line, with blocks separated by exactly one blank line,
 * and SHALL NOT contain standalone numeric index lines.
 */

/**
 * Generator for a non-empty array of valid WordTimestamp objects (Property 8).
 * Words are ordered: each word's startTime >= previous word's endTime.
 */
function arbitraryWordTimestampArrayP8(minLen = 1, maxLen = 50) {
  return fc.integer({ min: minLen, max: maxLen }).chain((len) =>
    fc.array(
      fc.record({
        duration: fc.double({ min: 0.01, max: 5.0, noNaN: true }),
        gap: fc.double({ min: 0, max: 5.0, noNaN: true }),
        word: fc.stringMatching(/^[a-z]{1,10}$/),
        speaker: fc.integer({ min: 0, max: 5 }),
      }),
      { minLength: len, maxLength: len }
    ).map((items) => {
      let currentTime = 0;
      return items.map((item) => {
        const startTime = currentTime + item.gap;
        const endTime = startTime + item.duration;
        currentTime = endTime;
        return {
          word: item.word || 'w',
          startTime,
          endTime,
          speaker: item.speaker,
        };
      });
    })
  );
}

describe('Property 8: VTT output structure', () => {
  const VTT_TIMECODE_REGEX = /^\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}$/;

  it('output begins with WEBVTT header followed by one blank line, cue blocks have correct structure, and no standalone numeric index lines', () => {
    fc.assert(
      fc.property(
        arbitraryWordTimestampArrayP8(1, 50),
        (words) => {
          const vttContent = generateVttContent(words);

          // Output must start with "WEBVTT\n\n" (header + blank line)
          expect(vttContent.startsWith('WEBVTT\n\n')).toBe(true);

          // Get content after the header
          const afterHeader = vttContent.slice('WEBVTT\n\n'.length);

          // Remove trailing newline for block splitting
          const trimmed = afterHeader.endsWith('\n') ? afterHeader.slice(0, -1) : afterHeader;

          // Split remaining content by double newline to get cue blocks
          const blocks = trimmed.split('\n\n');

          // Must have at least one cue block
          expect(blocks.length).toBeGreaterThanOrEqual(1);

          for (const block of blocks) {
            const lines = block.split('\n');

            // Each cue block has exactly 2 lines: timecode line and text line
            expect(lines.length).toBe(2);

            // Line 1: timecode line matching VTT format
            expect(lines[0]).toMatch(VTT_TIMECODE_REGEX);

            // Line 2: text line must be non-empty
            expect(lines[1].length).toBeGreaterThan(0);
          }

          // No standalone numeric index lines in the entire output
          const allLines = vttContent.split('\n');
          for (const line of allLines) {
            // A standalone numeric index line is a line that is just a number
            // (skip empty lines and the WEBVTT header)
            if (line !== '' && line !== 'WEBVTT') {
              expect(line).not.toMatch(/^\d+$/);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});


/**
 * Unit Tests: Download mechanism and PDF export
 * Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 3.7
 */

describe('downloadTextFile - download mechanism', () => {
  let mockAnchor;
  let createObjectURLMock;
  let revokeObjectURLMock;

  beforeEach(() => {
    mockAnchor = {
      href: '',
      download: '',
      click: vi.fn(),
    };

    vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor);
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => {});
    vi.spyOn(document.body, 'removeChild').mockImplementation(() => {});

    createObjectURLMock = vi.fn().mockReturnValue('blob:http://localhost/fake-url');
    revokeObjectURLMock = vi.fn();
    globalThis.URL.createObjectURL = createObjectURLMock;
    globalThis.URL.revokeObjectURL = revokeObjectURLMock;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('creates a Blob with correct content and MIME type for SRT', () => {
    const content = '1\n00:00:00,000 --> 00:00:01,000\nhello\n';
    const mimeType = 'text/plain;charset=utf-8';

    let capturedBlob;
    createObjectURLMock.mockImplementation((blob) => {
      capturedBlob = blob;
      return 'blob:http://localhost/fake-url';
    });

    downloadTextFile(content, 'test.srt', mimeType);

    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    expect(capturedBlob).toBeInstanceOf(Blob);
    expect(capturedBlob.type).toBe('text/plain;charset=utf-8');
  });

  it('creates a Blob with correct content and MIME type for VTT', () => {
    const content = 'WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello\n';
    const mimeType = 'text/vtt;charset=utf-8';

    let capturedBlob;
    createObjectURLMock.mockImplementation((blob) => {
      capturedBlob = blob;
      return 'blob:http://localhost/fake-url';
    });

    downloadTextFile(content, 'test.vtt', mimeType);

    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    expect(capturedBlob).toBeInstanceOf(Blob);
    expect(capturedBlob.type).toBe('text/vtt;charset=utf-8');
  });

  it('calls URL.createObjectURL with the Blob', () => {
    downloadTextFile('content', 'file.srt', 'text/plain;charset=utf-8');

    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    const arg = createObjectURLMock.mock.calls[0][0];
    expect(arg).toBeInstanceOf(Blob);
  });

  it('creates a temporary anchor element with correct href and download attributes', () => {
    downloadTextFile('content', 'myfile.srt', 'text/plain;charset=utf-8');

    expect(document.createElement).toHaveBeenCalledWith('a');
    expect(mockAnchor.href).toBe('blob:http://localhost/fake-url');
    expect(mockAnchor.download).toBe('myfile.srt');
  });

  it('appends anchor to body, clicks it, and removes it', () => {
    downloadTextFile('content', 'file.srt', 'text/plain;charset=utf-8');

    expect(document.body.appendChild).toHaveBeenCalledWith(mockAnchor);
    expect(mockAnchor.click).toHaveBeenCalledTimes(1);
    expect(document.body.removeChild).toHaveBeenCalledWith(mockAnchor);
  });

  it('calls URL.revokeObjectURL after the click to prevent memory leaks', () => {
    vi.useFakeTimers();
    downloadTextFile('content', 'file.srt', 'text/plain;charset=utf-8');

    // revokeObjectURL is deferred via setTimeout to avoid race condition
    expect(revokeObjectURLMock).not.toHaveBeenCalled();
    vi.advanceTimersByTime(100);
    expect(revokeObjectURLMock).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:http://localhost/fake-url');
    vi.useRealTimers();
  });

  it('exportSrt triggers download with .srt extension and text/plain MIME type', () => {
    const words = [
      { word: 'hello', startTime: 0, endTime: 0.5, speaker: 1 },
      { word: 'world', startTime: 0.6, endTime: 1.0, speaker: 1 },
    ];

    exportSrt(words, 'job123');

    expect(mockAnchor.download).toBe('job123.srt');
    const blob = createObjectURLMock.mock.calls[0][0];
    expect(blob.type).toBe('text/plain;charset=utf-8');
  });

  it('exportVtt triggers download with .vtt extension and text/vtt MIME type', () => {
    const words = [
      { word: 'hello', startTime: 0, endTime: 0.5, speaker: 1 },
      { word: 'world', startTime: 0.6, endTime: 1.0, speaker: 1 },
    ];

    exportVtt(words, 'job123');

    expect(mockAnchor.download).toBe('job123.vtt');
    const blob = createObjectURLMock.mock.calls[0][0];
    expect(blob.type).toBe('text/vtt;charset=utf-8');
  });
});

vi.mock('jspdf', () => {
  const mockDoc = {
    setFillColor: vi.fn(),
    rect: vi.fn(),
    setFont: vi.fn(),
    setFontSize: vi.fn(),
    setTextColor: vi.fn(),
    text: vi.fn(),
    splitTextToSize: vi.fn(function (text) {
      const lines = [];
      for (let i = 0; i < text.length; i += 80) {
        lines.push(text.slice(i, i + 80));
      }
      return lines.length > 0 ? lines : [text];
    }),
    addPage: vi.fn(),
    getNumberOfPages: vi.fn().mockReturnValue(1),
    setPage: vi.fn(),
    getTextWidth: vi.fn().mockReturnValue(100),
    save: vi.fn(),
  };

  function jsPDF() {
    return mockDoc;
  }

  return {
    jsPDF,
    __mockDoc: mockDoc,
  };
});

describe('exportPdf - PDF generation', () => {
  let mockDoc;

  beforeEach(async () => {
    const jspdfModule = await import('jspdf');
    mockDoc = jspdfModule.__mockDoc;
    // Reset all mocks
    Object.values(mockDoc).forEach(fn => {
      if (typeof fn === 'function' && fn.mockClear) {
        fn.mockClear();
      }
    });
    mockDoc.getNumberOfPages.mockReturnValue(1);
    mockDoc.splitTextToSize.mockImplementation((text, width) => {
      const lines = [];
      for (let i = 0; i < text.length; i += 80) {
        lines.push(text.slice(i, i + 80));
      }
      return lines.length > 0 ? lines : [text];
    });
  });

  it('generates PDF with all sections present (summary, chapters, highlights, actionItems)', () => {
    const data = {
      summary: 'This is a test summary of the video content.',
      chapters: [
        { startTime: 0, title: 'Introduction' },
        { startTime: 65, title: 'Main Content' },
      ],
      highlights: [
        { timestamp: 30, description: 'Key insight about the topic' },
        { timestamp: 120, description: 'Important conclusion' },
      ],
      actionItems: ['Review the documentation', 'Follow up with team'],
    };

    exportPdf(data, 'testjob');

    // Verify doc.save is called with correct filename
    expect(mockDoc.save).toHaveBeenCalledWith('testjob.pdf');

    // Verify all section headings are rendered
    const textCalls = mockDoc.text.mock.calls.map(call => call[0]);
    expect(textCalls).toContain('Summary');
    expect(textCalls).toContain('Chapters');
    expect(textCalls).toContain('Highlights');
    expect(textCalls).toContain('Action Items');
  });

  it('generates PDF with only summary (no chapters, highlights, or actionItems)', () => {
    const data = {
      summary: 'This is a standalone summary without other sections.',
    };

    exportPdf(data, 'summary-only');

    expect(mockDoc.save).toHaveBeenCalledWith('summary-only.pdf');

    const textCalls = mockDoc.text.mock.calls.map(call => call[0]);
    expect(textCalls).toContain('Summary');
    expect(textCalls).not.toContain('Chapters');
    expect(textCalls).not.toContain('Highlights');
    expect(textCalls).not.toContain('Action Items');
  });

  it('generates PDF without chapters section when chapters is undefined', () => {
    const data = {
      summary: 'Summary text here.',
      highlights: [{ timestamp: 10, description: 'A highlight' }],
      actionItems: ['Do something'],
    };

    exportPdf(data, 'no-chapters');

    const textCalls = mockDoc.text.mock.calls.map(call => call[0]);
    expect(textCalls).toContain('Summary');
    expect(textCalls).not.toContain('Chapters');
    expect(textCalls).toContain('Highlights');
    expect(textCalls).toContain('Action Items');
  });

  it('generates PDF without highlights section when highlights is empty array', () => {
    const data = {
      summary: 'Summary text here.',
      chapters: [{ startTime: 0, title: 'Intro' }],
      highlights: [],
      actionItems: ['Task one'],
    };

    exportPdf(data, 'no-highlights');

    const textCalls = mockDoc.text.mock.calls.map(call => call[0]);
    expect(textCalls).toContain('Summary');
    expect(textCalls).toContain('Chapters');
    expect(textCalls).not.toContain('Highlights');
    expect(textCalls).toContain('Action Items');
  });

  it('generates PDF without actionItems section when actionItems is undefined', () => {
    const data = {
      summary: 'Summary text here.',
      chapters: [{ startTime: 30, title: 'Chapter 1' }],
      highlights: [{ timestamp: 45, description: 'Highlight 1' }],
    };

    exportPdf(data, 'no-actions');

    const textCalls = mockDoc.text.mock.calls.map(call => call[0]);
    expect(textCalls).toContain('Summary');
    expect(textCalls).toContain('Chapters');
    expect(textCalls).toContain('Highlights');
    expect(textCalls).not.toContain('Action Items');
  });

  it('calls doc.save with correct filename format', () => {
    const data = { summary: 'Test summary.' };

    exportPdf(data, 'my-job-id-123');

    expect(mockDoc.save).toHaveBeenCalledTimes(1);
    expect(mockDoc.save).toHaveBeenCalledWith('my-job-id-123.pdf');
  });

  it('calls doc.addPage for multi-page PDF with large content', () => {
    // Generate a very long summary that will exceed page height
    // Page usable height = 842 - 50 - 50 - 30 = 712pt
    // Each line is 15pt, so ~47 lines per page
    // We need more than 47 lines to trigger addPage
    const longSummary = 'This is a long sentence that will be repeated many times to fill multiple pages. '.repeat(100);

    // Mock splitTextToSize to return many lines (simulating text wrapping)
    mockDoc.splitTextToSize.mockImplementation((text, width) => {
      const lines = [];
      for (let i = 0; i < text.length; i += 60) {
        lines.push(text.slice(i, i + 60));
      }
      return lines;
    });

    // Track page count to simulate multi-page behavior
    let pageCount = 1;
    mockDoc.addPage.mockImplementation(() => {
      pageCount++;
    });
    mockDoc.getNumberOfPages.mockImplementation(() => pageCount);

    const data = { summary: longSummary };

    exportPdf(data, 'multipage-test');

    // With very large content, addPage should be called at least once
    expect(mockDoc.addPage).toHaveBeenCalled();
    expect(mockDoc.save).toHaveBeenCalledWith('multipage-test.pdf');
  });
});
