"use client";

import React from "react";
import { LayoutDashboard, MessageSquare, Code2, Database, GitGraph, Settings, Beaker } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/" },
  { icon: MessageSquare, label: "Agent Chat", href: "/chat" },
  { icon: Code2, label: "Execution Sandbox", href: "/sandbox" },
  { icon: Database, label: "Memory Explorer", href: "/memory" },
  { icon: GitGraph, label: "Architecture", href: "/architecture" },
  { icon: Beaker, label: "Evaluation", href: "/eval" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 border-r border-slate-200 bg-white/80 backdrop-blur-md h-full flex flex-col pt-6 pb-4 shadow-sm z-20">
      <div className="px-6 mb-8 flex items-center gap-3">
        <div className="w-8 h-8 rounded bg-gradient-to-br from-indigo-500 to-blue-500 flex items-center justify-center font-bold text-white shadow-md">
          N
        </div>
        <span className="font-semibold text-lg premium-gradient tracking-tight">NexusForge</span>
      </div>

      <nav className="flex-1 px-4 space-y-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link key={item.href} href={item.href}>
              <div
                className={`relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group overflow-hidden ${
                  isActive
                    ? "text-indigo-700 bg-indigo-50"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute inset-0 bg-gradient-to-r from-indigo-500/10 to-transparent border-l-2 border-indigo-500"
                    initial={false}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  />
                )}
                <item.icon
                  size={18}
                  className={`relative z-10 transition-colors ${
                    isActive ? "text-indigo-600" : "text-slate-400 group-hover:text-slate-600"
                  }`}
                />
                <span className="relative z-10">{item.label}</span>
              </div>
            </Link>
          );
        })}
      </nav>

      <div className="px-4 mt-auto space-y-2">
        <button onClick={() => alert("Settings configuration coming soon.")} className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors">
          <Settings size={18} className="text-slate-400" />
          Settings
        </button>
        <button 
          onClick={() => {
            localStorage.removeItem("nexusforge_token");
            window.location.href = "/auth";
          }}
          className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-400"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          Log Out
        </button>
        {/* User Profile */}
        <div className="mt-4 pt-4 border-t border-slate-200">
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-sm">
              AM
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-medium text-slate-900 leading-none">Amogh</span>
              <span className="text-xs text-slate-500 mt-1">amogh2222@github</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
