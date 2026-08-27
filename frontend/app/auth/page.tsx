import React from "react";
import { AuthForms } from "@/components/Auth/AuthForms";
import { Bot, Terminal, Code2, Cpu } from "lucide-react";

export default function AuthPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background decorations */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-1/2 -left-1/2 w-full h-full bg-gradient-to-br from-indigo-500/10 to-purple-500/10 blur-3xl rounded-full transform rotate-12" />
        <div className="absolute -bottom-1/2 -right-1/2 w-full h-full bg-gradient-to-tl from-emerald-500/10 to-blue-500/10 blur-3xl rounded-full transform -rotate-12" />
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10 mb-8 text-center">
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg transform rotate-3 hover:rotate-6 transition-transform">
            <Bot size={32} className="text-white" />
          </div>
        </div>
        <h2 className="text-center text-4xl font-extrabold text-slate-900 tracking-tight">
          NexusForge AI
        </h2>
        <p className="mt-3 text-center text-slate-600 font-medium">
          The Autonomous AI Engineering OS
        </p>
      </div>

      <div className="relative z-10">
        <AuthForms />
      </div>

      <div className="mt-16 sm:mx-auto sm:w-full sm:max-w-3xl relative z-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
          <div className="glass p-6 rounded-2xl bg-white/40">
            <Code2 className="mx-auto text-indigo-500 mb-3" size={24} />
            <h3 className="font-semibold text-slate-800 mb-1">AST Analysis</h3>
            <p className="text-xs text-slate-500">Deep structural understanding of your entire codebase</p>
          </div>
          <div className="glass p-6 rounded-2xl bg-white/40">
            <Cpu className="mx-auto text-purple-500 mb-3" size={24} />
            <h3 className="font-semibold text-slate-800 mb-1">Multi-Agent Hive</h3>
            <p className="text-xs text-slate-500">6 specialized AI agents working together on your code</p>
          </div>
          <div className="glass p-6 rounded-2xl bg-white/40">
            <Terminal className="mx-auto text-emerald-500 mb-3" size={24} />
            <h3 className="font-semibold text-slate-800 mb-1">Secure Execution</h3>
            <p className="text-xs text-slate-500">Isolated Docker sandboxes for safe code execution</p>
          </div>
        </div>
      </div>
    </div>
  );
}
