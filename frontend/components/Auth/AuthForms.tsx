"use client";

import React, { useState } from "react";
import { Github, Mail, Lock, User, ArrowRight, Loader2, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

export function AuthForms() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleGithubLogin = () => {
    const proto = typeof window !== "undefined" ? window.location.protocol : "http:";
    const hostname = typeof window !== "undefined" ? window.location.hostname : "localhost";
    const apiUrl = typeof window !== "undefined" && window.location.port === "3000"
      ? `${proto}//${hostname}:8000/api/v1`
      : `${proto}//${typeof window !== "undefined" ? window.location.host : "localhost:8000"}/api/v1`;
    window.location.href = `${apiUrl}/auth/github/login`;
  };

  const handleDemoSignIn = async () => {
    setIsLoading(true);
    setError(null);
    try {
      try {
        await api.auth.login({ email: "demo@nexusforge.ai", password: "password123" });
      } catch {
        await api.auth.register({
          email: "demo@nexusforge.ai",
          username: "demodev",
          password: "password123",
        });
        await api.auth.login({ email: "demo@nexusforge.ai", password: "password123" });
      }
      window.location.href = "/";
    } catch (err: any) {
      setError(err.message || "Demo sign-in failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      if (isLogin) {
        await api.auth.login({ email, password });
      } else {
        await api.auth.register({
          email,
          username,
          password,
        });
        await api.auth.login({ email, password });
      }
      // On success, redirect to home
      window.location.href = "/";
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md mx-auto">
      <div className="glass p-8 rounded-3xl shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-500" />
        
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-purple-600 mb-2">
            {isLogin ? "Welcome Back" : "Create Account"}
          </h2>
          <p className="text-slate-500 text-sm">
            {isLogin ? "Sign in to access your AI engineering workspaces" : "Join NexusForge to autonomously scale your codebase"}
          </p>
        </div>

        <div className="space-y-3 mb-6">
          <button 
            onClick={handleGithubLogin}
            type="button"
            className="w-full flex items-center justify-center gap-3 bg-slate-900 text-white rounded-xl py-3 px-4 hover:bg-slate-800 transition-all shadow-md hover:shadow-lg font-medium"
          >
            <Github size={20} />
            <span>Continue with GitHub</span>
          </button>

          <button
            onClick={handleDemoSignIn}
            type="button"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-50 to-purple-50 hover:from-indigo-100 hover:to-purple-100 text-indigo-700 border border-indigo-200 rounded-xl py-2.5 px-4 text-xs font-semibold transition-all shadow-xs"
          >
            <span>⚡ Quick Demo Sign-in (1-Click)</span>
          </button>
        </div>

        <div className="relative flex items-center py-2 mb-2">
          <div className="flex-grow border-t border-slate-200"></div>
          <span className="flex-shrink-0 mx-4 text-slate-400 text-xs">OR SIGN IN WITH EMAIL</span>
          <div className="flex-grow border-t border-slate-200"></div>
        </div>

        <AnimatePresence mode="wait">
          {error && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }} 
              animate={{ opacity: 1, y: 0 }} 
              exit={{ opacity: 0 }}
              className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-600 text-sm"
            >
              <AlertCircle size={16} />
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <User size={18} />
                </div>
                <input 
                  type="text" 
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="block w-full pl-10 pr-3 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white/50 text-slate-900" 
                  placeholder="Username" 
                />
              </div>
            </motion.div>
          )}

          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              <Mail size={18} />
            </div>
            <input 
              type="email" 
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="block w-full pl-10 pr-3 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white/50 text-slate-900" 
              placeholder="Email Address" 
            />
          </div>

          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              <Lock size={18} />
            </div>
            <input 
              type="password" 
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="block w-full pl-10 pr-3 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white/50 text-slate-900" 
              placeholder="Password" 
            />
          </div>

          <button 
            type="submit" 
            disabled={isLoading || !email || !password || (!isLogin && !username)}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl py-3 px-4 hover:shadow-lg hover:shadow-indigo-500/30 transition-all disabled:opacity-70 mt-2"
          >
            {isLoading ? <Loader2 size={20} className="animate-spin" /> : (
              <>
                <span className="font-semibold">{isLogin ? "Sign In" : "Create Account"}</span>
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-slate-500">
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <button 
            onClick={() => { setIsLogin(!isLogin); setError(null); }}
            className="text-indigo-600 font-semibold hover:underline"
          >
            {isLogin ? "Sign Up" : "Log In"}
          </button>
        </div>
      </div>
    </div>
  );
}
