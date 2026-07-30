import React, { useState, useRef, useEffect } from 'react';
import { marked } from 'marked';
import ConfigModal from './ConfigModal';

export default function ChatSession({
  messages = [],
  sessionTitle = "New Chat Session",
  onSendMessage,
  loading,
  statusMessage,
  onNewChat,
  onClearHistory,
  topK,
  setTopK,
  apiHealth,
  onReindex,
  reindexing,
  onOpenAbout,
  threads = [],
  activeThreadId,
  onSelectThread,
  onDeleteThread,
  onGoHome
}) {
  const [inputQuery, setInputQuery] = useState("");
  const [collapsedLeft, setCollapsedLeft] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [mobileLeftOpen, setMobileLeftOpen] = useState(false);
  const [mobileRightOpen, setMobileRightOpen] = useState(false);
  const [expandedSourceIndex, setExpandedSourceIndex] = useState(null);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!inputQuery.trim() || loading) return;
    onSendMessage(inputQuery.trim());
    setInputQuery("");
  };

  // Get active citations from the latest assistant message that has citations
  const latestAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant' && m.citations && m.citations.length > 0);
  const currentCitations = latestAssistantMessage?.citations || [];

  return (
    <div className="w-full min-h-screen grid grid-cols-1 xl:grid-cols-[auto_1fr_310px] items-start relative z-10">
      
      {/* Mobile Top Navigation Bar for Small Screens */}
      <div className="xl:hidden w-full bg-white border-b border-orange-500/10 px-4 py-3 flex items-center justify-between sticky top-0 z-30 shadow-sm">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setMobileLeftOpen(true)}
            className="w-10 h-10 bg-white border border-orange-500/15 rounded-xl flex items-center justify-center shadow-sm"
          >
            <svg className="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16"></path>
            </svg>
          </button>
          <button onClick={onGoHome} className="text-xl font-extrabold tracking-tight text-[#171717]">
            Ask <span className="text-orange-600">GST</span>
          </button>
        </div>
        <button 
          onClick={() => setMobileRightOpen(true)}
          className="w-10 h-10 bg-white border border-orange-500/15 rounded-xl flex items-center justify-center shadow-sm"
        >
          <svg className="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"></path>
          </svg>
        </button>
      </div>

      {/* Mobile Drawer Left */}
      {mobileLeftOpen && (
        <div className="fixed inset-0 z-50 flex xl:hidden">
          <div className="fixed inset-0 bg-stone-900/50" onClick={() => setMobileLeftOpen(false)}></div>
          <div className="relative w-[310px] bg-white border-r border-orange-500/15 h-full flex flex-col justify-between py-6 px-6 overflow-y-auto z-10 animate-fade-in shadow-2xl">
            <div className="flex flex-col gap-8">
              <div className="flex items-center justify-between">
                <button onClick={onGoHome} className="text-2xl font-extrabold tracking-tight text-[#171717]">
                  Ask <span className="text-orange-600">GST</span>
                </button>
                <button onClick={() => setMobileLeftOpen(false)} className="w-9 h-9 bg-stone-100 rounded-xl flex items-center justify-center text-stone-600">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                  </svg>
                </button>
              </div>
              <button 
                onClick={() => { onNewChat(); setMobileLeftOpen(false); }}
                className="w-full h-11 px-4 flex items-center justify-center gap-2 bg-gradient-to-r from-[#F54900] to-[#FF6900] text-white font-semibold text-xs rounded-xl shadow-sm cursor-pointer"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path>
                </svg>
                <span>Start New Chat</span>
              </button>
              <div className="flex flex-col gap-3">
                <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-[#78716C]">RECENTS</span>
                <div className="flex flex-col gap-[10px]">
                  {threads.length === 0 ? (
                    <p className="text-xs text-stone-400 italic">No saved chats yet.</p>
                  ) : (
                    threads.map((thread) => (
                      <div 
                        key={thread.id}
                        onClick={() => { onSelectThread(thread.id); setMobileLeftOpen(false); }}
                        className={`w-full p-[10px_15px] rounded-xl border border-orange-500/10 flex items-center justify-between gap-2.5 cursor-pointer group ${thread.id === activeThreadId ? 'bg-orange-500/10 font-semibold' : ''}`}
                      >
                        <span className="text-xs font-medium text-[#44403C] line-clamp-2 leading-tight flex-1">{thread.title}</span>
                        
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteThread(thread.id);
                          }}
                          title="Delete thread"
                          className="p-1 hover:bg-orange-200/50 rounded-lg text-stone-500 hover:text-orange-700 transition-all shrink-0"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                          </svg>
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
            
            <div className="flex flex-col gap-3">
              <p className="text-[11px] font-medium font-mono text-[#57534E] opacity-50 leading-tight text-center px-1">
                Based on Acts, Rules, Notification and Circular till dated March 2026
              </p>
              <button 
                onClick={() => { onClearHistory(); setMobileLeftOpen(false); }}
                className="w-full h-11 px-4 flex items-center justify-center gap-2 bg-white border border-orange-500/15 text-[#292524] font-semibold text-xs rounded-xl shadow-sm cursor-pointer"
              >
                <svg className="w-4 h-4 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
                <span>Clear History</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mobile Drawer Right */}
      {mobileRightOpen && (
        <div className="fixed inset-0 z-50 flex justify-end xl:hidden">
          <div className="fixed inset-0 bg-stone-900/50" onClick={() => setMobileRightOpen(false)}></div>
          <div className="relative w-[310px] bg-white border-l border-orange-500/15 h-full flex flex-col py-6 px-6 gap-6 overflow-y-auto z-10 animate-fade-in shadow-2xl">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">Sources &amp; Config</span>
              <button onClick={() => setMobileRightOpen(false)} className="w-9 h-9 bg-stone-100 rounded-xl flex items-center justify-center text-stone-600">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={onOpenAbout} className="flex-1 h-11 px-3 bg-white border border-orange-500/15 rounded-xl flex items-center justify-center gap-2 shadow-sm text-xs font-semibold text-[#44403C]">About</button>
              <button onClick={() => setShowConfig(!showConfig)} className="flex-1 h-11 px-3 bg-white border border-orange-500/15 rounded-xl flex items-center justify-center gap-2 shadow-sm text-xs font-semibold text-[#44403C]">Config</button>
            </div>
            <div className="space-y-3 bg-stone-50 p-4 rounded-xl border border-orange-500/15">
              <div className="flex justify-between items-center text-xs font-medium text-stone-600">
                <span>Top-K Sources</span>
                <span className="font-mono text-orange-600 font-bold">{topK}</span>
              </div>
              <input 
                type="range" 
                min="1" 
                max="10" 
                value={topK} 
                onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                className="w-full accent-orange-500 cursor-pointer" 
              />
            </div>
            <div className="flex flex-col gap-4">
              <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-[#78716C]">Sources Used</span>
              {currentCitations.length === 0 ? (
                <p className="text-xs text-stone-500 italic">No statutory citations for this response.</p>
              ) : (
                currentCitations.map((c, i) => (
                  <div key={i} className="bg-white border border-orange-500/15 p-4 rounded-xl flex flex-col gap-2 shadow-sm">
                    <span className="px-2 py-0.5 bg-orange-500/10 border border-orange-500/20 rounded text-[10px] font-semibold uppercase tracking-[0.09em] text-orange-600 self-start">
                      {c.unit_number || c.law_title || "Statute"}
                    </span>
                    <p className="text-xs font-medium text-[#44403C]">{c.snippet}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* LEFT SIDEBAR - Silky Smooth Collapse & Expand */}
      <aside className={`hidden xl:flex ${collapsedLeft ? 'w-[68px] px-2.5' : 'w-[310px] px-6'} h-screen sticky top-0 bg-white flex-col justify-between py-6 border-r border-orange-500/15 shrink-0 z-40 overflow-x-hidden overflow-y-auto transition-all duration-300 ease-in-out`}>
        <div className="flex flex-col gap-8 w-full">
          
          {/* Header Logo Area */}
          <div className={`flex items-center w-full h-10 ${collapsedLeft ? 'justify-center' : 'justify-between'}`}>
            {!collapsedLeft && (
              <button 
                onClick={onGoHome} 
                className="text-2xl font-extrabold tracking-tight text-[#171717] hover:opacity-90 transition-all duration-300 ease-in-out text-left whitespace-nowrap overflow-hidden"
              >
                Ask <span className="text-orange-600">GST</span>
              </button>
            )}

            {/* Side Panel Collapse Toggle Button (No Tooltip) */}
            <button 
              onClick={() => setCollapsedLeft(!collapsedLeft)}
              className="w-9 h-9 hover:bg-orange-50 rounded-xl flex items-center justify-center text-orange-600 transition-all duration-300 ease-in-out shrink-0 cursor-pointer"
            >
              <svg className={`w-5 h-5 transform transition-transform duration-300 ease-in-out ${collapsedLeft ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7"></path>
              </svg>
            </button>
          </div>

          {!collapsedLeft ? (
            /* Expanded Left Sidebar Content */
            <div className="flex flex-col gap-6 w-full transition-all duration-300 ease-in-out">
              <button 
                onClick={onNewChat}
                className="w-full h-11 px-4 flex items-center justify-center gap-2 bg-gradient-to-r from-[#F54900] to-[#FF6900] text-white font-semibold text-xs rounded-xl shadow-md hover:opacity-95 transition-all transform active:scale-95 cursor-pointer whitespace-nowrap"
              >
                <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path>
                </svg>
                <span>Start New Chat</span>
              </button>

              <div className="flex flex-col gap-3">
                <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-[#78716C] px-1">RECENTS</span>
                <div className="flex flex-col gap-2">
                  {threads.length === 0 ? (
                    <p className="text-xs text-stone-400 italic px-1">No saved chats yet.</p>
                  ) : (
                    threads.map((thread) => (
                      <div 
                        key={thread.id}
                        onClick={() => onSelectThread(thread.id)}
                        className={`w-full p-2.5 rounded-xl border flex items-center justify-between gap-2 cursor-pointer transition-all group ${thread.id === activeThreadId ? 'bg-orange-500/10 border-orange-500/30 font-semibold' : 'bg-white border-stone-200/70 hover:border-orange-500/20 hover:bg-orange-50/30'}`}
                      >
                        <span className="text-xs font-medium text-[#44403C] line-clamp-2 leading-tight flex-1">{thread.title}</span>
                        
                        {/* Delete thread icon button on hover */}
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteThread(thread.id);
                          }}
                          title="Delete thread"
                          className="opacity-0 group-hover:opacity-100 p-1 hover:bg-orange-200/60 rounded-md text-stone-400 hover:text-orange-700 transition-all shrink-0 cursor-pointer"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                          </svg>
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* Collapsed Icon-Only View: Clean & Minimal (No chat lists or numbers) */
            <div className="flex flex-col items-center gap-5 w-full transition-all duration-300 ease-in-out">
              {/* Start New Chat Icon Button Only */}
              <div className="relative group">
                <button 
                  onClick={onNewChat}
                  className="w-10 h-10 bg-gradient-to-r from-[#F54900] to-[#FF6900] rounded-xl flex items-center justify-center text-white shadow-md hover:opacity-95 transition-all cursor-pointer"
                >
                  <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path>
                  </svg>
                </button>
                <div className="absolute top-1/2 left-full -translate-y-1/2 ml-3 px-3 py-1.5 bg-[#1C1917] text-white text-[11px] font-medium rounded-lg shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
                  Start New Chat
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Disclaimer & Clear History Button */}
        <div className="w-full flex flex-col gap-3 transition-all duration-300 ease-in-out">
          {!collapsedLeft && (
            <p className="text-[11px] font-medium font-mono text-[#57534E] opacity-50 leading-tight text-left px-1 transition-all duration-300 ease-in-out">
              Based on Acts, Rules, Notification and Circular till dated March 2026
            </p>
          )}

          {!collapsedLeft ? (
            <button 
              onClick={onClearHistory}
              className="w-full h-11 px-4 flex items-center justify-center gap-2 bg-white border border-stone-200/80 hover:border-orange-500/20 text-[#292524] font-semibold text-xs rounded-xl shadow-sm hover:bg-orange-50/50 transition-all cursor-pointer whitespace-nowrap"
            >
              <svg className="w-4 h-4 text-orange-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
              </svg>
              <span>Clear History</span>
            </button>
          ) : (
            <div className="relative group flex justify-center">
              <button 
                onClick={onClearHistory}
                className="w-10 h-10 bg-white border border-stone-200 hover:border-orange-300 rounded-xl flex items-center justify-center text-[#292524] shadow-sm hover:bg-orange-50 transition-all cursor-pointer"
              >
                <svg className="w-4 h-4 text-orange-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
              </button>
              <div className="absolute top-1/2 left-full -translate-y-1/2 ml-3 px-3 py-1.5 bg-[#1C1917] text-white text-[11px] font-medium rounded-lg shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
                Clear History
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* CENTER CHAT MAIN STREAM */}
      <main className="flex-1 flex flex-col min-h-screen bg-transparent">
        {/* Top Conversation Title Bar */}
        <div className="w-full h-[88px] bg-white px-6 lg:px-10 py-[30px] flex items-center justify-between border-b border-orange-500/10">
          <h1 className="text-base lg:text-lg font-bold text-[#44403C] tracking-tight truncate">
            {sessionTitle || "New Chat Session"}
          </h1>
        </div>

        {/* Scrollable Message Stream */}
        <div className="flex-1 flex flex-col justify-end">
          <div className="w-full max-w-[675px] mx-auto px-6 py-8 flex flex-col gap-8 custom-scrollbar">
            
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-4 py-16 text-center animate-fade-in">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-orange-600 to-orange-500 flex items-center justify-center text-white shadow-lg shadow-orange-500/20">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
                  </svg>
                </div>
                <h3 className="text-lg font-bold text-stone-800">Start a New GST Inquiry Thread</h3>
                <p className="text-xs text-stone-500 max-w-sm leading-relaxed">
                  Type your tax query below. A unique thread ID will be generated upon sending your first message.
                </p>
              </div>
            ) : (
              messages.map((msg) => (
                <React.Fragment key={msg.id}>
                  {msg.role === 'user' ? (
                    /* User Query Bubble */
                    <div className="flex flex-col items-end gap-2 w-full animate-fade-in">
                      <div className="p-4 bg-orange-500/15 border border-orange-500/15 rounded-2xl shadow-sm max-w-[80%]">
                        <p className="text-sm font-regular text-[#1C1917]">{msg.content}</p>
                      </div>
                      <div className="flex items-center gap-2 px-1">
                        <span className="text-[10px] font-semibold uppercase tracking-[0.05em] text-[#79716B]">{msg.timestamp}</span>
                        <svg className="w-3.5 h-3.5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                        </svg>
                      </div>
                    </div>
                  ) : (
                    /* Assistant RAG Response */
                    <div className="flex items-start gap-4 w-full animate-fade-in">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-r from-[#F54900] to-[#FE9A00] flex items-center justify-center text-white shrink-0 shadow-md">
                        <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                        </svg>
                      </div>
                      <div className="flex-1 flex flex-col gap-4">
                        <div className="bg-white border border-orange-500/15 p-6 rounded-2xl flex flex-col gap-4 shadow-sm">
                          <div 
                            className="prose prose-stone prose-sm max-w-none text-sm text-[#292524] leading-relaxed"
                            dangerouslySetInnerHTML={{ __html: marked.parse(msg.content || '') }}
                          />
                        </div>

                        {/* Citations Pill */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-orange-600">
                              {msg.citations.length} Citation{msg.citations.length > 1 ? 's' : ''} &amp; Sources found
                            </span>
                            <svg className="w-3.5 h-3.5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                          </div>
                        )}

                        <div className="flex items-center gap-2 px-1">
                          <span className="text-[10px] font-semibold uppercase tracking-[0.05em] text-[#79716B]">{msg.timestamp}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </React.Fragment>
              ))
            )}

            {loading && (
              <div className="flex items-start gap-4 w-full animate-fade-in">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-r from-[#F54900] to-[#FE9A00] flex items-center justify-center text-white shrink-0 shadow-md">
                  <svg className="w-5 h-5 text-white animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                  </svg>
                </div>
                <div className="bg-white border border-orange-500/15 p-5 rounded-2xl flex items-center gap-3 text-stone-700 text-sm shadow-sm">
                  <span className="font-medium text-xs sm:text-sm">{statusMessage || "Searching tax vector index & synthesizing answer..."}</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Bar Area - White Background */}
          <div className="sticky bottom-0 w-full px-6 py-4 flex items-center justify-center bg-transparent">
            <form onSubmit={handleSubmit} className="relative w-full max-w-[675px]">
              <input 
                type="text" 
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                placeholder="Ask follow-up query on GST Acts, Rules..." 
                className="w-full h-[84px] bg-white border border-orange-500/25 rounded-2xl px-6 pr-28 text-sm text-[#292524] placeholder-[#A6A09B] focus:outline-none focus:border-orange-500 shadow-md transition-all font-medium"
              />
              
              <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-3">
                {/* Attach File Button */}
                <div className="relative group">
                  <button 
                    type="button"
                    onClick={() => alert("File attached for legal reference.")}
                    className="w-10 h-10 bg-transparent border border-orange-500/15 rounded-xl flex items-center justify-center hover:bg-orange-50/50 transition-colors cursor-pointer"
                  >
                    <svg className="w-4 h-4 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"></path>
                    </svg>
                  </button>
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-1.5 bg-[#1C1917] text-white text-[11px] font-medium rounded-lg shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-30">
                    Attach File (.pdf, .csv, .png)
                  </div>
                </div>

                {/* Send Query Button */}
                <div className="relative group">
                  <button 
                    type="submit"
                    disabled={loading || !inputQuery.trim()}
                    className="w-10 h-10 bg-gradient-to-r from-[#F54900] to-[#E17100] rounded-xl flex items-center justify-center text-white shadow-sm hover:opacity-95 transition-all cursor-pointer disabled:opacity-50"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path>
                    </svg>
                  </button>
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-1.5 bg-[#1C1917] text-white text-[11px] font-medium rounded-lg shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-30">
                    Send Query
                  </div>
                </div>
              </div>
            </form>
          </div>

          {/* Footer Disclaimer */}
          <div className="w-full px-4 py-4 flex items-center justify-center text-center">
            <p className="text-[12px] font-medium font-mono text-[#78716C]">
              AI can make mistakes. Please verify with official <a href="https://www.cbic.gov.in" target="_blank" rel="noreferrer" className="underline hover:text-orange-600">CBIC sources</a>.
            </p>
          </div>
        </div>
      </main>

      {/* RIGHT SIDEBAR - Stitched Flush to Right Edge */}
      <aside className="hidden xl:flex w-[310px] h-screen sticky top-0 bg-white flex-col py-[22px] px-[24px] gap-[38px] border-l border-orange-500/10 shrink-0 z-50 overflow-y-auto">
        {/* Top Navigation controls */}
        <div className="flex items-center justify-end gap-3 relative">
          {/* About Button */}
          <div className="relative group">
            <button 
              onClick={onOpenAbout}
              className="h-11 px-4 bg-white border border-orange-500/15 rounded-xl flex items-center gap-2 shadow-sm hover:bg-orange-50 transition-all cursor-pointer"
            >
              <svg className="w-4 h-4 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
              </svg>
              <span className="text-xs font-semibold text-[#44403C]">About</span>
            </button>
            <div className="absolute top-full right-0 mt-2 px-3 py-1.5 bg-[#1C1917] text-white text-[11px] font-medium rounded-lg shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-30">
              About GST RAG
            </div>
          </div>

          {/* Config Button */}
          <div className="relative group">
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setShowConfig(!showConfig);
              }}
              className="h-11 px-4 bg-white border border-orange-500/15 rounded-xl flex items-center gap-2 shadow-sm hover:bg-orange-50 transition-all cursor-pointer"
            >
              <svg className="w-4 h-4 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
              </svg>
              <span className="text-xs font-semibold text-[#44403C]">Config</span>
            </button>
            <div className="absolute top-full right-0 mt-2 px-3 py-1.5 bg-[#1C1917] text-white text-[11px] font-medium rounded-lg shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-30">
              System Configuration
            </div>
          </div>

          {/* GitHub Button */}
          <div className="relative group">
            <a 
              href="https://github.com" 
              target="_blank" 
              rel="noreferrer"
              className="w-11 h-11 bg-white border border-orange-500/15 rounded-xl flex items-center justify-center shadow-sm hover:bg-orange-50 transition-all"
            >
              <svg className="w-5 h-5 text-[#44403C]" fill="currentColor" viewBox="0 0 24 24">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"></path>
              </svg>
            </a>
            <div className="absolute top-full right-0 mt-2 px-3 py-1.5 bg-[#1C1917] text-white text-[11px] font-medium rounded-lg shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-30">
              GitHub Repository
            </div>
          </div>
        </div>

        {/* Sources Used Panel */}
        <div className="flex flex-col gap-5 w-full">
          <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-[#78716C]">
            Sources Used ({currentCitations.length})
          </span>
          {currentCitations.length === 0 ? (
            <p className="text-xs text-[#78716C] italic">No sources retrieved for current query.</p>
          ) : (
            <div className="flex flex-col gap-4">
              {currentCitations.map((citation, idx) => {
                const isExpanded = expandedSourceIndex === idx;
                return (
                  <div key={idx} className="bg-white border border-orange-500/15 p-4 rounded-xl flex flex-col gap-3 relative overflow-hidden shadow-sm">
                    <div className="flex items-center justify-between">
                      <span className="px-2 py-0.5 bg-orange-500/10 border border-orange-500/20 rounded text-[10px] font-semibold uppercase tracking-[0.09em] text-orange-600">
                        {citation.unit_number || citation.law_title || `Source #${idx + 1}`}
                      </span>
                    </div>
                    <div className="relative">
                      <p className={`text-xs font-medium text-[#44403C] leading-relaxed ${isExpanded ? '' : 'line-clamp-3'}`}>
                        {citation.snippet}
                      </p>
                    </div>
                    <button 
                      onClick={() => setExpandedSourceIndex(isExpanded ? null : idx)}
                      className="text-[11px] font-semibold text-orange-600 self-start mt-1 hover:underline cursor-pointer"
                    >
                      {isExpanded ? 'Show less' : 'Expand'}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>

      {/* Render ConfigModal at root level of ChatSession so parent overflow-y-auto never clips it! */}
      <ConfigModal 
        isOpen={showConfig}
        onClose={() => setShowConfig(false)}
        topK={topK}
        setTopK={setTopK}
        apiHealth={apiHealth}
        onReindex={onReindex}
        reindexing={reindexing}
      />

    </div>
  );
}
