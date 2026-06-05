"use client";
import { useState, useRef, useEffect } from "react";
import { Send, ChevronRight, Loader2, Bot, User, Swords } from "lucide-react";

const API = "http://localhost:8000";

type Message = {
  role: "user" | "assistant";
  content: string;
};

const SUGGESTED = [
  "Why do I keep losing? What is my biggest weakness?",
  "Which opening should I stop playing?",
  "Do I perform better as White or Black?",
  "What patterns do you see in my endgame losses?",
  "Give me a personalized study plan for this week",
];

export default function Home() {
  const [messages, setMessages]   = useState<Message[]>([]);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);
  const bottomRef                 = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(question: string) {
    if (!question.trim() || loading) return;

    const userMsg: Message = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error connecting to backend. Make sure FastAPI is running on port 8000." },
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
          <p className="text-xs text-gray-400 mt-0.5">Powered by your real game history</p>
        </div>
        <span className="ml-auto text-xs bg-green-900 text-green-300 px-2 py-1 rounded-full">
          275 games indexed
        </span>
      </header>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6 max-w-3xl mx-auto w-full">

        {/* Empty state */}
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-2xl bg-purple-600/20 border border-purple-500/30 flex items-center justify-center mx-auto mb-4">
              <Swords size={28} className="text-purple-400" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Ask about your chess</h2>
            <p className="text-gray-400 text-sm mb-8 max-w-md mx-auto">
              I&apos;ve analyzed all 275 of your Chess.com games.
            </p>

            {/* Suggested questions */}
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

        {/* Messages */}
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

        {/* Loading */}
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
          Answers are grounded in your real Chess.com game history
        </p>
      </div>

    </div>
  );
}