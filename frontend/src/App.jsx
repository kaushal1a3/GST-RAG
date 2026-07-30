import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useParams, Navigate } from 'react-router-dom';
import LandingPage from './components/LandingPage';
import ChatSession from './components/ChatSession';
import AboutModal from './components/AboutModal';
import './index.css';

const generateUniqueThreadId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return 'chat-' + crypto.randomUUID().substring(0, 8);
  }
  return 'chat-' + Date.now().toString(36) + Math.random().toString(36).substring(2, 6);
};

const DEFAULT_INITIAL_THREADS = [];

function ChatContainer({ 
  threads, 
  setThreads, 
  apiBaseUrl, 
  topK, 
  setTopK, 
  apiHealth, 
  onOpenAbout 
}) {
  const navigate = useNavigate();
  const { threadId } = useParams();

  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  const isNewSession = !threadId;

  // If threadId is provided in URL but does NOT exist in saved threads, redirect to /chat
  if (threadId && !threads.some(t => t.id === threadId)) {
    return <Navigate to="/chat" replace />;
  }

  const activeId = threadId || "new";
  const activeThread = isNewSession
    ? { id: "new", title: "New Chat Session", messages: [] }
    : (threads.find(t => t.id === activeId) || { id: activeId, title: "New Chat Session", messages: [] });

  const handleSendMessage = async (queryText) => {
    if (!queryText || !queryText.trim() || loading) return;
    const cleanQuery = queryText.trim();
    const currentTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    let targetId = activeId;

    // If sending first message in a /chat new session, dynamically create unique ID now
    if (isNewSession) {
      const generatedId = generateUniqueThreadId();
      targetId = generatedId;

      const userMsg = {
        id: `user-${Date.now()}`,
        role: "user",
        content: cleanQuery,
        timestamp: currentTime
      };

      const newThread = {
        id: generatedId,
        title: cleanQuery,
        createdAt: Date.now(),
        messages: [userMsg]
      };

      // Add to threads & update route to /chat/:generatedId
      setThreads(prev => [newThread, ...prev]);
      navigate(`/chat/${generatedId}`, { replace: true });
    } else {
      // Append user message to existing thread
      const userMsg = {
        id: `user-${Date.now()}`,
        role: "user",
        content: cleanQuery,
        timestamp: currentTime
      };

      setThreads((prevThreads) => 
        prevThreads.map((t) => {
          if (t.id === targetId) {
            const isTitleDefault = t.title === "New Chat Session" || t.messages.length === 0;
            return {
              ...t,
              title: isTitleDefault ? cleanQuery : t.title,
              messages: [...t.messages, userMsg]
            };
          }
          return t;
        })
      );
    }

    setLoading(true);
    setStatusMessage("Analyzing request with LLM Query Router...");

    try {
      const res = await fetch(`${apiBaseUrl}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: cleanQuery,
          top_k: parseInt(topK, 10)
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "API Server Error" }));
        throw new Error(errData.detail || `Server returned ${res.status}`);
      }

      const data = await res.json();

      const aiMsg = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: data.answer,
        citations: data.citations || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setThreads((prevThreads) => 
        prevThreads.map((t) => {
          if (t.id === targetId) {
            return {
              ...t,
              messages: [...t.messages, aiMsg]
            };
          }
          return t;
        })
      );
    } catch (err) {
      const errorMsg = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `⚠️ **Error processing request**: ${err.message}. Please verify the FastAPI backend is running.`,
        citations: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setThreads((prevThreads) => 
        prevThreads.map((t) => {
          if (t.id === targetId) {
            return {
              ...t,
              messages: [...t.messages, errorMsg]
            };
          }
          return t;
        })
      );
    } finally {
      setLoading(false);
      setStatusMessage("");
    }
  };

  const handleNewChat = () => {
    navigate('/chat');
  };

  const handleDeleteThread = (threadIdToDelete) => {
    const updatedThreads = threads.filter(t => t.id !== threadIdToDelete);
    setThreads(updatedThreads);

    if (activeId === threadIdToDelete) {
      if (updatedThreads.length > 0) {
        navigate(`/chat/${updatedThreads[0].id}`);
      } else {
        navigate('/chat');
      }
    }
  };

  const handleClearHistory = () => {
    setThreads([]);
    localStorage.removeItem("gst_rag_chat_threads");
    navigate('/chat');
  };

  return (
    <ChatSession 
      messages={activeThread.messages}
      sessionTitle={activeThread.title}
      onSendMessage={handleSendMessage}
      loading={loading}
      statusMessage={statusMessage}
      onNewChat={handleNewChat}
      onClearHistory={handleClearHistory}
      topK={topK}
      setTopK={setTopK}
      apiHealth={apiHealth}
      onOpenAbout={onOpenAbout}
      threads={threads}
      activeThreadId={activeId}
      onSelectThread={(id) => navigate(`/chat/${id}`)}
      onDeleteThread={handleDeleteThread}
      onGoHome={() => navigate('/')}
    />
  );
}

export default function App() {
  const navigate = useNavigate();

  // Load threads array from localStorage cache
  const [threads, setThreads] = useState(() => {
    try {
      const cached = localStorage.getItem("gst_rag_chat_threads");
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch (err) {
      console.warn("Could not load threads from localStorage", err);
    }
    return DEFAULT_INITIAL_THREADS;
  });

  const [topK, setTopK] = useState(5);
  const [apiHealth, setApiHealth] = useState(null);
  const [showAboutModal, setShowAboutModal] = useState(false);

  const [apiBaseUrl] = useState(() => {
    if (import.meta.env && import.meta.env.VITE_API_BASE_URL) {
      return import.meta.env.VITE_API_BASE_URL.replace(/\/+$/, '');
    }
    const isLocal = typeof window !== 'undefined' && (
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1' ||
      window.location.port === '8000' ||
      window.location.port === '5173'
    );
    return isLocal ? 'http://127.0.0.1:8000' : 'https://gst-rag-six.vercel.app';
  });


  // Persist threads to localStorage
  useEffect(() => {
    try {
      localStorage.setItem("gst_rag_chat_threads", JSON.stringify(threads));
    } catch (err) {
      console.warn("Could not persist threads to localStorage", err);
    }
  }, [threads]);

  // Fetch API Health status
  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, [apiBaseUrl]);

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/health`);
      if (res.ok) {
        const data = await res.json();
        setApiHealth(data);
      } else {
        setApiHealth({ status: "error" });
      }
    } catch (err) {
      setApiHealth({ status: "offline" });
    }
  };

  // Called when user submits query on LandingPage
  const handleStartChatFromLanding = (queryText) => {
    const cleanQuery = queryText ? queryText.trim() : "";

    if (!cleanQuery) {
      // If user just clicks "Start New Chat" with empty query, navigate to /chat
      navigate('/chat');
      return;
    }

    const newUniqueId = generateUniqueThreadId();
    const currentTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    const userMsg = {
      id: `user-${Date.now()}`,
      role: "user",
      content: cleanQuery,
      timestamp: currentTime
    };

    const newThread = {
      id: newUniqueId,
      title: cleanQuery,
      createdAt: Date.now(),
      messages: [userMsg]
    };

    setThreads(prev => [newThread, ...prev]);
    navigate(`/chat/${newUniqueId}`);

    // Fetch backend RAG answer
    fetch(`${apiBaseUrl}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: cleanQuery,
        top_k: parseInt(topK, 10)
      })
    })
    .then(res => res.json())
    .then(data => {
      const aiMsg = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: data.answer,
        citations: data.citations || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setThreads(prevThreads => 
        prevThreads.map(t => {
          if (t.id === newUniqueId) {
            return {
              ...t,
              messages: [...t.messages, aiMsg]
            };
          }
          return t;
        })
      );
    })
    .catch(err => {
      const errorMsg = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `⚠️ **Error processing request**: ${err.message}.`,
        citations: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setThreads(prevThreads => 
        prevThreads.map(t => {
          if (t.id === newUniqueId) {
            return {
              ...t,
              messages: [...t.messages, errorMsg]
            };
          }
          return t;
        })
      );
    });
  };

  return (
    <div className="min-h-screen bg-transparent text-[#1C1917] font-sans antialiased">
      <Routes>
        <Route 
          path="/" 
          element={
            <LandingPage 
              onStartChat={handleStartChatFromLanding}
              topK={topK}
              setTopK={setTopK}
              apiHealth={apiHealth}
              onOpenAbout={() => setShowAboutModal(true)}
            />
          } 
        />
        
        {/* /chat route renders new chat state */}
        <Route 
          path="/chat" 
          element={
            <ChatContainer 
              threads={threads}
              setThreads={setThreads}
              apiBaseUrl={apiBaseUrl}
              topK={topK}
              setTopK={setTopK}
              apiHealth={apiHealth}
              onOpenAbout={() => setShowAboutModal(true)}
            />
          } 
        />

        {/* /chat/:threadId route renders unique thread */}
        <Route 
          path="/chat/:threadId" 
          element={
            <ChatContainer 
              threads={threads}
              setThreads={setThreads}
              apiBaseUrl={apiBaseUrl}
              topK={topK}
              setTopK={setTopK}
              apiHealth={apiHealth}
              onOpenAbout={() => setShowAboutModal(true)}
            />
          } 
        />

        {/* Catch-all fallback redirects to /chat */}
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>

      <AboutModal 
        isOpen={showAboutModal}
        onClose={() => setShowAboutModal(false)}
      />
    </div>
  );
}
