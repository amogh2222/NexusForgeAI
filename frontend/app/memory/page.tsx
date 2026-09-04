"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Search, Database, FileCode2, Network, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";

export default function MemoryPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{
    points_count?: number;
    vectors_count?: number;
    status?: string;
  } | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const projects = await api.projects.list();
        if (projects && projects.length > 0) {
          const pid = projects[0].id;
          setProjectId(pid);
          try {
            const st = await api.memory.getStats(pid);
            setStats(st);
          } catch (e) {
            console.warn("Could not fetch memory stats", e);
          }
        }
      } catch (err) {
        console.error("Failed to load project:", err);
      }
    }
    init();
  }, []);

  const handleSearch = async () => {
    if (!query || !projectId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.memory.retrieve(projectId, query, 10);
      if (res && res.context) {
        setResults(res.context);
      } else {
        setResults([]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to search memory");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col md:flex-row h-[100dvh] w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-8 pb-nav md:pb-8 relative min-w-0 bg-slate-50">
        <header className="h-14 sm:h-16 border-b border-slate-200 bg-white/80 backdrop-blur flex items-center px-4 md:px-6 justify-between z-10 sticky top-0 shadow-xs">
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            <h2 className="font-semibold text-base sm:text-lg">Memory Explorer</h2>
            {typeof window !== "undefined" && localStorage.getItem("nexusforge_active_repo_name") && (
              <div className="px-2 py-0.5 rounded text-[11px] sm:text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                Repo: {localStorage.getItem("nexusforge_active_repo_name")}
              </div>
            )}
          </div>
          <div className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm text-slate-500">
            <Database size={15} />
            <span className="hidden xs:inline">Qdrant HNSW:</span>{" "}
            <strong className="text-emerald-700 font-medium">
              {stats ? `${stats.points_count ?? 0} vectors (${stats.status || "indexed"})` : "Connected"}
            </strong>
          </div>
        </header>

        <div className="p-2 sm:p-4 md:p-8 max-w-5xl mx-auto w-full">
          {/* Search Bar */}
          <div className="relative group mb-6 sm:mb-8">
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-blue-500 rounded-xl blur opacity-10 transition-opacity" />
            <div className="relative flex items-center bg-white rounded-xl border border-slate-300 p-1.5 sm:p-2 shadow-xs focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all">
              <Search className="text-slate-400 ml-2 shrink-0" size={18} />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="Semantic search across repository codebase..."
                className="flex-1 bg-transparent border-none outline-none px-2 sm:px-4 text-slate-900 placeholder-slate-400 h-9 sm:h-10 text-sm sm:text-base min-w-0"
                disabled={loading}
              />
              <button 
                onClick={handleSearch}
                disabled={loading || !query.trim()}
                className="px-4 sm:px-6 py-1.5 sm:py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium text-xs sm:text-sm transition-colors flex items-center gap-1.5 min-h-[36px] touch-manipulation shrink-0"
              >
                {loading && <Loader2 size={15} className="animate-spin" />}
                <span>Search</span>
              </button>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 p-4 rounded-xl mb-6 shadow-sm">
              {error}
            </div>
          )}

          {/* Results Area */}
          <div className="space-y-4">
            {results.map((res, i) => (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                key={i} 
                className="glass rounded-xl p-5 shadow-md"
              >
                <div className="flex justify-between items-center mb-3">
                  <div className="flex items-center gap-2 text-indigo-600 text-sm font-medium">
                    <FileCode2 size={16} />
                    {res.file_path}
                  </div>
                  <div className="flex items-center gap-1 text-xs px-2 py-1 bg-slate-100 rounded text-slate-600 border border-slate-200 shadow-sm">
                    <Network size={12} className="text-emerald-500" />
                    Score: {res.score ? res.score.toFixed(3) : "N/A"}
                  </div>
                </div>
                <pre className="p-4 bg-slate-50 rounded-lg text-sm text-slate-800 overflow-x-auto border border-slate-200 whitespace-pre-wrap shadow-inner">
                  <code>{res.content}</code>
                </pre>
              </motion.div>
            ))}

            {results.length === 0 && !loading && (
              <div className="text-center text-slate-400 mt-20">
                <Database size={48} className="mx-auto mb-4 opacity-20 text-indigo-500" />
                <p className="text-slate-500">Enter a query to search the semantic vector space.</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
