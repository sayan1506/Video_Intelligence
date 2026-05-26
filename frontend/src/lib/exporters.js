import { jsPDF } from 'jspdf';

/**
 * Video Export Module
 *
 * Contains pure functions for SRT, VTT, and PDF export generation.
 * All export logic runs entirely in the browser.
 */

/**
 * Formats a time value in seconds to SRT timecode format: HH:MM:SS,mmm
 * @param {number} seconds - Non-negative time value in seconds
 * @returns {string} - Formatted timecode string
 */
export function formatSrtTimecode(seconds) {
  const totalMs = Math.round(seconds * 1000);
  const ms = totalMs % 1000;
  const totalSeconds = Math.floor(totalMs / 1000);
  const s = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const m = totalMinutes % 60;
  const h = Math.floor(totalMinutes / 60);

  const hh = String(h).padStart(2, '0');
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  const mmm = String(ms).padStart(3, '0');

  return `${hh}:${mm}:${ss},${mmm}`;
}

/**
 * Formats a time value in seconds to VTT timecode format: HH:MM:SS.mmm
 * @param {number} seconds - Non-negative time value in seconds
 * @returns {string} - Formatted timecode string
 */
export function formatVttTimecode(seconds) {
  const totalMs = Math.round(seconds * 1000);
  const ms = totalMs % 1000;
  const totalSeconds = Math.floor(totalMs / 1000);
  const s = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const m = totalMinutes % 60;
  const h = Math.floor(totalMinutes / 60);

  const hh = String(h).padStart(2, '0');
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  const mmm = String(ms).padStart(3, '0');

  return `${hh}:${mm}:${ss}.${mmm}`;
}

/**
 * Groups an array of WordTimestamp objects into subtitle Cues.
 * Split boundaries: max 10 words per cue OR gap > 2s between consecutive words.
 * @param {Array<{word: string, startTime: number, endTime: number, speaker: number}>} words - Array of word objects
 * @returns {Array<{startTime: number, endTime: number, text: string, words: Array}>} - Array of cue objects
 */
export function groupWordsToCues(words) {
  if (!words || words.length === 0) {
    return [];
  }

  const cues = [];
  let currentCueWords = [words[0]];

  for (let i = 1; i < words.length; i++) {
    const currentWord = words[i];
    const previousWord = words[i - 1];
    const gap = currentWord.startTime - previousWord.endTime;

    if (currentCueWords.length >= 10 || gap > 2) {
      // Finalize the current cue and start a new one
      cues.push({
        startTime: currentCueWords[0].startTime,
        endTime: currentCueWords[currentCueWords.length - 1].endTime,
        text: currentCueWords.map(w => w.word).join(' '),
        words: currentCueWords,
      });
      currentCueWords = [currentWord];
    } else {
      currentCueWords.push(currentWord);
    }
  }

  // Finalize the last cue
  cues.push({
    startTime: currentCueWords[0].startTime,
    endTime: currentCueWords[currentCueWords.length - 1].endTime,
    text: currentCueWords.map(w => w.word).join(' '),
    words: currentCueWords,
  });

  return cues;
}

/**
 * Generates SRT subtitle content string from a WordTimestamp array.
 * @param {Array<{word: string, startTime: number, endTime: number, speaker: number}>} words - Transcript word array
 * @returns {string} - Complete SRT file content
 */
export function generateSrtContent(words) {
  const cues = groupWordsToCues(words);

  const blocks = cues.map((cue, i) => {
    const index = i + 1;
    const timecode = `${formatSrtTimecode(cue.startTime)} --> ${formatSrtTimecode(cue.endTime)}`;
    return `${index}\n${timecode}\n${cue.text}`;
  });

  return blocks.join('\n\n') + '\n';
}

/**
 * Triggers SRT download for the given transcript.
 * @param {Array<{word: string, startTime: number, endTime: number, speaker: number}>} words - Transcript word array
 * @param {string} filenameBase - Base filename (jobId)
 */
export function exportSrt(words, filenameBase) {
  const content = generateSrtContent(words);
  downloadTextFile(content, `${filenameBase}.srt`, 'text/plain;charset=utf-8');
}

/**
 * Generates VTT subtitle content string from a WordTimestamp array.
 * @param {Array<{word: string, startTime: number, endTime: number, speaker: number}>} words - Transcript word array
 * @returns {string} - Complete VTT file content
 */
export function generateVttContent(words) {
  const cues = groupWordsToCues(words);

  const blocks = cues.map((cue) => {
    const timecode = `${formatVttTimecode(cue.startTime)} --> ${formatVttTimecode(cue.endTime)}`;
    return `${timecode}\n${cue.text}`;
  });

  return 'WEBVTT\n\n' + blocks.join('\n\n') + '\n';
}

/**
 * Triggers VTT download for the given transcript.
 * @param {Array<{word: string, startTime: number, endTime: number, speaker: number}>} words - Transcript word array
 * @param {string} filenameBase - Base filename (jobId)
 */
export function exportVtt(words, filenameBase) {
  const content = generateVttContent(words);
  downloadTextFile(content, `${filenameBase}.vtt`, 'text/vtt;charset=utf-8');
}

/**
 * Triggers a browser file download from a string content.
 * Creates a Blob with the specified MIME type, generates a temporary object URL,
 * and triggers a download via a temporary anchor element.
 * Revokes the object URL after download to prevent memory leaks.
 *
 * @param {string} content - File content
 * @param {string} filename - Full filename with extension
 * @param {string} mimeType - MIME type for the Blob
 */
export function downloadTextFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);

  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;

  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);

  URL.revokeObjectURL(url);
}

