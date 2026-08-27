"use client";

import React, { useState, useEffect, useRef } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Send, Bot, User, Settings, Play, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";

export default function ChatPage() {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [projectId, setProjectId] = useState<string | null>(null);
  const [agentLogs, setAgentLogs] = useState<any[]>([]);
  const [isSending, setIsSending] = useState(false);
  const threadId = useRef(`thread-${Math.random().toString(36).substring(7)}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize Project
  useEffect(() => {
    async function init() {
      try {
        const projects = await api.projects.list();
        if (projects && projects.length > 0) {
          setProjectId(projects[0].id);
        }
      } catch (err) {
        console.error("Failed to load project:", err);
      }
    }
    init();
  }, []);

  // Poll Chat History & Agent Logs
  useEffect(() => {
    if (!projectId) return;

    async function pollData() {
      try {
        const [history, logs] = await Promise.all([
          api.chat.getHistory(threadId.current),
          api.agents.getLogs(projectId as string, 20)
        ]);
        if (history && history.length > 0) {
          setMessages(history);
        }
        if (logs) setAgentLogs(logs);
      } catch (err) {
        // ignore polling errors
      }
    }

    pollData();
    const interval = setInterval(pollData, 3000);
    return () => clearInterval(interval);
  }, [projectId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !projectId) return;
    
    const userMsg = { role: "user", content: input, agent_name: "User", created_at: new Date().toISOString(), id: Math.random().toString() };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsSending(true);
    
    try {
      await api.chat.sendMessage({
        project_id: projectId,
        thread_id: threadId.current,
        content: userMsg.content,
      });
      // Polling will catch the response
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col relative bg-slate-50">
        <header className="h-16 border-b border-slate-200 bg-white/80 backdrop-blur flex items-center px-6 justify-between z-10 shadow-sm">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-lg">Agent Workspace</h2>
            <div className="px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              Active Project: {projectId ? "Connected" : "Loading..."}
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && (
            <div className="text-center text-slate-400 mt-20">
              <Bot size={48} className="mx-auto mb-4 opacity-50 text-indigo-500" />
              <p className="text-slate-600">Hello! I&apos;m NexusForge AI. How can I help you scale this repository?</p>
            </div>
          )}
          {messages.map((msg, i) => {
            const isUser = msg.role.toLowerCase() === "user";
            return (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                key={msg.id || i} 
                className={`flex gap-4 max-w-4xl ${isUser ? "ml-auto flex-row-reverse" : ""}`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  isUser ? "bg-blue-600" : "bg-purple-600"
                }`}>
                  {isUser ? <User size={16} /> : <Bot size={16} />}
                </div>
                <div className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-slate-500 font-medium">{msg.agent_name || (isUser ? 'User' : 'Agent')}</span>
                  </div>
                  <div className={`p-4 rounded-2xl whitespace-pre-wrap shadow-sm ${
                    isUser 
                      ? "bg-blue-600 text-white" 
                      : "bg-white border border-slate-200 text-slate-800"
                  }`}>
                    {msg.content}
                  </div>
                </div>
              </motion.div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-6 bg-white border-t border-slate-200">
          <div className="max-w-4xl mx-auto relative group">
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-blue-500 rounded-xl blur opacity-10 group-hover:opacity-20 transition-opacity" />
            <div className="relative flex items-center bg-slate-50 rounded-xl border border-slate-300 p-2 shadow-sm focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Ask agents to review code, generate docs, or fix bugs..."
                className="flex-1 bg-transparent border-none outline-none px-4 text-slate-900 placeholder-slate-400"
                disabled={isSending}
              />
              <button 
                onClick={handleSend}
                disabled={isSending || !input.trim()}
                className="p-2 rounded-lg bg-purple-600 hover:bg-purple-700 text-white transition-colors disabled:opacity-50"
              >
                {isSending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
              </button>
            </div>
          </div>
        </div>
      </main>

      <aside className="w-80 border-l border-slate-200 bg-white flex flex-col z-10 shadow-[-4px_0_24px_rgba(0,0,0,0.02)]">
        <div className="p-4 border-b border-slate-200 bg-slate-50/50">
          <h3 className="font-semibold text-sm text-slate-500 uppercase tracking-wider">Live Agent Graph</h3>
        </div>
        <div className="p-4 flex-1 overflow-y-auto space-y-4">
          {agentLogs.length === 0 ? (
            <p className="text-slate-400 text-sm text-center mt-10">No recent agent activity</p>
          ) : (
            agentLogs.map((log) => (
              <motion.div initial={{opacity:0, x:20}} animate={{opacity:1, x:0}} key={log.id} className={`bg-white shadow-sm p-3 rounded-lg border-l-4 border-y border-r border-slate-100 ${log.status === 'error' ? 'border-l-red-500' : 'border-l-indigo-500'}`}>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-semibold text-indigo-600">{log.agent_name}</span>
                  <span className={`text-xs flex items-center gap-1 font-medium ${log.status === 'running' ? 'text-blue-500 animate-pulse' : 'text-slate-500'}`}>
                    {log.status === 'running' && <Play size={10} />} {log.status}
                  </span>
                </div>
                <p className="text-xs text-slate-600">{log.action}</p>
                {log.output_summary && <p className="text-xs text-slate-500 mt-2 line-clamp-2">{log.output_summary}</p>}
              </motion.div>
            ))
          )}
        </div>
      </aside>
    </div>
  );
}
