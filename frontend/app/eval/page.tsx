"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Beaker, Play, Loader2, CheckCircle2, AlertCircle, BarChart3, Activity, ChevronDown, ChevronUp } from "lucide-react";
import { api, getAuthToken } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const TEST_CASES = [
  { id: "readme-001", title: "Production README Generation", desc: "Generates a complete, accurate README.md based on repo contents." },
  { id: "bugfix-001", title: "SQL Injection Fix", desc: "Detects and patches a SQL injection vulnerability autonomously." },
  { id: "review-001", title: "Async Performance Review", desc: "Reviews Python code for blocking calls in async contexts." },
  { id: "arch-001", title: "CQRS Architecture", desc: "Explains the CQRS architectural pattern as implemented in the code." },
  { id: "sysdesign-001", title: "Scale to 10K RPS", desc: "Designs a system architecture to handle 10K requests per second." }
];

export default function EvalPage() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedCaseId, setExpandedCaseId] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      try {
        let token = getAuthToken();
        if (!token) {
          window.location.href = "/auth";
          return;
        }
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

  const runBenchmark = async (caseId?: string) => {
    if (!projectId) return;
    setIsRunning(true);
    setError(null);
    setResults(null);
    
    try {
      const suiteId = `suite_${Date.now()}`;
      const payload: any = { suite_id: suiteId, project_id: projectId };
      if (caseId) payload.case_ids = [caseId];
      
      await api.evaluation.runBenchmark(payload);
      
      // Poll actual backend status with incremental real results
      let pollCount = 0;
      const poll = async () => {
        pollCount++;
        try {
          const statusRes = await api.evaluation.getStatus(suiteId);
          
          // Render real completed cases live as they finish
          if (statusRes && statusRes.runs && statusRes.runs.length > 0) {
            setResults({
              overall_score: Math.round(statusRes.mean_score || 0),
              pass_rate: statusRes.pass_rate || 0,
              cases: statusRes.runs.map((r: any) => ({
                id: r.case_id,
                name: r.case_name,
                status: r.passed ? "PASS" : "FAIL",
                score: Math.round(r.overall_score || 0),
                duration: `${((r.latency_ms || 1000) / 1000).toFixed(1)}s`,
                rubric_score: r.rubric_score,
                keyword_recall: r.keyword_recall,
                actual_output: r.actual_output || "*Execution in progress...*"
              }))
            });
          }

          if (statusRes.status === "complete") {
            setIsRunning(false);
          } else if (pollCount < 200) {
            // Keep polling while cases are executing in background (up to 5 mins)
            setTimeout(poll, 1500);
          } else {
            setError("Evaluation timed out after 5 minutes. The model may be busy.");
            setIsRunning(false);
          }
        } catch (e: any) {
          if (pollCount < 200) {
            setTimeout(poll, 1500);
          } else {
            setError("Failed to retrieve benchmark results from server: " + (e.message || e));
            setIsRunning(false);
          }
        }
      };

      setTimeout(poll, 1000);
      
    } catch (err: any) {
      setError(err.message || "Failed to start benchmark");
      setIsRunning(false);
    }
  };

  return (
    <div className="flex flex-col md:flex-row h-screen w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col relative bg-slate-50 overflow-y-auto min-w-0">
        <header className="min-h-[4rem] py-2.5 border-b border-slate-200 bg-white/80 backdrop-blur flex flex-wrap items-center px-4 md:px-6 justify-between z-10 sticky top-0 shadow-sm gap-2">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-lg flex items-center gap-2">
              <Beaker className="text-indigo-500" size={20} />
              Agent Evaluation Suite
            </h2>
            {!projectId && (
              <div className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700 border border-red-200 font-medium">
                No Active Project
              </div>
            )}
          </div>
          <button 
            onClick={() => runBenchmark()}
            disabled={isRunning || !projectId}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-colors disabled:opacity-50 font-medium text-sm shadow-md min-h-[40px]"
          >
            {isRunning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            Run All Benchmarks
          </button>
        </header>

        <div className="p-4 md:p-8 max-w-5xl mx-auto w-full">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div className="lg:col-span-2 glass bg-white/60 p-6 rounded-2xl border border-white/40 shadow-xl relative overflow-hidden">
              <div className="absolute top-0 right-0 p-32 bg-gradient-to-br from-indigo-500/10 to-purple-500/10 blur-3xl -z-10 rounded-full" />
              <h3 className="font-semibold text-xl text-slate-800 mb-2">Golden Test Cases</h3>
              <p className="text-slate-500 mb-6 text-sm">Evaluate the autonomous agent against standardized repository challenges to measure reasoning, coding, and debugging capabilities.</p>
              
              <div className="space-y-4">
                {TEST_CASES.map(tc => {
                  const res = results?.cases?.find((r: any) => r.id === tc.id);
                  return (
                    <motion.div 
                      key={tc.id}
                      className="flex flex-col rounded-xl border border-slate-200 bg-white shadow-sm hover:border-indigo-300 transition-colors overflow-hidden"
                    >
                      <div className="flex items-center justify-between p-4 cursor-pointer" onClick={() => res?.actual_output ? setExpandedCaseId(expandedCaseId === tc.id ? null : tc.id) : null}>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-semibold text-slate-800">{tc.title}</h4>
                            <span className="text-xs font-mono text-slate-400 bg-slate-100 px-1.5 rounded">{tc.id}</span>
                          </div>
                          <p className="text-sm text-slate-500">{tc.desc}</p>
                        </div>
                        
                        <div className="flex items-center gap-4 pl-4 ml-4 border-l border-slate-100">
                          {res ? (
                            <div className="flex items-center gap-3 text-right">
                              <div>
                                <div className="text-xs text-slate-400">Score</div>
                                <div className="font-semibold text-indigo-600">{res.score}/100</div>
                              </div>
                              <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center">
                                <CheckCircle2 size={18} />
                              </div>
                              <div className="text-slate-400">
                                {expandedCaseId === tc.id ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                              </div>
                            </div>
                          ) : (
                            <button 
                              onClick={(e) => { e.stopPropagation(); runBenchmark(tc.id); }}
                              disabled={isRunning || !projectId}
                              className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-100 text-slate-500 hover:bg-indigo-100 hover:text-indigo-600 transition-colors disabled:opacity-50"
                            >
                              <Play size={16} className="ml-0.5" />
                            </button>
                          )}
                        </div>
                      </div>

                      <AnimatePresence>
                        {expandedCaseId === tc.id && res?.actual_output && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="border-t border-slate-100 bg-slate-50 overflow-hidden"
                          >
                            <div className="p-6 prose prose-sm max-w-none prose-slate prose-pre:bg-slate-900 prose-pre:text-slate-100 text-xs">
                              <h5 className="text-slate-500 uppercase tracking-wider mb-4 border-b border-slate-200 pb-2">Agent Output</h5>
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {res.actual_output}
                              </ReactMarkdown>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  )
                })}
              </div>
            </div>
            
            <div className="flex flex-col gap-6">
              <div className="glass bg-white/60 p-6 rounded-2xl border border-white/40 shadow-xl flex flex-col items-center justify-center text-center min-h-[200px]">
                {results ? (
                  <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
                    <div className="text-6xl font-bold text-transparent bg-clip-text bg-gradient-to-br from-indigo-500 to-purple-600 mb-2">
                      {results.overall_score}
                    </div>
                    <div className="font-semibold text-slate-700">Overall Grade</div>
                    <div className="text-xs text-emerald-600 font-medium mt-1">Excellent Performance</div>
                  </motion.div>
                ) : (
                  <div className="text-slate-400 flex flex-col items-center">
                    <BarChart3 size={48} className="mb-3 opacity-30" />
                    <p className="text-sm font-medium">Run benchmarks to view score</p>
                  </div>
                )}
              </div>
              
              <div className="glass bg-white/60 p-6 rounded-2xl border border-white/40 shadow-xl">
                <h3 className="font-semibold text-slate-800 flex items-center gap-2 mb-4">
                  <Activity size={18} className="text-purple-500" />
                  Live Status
                </h3>
                {isRunning ? (
                  <div className="flex items-center gap-3 text-sm text-indigo-600 bg-indigo-50 p-3 rounded-lg border border-indigo-100">
                    <Loader2 size={16} className="animate-spin" />
                    Executing Agent Pipeline...
                  </div>
                ) : error ? (
                  <div className="flex items-center gap-3 text-sm text-red-600 bg-red-50 p-3 rounded-lg border border-red-100">
                    <AlertCircle size={16} />
                    {error}
                  </div>
                ) : results ? (
                  <div className="flex items-center gap-3 text-sm text-emerald-600 bg-emerald-50 p-3 rounded-lg border border-emerald-100">
                    <CheckCircle2 size={16} />
                    All checks completed
                  </div>
                ) : (
                  <div className="text-sm text-slate-500 p-3 bg-slate-50 rounded-lg">
                    Ready to run evaluations
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
