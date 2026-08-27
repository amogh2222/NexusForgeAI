"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Loader2, Zap } from "lucide-react";
import { api } from "@/lib/api";

export default function ArchitecturePage() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [design, setDesign] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scale, setScale] = useState("10M_users");

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

  const generateDesign = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.intelligence.getSystemDesign({
        project_id: projectId,
        scale: scale
      });
      setDesign(result);
    } catch (err: any) {
      setError(err.message || "Failed to generate design");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col relative overflow-y-auto bg-slate-50">
        <header className="h-16 border-b border-slate-200 bg-white/80 backdrop-blur flex items-center px-6 justify-between z-10 sticky top-0 w-full shadow-sm">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-lg">System Architecture</h2>
            <div className="text-xs bg-indigo-100 text-indigo-700 px-3 py-1 rounded border border-indigo-200 font-medium">
              AI Generated
            </div>
          </div>
          <div className="flex items-center gap-4">
            <select 
              value={scale} 
              onChange={(e) => setScale(e.target.value)}
              className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm text-slate-900 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-sm transition-all cursor-pointer"
              disabled={loading}
            >
              <option value="1M_users">1M Users</option>
              <option value="10M_users">10M Users</option>
              <option value="100M_users">100M Users</option>
              <option value="1B_users">1B Users</option>
            </select>
            <button 
              onClick={generateDesign} 
              disabled={loading || !projectId}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors text-white shadow-sm"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
              Generate Design
            </button>
          </div>
        </header>

        <div className="flex-1 w-full p-8 max-w-5xl mx-auto">
          {!design && !loading && (
            <div className="text-center mt-20 text-slate-500">
              <Zap size={48} className="mx-auto mb-4 opacity-50 text-indigo-500" />
              <p>Click Generate Design to create a scalable architecture document based on your codebase.</p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 p-4 rounded-xl mb-6 shadow-sm">
              {error}
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center mt-20 text-slate-500">
              <Loader2 size={48} className="animate-spin mb-4 text-indigo-500" />
              <p>Analyzing codebase and generating architecture...</p>
              <p className="text-xs mt-2 opacity-60">This may take up to 30 seconds</p>
            </div>
          )}

          {design && !loading && (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <div className="glass p-8 rounded-2xl shadow-xl">
                <h1 className="text-3xl font-bold mb-2 text-slate-900">System Design for {scale.replace('_', ' ')}</h1>
                <p className="text-slate-600 mb-6">{design.executive_summary}</p>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Target Users</p>
                    <p className="font-semibold text-lg text-slate-900">{design.users}</p>
                  </div>
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Est. RPS</p>
                    <p className="font-semibold text-lg text-slate-900">{design.rps}</p>
                  </div>
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Est. Cost/Mo</p>
                    <p className="font-semibold text-emerald-600 text-lg">{design.cost_estimate}</p>
                  </div>
                </div>

                <div className="space-y-8">
                  <section>
                    <h3 className="text-xl font-semibold mb-3 border-b border-slate-200 pb-2 text-slate-800">Load Balancing</h3>
                    <p className="text-slate-600 leading-relaxed">{design.load_balancing}</p>
                  </section>
                  <section>
                    <h3 className="text-xl font-semibold mb-3 border-b border-slate-200 pb-2 text-slate-800">Database Strategy</h3>
                    <p className="text-slate-600 leading-relaxed">{design.database_strategy}</p>
                  </section>
                  <section>
                    <h3 className="text-xl font-semibold mb-3 border-b border-slate-200 pb-2 text-slate-800">Cache Layer</h3>
                    <p className="text-slate-600 leading-relaxed">{design.cache_layer}</p>
                  </section>
                  <section>
                    <h3 className="text-xl font-semibold mb-3 border-b border-slate-200 pb-2 text-slate-800">Queue & Async</h3>
                    <p className="text-slate-600 leading-relaxed">{design.queue_design}</p>
                  </section>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
