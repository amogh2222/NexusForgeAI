"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import Editor from "@monaco-editor/react";
import { Play, TerminalSquare, Loader2 } from "lucide-react";
import { api, getAuthToken } from "@/lib/api";

export default function SandboxPage() {
  const [code, setCode] = useState("print('Hello from NexusForge Sandbox')\n");
  const [output, setOutput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);

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
        if (err instanceof Error && err.message.includes("401")) {
          window.location.href = "/auth";
        }
      }
    }
    init();
  }, []);

  const handleRun = async () => {
    if (!projectId) return;
    setIsRunning(true);
    setOutput("Initializing Sandbox...\nExecuting code...\n");
    
    let seconds = 0;
    try {
      const res = await api.executions.create({
        project_id: projectId,
        runtime: "python",
        code: code
      });
      
      const executionId = res.execution_id;
      
      // Poll for result
      const poll = async () => {
        seconds += 1;
        try {
          const status = await api.executions.get(executionId);
          if (status.status === "success" || status.status === "failed" || status.status === "error" || status.status === "timeout") {
            let finalOutput = "";
            if (status.stdout) finalOutput += status.stdout + "\n";
            if (status.stderr) finalOutput += status.stderr + "\n";
            if (!status.stdout && !status.stderr) finalOutput += `Exited with code ${status.exit_code}\n`;
            
            finalOutput += `\nExecution finished in ${status.duration_ms || 0}ms.`;
            setOutput(finalOutput);
            setIsRunning(false);
          } else {
            setOutput(`[Status: ${status.status || 'queued'}] Waiting for isolated Docker container (${seconds}s)...\nTip: If Celery is busy with embeddings, this will execute shortly.`);
            if (seconds < 60) {
              setTimeout(poll, 1000);
            } else {
              setOutput("Execution timed out after 60s. Celery workers may be busy.");
              setIsRunning(false);
            }
          }
        } catch (e: any) {
          setOutput(`Error polling execution status: ${e.message || e}`);
          setIsRunning(false);
        }
      };
      
      setTimeout(poll, 1000);

    } catch (err: any) {
      setOutput(err.message || "Failed to execute code");
      setIsRunning(false);
    }
  };

  return (
    <div className="flex flex-col md:flex-row h-screen w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col relative bg-slate-50 min-w-0">
        <header className="min-h-[4rem] py-2.5 border-b border-slate-200 bg-white/80 backdrop-blur flex flex-wrap items-center px-4 md:px-6 justify-between z-10 shadow-sm gap-2">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-lg">Execution Sandbox</h2>
            <div className="px-2 py-0.5 rounded text-xs bg-indigo-100 text-indigo-700 border border-indigo-200 font-medium">
              Python 3.11
            </div>
            {!projectId && (
              <div className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700 border border-red-200 font-medium">
                No Active Project
              </div>
            )}
          </div>
          <button 
            onClick={handleRun}
            disabled={isRunning || !projectId}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition-colors disabled:opacity-50 font-medium text-sm min-h-[40px]"
          >
            {isRunning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            Run Code
          </button>
        </header>

        <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
          {/* Editor */}
          <div className="flex-1 h-1/2 md:h-full border-b md:border-b-0 md:border-r border-slate-200 bg-white min-h-0">
            <Editor
              height="100%"
              defaultLanguage="python"
              theme="light"
              value={code}
              onChange={(value) => setCode(value || "")}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                padding: { top: 16 }
              }}
            />
          </div>
          
          {/* Terminal */}
          <div className="w-full md:w-1/3 h-1/2 md:h-full bg-slate-900 flex flex-col min-h-0">
            <div className="p-3 border-b border-slate-700 flex items-center gap-2 text-slate-400 bg-slate-800 shrink-0">
              <TerminalSquare size={16} />
              <span className="text-xs font-semibold uppercase tracking-wider">Output</span>
            </div>
            <div className="p-4 flex-1 overflow-y-auto font-mono text-sm text-emerald-400 whitespace-pre-wrap">
              {output}
              {isRunning && <span className="animate-pulse">_</span>}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
