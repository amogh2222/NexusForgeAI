"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { FileUp, GitBranch, Terminal, Database, Activity, Code, Clock, Trash2 } from "lucide-react";
import { motion } from "framer-motion";
import { GithubModal, ZipUploadModal } from "@/components/IngestionModals";
import { api, getAuthToken } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";

export default function Home() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [repositories, setRepositories] = useState<any[]>([]);
  const [isGithubModalOpen, setIsGithubModalOpen] = useState(false);
  const [isZipModalOpen, setIsZipModalOpen] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);

  const handleDeleteRepo = async (repoId: string, repoName: string) => {
    if (!confirm(`Are you sure you want to delete repository "${repoName}"?`)) return;
    try {
      await api.repositories.delete(repoId);
      if (projectId) {
        const repos = await api.repositories.list(projectId);
        setRepositories(repos || []);
      }
    } catch (err: any) {
      alert("Failed to delete repository: " + (err.message || err));
    }
  };

  // WebSocket for Real-Time Indexing Progress
  const { isConnected, lastEvent } = useWebSocket(projectId);
  const [indexingState, setIndexingState] = useState<{
    status: 'idle' | 'running' | 'complete';
    progress: number;
    currentFile: string;
    totalFiles: number;
  }>({ status: 'idle', progress: 0, currentFile: '', totalFiles: 0 });

  // Initialize Auth & Project
  useEffect(() => {
    async function init() {
      try {
        // Handle OAuth token redirect
        const params = new URLSearchParams(window.location.search);
        const urlToken = params.get("token");
        if (urlToken) {
          localStorage.setItem("nexusforge_token", urlToken);
          window.history.replaceState({}, document.title, "/");
        }

        let token = getAuthToken();
        if (!token) {
          window.location.href = "/auth";
          return;
        }
        
        // Ensure a project exists
        const projects = await api.projects.list();
        if (projects && projects.length > 0) {
          setProjectId(projects[0].id);
        } else {
          const newProject = await api.projects.create({ name: "Default Project" });
          setProjectId(newProject.id);
        }
      } catch (err) {
        console.error("Initialization error:", err);
        // If API fails (e.g. 401 Unauthorized), redirect to auth
        if (err instanceof Error && err.message.includes("401")) {
          window.location.href = "/auth";
        }
      } finally {
        setIsInitializing(false);
      }
    }
    init();
  }, []);

  // Poll for Repositories
  useEffect(() => {
    if (!projectId) return;

    async function fetchRepos() {
      try {
        const repos = await api.repositories.list(projectId as string);
        setRepositories(repos);
      } catch (err) {
        console.error("Failed to fetch repositories:", err);
      }
    }

    fetchRepos();
    const interval = setInterval(fetchRepos, 3000); // Poll every 3 seconds
    return () => clearInterval(interval);
  }, [projectId]);

  // Handle Real-Time WebSocket Events
  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent.type === 'indexing_start') {
      setIndexingState(prev => ({ ...prev, status: 'running', progress: 0 }));
    } else if (lastEvent.type === 'indexing_progress') {
      setIndexingState({
        status: 'running',
        progress: lastEvent.progress,
        currentFile: lastEvent.current_file || '',
        totalFiles: lastEvent.total_files || 0
      });
    } else if (lastEvent.type === 'indexing_complete' || lastEvent.type === 'indexing_error') {
      setIndexingState(prev => ({ ...prev, status: 'complete', progress: 100 }));
      // Refresh repositories immediately
      if (projectId) {
        api.repositories.list(projectId).then(setRepositories).catch(console.error);
      }
      setTimeout(() => setIndexingState(prev => ({ ...prev, status: 'idle' })), 5000);
    }
  }, [lastEvent, projectId]);

  const handleGithubSubmit = async (data: { url: string; branch: string }) => {
    if (!projectId) return;
    setIndexingState({ status: 'running', progress: 0, currentFile: 'Initializing...', totalFiles: 0 });
    await api.repositories.connectGithub({ project_id: projectId, ...data });
  };

  const handleZipSubmit = async (file: File) => {
    if (!projectId) return;
    setIndexingState({ status: 'running', progress: 0, currentFile: 'Uploading and extracting...', totalFiles: 0 });
    await api.repositories.uploadZip(projectId, file);
  };

  return (
    <div className="flex h-screen w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-8 relative">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-200/40 rounded-full blur-[120px] pointer-events-none animate-float" />
        <div className="absolute bottom-0 left-1/4 w-[600px] h-[600px] bg-sky-200/40 rounded-full blur-[150px] pointer-events-none animate-float" style={{ animationDelay: "2s" }} />

        <div className="max-w-6xl mx-auto relative z-10">
          <header className="mb-12">
            <h1 className="text-4xl font-bold mb-4 tracking-tight">
              Welcome to <span className="premium-gradient">NexusForge AI</span>
            </h1>
            <p className="text-slate-500 text-lg max-w-2xl">
              Autonomous AI engineering platform. Upload a repository to deploy specialized agents that understand, review, and scale your code.
            </p>
          </header>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
            {/* Quick Actions */}
            <motion.div 
              whileHover={{ y: -5, scale: 1.02 }} 
              onClick={() => setIsZipModalOpen(true)}
              className="glass p-6 rounded-2xl cursor-pointer group relative overflow-hidden transition-all shadow-sm hover:shadow-xl"
            >
              <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center mb-4 text-indigo-500 group-hover:bg-indigo-500/20 transition-colors">
                <FileUp size={24} />
              </div>
              <h3 className="text-xl font-semibold mb-2">Upload Repository</h3>
              <p className="text-sm text-slate-500">Upload a ZIP file containing your source code to begin AST-level parsing.</p>
              {isInitializing && <div className="absolute inset-0 bg-white/50 flex items-center justify-center backdrop-blur-sm text-slate-600">Initializing...</div>}
            </motion.div>

            <motion.div 
              whileHover={{ y: -5, scale: 1.02 }} 
              onClick={() => setIsGithubModalOpen(true)}
              className="glass p-6 rounded-2xl cursor-pointer group relative overflow-hidden transition-all shadow-sm hover:shadow-xl"
            >
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center mb-4 text-blue-500 group-hover:bg-blue-500/20 transition-colors">
                <GitBranch size={24} />
              </div>
              <h3 className="text-xl font-semibold mb-2">Connect GitHub</h3>
              <p className="text-sm text-slate-500">Clone a public or private repository directly from a GitHub URL.</p>
              {isInitializing && <div className="absolute inset-0 bg-white/50 flex items-center justify-center backdrop-blur-sm text-slate-600">Initializing...</div>}
            </motion.div>

            <motion.div whileHover={{ y: -5, scale: 1.02 }} className="glass p-6 rounded-2xl cursor-pointer group opacity-60 transition-all shadow-sm">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center mb-4 text-emerald-500 group-hover:bg-emerald-500/20 transition-colors">
                <Terminal size={24} />
              </div>
              <h3 className="text-xl font-semibold mb-2">Sandbox Execution</h3>
              <p className="text-sm text-slate-500">Coming soon. Run arbitrary code in an isolated Docker sandbox.</p>
            </motion.div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 flex flex-col gap-8">
              
              {/* Real-time Indexing Progress */}
              {indexingState.status !== 'idle' && (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }} 
                  animate={{ opacity: 1, y: 0 }} 
                  className="glass rounded-2xl p-6 shadow-lg border border-blue-500/20 bg-blue-50/50"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold flex items-center gap-2 text-blue-900">
                      <Activity size={20} className="text-blue-500 animate-pulse" />
                      {indexingState.status === 'running' ? 'Indexing Repository...' : 'Indexing Complete!'}
                    </h3>
                    <span className="text-sm font-medium text-blue-700">{indexingState.progress}%</span>
                  </div>
                  
                  <div className="w-full bg-blue-100 rounded-full h-2.5 mb-3 overflow-hidden">
                    <motion.div 
                      className="bg-blue-600 h-2.5 rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${indexingState.progress}%` }}
                      transition={{ type: "spring", bounce: 0 }}
                    ></motion.div>
                  </div>
                  
                  {indexingState.status === 'running' && indexingState.currentFile && (
                    <div className="flex justify-between items-center text-xs text-blue-600/80">
                      <span className="truncate max-w-[70%]">Processing: {indexingState.currentFile}</span>
                      {indexingState.totalFiles > 0 && <span>Total files: {indexingState.totalFiles}</span>}
                    </div>
                  )}
                </motion.div>
              )}

              <div className="glass rounded-2xl p-6 shadow-lg">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <Database size={20} className="text-indigo-500" />
                    Repository Database
                  </h3>
                  <div className="flex gap-2 items-center">
                    {isConnected ? (
                      <span className="text-xs bg-emerald-500/20 text-emerald-600 px-2 py-1 rounded-md flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                        WebSocket Connected
                      </span>
                    ) : (
                      <span className="text-xs bg-amber-500/20 text-amber-600 px-2 py-1 rounded-md">Connecting...</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-4 mb-6">
                  <button 
                    onClick={() => setIsGithubModalOpen(true)}
                    className="btn-3d flex items-center px-5 py-3 rounded-xl font-medium"
                  >
                    <GitBranch className="w-5 h-5 mr-2" />
                    Connect GitHub Repo
                  </button>
                  <button 
                    onClick={() => setIsZipModalOpen(true)}
                    className="glass flex items-center px-5 py-3 rounded-xl font-medium text-slate-700 hover:text-slate-900"
                  >
                    <FileUp className="w-5 h-5 mr-2" />
                    Upload Local ZIP
                  </button>
                </div>
              
              <div className="space-y-4">
                {repositories.length === 0 ? (
                  <div className="text-slate-500 text-sm py-8 text-center border-2 border-dashed border-slate-200 rounded-xl bg-white/50">
                    No repositories added yet. Upload a ZIP or connect GitHub to begin.
                  </div>
                ) : (
                  repositories.map(repo => (
                    <motion.div 
                      key={repo.id} 
                      whileHover={{ scale: 1.01 }}
                      className="flex gap-4 items-center p-4 bg-white/60 rounded-xl border border-slate-200 hover:border-indigo-300 transition-all shadow-sm hover:shadow"
                    >
                      <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0 text-blue-600">
                        {repo.source_type === 'github' || repo.source_type === 'github_public' || repo.source_type === 'github_private' ? <GitBranch size={18} /> : <FileUp size={18} />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <p className="text-sm font-medium text-slate-900 truncate">{repo.name}</p>
                          <div className="flex items-center gap-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              repo.indexed_status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-700' :
                              repo.indexed_status === 'FAILED' ? 'bg-red-100 text-red-700' :
                              'bg-amber-100 text-amber-700 animate-pulse'
                            }`}>
                              {repo.indexed_status}
                            </span>
                            <button
                              onClick={() => handleDeleteRepo(repo.id, repo.name)}
                              className="text-slate-400 hover:text-red-600 p-1 rounded hover:bg-red-50 transition-colors"
                              title="Delete Repository"
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-slate-500">
                          <span className="flex items-center gap-1"><Code size={12} /> {repo.total_files} files</span>
                          <span className="flex items-center gap-1"><Clock size={12} /> Progress: {repo.indexing_progress}%</span>
                        </div>
                        
                        {/* Progress Bar */}
                        <div className="mt-3 h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
                          <motion.div 
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.max(repo.indexing_progress, 5)}%` }}
                            transition={{ duration: 0.5 }}
                            className={`h-full ${
                              repo.indexed_status === 'FAILED' ? 'bg-red-500' :
                              repo.indexed_status === 'COMPLETED' ? 'bg-emerald-500' : 'bg-indigo-500'
                            }`}
                          />
                        </div>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="glass rounded-2xl p-6 h-fit shadow-lg">
              <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                <Database size={20} className="text-blue-500" />
                System Status
              </h3>
              <div className="space-y-5">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-500">Backend API</span>
                    <span className="text-emerald-600 font-medium">Connected</span>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-500">PostgreSQL</span>
                    <span className="text-emerald-600 font-medium">Online</span>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-500">Qdrant Vectors</span>
                    <span className="text-emerald-600 font-medium">Online</span>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-500">Redis / Celery</span>
                    <span className="text-emerald-600 font-medium">Active</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <GithubModal 
        isOpen={isGithubModalOpen} 
        onClose={() => setIsGithubModalOpen(false)} 
        onSubmit={handleGithubSubmit} 
      />
      <ZipUploadModal 
        isOpen={isZipModalOpen} 
        onClose={() => setIsZipModalOpen(false)} 
        onSubmit={handleZipSubmit} 
      />
    </div>
  );
}

