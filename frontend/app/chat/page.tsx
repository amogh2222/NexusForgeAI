"use client";

import React, { useState, useEffect, useRef } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Send, Bot, User, Settings, Play, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";

export default function ChatPage() {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [projectId, setProjectId] = useState<string | null>(null);
  const [agentLogs, setAgentLogs] = useState<any[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [isAgentThinking, setIsAgentThinking] = useState(false);
  const threadId = useRef(`thread-${Math.random().toString(36).substring(7)}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // WebSocket Integration
  const { isConnected, lastEvent } = useWebSocket(projectId, threadId.current);

  // Initialize Project and load initial history
  useEffect(() => {
    async function init() {
      try {
        const projects = await api.projects.list();
        if (projects && projects.length > 0) {
          const pid = projects[0].id;
          setProjectId(pid);
          
          // Initial load
          const [history, logs] = await Promise.all([
            api.chat.getHistory(threadId.current),
            api.agents.getLogs(pid, 20)
          ]);
          if (history && history.length > 0) setMessages(history);
          if (logs) setAgentLogs(logs);
        }
      } catch (err) {
        console.error("Failed to load project:", err);
      }
    }
    init();
  }, []);

  // Handle Real-Time WebSocket Events
  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent.type === 'token') {
      setIsAgentThinking(false);
      setMessages((prev) => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg && lastMsg.role.toLowerCase() !== 'user' && lastMsg.isStreaming) {
          // Append to existing streaming message
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...lastMsg,
            content: lastMsg.content + lastEvent.content,
            agent_name: lastEvent.agent_name || lastMsg.agent_name
          };
          return updated;
        } else {
          // Create new streaming message
          return [...prev, {
            id: Math.random().toString(),
            role: 'ASSISTANT',
            content: lastEvent.content,
            agent_name: lastEvent.agent_name || 'Agent',
            isStreaming: true
          }];
        }
      });
    } else if (lastEvent.type === 'agent_start') {
      setIsAgentThinking(true);
      setAgentLogs(prev => [{
        id: Math.random().toString(),
        agent_name: lastEvent.agent_name,
        action: lastEvent.action,
        status: 'running',
        created_at: new Date().toISOString()
      }, ...prev].slice(0, 20));
    } else if (lastEvent.type === 'agent_end') {
      setAgentLogs(prev => prev.map(log => 
        log.agent_name === lastEvent.agent_name && log.status === 'running'
          ? { ...log, status: 'success', output_summary: lastEvent.output_summary }
          : log
      ));
      // End streaming state for the last message
      setMessages(prev => {
        const updated = [...prev];
        const lastMsg = updated[updated.length - 1];
        if (lastMsg && lastMsg.isStreaming) {
          lastMsg.isStreaming = false;
        }
        return updated;
      });
      setIsAgentThinking(false);
    }
  }, [lastEvent]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isAgentThinking]);

  const handleSend = async () => {
    if (!input.trim() || !projectId) return;
    
    const userMsg = { role: "user", content: input, agent_name: "User", created_at: new Date().toISOString(), id: Math.random().toString() };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsSending(true);
    setIsAgentThinking(true);
    
    try {
      await api.chat.sendMessage({
        project_id: projectId,
        thread_id: threadId.current,
        content: userMsg.content,
      });
    } catch (err) {
      console.error("Failed to send message:", err);
      setIsAgentThinking(false);
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
            <div className="flex gap-2 items-center">
              <div className="px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-600 border border-emerald-500/30">
                Active Project: {projectId ? "Connected" : "Loading..."}
              </div>
              {isConnected ? (
                <div className="px-2 py-0.5 rounded text-xs bg-blue-500/10 text-blue-600 border border-blue-500/20 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                  WS Connected
                </div>
              ) : (
                <div className="px-2 py-0.5 rounded text-xs bg-amber-500/10 text-amber-600 border border-amber-500/20">
                  WS Connecting...
                </div>
              )}
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
                    {msg.isStreaming && (
                      <motion.span 
                        animate={{ opacity: [1, 0, 1] }} 
                        transition={{ repeat: Infinity, duration: 0.8 }}
                        className="inline-block w-1.5 h-4 ml-1 bg-slate-400 translate-y-1"
                      />
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
          
          {isAgentThinking && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-4 max-w-4xl"
            >
              <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-purple-600">
                <Bot size={16} className="text-white" />
              </div>
              <div className="flex flex-col items-start">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-slate-500 font-medium">Agent</span>
                </div>
                <div className="p-4 rounded-2xl shadow-sm bg-white border border-slate-200 text-slate-800 flex gap-1">
                  <motion.div animate={{ y: [0, -3, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0 }} className="w-1.5 h-1.5 bg-slate-400 rounded-full" />
                  <motion.div animate={{ y: [0, -3, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }} className="w-1.5 h-1.5 bg-slate-400 rounded-full" />
                  <motion.div animate={{ y: [0, -3, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }} className="w-1.5 h-1.5 bg-slate-400 rounded-full" />
                </div>
              </div>
            </motion.div>
          )}
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
