import { Zap, FileText, Brain, BookOpen, Layers, Star, Activity } from 'lucide-react';
import ThemeToggle from './ThemeToggle';

/**
 * ComingSoonPage — public showcase shown when the app is gated behind the
 * COMING_SOON flag in App.jsx. It mirrors the marketing content of the real
 * LandingPage so visitors can see what VidIQ does, but every call-to-action
 * (sign in, dashboard, analyse-a-video, see-how-it-works) is removed so there
 * is no way into the app. Renders outside the router, so it uses no
 * navigation or auth — only ThemeToggle, which needs only ThemeProvider.
 *
 * To restore the full routed app, set COMING_SOON = false in App.jsx.
 */
export default function ComingSoonPage() {
  return (
    <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary text-gold-light-text-primary dark:text-gold-text-primary font-sans">
      {/* Services-paused banner */}
      <div className="bg-gold-light-accent dark:bg-gold-accent text-white dark:text-gold-bg-primary text-center text-sm font-semibold tracking-wide py-2.5 px-4">
        Services Paused
      </div>

      {/* Navbar — brand + theme toggle only, no sign-in CTA */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-gold-light-bg-primary/80 dark:bg-gold-bg-primary/80 border-b border-gold-light-border dark:border-gold-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xl font-bold tracking-tight">
          <Zap className="w-6 h-6 text-gold-light-accent dark:text-gold-accent" fill="currentColor" />
          <span className="font-display">VidIQ</span>
        </div>
        <ThemeToggle />
      </nav>

      {/* Hero Section — no CTA buttons */}
      <section className="relative px-6 pt-32 pb-24 max-w-5xl mx-auto text-center animate-fade-in overflow-hidden">
        {/* Background glow orb */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gold-accent-muted dark:bg-gold-accent-muted rounded-full blur-[120px] pointer-events-none animate-pulse-slow -z-10" />

        <div className="flex flex-wrap justify-center gap-3 mb-8 text-sm font-medium text-gold-light-text-secondary dark:text-gold-text-secondary">
          <span className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded-full px-4 py-1.5">AI Transcript</span>
          <span className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded-full px-4 py-1.5">Scene Detection</span>
          <span className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded-full px-4 py-1.5">Smart Chapters</span>
          <span className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded-full px-4 py-1.5">Sentiment Analysis</span>
        </div>

        <h1 className="font-display text-5xl md:text-6xl font-bold tracking-tight mb-6 mt-4">
          Turn Any Video Into <span className="text-gold-light-accent dark:text-gold-accent">Intelligence</span>
        </h1>
        <p className="text-xl text-gold-light-text-secondary dark:text-gold-text-secondary max-w-2xl mx-auto leading-relaxed">
          Upload a video. Get a full transcript, AI summary, scene analysis, and smart chapters — powered by Google Cloud AI.
        </p>
      </section>

      {/* Gold String Separator */}
      <div className="h-px w-full bg-gold-light-accent dark:bg-gold-accent" />

      {/* Features Section */}
      <section id="features" className="px-6 py-24 bg-gold-light-bg-tertiary/50 dark:bg-gold-bg-secondary/50 border-y border-gold-light-border dark:border-gold-border scroll-mt-20">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight mb-4">Everything you need to understand video at scale</h2>
            <p className="text-gold-light-text-secondary dark:text-gold-text-secondary">Deep insights extracted automatically by advanced multimodal AI.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard
              icon={<FileText className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />}
              title="Full Transcript"
              description="Word-by-word transcript with timestamps. Click any word to jump to that moment in the video."
            />
            <FeatureCard
              icon={<Brain className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />}
              title="AI Summary"
              description="Gemini AI reads your entire video and generates an executive summary with key insights."
            />
            <FeatureCard
              icon={<BookOpen className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />}
              title="Smart Chapters"
              description="Automatically splits your video into titled chapters so you can navigate like a book."
            />
            <FeatureCard
              icon={<Layers className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />}
              title="Scene Detection"
              description="Google Video Intelligence detects every scene change and labels what's in each shot."
            />
            <FeatureCard
              icon={<Star className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />}
              title="Key Highlights"
              description="The most important moments extracted and timestamped so you never miss what matters."
            />
            <FeatureCard
              icon={<Activity className="w-5 h-5 text-gold-light-accent dark:text-gold-accent" />}
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
          <p className="text-gold-light-text-secondary dark:text-gold-text-secondary">From raw video to actionable intelligence in three simple steps.</p>
        </div>

        <div className="flex flex-col md:flex-row gap-8 relative">
          {/* Desktop dashed connector */}
          <div className="hidden md:block absolute top-[52px] left-[16%] right-[16%] h-[2px] border-t-2 border-dashed border-gold-light-border dark:border-gold-border -z-10" />

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
      <section className="px-6 py-12 border-t border-gold-light-border dark:border-gold-border bg-gold-light-bg-secondary dark:bg-gold-bg-secondary">
        <div className="max-w-5xl mx-auto text-center">
          <p className="text-sm font-medium text-gold-light-text-muted dark:text-gold-text-muted mb-6 uppercase tracking-wider">Powered by modern infrastructure</p>
          <div className="flex flex-wrap justify-center gap-6 text-gold-light-text-secondary dark:text-gold-text-secondary font-medium">
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-gold-light-accent dark:bg-gold-accent"></div> Google Cloud</span>
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-gold-light-accent dark:bg-gold-accent"></div> Gemini AI</span>
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-gold-light-accent dark:bg-gold-accent"></div> Speech-to-Text</span>
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-gold-light-accent dark:bg-gold-accent"></div> Video Intelligence API</span>
            <span className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-gold-light-accent dark:bg-gold-accent"></div> Cloud Run</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-6 py-8 border-t border-gold-light-border dark:border-gold-border text-center text-gold-light-text-muted dark:text-gold-text-muted text-sm">
        <p>VidIQ &middot; Built on Google Cloud &middot; Copyright 2024</p>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border-l-[3px] border-l-gold-light-accent dark:border-l-gold-accent border border-gold-light-border dark:border-gold-border rounded-lg p-6 hover:scale-[1.02] transition-transform duration-200 motion-reduce:transition-none group">
      <div className="w-12 h-12 rounded-full bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border flex items-center justify-center mb-5">
        {icon}
      </div>
      <h3 className="text-lg font-bold mb-2">{title}</h3>
      <p className="text-gold-light-text-secondary dark:text-gold-text-secondary text-sm leading-relaxed">{description}</p>
    </div>
  );
}

function StepCard({ number, title, description }) {
  return (
    <div className="flex-1 text-center group">
      <div className="w-16 h-16 mx-auto rounded-2xl bg-gold-light-bg-primary dark:bg-gold-bg-primary border border-gold-light-border dark:border-gold-border flex items-center justify-center text-2xl font-bold text-gold-light-accent dark:text-gold-accent mb-6 shadow-xl relative z-10 group-hover:scale-110 transition-transform duration-200 motion-reduce:transition-none">
        {number}
      </div>
      <h3 className="text-lg font-bold mb-3">{title}</h3>
      <p className="text-gold-light-text-secondary dark:text-gold-text-secondary text-sm leading-relaxed">{description}</p>
    </div>
  );
}