/**
 * Formats seconds to M:SS format for PDF display.
 * @param {number} seconds - Time value in seconds
 * @returns {string} - Formatted time string (e.g., "1:05")
 */
function formatPdfTimestamp(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = String(Math.floor(seconds % 60)).padStart(2, '0');
  return `${mins}:${secs}`;
}

/**
 * Generates and downloads a PDF summary document.
 * Creates an A4 document (595×842 pt) with dark background, renders summary,
 * chapters, highlights, and action items sections with automatic page breaks,
 * and adds a footer on every page.
 *
 * @param {{ summary: string, chapters?: Array<{startTime: number, title: string}>, highlights?: Array<{timestamp: number, description: string}>, actionItems?: string[] }} data - Analysis data
 * @param {string} filenameBase - Base filename (jobId) without extension
 */
export function exportPdf(data, filenameBase) {
  const PAGE_WIDTH = 595;
  const PAGE_HEIGHT = 842;
  const MARGIN = 50;
  const USABLE_WIDTH = PAGE_WIDTH - 2 * MARGIN;
  const FOOTER_HEIGHT = 30;
  const MAX_Y = PAGE_HEIGHT - MARGIN - FOOTER_HEIGHT;
  const BG_COLOR = '#1a1a2e';
  const HEADING_COLOR = '#4fc3f7';
  const TEXT_COLOR = '#e0e0e0';
  const SUBTEXT_COLOR = '#b0b0b0';

  const doc = new jsPDF({ unit: 'pt', format: 'a4' });

  // Fill first page background
  function fillBackground() {
    doc.setFillColor(BG_COLOR);
    doc.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, 'F');
  }

  fillBackground();

  let y = MARGIN;

  /**
   * Checks if we need a page break and adds a new page if so.
   * @param {number} neededHeight - Height needed for the next content block
   */
  function checkPageBreak(neededHeight) {
    if (y + neededHeight > MAX_Y) {
      doc.addPage();
      fillBackground();
      y = MARGIN;
    }
  }

  /**
   * Renders a section heading.
   * @param {string} title - Section title text
   */
  function renderHeading(title) {
    checkPageBreak(30);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(16);
    doc.setTextColor(HEADING_COLOR);
    doc.text(title, MARGIN, y);
    y += 24;
  }

  /**
   * Renders wrapped body text.
   * @param {string} text - Text content to render
   */
  function renderBodyText(text) {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(11);
    doc.setTextColor(TEXT_COLOR);

    const lines = doc.splitTextToSize(text, USABLE_WIDTH);
    const lineHeight = 15;

    for (let i = 0; i < lines.length; i++) {
      checkPageBreak(lineHeight);
      doc.text(lines[i], MARGIN, y);
      y += lineHeight;
    }
  }

  /**
   * Renders a list item with timestamp prefix.
   * @param {string} timestamp - Formatted timestamp (M:SS)
   * @param {string} text - Item text
   */
  function renderTimestampItem(timestamp, text) {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(11);

    const itemText = `${timestamp} - ${text}`;
    const lines = doc.splitTextToSize(itemText, USABLE_WIDTH);
    const lineHeight = 15;

    for (let i = 0; i < lines.length; i++) {
      checkPageBreak(lineHeight);
      doc.setTextColor(i === 0 ? SUBTEXT_COLOR : TEXT_COLOR);
      doc.text(lines[i], MARGIN, y);
      y += lineHeight;
    }
  }

  /**
   * Renders a numbered list item.
   * @param {number} index - Item number (1-based)
   * @param {string} text - Item text
   */
  function renderNumberedItem(index, text) {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(11);
    doc.setTextColor(TEXT_COLOR);

    const itemText = `${index}. ${text}`;
    const lines = doc.splitTextToSize(itemText, USABLE_WIDTH);
    const lineHeight = 15;

    for (let i = 0; i < lines.length; i++) {
      checkPageBreak(lineHeight);
      doc.text(lines[i], MARGIN, y);
      y += lineHeight;
    }
  }

  // --- Render Summary section ---
  renderHeading('Summary');
  renderBodyText(data.summary);
  y += 10; // spacing after section

  // --- Render Chapters section (conditional) ---
  if (data.chapters && data.chapters.length > 0) {
    renderHeading('Chapters');
    for (const chapter of data.chapters) {
      const ts = formatPdfTimestamp(chapter.startTime);
      renderTimestampItem(ts, chapter.title);
    }
    y += 10;
  }

  // --- Render Highlights section (conditional) ---
  if (data.highlights && data.highlights.length > 0) {
    renderHeading('Highlights');
    for (const highlight of data.highlights) {
      const ts = formatPdfTimestamp(highlight.timestamp);
      renderTimestampItem(ts, highlight.description);
    }
    y += 10;
  }

  // --- Render Action Items section (conditional) ---
  if (data.actionItems && data.actionItems.length > 0) {
    renderHeading('Action Items');
    for (let i = 0; i < data.actionItems.length; i++) {
      renderNumberedItem(i + 1, data.actionItems[i]);
    }
    y += 10;
  }

  // --- Add footer on every page ---
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.setTextColor(SUBTEXT_COLOR);
    const footerText = `Generated by VidIQ \u00B7 Page ${i} of ${totalPages}`;
    const textWidth = doc.getTextWidth(footerText);
    const footerX = (PAGE_WIDTH - textWidth) / 2;
    const footerY = PAGE_HEIGHT - MARGIN + 15;
    doc.text(footerText, footerX, footerY);
  }

  // --- Save the PDF ---
  doc.save(`${filenameBase}.pdf`);
}
