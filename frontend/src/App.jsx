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

async function sendQueryRequest(apiBaseUrl, question, topK) {
  const payload = JSON.stringify({
    question: question,
    top_k: parseInt(topK, 10)
  });
  const headers = { "Content-Type": "application/json" };

  // Always POST to /api/query — this is the Vercel serverless function route.
  // Do NOT attempt /query first; on Vercel that path serves static files and
  // returns 405 for POST requests.
  const res = await fetch(`${apiBaseUrl}/api/query`, {
    method: "POST",
    headers,
    body: payload,
  }).catch(() => null);

  if (!res) {
    throw new Error("Unable to connect to backend server. Please check if the FastAPI backend is running.");
  }

  const rawText = await res.text();
  if (!rawText || !rawText.trim()) {
    throw new Error(`Server returned HTTP ${res.status} with an empty response.`);
  }

  let data;
  try {
    data = JSON.parse(rawText);
  } catch (e) {
    throw new Error(`Server returned invalid non-JSON output (HTTP ${res.status}): ${rawText.substring(0, 100)}`);
  }

  if (!res.ok) {
    throw new Error(data.detail || data.message || `Server returned error ${res.status}`);
  }

  return data;
}

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
      const data = await sendQueryRequest(apiBaseUrl, cleanQuery, topK);

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
        content: `⚠️ **Error processing request**: ${err.message}`,
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

  const handleRenameThread = (threadIdToRename, newTitle) => {
    if (!newTitle || !newTitle.trim()) return;
    const cleanTitle = newTitle.trim();
    setThreads((prevThreads) =>
      prevThreads.map((t) => (t.id === threadIdToRename ? { ...t, title: cleanTitle } : t))
    );
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
      onRenameThread={handleRenameThread}
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
    const isLocal = typeof window !== 'undefined' && (
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1' ||
      window.location.hostname.startsWith('192.168.') ||
      window.location.port === '8000' ||
      window.location.port === '5173'
    );

    if (isLocal) {
      if (import.meta.env && import.meta.env.VITE_API_BASE_URL && (import.meta.env.VITE_API_BASE_URL.includes('localhost') || import.meta.env.VITE_API_BASE_URL.includes('127.0.0.1'))) {
        return import.meta.env.VITE_API_BASE_URL.replace(/\/+$/, '');
      }
      return 'http://127.0.0.1:8000';
    }

    if (import.meta.env && import.meta.env.VITE_API_BASE_URL && import.meta.env.VITE_API_BASE_URL.trim()) {
      return import.meta.env.VITE_API_BASE_URL.replace(/\/+$/, '');
    }

    return typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8000';
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
      // Always call /api/health — the Vercel serverless function route.
      const res = await fetch(`${apiBaseUrl}/api/health`).catch(() => null);

      if (res && res.ok) {
        const data = await res.json();
        setApiHealth(data);
      } else {
        setApiHealth({ status: "offline" });
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

    // Fetch backend RAG answer via sendQueryRequest
    sendQueryRequest(apiBaseUrl, cleanQuery, topK)
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
          content: `⚠️ **Error processing request**: ${err.message}`,
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
