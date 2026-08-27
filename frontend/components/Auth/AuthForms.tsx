"use client";

import React from "react";
import { Github } from "lucide-react";

export function AuthForms() {
  const handleGithubLogin = () => {
    // Redirect to backend GitHub OAuth endpoint
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    window.location.href = `${API_URL}/auth/github/login`;
  };

  return (
    <div className="w-full max-w-md mx-auto">
      <div className="glass p-8 rounded-3xl shadow-2xl relative overflow-hidden text-center">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-500" />
        
        <div className="mb-8 mt-4">
          <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-purple-600 mb-2">
            Welcome to NexusForge
          </h2>
          <p className="text-slate-500 text-sm">
            Sign in with GitHub to access your workspaces and repositories.
          </p>
        </div>

        <button 
          onClick={handleGithubLogin}
          type="button"
          className="w-full mb-4 flex items-center justify-center gap-3 bg-slate-900 text-white rounded-xl py-4 px-6 hover:bg-slate-800 transition-all shadow-md hover:shadow-lg text-lg"
        >
          <Github size={24} />
          <span className="font-medium">Continue with GitHub</span>
        </button>
        
        <p className="text-xs text-slate-400 mt-6">
          Every user must authenticate via GitHub to sync their repositories and execute code autonomously.
        </p>
      </div>
    </div>
  );
}
