"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { FileUp, GitBranch, Terminal, Database, Activity, Code, Clock } from "lucide-react";
import { motion } from "framer-motion";
import { GithubModal, ZipUploadModal } from "@/components/IngestionModals";
import { api, getAuthToken } from "@/lib/api";

export default function Home() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [repositories, setRepositories] = useState<any[]>([]);
  const [isGithubModalOpen, setIsGithubModalOpen] = useState(false);
  const [isZipModalOpen, setIsZipModalOpen] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);

  // Initialize Auth & Project
  useEffect(() => {
    async function init() {
      try {
        let token = getAuthToken();
        if (!token) {
          // Attempt to register a default test user
          try {
            await api.auth.register({
              email: "testuser@nexusforge.ai",
              username: "testuser",
              password: "testpassword123",
              full_name: "Test User"
            });
          } catch (e) {
            // Might already exist, ignore
          }
          await api.auth.login({
            email: "testuser@nexusforge.ai",
            password: "testpassword123"
          });
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

  const handleGithubSubmit = async (data: { url: string; branch: string }) => {
    if (!projectId) return;
    await api.repositories.connectGithub({ project_id: projectId, ...data });
  };

  const handleZipSubmit = async (file: File) => {
    if (!projectId) return;
    await api.repositories.uploadZip(projectId, file);
  };

  return (
    <div className="flex h-screen w-full bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-8 relative">
        <motion.div 
          animate={{ x: [0, 50, 0], y: [0, 30, 0] }}
          transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
          className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-200/40 rounded-full blur-[120px] pointer-events-none" 
        />
        <motion.div 
          animate={{ x: [0, -40, 0], y: [0, -50, 0] }}
          transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
          className="absolute bottom-0 left-1/4 w-[600px] h-[600px] bg-blue-200/40 rounded-full blur-[150px] pointer-events-none" 
        />

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
            <div className="lg:col-span-2 glass rounded-2xl p-6 shadow-lg">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <Activity size={20} className="text-indigo-500" />
                  Repository Status
                </h3>
                <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded-md">Live Polling</span>
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
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            repo.indexed_status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-700' :
                            repo.indexed_status === 'FAILED' ? 'bg-red-100 text-red-700' :
                            'bg-amber-100 text-amber-700 animate-pulse'
                          }`}>
                            {repo.indexed_status}
                          </span>
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

