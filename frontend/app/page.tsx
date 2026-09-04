"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Sidebar } from "@/components/Sidebar";
import { FileUp, GitBranch, Terminal, Database, Activity, Code, Clock, Trash2, Github, Search, CheckCircle2, ArrowRight, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import Link from "next/link";
import { GithubModal, ZipUploadModal } from "@/components/IngestionModals";
import { api, getAuthToken } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";

export default function Home() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [repositories, setRepositories] = useState<any[]>([]);
  const [githubRepos, setGithubRepos] = useState<any[]>([]);
  const [isGithubConnected, setIsGithubConnected] = useState(false);
  const [githubSearch, setGithubSearch] = useState("");
  const [isFetchingGh, setIsFetchingGh] = useState(false);
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null);
  const [activeRepoName, setActiveRepoName] = useState<string | null>(null);

  const [isGithubModalOpen, setIsGithubModalOpen] = useState(false);
  const [isZipModalOpen, setIsZipModalOpen] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);

  // Sync active repository from localStorage & window events
  const syncActiveRepo = () => {
    const storedId = typeof window !== "undefined" ? localStorage.getItem("nexusforge_active_repo_id") : null;
    const storedName = typeof window !== "undefined" ? localStorage.getItem("nexusforge_active_repo_name") : null;
    setActiveRepoId(storedId);
    setActiveRepoName(storedName);
  };

  useEffect(() => {
    syncActiveRepo();
    window.addEventListener("nexusforge_repo_changed", syncActiveRepo);
    return () => window.removeEventListener("nexusforge_repo_changed", syncActiveRepo);
  }, []);

  const handleSelectActiveRepo = (repoId: string, repoName: string) => {
    setActiveRepoId(repoId);
    setActiveRepoName(repoName);
    localStorage.setItem("nexusforge_active_repo_id", repoId);
    localStorage.setItem("nexusforge_active_repo_name", repoName);
    window.dispatchEvent(new Event("nexusforge_repo_changed"));
  };

  const handleDeleteRepo = async (repoId: string, repoName: string) => {
    if (!confirm(`Are you sure you want to delete repository "${repoName}"?`)) return;
    try {
      await api.repositories.delete(repoId);
      if (projectId) {
        const repos = await api.repositories.list(projectId);
        setRepositories(repos || []);
        if (activeRepoId === repoId) {
          if (repos && repos.length > 0) {
            handleSelectActiveRepo(repos[0].id, repos[0].name);
          } else {
            localStorage.removeItem("nexusforge_active_repo_id");
            localStorage.removeItem("nexusforge_active_repo_name");
            setActiveRepoId(null);
            setActiveRepoName(null);
            window.dispatchEvent(new Event("nexusforge_repo_changed"));
          }
        }
      }
    } catch (err: any) {
      alert("Failed to delete repository: " + (err.message || err));
    }
  };

  const [systemHealth, setSystemHealth] = useState<{
    status: string;
    checks: Record<string, string>;
  } | null>(null);

  // Poll for live system health
  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await api.health.getDetailed();
        setSystemHealth(res);
      } catch (err) {
        console.error("Health check error:", err);
      }
    }
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

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
        if (err instanceof Error && err.message.includes("401")) {
          window.location.href = "/auth";
        }
      } finally {
        setIsInitializing(false);
      }
    }
    init();
  }, []);

  // Fetch user's GitHub repositories
  const fetchGitHubRepos = async () => {
    setIsFetchingGh(true);
    try {
      const res = await api.github.listRepos();
      if (res && res.repositories) {
        setGithubRepos(res.repositories);
        setIsGithubConnected(true);
      }
    } catch (err) {
      // Not logged in via GitHub
      setIsGithubConnected(false);
    } finally {
      setIsFetchingGh(false);
    }
  };

  useEffect(() => {
    fetchGitHubRepos();
  }, []);

  // Poll for Repositories
  useEffect(() => {
    if (!projectId) return;

    async function fetchRepos() {
      try {
        const repos = await api.repositories.list(projectId as string);
        setRepositories(repos);
        const stored = localStorage.getItem("nexusforge_active_repo_id");
        if ((!stored || !repos.some((r: any) => r.id === stored)) && repos && repos.length > 0) {
          handleSelectActiveRepo(repos[0].id, repos[0].name);
        }
      } catch (err) {
        console.error("Failed to fetch repositories:", err);
      }
    }

    fetchRepos();
    const interval = setInterval(fetchRepos, 4000);
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
      if (projectId) {
        api.repositories.list(projectId).then(repos => {
          setRepositories(repos || []);
          if (repos && repos.length > 0) {
            const latest = repos[0];
            handleSelectActiveRepo(latest.id, latest.name);
          }
        }).catch(console.error);
      }
      setTimeout(() => setIndexingState(prev => ({ ...prev, status: 'idle' })), 4000);
    }
  }, [lastEvent, projectId]);

  const handleGithubSubmit = async (data: { url: string; branch: string }) => {
    if (!projectId) return;
    setIndexingState({ status: 'running', progress: 0, currentFile: 'Cloning repository...', totalFiles: 0 });
    try {
      const newRepo = await api.repositories.connectGithub({ project_id: projectId, ...data });
      if (newRepo && newRepo.id) {
        handleSelectActiveRepo(newRepo.id, newRepo.name);
      }
      const repos = await api.repositories.list(projectId);
      setRepositories(repos || []);
    } catch (err: any) {
      alert("Failed to connect GitHub repo: " + (err.message || err));
      setIndexingState({ status: 'idle', progress: 0, currentFile: '', totalFiles: 0 });
    }
  };

  const handleWorkOnGithubRepo = async (ghRepo: any) => {
    if (!projectId) return;
    const existing = repositories.find(
      (r) => r.name.toLowerCase() === ghRepo.name.toLowerCase() || (r.source_url && r.source_url.includes(ghRepo.full_name))
    );
    if (existing) {
      handleSelectActiveRepo(existing.id, existing.name);
      return;
    }
    await handleGithubSubmit({ url: ghRepo.clone_url, branch: ghRepo.default_branch || 'main' });
  };

  const handleZipSubmit = async (file: File) => {
    if (!projectId) return;
    setIndexingState({ status: 'running', progress: 0, currentFile: 'Uploading and extracting...', totalFiles: 0 });
    try {
      const newRepo = await api.repositories.uploadZip(projectId, file);
      if (newRepo && newRepo.id) {
        handleSelectActiveRepo(newRepo.id, newRepo.name);
      }
      const repos = await api.repositories.list(projectId);
      setRepositories(repos || []);
    } catch (err: any) {
      alert("Failed to upload ZIP: " + (err.message || err));
      setIndexingState({ status: 'idle', progress: 0, currentFile: '', totalFiles: 0 });
    }
  };

  const filteredGithubRepos = useMemo(() => {
    if (!githubSearch.trim()) return githubRepos;
    const q = githubSearch.toLowerCase();
    return githubRepos.filter(
      r => r.name.toLowerCase().includes(q) || (r.description && r.description.toLowerCase().includes(q))
    );
  }, [githubRepos, githubSearch]);

  return (
    <div className="flex flex-col md:flex-row h-[100dvh] w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 pb-nav md:pb-8 relative">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-200/40 rounded-full blur-[120px] pointer-events-none animate-float" />
        <div className="absolute bottom-0 left-1/4 w-[600px] h-[600px] bg-sky-200/40 rounded-full blur-[150px] pointer-events-none animate-float" style={{ animationDelay: "2s" }} />

        <div className="max-w-6xl mx-auto relative z-10">
          <header className="mb-6 sm:mb-8 md:mb-12">
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-3 tracking-tight">
              Welcome to <span className="premium-gradient">NexusForge AI</span>
            </h1>
            <p className="text-slate-500 text-sm sm:text-base md:text-lg max-w-2xl">
              Autonomous AI engineering platform. Upload a repository to deploy specialized agents that understand, review, and scale your code.
            </p>
          </header>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 mb-8 sm:mb-12">
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

            <Link href="/sandbox">
              <motion.div whileHover={{ y: -5, scale: 1.02 }} className="glass p-6 rounded-2xl cursor-pointer group transition-all shadow-sm hover:shadow-xl">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center mb-4 text-emerald-500 group-hover:bg-emerald-500/20 transition-colors">
                  <Terminal size={24} />
                </div>
                <h3 className="text-xl font-semibold mb-2">Sandbox Execution</h3>
                <p className="text-sm text-slate-500">Run arbitrary code in an isolated Docker sandbox.</p>
              </motion.div>
            </Link>
          </div>

          {/* Active Workspace Banner */}
          {activeRepoId && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-8 p-5 rounded-2xl bg-gradient-to-r from-indigo-900 via-indigo-800 to-purple-900 text-white shadow-xl relative overflow-hidden flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="absolute -right-10 -bottom-10 w-40 h-40 bg-white/5 rounded-full blur-2xl pointer-events-none" />
              <div className="flex items-center gap-3.5 z-10">
                <div className="w-11 h-11 rounded-xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 text-indigo-200">
                  <GitBranch size={22} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs uppercase font-bold tracking-wider text-indigo-300">Active Workspace Repo</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  </div>
                  <h2 className="text-xl font-bold tracking-tight text-white">{activeRepoName || "Repository"}</h2>
                </div>
              </div>

              <div className="flex items-center gap-2.5 z-10 w-full sm:w-auto">
                <Link 
                  href="/chat"
                  className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-white text-indigo-950 font-semibold text-xs hover:bg-indigo-50 transition-colors shadow-sm"
                >
                  <span>Chat with AI</span>
                  <ArrowRight size={14} />
                </Link>
                <Link 
                  href="/sandbox"
                  className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold text-xs border border-white/20 transition-colors"
                >
                  <span>Sandbox</span>
                </Link>
              </div>
            </motion.div>
          )}

          {/* Your GitHub Repositories Section */}
          {isGithubConnected && githubRepos.length > 0 && (
            <div className="glass rounded-2xl p-6 shadow-lg border border-slate-200 mb-8">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
                <div>
                  <h3 className="text-lg font-bold flex items-center gap-2 text-slate-900">
                    <div className="w-7 h-7 rounded-lg bg-slate-900 text-white flex items-center justify-center">
                      <Github size={16} />
                    </div>
                    Your GitHub Repositories
                    <span className="text-xs bg-indigo-50 text-indigo-700 px-2.5 py-0.5 rounded-full font-semibold border border-indigo-200">
                      {githubRepos.length} Repos
                    </span>
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    Choose any repository from your GitHub account to set as your active project workspace.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-full sm:w-64 relative">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Search your repos..."
                      value={githubSearch}
                      onChange={(e) => setGithubSearch(e.target.value)}
                      className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-xs"
                    />
                  </div>
                  <button
                    onClick={fetchGitHubRepos}
                    disabled={isFetchingGh}
                    className="p-2 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 transition-colors"
                    title="Refresh Repositories"
                  >
                    <RefreshCw size={14} className={isFetchingGh ? "animate-spin" : ""} />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 max-h-[380px] overflow-y-auto pr-1">
                {filteredGithubRepos.slice(0, 30).map((gh: any) => {
                  const existingRepo = repositories.find(
                    (r) => r.name.toLowerCase() === gh.name.toLowerCase() || (r.source_url && r.source_url.includes(gh.full_name))
                  );
                  const isActive = existingRepo && existingRepo.id === activeRepoId;

                  return (
                    <div
                      key={gh.id}
                      className={`p-4 rounded-xl border transition-all flex flex-col justify-between ${
                        isActive
                          ? "bg-indigo-50/70 border-indigo-400 shadow-sm"
                          : existingRepo
                          ? "bg-white/80 border-slate-200 hover:border-slate-300"
                          : "bg-white/50 border-slate-200 hover:border-indigo-200"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-1.5">
                          <h4 className="font-semibold text-sm text-slate-900 truncate" title={gh.full_name}>
                            {gh.name}
                          </h4>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {gh.private ? (
                              <span className="text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200 px-1.5 py-0.5 rounded">
                                Private
                              </span>
                            ) : (
                              <span className="text-[10px] font-medium bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                                Public
                              </span>
                            )}
                          </div>
                        </div>
                        <p className="text-xs text-slate-500 line-clamp-2 mb-3 min-h-[2rem]">
                          {gh.description || "No description provided."}
                        </p>
                      </div>

                      <div className="flex items-center justify-between pt-2 border-t border-slate-100 mt-auto">
                        <span className="text-[11px] text-slate-400 truncate">
                          {gh.default_branch || "main"}
                        </span>
                        {isActive ? (
                          <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                            <CheckCircle2 size={14} /> Active
                          </span>
                        ) : existingRepo ? (
                          <button
                            onClick={() => handleSelectActiveRepo(existingRepo.id, existingRepo.name)}
                            className="text-xs font-semibold bg-white border border-indigo-300 text-indigo-600 hover:bg-indigo-50 px-2.5 py-1 rounded-lg transition-colors"
                          >
                            Set Active
                          </button>
                        ) : (
                          <button
                            onClick={() => handleWorkOnGithubRepo(gh)}
                            disabled={indexingState.status === "running"}
                            className="text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1 disabled:opacity-50"
                          >
                            Work on this
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

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
                    Imported Repositories
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
                  repositories.map(repo => {
                    const isActive = repo.id === activeRepoId;

                    return (
                      <motion.div 
                        key={repo.id} 
                        whileHover={{ scale: 1.01 }}
                        className={`flex gap-4 items-center p-4 rounded-xl border transition-all shadow-sm hover:shadow ${
                          isActive 
                            ? "bg-indigo-50/70 border-indigo-300 ring-1 ring-indigo-200" 
                            : "bg-white/60 border-slate-200 hover:border-indigo-200"
                        }`}
                      >
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                          isActive ? "bg-indigo-600 text-white shadow-xs" : "bg-blue-50 text-blue-600"
                        }`}>
                          {repo.source_type === 'github' || repo.source_type === 'github_public' || repo.source_type === 'github_private' ? <GitBranch size={18} /> : <FileUp size={18} />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2 truncate">
                              <p className="text-sm font-semibold text-slate-900 truncate">{repo.name}</p>
                              {isActive && (
                                <span className="text-[10px] font-bold bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-300">
                                  Active Workspace
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              {!isActive && (
                                <button
                                  onClick={() => handleSelectActiveRepo(repo.id, repo.name)}
                                  className="text-xs font-semibold bg-white border border-indigo-200 text-indigo-600 hover:bg-indigo-50 px-2.5 py-1 rounded-lg transition-colors"
                                >
                                  Set Active
                                </button>
                              )}
                              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                repo.indexed_status === 'COMPLETED' || repo.indexed_status === 'INDEXED' ? 'bg-emerald-100 text-emerald-700' :
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
                                repo.indexed_status === 'COMPLETED' || repo.indexed_status === 'INDEXED' ? 'bg-emerald-500' : 'bg-indigo-500'
                              }`}
                            />
                          </div>
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          <div className="glass rounded-2xl p-6 h-fit shadow-lg">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold flex items-center gap-2 text-slate-900">
                  <Database size={20} className="text-indigo-500" />
                  System Health
                </h3>
                <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1.5 ${
                  systemHealth?.status === "healthy"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-amber-100 text-amber-700"
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    systemHealth?.status === "healthy" ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
                  }`} />
                  {systemHealth?.status === "healthy" ? "All Systems Operational" : "Checking..."}
                </span>
              </div>
              <div className="space-y-4">
                {[
                  { key: "api", name: "FastAPI Backend", fallback: "Connected" },
                  { key: "database", name: "PostgreSQL Database", fallback: "Online" },
                  { key: "redis", name: "Redis & Celery Swarm", fallback: "Active" },
                  { key: "qdrant", name: "Qdrant Vector DB", fallback: "Online" },
                  { key: "neo4j", name: "Neo4j Knowledge Graph", fallback: "Online" },
                ].map((svc) => {
                  const check = systemHealth?.checks?.[svc.key];
                  const isOk = check === "ok" || (!systemHealth && true);
                  return (
                    <div key={svc.key} className="flex items-center justify-between text-sm py-1 border-b border-slate-100 last:border-0">
                      <span className="text-slate-600 font-medium text-xs">{svc.name}</span>
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded flex items-center gap-1 ${
                        isOk ? "bg-emerald-50 text-emerald-600 border border-emerald-200" : "bg-red-50 text-red-600 border border-red-200"
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${isOk ? "bg-emerald-500" : "bg-red-500"}`} />
                        {check === "ok" ? "Operational" : check ? "Error" : svc.fallback}
                      </span>
                    </div>
                  );
                })}
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

