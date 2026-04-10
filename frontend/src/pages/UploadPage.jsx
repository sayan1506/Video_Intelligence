import { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Upload, AlertCircle, Film, X, Zap, CheckCircle } from 'lucide-react';
import { getUploadUrl, uploadToGcs, confirmUpload } from '../services/api';

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
    const validTypes = ['video/mp4', 'video/quicktime', 'video/avi'];
    
    if (!validTypes.includes(selectedFile.type)) {
      setError("Invalid file type. Please upload MP4, MOV, or AVI.");
      return;
    }

    const fileSizeMb = selectedFile.size / (1024 * 1024);
    if (fileSizeMb > 500) {
      setError("File is too large. Maximum size is 500MB.");
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

    const fileSizeMb = file.size / (1024 * 1024);

    try {
      // Step 1
      const { jobId, uploadUrl, gcsPath } = await getUploadUrl(file.name, file.type, fileSizeMb)

      // Step 2
      setUploadStepText('Uploading...');
      await uploadToGcs(uploadUrl, file, (percent) => {
        setUploadProgress(percent);
      });

      // Step 3
      setUploadStepText('Confirming upload...');
      await confirmUpload(jobId, gcsPath, file.name, file.type)

      setUploadStepText('Starting AI processing...');
      setUploadState('redirecting');
      
      setTimeout(() => {
        navigate('/status/' + jobId);
      }, 1500);

    } catch (err) {
      console.error(err);
      if (uploadStepText === 'Preparing upload...') {
         setError("Failed to prepare upload. Please try again.");
         setUploadState('idle');
      } else if (uploadStepText === 'Uploading...') {
         setError("Upload failed. Check your connection.");
         setUploadState('idle');
      } else {
         setError("Upload succeeded but processing could not start. Please refresh and try again.");
         // We do not reset to idle as the file is in GCS already
      }
    }
  };

  return (
    <div className="min-h-screen bg-dark-base text-slate-100 font-sans flex flex-col">
      {/* Simple navbar for subpages */}
      <nav className="border-b border-white/5 px-6 py-4 flex items-center justify-between bg-dark-base">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
          <Zap className="w-6 h-6 text-violet-500" fill="currentColor" />
          <span>VidIQ</span>
        </Link>
      </nav>

      <main className="flex-1 flex items-center justify-center p-6 animate-fade-in">
        <div className="w-full max-w-[600px] bg-dark-surface border border-dark-border rounded-3xl p-8 shadow-2xl relative overflow-hidden">
          
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold tracking-tight mb-2">Upload Your Video</h1>
            <p className="text-slate-400 text-sm">MP4, MOV or AVI &middot; Max 500MB</p>
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
                <div 
                  className="border-2 border-dashed border-white/20 hover:border-violet-500/50 hover:bg-violet-500/[0.02] transition-colors rounded-2xl p-12 text-center cursor-pointer group"
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <div className="w-16 h-16 mx-auto rounded-full bg-white/5 flex items-center justify-center mb-4 group-hover:bg-violet-500/10 transition-colors">
                    <Upload className="w-8 h-8 text-violet-400" />
                  </div>
                  <p className="text-lg font-medium text-slate-200 mb-1">Drag & drop your video here</p>
                  <p className="text-sm text-slate-500">or click to browse</p>
                  <input 
                    type="file" 
                    className="hidden" 
                    ref={fileInputRef} 
                    onChange={handleFileChange}
                    accept="video/mp4,video/quicktime,video/avi"
                  />
                </div>
              ) : (
                <div className="animate-slide-up">
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex items-center gap-4 mb-6">
                    <div className="w-10 h-10 rounded-lg bg-indigo-500/20 flex items-center justify-center shrink-0">
                      <Film className="w-5 h-5 text-indigo-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-200 truncate">{file.name}</p>
                      <p className="text-xs text-slate-500">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                    <button 
                      onClick={clearFile}
                      className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                      title="Remove file"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                  
                  <button 
                    onClick={handleUpload}
                    className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 active:scale-95 transition-all text-white py-3.5 rounded-xl font-medium text-lg shadow-lg"
                  >
                    Upload & Analyse
                  </button>
                </div>
              )}
            </>
          )}

          {/* State 2 & 3: Uploading & Redirecting */}
          {(uploadState === 'uploading' || uploadState === 'redirecting') && (
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6 animate-slide-up text-center">
              {uploadState === 'uploading' ? (
                <>
                  <p className="text-sm font-medium text-slate-300 mb-6 truncate">{file?.name}</p>
                  
                  <div className="h-2 w-full bg-dark-base rounded-full overflow-hidden mb-4 border border-white/5">
                    <div 
                      className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-500 ease-out"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400 font-medium">{uploadStepText}</span>
                    <span className="text-indigo-400 font-bold">{uploadProgress}%</span>
                  </div>
                </>
              ) : (
                <div className="py-4 animate-fade-in flex flex-col items-center">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mb-4 text-emerald-400">
                    <CheckCircle className="w-8 h-8" />
                  </div>
                  <h3 className="text-lg font-bold text-slate-100 mb-1">Upload complete!</h3>
                  <p className="text-sm text-slate-400">Redirecting to status page...</p>
                </div>
              )}
            </div>
          )}

        </div>
      </main>
    </div>
  );
}
