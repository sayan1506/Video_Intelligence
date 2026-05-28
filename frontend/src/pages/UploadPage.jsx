import { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Upload, AlertCircle, Film, X, Zap, CheckCircle, Loader2, LayoutDashboard } from 'lucide-react';
import { getUploadUrl, uploadToGcs, confirmUpload } from '../services/api';
import ThemeToggle from '../components/ThemeToggle';
import UploadDropzone from '../components/UploadDropzone';

const MAX_FILE_SIZE_MB = 2048;

export default function UploadPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  // States
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);

  // 'idle' | 'uploading' | 'redirecting'
  const [uploadState, setUploadState] = useState('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStepText, setUploadStepText] = useState('');

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (uploadState !== 'idle') return;

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      validateAndSetFile(droppedFile);
    }
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      validateAndSetFile(selectedFile);
    }
  };

  const validateAndSetFile = (selectedFile) => {
    setError(null);
    const validTypes = ['video/mp4', 'video/quicktime', 'video/avi', 'video/x-matroska', 'video/matroska'];
    const validExtensions = ['.mp4', '.mov', '.avi', '.mkv'];

    const fileExtension = '.' + selectedFile.name.split('.').pop().toLowerCase();
    const isValidType = validTypes.includes(selectedFile.type) || validExtensions.includes(fileExtension);

    if (!isValidType) {
      setError("Invalid file type. Please upload MP4, MOV, AVI, or MKV.");
      return;
    }

    const fileSizeMb = selectedFile.size / (1024 * 1024);
    if (fileSizeMb > MAX_FILE_SIZE_MB) {
      setError(`File is too large. Maximum size is ${MAX_FILE_SIZE_MB}MB.`);
      return;
    }

    setFile(selectedFile);
  };

  const clearFile = () => {
    setFile(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploadState('uploading');
    setError(null);
    setUploadStepText('Preparing upload...');
    setUploadProgress(0);
    let currentStep = 'prepare';

    const fileSizeMb = file.size / (1024 * 1024);

    // Resolve content type — browsers often don't recognize .mkv
    const extensionMimeMap = { '.mkv': 'video/x-matroska' };
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    const contentType = file.type || extensionMimeMap[ext] || 'application/octet-stream';

    try {
      // Step 1 — get signed PUT URL from backend
      const { jobId, uploadUrl, gcsPath } = await getUploadUrl(file.name, contentType, file.size);

      // Step 2 — upload directly to GCS
      currentStep = 'upload';
      setUploadStepText('Uploading...');
      await uploadToGcs(uploadUrl, file, (percent) => {
        setUploadProgress(percent);
      });

      // Step 3 — confirm upload and trigger processing
      currentStep = 'confirm';
      setUploadStepText('Confirming upload...');
      await confirmUpload(jobId, gcsPath, file.name, contentType);

      setUploadState('redirecting');
      navigate(`/status/${jobId}`);
    } catch (err) {
      console.error(err);
      if (err.response?.status === 429) {
        setError(err.response.data?.detail || 'Monthly video limit reached. Quota resets on the 1st of next month. Upgrade to Pro for more.');
        setUploadState('idle');
      } else if (currentStep === 'prepare') {
        setError("Failed to prepare upload. Please try again.");
        setUploadState('idle');
      } else if (currentStep === 'upload') {
        setError("Upload failed. Check your connection and try again.");
        setUploadState('idle');
      } else {
        setError("Upload succeeded but processing could not start. Please refresh and try again.");
      }
    }
  };

  return (
    <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary text-gold-light-text-primary dark:text-gold-text-primary font-sans flex flex-col transition-colors">
      {/* Navbar */}
      <nav className="border-b border-gold-light-border dark:border-gold-border px-6 py-4 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <span className="font-display text-2xl font-bold tracking-tight text-gold-light-text-primary dark:text-gold-text-primary">VidIQ</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link
            to="/dashboard"
            className="flex items-center gap-2 text-sm text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-accent dark:hover:text-gold-accent transition-colors"
          >
            <LayoutDashboard className="w-4 h-4" />
            Dashboard
          </Link>
          <ThemeToggle />
        </div>
      </nav>

      {/* Gold string separator */}
      <div className="h-px w-full bg-gold-light-accent dark:bg-gold-accent" />

      <main className="flex-1 flex items-center justify-center p-6 animate-fade-in">
        <div className="w-full max-w-[600px] bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border border-gold-light-border dark:border-gold-border border-t-2 border-t-gold-light-accent dark:border-t-gold-accent rounded-3xl p-8 shadow-2xl relative overflow-hidden">

          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold tracking-tight mb-2 text-gold-light-text-primary dark:text-gold-text-primary">Upload Your Video</h1>
            <p className="text-gold-light-text-secondary dark:text-gold-text-secondary text-sm">MP4, MOV or AVI &middot; Max {MAX_FILE_SIZE_MB}MB</p>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-start gap-3 text-red-400 text-sm">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <p>{error}</p>
            </div>
          )}

          {/* State 1: Idle */}
          {uploadState === 'idle' && (
            <>
              {!file ? (
                <UploadDropzone
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  fileInputRef={fileInputRef}
                  onFileChange={handleFileChange}
                  accept="video/mp4,video/quicktime,video/avi,video/x-matroska,.mkv"
                />
              ) : (
                <div className="animate-slide-up">
                  <div className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded-xl p-4 flex items-center gap-4 mb-6">
                    <div className="w-10 h-10 rounded-lg bg-gold-accent-muted flex items-center justify-center shrink-0">
                      <Film className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gold-light-text-primary dark:text-gold-text-primary truncate">{file.name}</p>
                      <p className="text-xs text-gold-light-text-muted dark:text-gold-text-muted">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                    <button
                      onClick={clearFile}
                      className="w-11 h-11 flex items-center justify-center text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-light-accent dark:focus-visible:ring-gold-accent"
                      title="Remove file"
                      aria-label="Remove file"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>

                  <button
                    onClick={handleUpload}
                    disabled={uploadState !== 'idle'}
                    className="w-full bg-gold-light-accent dark:bg-gold-accent hover:bg-gold-light-accent-hover dark:hover:bg-gold-accent-hover active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-white py-3.5 rounded-xl font-medium text-lg shadow-lg flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-light-accent dark:focus-visible:ring-gold-accent focus-visible:ring-offset-2 focus-visible:ring-offset-gold-light-bg-secondary dark:focus-visible:ring-offset-gold-bg-secondary"
                  >
                    <>Upload &amp; Analyse</>
                  </button>
                </div>
              )}
            </>
          )}

          {/* State 2 & 3: Uploading & Redirecting */}
          {(uploadState === 'uploading' || uploadState === 'redirecting') && (
            <div className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded-2xl p-6 animate-slide-up text-center">
              {uploadState === 'uploading' ? (
                <>
                  <p className="text-sm font-medium text-gold-light-text-secondary dark:text-gold-text-secondary mb-6 truncate">{file?.name}</p>

                  <div className="h-2 w-full bg-gold-light-bg-primary dark:bg-gold-bg-primary rounded-full overflow-hidden mb-4 border border-gold-light-border-subtle dark:border-gold-border-subtle">
                    <div
                      className="h-full bg-gold-light-accent dark:bg-gold-accent transition-all duration-500 ease-out"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gold-light-text-secondary dark:text-gold-text-secondary font-medium">{uploadStepText}</span>
                    <span className="text-gold-light-accent dark:text-gold-accent font-bold">{uploadProgress}%</span>
                  </div>
                </>
              ) : (
                <div className="py-4 animate-fade-in flex flex-col items-center">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mb-4 text-emerald-400">
                    <CheckCircle className="w-8 h-8" />
                  </div>
                  <h3 className="text-lg font-bold text-gold-light-text-primary dark:text-gold-text-primary mb-1">Upload complete!</h3>
                  <p className="text-sm text-gold-light-text-secondary dark:text-gold-text-secondary">Redirecting to status page...</p>
                </div>
              )}
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
