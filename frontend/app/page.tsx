"use client";
import { useState, useRef, useEffect } from "react";
import { Send, ChevronRight, Loader2, Bot, User, Swords, ArrowRight, RefreshCw } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Message = { role: "user" | "assistant"; content: string };
type AppState = "username_input" | "setting_up" | "chat";

const SUGGESTED = [
  "Why do I keep losing? What is my biggest weakness?",
  "Which opening should I stop playing?",
  "Do I perform better as White or Black?",
  "What patterns do you see in my endgame losses?",
  "Give me a personalized study plan for this week",
];

// ── Username input screen ────────────────────────────────────────────
function UsernameScreen({
  onReady,
}: {
  onReady: (username: string, totalGames: number) => void;
}) {
  const [username,  setUsername]  = useState("");
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState("");
  const [status,    setStatus]    = useState("");

  async function handleStart() {
    const u = username.trim().toLowerCase();
    if (!u) return;

    setLoading(true);
    setError("");
    setStatus("Checking if your games are already indexed...");

    try {
      // First check if already set up
      const checkRes  = await fetch(`${API}/check/${u}`);
      const checkData = await checkRes.json();

      if (checkData.ready) {
        onReady(u, checkData.total_games);
        return;
      }

      // Need to set up — this takes ~30-60s
      setStatus("Fetching your games from Chess.com...");

      const setupRes = await fetch(`${API}/setup/${u}`, { method: "POST" });

      if (!setupRes.ok) {
        const err = await setupRes.json();
        throw new Error(err.detail || "Setup failed");
      }

      const setupData = await setupRes.json();
      setStatus(`✓ Indexed ${setupData.total_games} games!`);
      setTimeout(() => onReady(u, setupData.total_games), 800);

    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setError(msg);
      setLoading(false);
      setStatus("");
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="text-center mb-10">
          <div className="w-16 h-16 rounded-2xl bg-purple-600/20 border border-purple-500/30 flex items-center justify-center mx-auto mb-4">
            <Swords size={28} className="text-purple-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">ChessCoach AI</h1>
          <p className="text-gray-400 text-sm mt-2">
            Enter your Chess.com username to analyze your games
          </p>
        </div>

        {/* Input */}
        <div className="space-y-3">
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && handleStart()}
            placeholder="your chess.com username"
            disabled={loading}
            className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors disabled:opacity-50"
          />

          <button
            onClick={handleStart}
            disabled={loading || !username.trim()}
            className="w-full bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl px-4 py-3 text-white font-medium flex items-center justify-center gap-2 transition-colors"
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>{status || "Setting up..."}</span>
              </>
            ) : (
              <>
                <span>Analyze My Games</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>

          {error && (
            <p className="text-red-400 text-sm text-center">{error}</p>
          )}
        </div>

        <p className="text-center text-xs text-gray-600 mt-6">
          Uses your public Chess.com game history · No account needed
        </p>
      </div>
    </div>
  );
}

// ── Main chat screen ─────────────────────────────────────────────────
function ChatScreen({
  username,
  totalGames,
  onReset,
}: {
  username:   string;
  totalGames: number;
  onReset:    () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input,    setInput]    = useState("");
  const [loading,  setLoading]  = useState(false);
  const bottomRef               = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(question: string) {
    if (!question.trim() || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/ask`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ question, username }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error connecting to backend." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">

      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-purple-600 flex items-center justify-center">
          <Swords size={18} />
        </div>
        <div>
          <h1 className="font-semibold text-white leading-none">ChessCoach AI</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            Analyzing <span className="text-purple-400 font-medium">{username}</span>
          </p>
        </div>
        <span className="ml-auto text-xs bg-green-900 text-green-300 px-2 py-1 rounded-full">
          {totalGames} games indexed
        </span>
        <button
          onClick={onReset}
          title="Switch user"
          className="ml-2 p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
        >
          <RefreshCw size={14} />
        </button>
      </header>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6 max-w-3xl mx-auto w-full">

        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-2xl bg-purple-600/20 border border-purple-500/30 flex items-center justify-center mx-auto mb-4">
              <Swords size={28} className="text-purple-400" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Ask about your chess</h2>
            <p className="text-gray-400 text-sm mb-8 max-w-md mx-auto">
              I&apos;ve analyzed all {totalGames} of {username}&apos;s Chess.com games.
            </p>
            <div className="grid gap-2 max-w-lg mx-auto">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="flex items-center gap-2 text-left px-4 py-3 rounded-xl border border-gray-700 hover:border-purple-500 hover:bg-purple-500/10 transition-all text-sm text-gray-300 hover:text-white group"
                >
                  <ChevronRight size={14} className="text-gray-500 group-hover:text-purple-400 flex-shrink-0" />
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-lg bg-purple-600 flex items-center justify-center flex-shrink-0 mt-1">
                <Bot size={14} />
              </div>
            )}
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-purple-600 text-white rounded-br-sm"
                : "bg-gray-800 text-gray-100 rounded-bl-sm"
            }`}>
              {msg.content}
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-lg bg-gray-700 flex items-center justify-center flex-shrink-0 mt-1">
                <User size={14} />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-lg bg-purple-600 flex items-center justify-center flex-shrink-0">
              <Bot size={14} />
            </div>
            <div className="bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-purple-400" />
              <span className="text-sm text-gray-400">Analyzing your games...</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 px-4 py-4">
        <div className="max-w-3xl mx-auto flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
            placeholder="Ask about your chess games..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 transition-colors"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
            className="w-11 h-11 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors flex-shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
        <p className="text-center text-xs text-gray-600 mt-2">
          Answers grounded in real Chess.com game history
        </p>
      </div>
    </div>
  );
}

// ── Root component ───────────────────────────────────────────────────
export default function Home() {
  const [appState,   setAppState]   = useState<AppState>("username_input");
  const [username,   setUsername]   = useState("");
  const [totalGames, setTotalGames] = useState(0);

  function handleReady(u: string, games: number) {
    setUsername(u);
    setTotalGames(games);
    setAppState("chat");
  }

  function handleReset() {
    setAppState("username_input");
    setUsername("");
    setTotalGames(0);
  }

  if (appState === "username_input") {
    return <UsernameScreen onReady={handleReady} />;
  }

  return (
    <ChatScreen
      username={username}
      totalGames={totalGames}
      onReset={handleReset}
    />
  );
}