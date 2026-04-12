import { useNavigate } from 'react-router-dom';
import { Zap, FileText, Brain, BookOpen, Layers, Star, Activity } from 'lucide-react';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-dark-base text-slate-100 font-sans selection:bg-indigo-500/30">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-dark-base/80 border-b border-white/5 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xl font-bold tracking-tight cursor-pointer" onClick={() => navigate('/')}>
          <Zap className="w-6 h-6 text-violet-500" fill="currentColor" />
          <span>VidIQ</span>
        </div>
        <button 
          onClick={() => navigate('/upload')}
          className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 active:scale-95 transition-all text-white px-5 py-2 rounded-full font-medium"
        >
          Launch App
        </button>
      </nav>

      {/* Hero Section */}
      <section className="relative px-6 pt-32 pb-24 max-w-5xl mx-auto text-center animate-fade-in overflow-hidden">
        {/* Background glow orb */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none animate-pulse-slow -z-10" />

        <div className="flex flex-wrap justify-center gap-3 mb-8 text-sm font-medium text-slate-300">
          <span className="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 backdrop-blur-sm">AI Transcript</span>
          <span className="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 backdrop-blur-sm">Scene Detection</span>
          <span className="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 backdrop-blur-sm">Smart Chapters</span>
          <span className="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 backdrop-blur-sm">Sentiment Analysis</span>
        </div>

        <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-6 mt-4">
          Turn Any Video Into <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-indigo-400">Intelligence</span>
        </h1>
        <p className="text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Upload a video. Get a full transcript, AI summary, scene analysis, and smart chapters — powered by Google Cloud AI.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button 
            onClick={() => navigate('/upload')}
            className="w-full sm:w-auto bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 active:scale-95 transition-all text-white px-8 py-3.5 rounded-full font-medium text-lg shadow-[0_0_40px_-10px_rgba(124,58,237,0.5)]"
          >
            Analyse a Video &rarr;
          </button>
          <a 
            href="#features"
            className="w-full sm:w-auto bg-white/5 hover:bg-white/10 border border-white/10 active:scale-95 transition-all text-white px-8 py-3.5 rounded-full font-medium text-lg"
          >
            See how it works
          </a>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="px-6 py-24 bg-dark-surface/50 border-y border-white/5 scroll-mt-20">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight mb-4">Everything you need to understand video at scale</h2>
            <p className="text-slate-400">Deep insights extracted automatically by advanced multimodal AI.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard 
              icon={<FileText className="w-5 h-5 text-violet-400" />}
              title="Full Transcript"
              description="Word-by-word transcript with timestamps. Click any word to jump to that moment in the video."
            />
            <FeatureCard 
              icon={<Brain className="w-5 h-5 text-indigo-400" />}
              title="AI Summary"
              description="Gemini AI reads your entire video and generates an executive summary with key insights."
            />
            <FeatureCard 
              icon={<BookOpen className="w-5 h-5 text-violet-400" />}
              title="Smart Chapters"
              description="Automatically splits your video into titled chapters so you can navigate like a book."
            />
            <FeatureCard 
              icon={<Layers className="w-5 h-5 text-indigo-400" />}
              title="Scene Detection"
              description="Google Video Intelligence detects every scene change and labels what's in each shot."
            />
            <FeatureCard 
              icon={<Star className="w-5 h-5 text-violet-400" />}
              title="Key Highlights"
              description="The most important moments extracted and timestamped so you never miss what matters."
            />
            <FeatureCard 
              icon={<Activity className="w-5 h-5 text-indigo-400" />}
              title="Sentiment Analysis"
              description="Understand the emotional tone of your video — positive, neutral, or negative."
            />
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="px-6 py-24 max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold tracking-tight mb-4">How it works</h2>
          <p className="text-slate-400">From raw video to actionable intelligence in three simple steps.</p>
        </div>

        <div className="flex flex-col md:flex-row gap-8 relative">
          {/* Desktop dashed connector */}
          <div className="hidden md:block absolute top-[52px] left-[16%] right-[16%] h-[2px] border-t-2 border-dashed border-white/10 -z-10" />

          <StepCard 
            number="1"
            title="Upload Your Video"
            description="Drag and drop or browse. Supports MP4, MOV, AVI up to 500MB."
          />
          <StepCard 
            number="2"
            title="AI Processes It"
            description="Google Cloud Speech-to-Text, Video Intelligence API, and Gemini AI analyse your video in parallel."
          />
          <StepCard 
            number="3"
            title="Explore Your Results"
            description="Interactive dashboard with video player, transcript, summary, scenes, and chapters — all synced together."
          />
        </div>
      </section>

      {/* Tech Stack Section */}
      <section className="px-6 py-12 border-t border-white/5 bg-dark-surface">
        <div className="max-w-5xl mx-auto text-center">
          <p className="text-sm font-medium text-slate-500 mb-6 uppercase tracking-wider">Powered by modern infrastructure</p>
          <div className="flex flex-wrap justify-center gap-6 text-slate-400 font-medium">
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-blue-500"></div> Google Cloud</span>
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-violet-500"></div> Gemini AI</span>
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-green-500"></div> Speech-to-Text</span>
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-indigo-500"></div> Video Intelligence API</span>
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-purple-500"></div> Cloud Run</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-6 py-8 border-t border-white/5 text-center text-slate-500 text-sm">
        <p>VidIQ &middot; Built on Google Cloud &middot; Copyright 2024</p>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="bg-white/[0.02] border border-dark-border backdrop-blur-md rounded-2xl p-6 hover:scale-[1.02] transition-transform duration-200 group">
      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-white/10 to-white/5 border border-white/10 flex items-center justify-center mb-5 group-hover:from-violet-500/20 group-hover:to-indigo-500/20 transition-colors">
        {icon}
      </div>
      <h3 className="text-lg font-bold mb-2 text-slate-100">{title}</h3>
      <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
    </div>
  );
}

function StepCard({ number, title, description }) {
  return (
    <div className="flex-1 text-center group">
      <div className="w-16 h-16 mx-auto rounded-2xl bg-dark-base border border-dark-border flex items-center justify-center text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-br from-violet-400 to-indigo-400 mb-6 shadow-xl relative z-10 group-hover:scale-110 transition-transform">
        {number}
      </div>
      <h3 className="text-lg font-bold mb-3 text-slate-100">{title}</h3>
      <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
    </div>
  );
}
