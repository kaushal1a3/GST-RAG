import React, { useState, useEffect, useRef } from 'react';
import ConfigModal from './ConfigModal';

const SUGGESTIONS = [
  "Ask about GST rates, ITC blocking, or reverse charge rules...",
  "What are the conditions for claiming Input Tax Credit under Section 16?",
  "Explain reverse charge mechanism and liability for e-commerce operators..."
];

export default function LandingPage({
  onStartChat,
  topK,
  setTopK,
  apiHealth,
  onOpenAbout
}) {
  const [inputQuery, setInputQuery] = useState("");
  const [showConfig, setShowConfig] = useState(false);

  // Kinetic Typewriter state
  const [suggestionText, setSuggestionText] = useState("");
  const suggestionIndexRef = useRef(0);
  const charIndexRef = useRef(0);
  const isDeletingRef = useRef(false);
  const isFocusedRef = useRef(false);

  useEffect(() => {
    let timeoutId;

    const typeWriterEffect = () => {
      if (isFocusedRef.current || inputQuery.length > 0) {
        timeoutId = setTimeout(typeWriterEffect, 200);
        return;
      }

      const currentFullText = SUGGESTIONS[suggestionIndexRef.current];

      if (isDeletingRef.current) {
        charIndexRef.current--;
      } else {
        charIndexRef.current++;
      }

      setSuggestionText(currentFullText.substring(0, charIndexRef.current));

      let delay = isDeletingRef.current ? 30 : 60;

      if (!isDeletingRef.current && charIndexRef.current === currentFullText.length) {
        isDeletingRef.current = true;
        delay = 2000;
      } else if (isDeletingRef.current && charIndexRef.current === 0) {
        isDeletingRef.current = false;
        suggestionIndexRef.current = (suggestionIndexRef.current + 1) % SUGGESTIONS.length;
        delay = 500;
      }

      timeoutId = setTimeout(typeWriterEffect, delay);
    };

    timeoutId = setTimeout(typeWriterEffect, 1000);
    return () => clearTimeout(timeoutId);
  }, [inputQuery]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!inputQuery.trim()) return;
    onStartChat(inputQuery.trim());
  };

  const handleCardClick = (promptText) => {
    onStartChat(promptText);
  };

  return (
    <div className="h-full flex flex-col justify-between items-center relative overflow-x-hidden selection:bg-orange-500 selection:text-white min-h-screen">
      {/* Ambient background glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[450px] bg-gradient-to-b from-orange-500/10 via-orange-500/5 to-transparent rounded-full blur-3xl pointer-events-none -z-10"></div>

      {/* Top Navigation & Config Panel */}
      <header className="w-full max-w-7xl flex justify-between items-center pt-8 px-8 relative z-50">
        {/* Logo / Brand Tag */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => onStartChat("")}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-orange-600 to-orange-500 flex items-center justify-center text-white shadow-md shadow-orange-500/20">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
            </svg>
          </div>
          <span className="display-font font-bold text-lg tracking-tight text-stone-900">Ask GST</span>
        </div>

        <div className="flex items-center gap-3">
          {/* Demo / About Button */}
          <div className="relative group/tooltip">
            <button
              onClick={onOpenAbout}
              title="About GST RAG"
              className="bg-white border border-[var(--border)] px-4 h-11 rounded-xl flex items-center gap-2 text-stone-700 hover:text-stone-900 shadow-sm transition-all duration-200 cursor-pointer group"
            >
              <svg className="w-4 h-4 text-orange-600 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
              </svg>
              <span className="text-xs font-semibold tracking-wide">About</span>
            </button>
            <div className="absolute top-full right-0 mt-2 hidden group-hover/tooltip:block bg-stone-900 text-white text-xs px-2.5 py-1 rounded-lg shadow-lg whitespace-nowrap z-50 animate-fade-in font-medium">
              About GST RAG
            </div>
          </div>

          {/* Config Button */}
          <div className="relative group/tooltip">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowConfig(!showConfig);
              }}
              title="Retrieval Settings"
              className="bg-white border border-[var(--border)] px-4 h-11 rounded-xl flex items-center gap-2 text-stone-700 hover:text-stone-900 shadow-sm transition-all duration-200 cursor-pointer relative"
            >
              <svg className="w-4 h-4 text-stone-500 hover:text-stone-900 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
              </svg>
              <span className="text-xs font-semibold tracking-wide">Config</span>
            </button>
            <div className="absolute top-full right-0 mt-2 hidden group-hover/tooltip:block bg-stone-900 text-white text-xs px-2.5 py-1 rounded-lg shadow-lg whitespace-nowrap z-50 animate-fade-in font-medium">
              Retrieval Settings
            </div>
          </div>

          {/* Github Button */}
          <div className="relative group/tooltip">
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer"
              title="View Source on GitHub"
              className="bg-white border border-[var(--border)] w-11 h-11 rounded-xl flex items-center justify-center shadow-sm transition-all duration-200"
            >
              <svg className="w-5 h-5 text-stone-700" fill="currentColor" viewBox="0 0 24 24">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"></path>
              </svg>
            </a>
            <div className="absolute top-full right-0 mt-2 hidden group-hover/tooltip:block bg-stone-900 text-white text-xs px-2.5 py-1 rounded-lg shadow-lg whitespace-nowrap z-50 animate-fade-in font-medium">
              View on GitHub
            </div>
          </div>

          <ConfigModal
            isOpen={showConfig}
            onClose={() => setShowConfig(false)}
            topK={topK}
            setTopK={setTopK}
            apiHealth={apiHealth}
          />
        </div>
      </header>

      {/* Main Content Center */}
      <main className="w-full max-w-[1000px] mx-auto px-6 flex flex-col items-center gap-12 my-auto py-16">

        {/* Top Hero Editorial Block */}
        <div className="w-full max-w-3xl flex flex-col items-center gap-6 text-center hero-block">

          {/* Claude Animated SVG / Lottie Logo */}
          <div className="w-32 h-20 sm:w-40 sm:h-24 flex items-center justify-center -mb-2 text-orange-600 cursor-pointer hover:scale-105 transition-transform duration-300">
            <img src="/claude.svg" alt="Claude Logo" className="w-full h-full object-contain" />
          </div>

          {/* Heading */}
          <div className="w-full flex flex-col gap-4">
            <h1 className="text-4xl sm:text-6xl font-extrabold text-stone-900 tracking-tight leading-[1.1]">
              Ask GST anything with <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-600 to-amber-600">vector precision</span>.
            </h1>
            <p className="text-base sm:text-lg text-stone-600 font-normal leading-relaxed max-w-xl mx-auto">
              Navigate complex GST rates, ITC blocking rules, and regulatory filings instantaneously with verified semantic search.
            </p>
          </div>
        </div>

        {/* Chat Input & Suggestions */}
        <div className="w-full max-w-3xl flex flex-col gap-6">
          {/* Input Box */}
          <form onSubmit={handleSubmit} className="w-full bg-white border border-orange-500/20 rounded-2xl p-6 sm:p-7 flex flex-col gap-5 relative group shadow-xl">
            <div className="w-full relative flex items-center bg-[#FFFBF5]/80 border border-orange-500/20 rounded-xl p-3.5 shadow-sm">
              <textarea
                rows={2}
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                onFocus={() => { isFocusedRef.current = true; }}
                onBlur={() => { isFocusedRef.current = false; }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                placeholder=""
                className="w-full text-base sm:text-lg text-stone-900 placeholder-transparent bg-transparent border-none outline-none resize-none leading-relaxed z-10 relative font-medium"
              />

              {/* Kinetic Typography Suggestions */}
              {inputQuery.length === 0 && (
                <div className="absolute inset-0 pointer-events-none flex items-center px-4 text-base text-stone-400 transition-all duration-500 ease-in-out font-normal overflow-hidden whitespace-nowrap">
                  <span className="inline-block">{suggestionText}</span>
                </div>
              )}
            </div>

            <div className="w-full flex justify-end items-center pt-2">
              <div className="flex items-center gap-3">
                {/* Attach Button */}
                <div className="relative group/tooltip">
                  <button
                    type="button"
                    onClick={() => alert("Attachment feature available.")}
                    title="Attach Section / PDF"
                    className="p-3 rounded-xl bg-white border border-stone-200 hover:border-orange-300 text-stone-600 hover:text-stone-900 flex items-center justify-center transition-all cursor-pointer shadow-sm"
                  >
                    <svg className="w-4 h-4 text-stone-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"></path>
                    </svg>
                  </button>
                  <div className="absolute bottom-full right-0 mb-2 hidden group-hover/tooltip:block bg-stone-900 text-white text-xs px-2.5 py-1 rounded-lg shadow-lg whitespace-nowrap z-50 animate-fade-in font-medium">
                    Attach File (.pdf, .csv, .png)
                  </div>
                </div>

                {/* Send Button */}
                <div className="relative group/tooltip">
                  <button
                    type="submit"
                    className="p-3 rounded-xl bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white flex items-center justify-center transition-all shadow-lg shadow-orange-500/25 border border-orange-400/30 cursor-pointer interactive"
                  >
                    <svg className="w-4 h-4 text-white fill-current" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z"></path>
                    </svg>
                  </button>
                  <div className="absolute bottom-full right-0 mb-2 hidden group-hover/tooltip:block bg-stone-900 text-white text-xs px-2.5 py-1 rounded-lg shadow-lg whitespace-nowrap z-50 animate-fade-in font-medium">
                    Start Chat Session
                  </div>
                </div>
              </div>
            </div>
          </form>

          {/* Example suggestion cards with gapless bento-density */}
          <div className="w-full flex flex-col gap-3">
            <div className="flex items-center justify-between px-1">
              <span className="caps-label text-stone-500">Suggested Inquiries</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">

              {/* Card 1 */}
              <div
                onClick={() => handleCardClick("What are the condition under ITC eligibility?")}
                className="bg-white border border-orange-500/20 hover:border-orange-500/40 p-4 rounded-xl flex flex-col justify-between gap-3 cursor-pointer group interactive shadow-sm hover:shadow-md transition-all"
              >
                <div className="flex justify-between items-start">
                  <span className="caps-label text-orange-600 text-[10px] px-2 py-0.5 rounded bg-orange-500/10 border border-orange-500/20">Section 16</span>
                  <svg className="w-3.5 h-3.5 text-stone-400 group-hover:text-orange-600 transition-colors transform group-hover:translate-x-0.5 duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                  </svg>
                </div>
                <p className="text-xs text-stone-700 font-medium line-clamp-2 leading-relaxed">“What are the condition under ITC eligibility?”</p>
              </div>

              {/* Card 2 */}
              <div
                onClick={() => handleCardClick("What are the penalties for late filing GSTR-3B?")}
                className="bg-white border border-orange-500/20 hover:border-orange-500/40 p-4 rounded-xl flex flex-col justify-between gap-3 cursor-pointer group interactive shadow-sm hover:shadow-md transition-all"
              >
                <div className="flex justify-between items-start">
                  <span className="caps-label text-amber-600 text-[10px] px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">Sec 47/50</span>
                  <svg className="w-3.5 h-3.5 text-stone-400 group-hover:text-amber-600 transition-colors transform group-hover:translate-x-0.5 duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                  </svg>
                </div>
                <p className="text-xs text-stone-700 font-medium line-clamp-2 leading-relaxed">“What are the penalties for late filing GSTR-3B?”</p>
              </div>

              {/* Card 3 */}
              <div
                onClick={() => handleCardClick("Explain reverse charge mechanism under GST.")}
                className="bg-white border border-orange-500/20 hover:border-orange-500/40 p-4 rounded-xl flex flex-col justify-between gap-3 cursor-pointer group interactive shadow-sm hover:shadow-md transition-all"
              >
                <div className="flex justify-between items-start">
                  <span className="caps-label text-orange-700 text-[10px] px-2 py-0.5 rounded bg-orange-600/10 border border-orange-600/20">Sec 9(3)/(4)</span>
                  <svg className="w-3.5 h-3.5 text-stone-400 group-hover:text-orange-700 transition-colors transform group-hover:translate-x-0.5 duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                  </svg>
                </div>
                <p className="text-xs text-stone-700 font-medium line-clamp-2 leading-relaxed">“Explain reverse charge mechanism under GST.”</p>
              </div>

              {/* Card 4 */}
              <div
                onClick={() => handleCardClick("What is the procedure for GST registration cancellation?")}
                className="bg-white border border-orange-500/20 hover:border-orange-500/40 p-4 rounded-xl flex flex-col justify-between gap-3 cursor-pointer group interactive shadow-sm hover:shadow-md transition-all"
              >
                <div className="flex justify-between items-start">
                  <span className="caps-label text-yellow-700 text-[10px] px-2 py-0.5 rounded bg-yellow-500/10 border border-yellow-500/20">Section 29</span>
                  <svg className="w-3.5 h-3.5 text-stone-400 group-hover:text-yellow-700 transition-colors transform group-hover:translate-x-0.5 duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                  </svg>
                </div>
                <p className="text-xs text-stone-700 font-medium line-clamp-2 leading-relaxed">“What is the procedure for GST registration cancellation?”</p>
              </div>

            </div>
          </div>
        </div>

      </main>

      {/* Footer Disclaimer */}
      <footer className="w-full text-center pb-8 px-4">
        <p className="text-xs text-stone-500">AI assistant grounded in verified tax acts. Please verify against <a href="https://www.cbic.gov.in" target="_blank" rel="noreferrer" className="underline hover:text-stone-700">official CBIC sources</a>.</p>
      </footer>
    </div>
  );
}
