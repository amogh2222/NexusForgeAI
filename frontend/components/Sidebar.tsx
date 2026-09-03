"use client";

import React, { useState, useEffect } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  Code2,
  Database,
  GitGraph,
  Settings,
  Beaker,
  Menu,
  X,
  LogOut,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

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
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  // Close mobile drawer on route change
  useEffect(() => {
    setIsMobileOpen(false);
  }, [pathname]);

  const handleLogout = () => {
    localStorage.removeItem("nexusforge_token");
    window.location.href = "/auth";
  };

  const navContent = (isMobile: boolean = false) => (
    <>
      <div className="px-6 mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-blue-500 flex items-center justify-center font-bold text-white shadow-md">
            N
          </div>
          <span className="font-semibold text-lg premium-gradient tracking-tight">NexusForge</span>
        </div>
        {isMobile && (
          <button
            onClick={() => setIsMobileOpen(false)}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 min-h-[44px] min-w-[44px] flex items-center justify-center"
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        )}
      </div>

      <nav className="flex-1 px-4 space-y-1.5 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => isMobile && setIsMobileOpen(false)}
            >
              <div
                className={`relative flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium transition-all duration-200 group overflow-hidden min-h-[44px] ${
                  isActive
                    ? "text-indigo-700 bg-indigo-50/80 font-semibold"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId={isMobile ? "mobile-sidebar-active" : "sidebar-active"}
                    className="absolute inset-0 bg-gradient-to-r from-indigo-500/10 to-transparent border-l-2 border-indigo-500"
                    initial={false}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  />
                )}
                <item.icon
                  size={18}
                  className={`relative z-10 transition-colors shrink-0 ${
                    isActive ? "text-indigo-600" : "text-slate-400 group-hover:text-slate-600"
                  }`}
                />
                <span className="relative z-10">{item.label}</span>
              </div>
            </Link>
          );
        })}
      </nav>

      <div className="px-4 mt-auto space-y-2 pt-4">
        <button
          onClick={() => alert("Settings configuration coming soon.")}
          className="flex items-center gap-3 px-3 py-2.5 w-full rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors min-h-[44px]"
        >
          <Settings size={18} className="text-slate-400 shrink-0" />
          <span>Settings</span>
        </button>
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 w-full rounded-lg text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors min-h-[44px]"
        >
          <LogOut size={18} className="text-red-400 shrink-0" />
          <span>Log Out</span>
        </button>

        {/* User Profile */}
        <div className="mt-4 pt-4 border-t border-slate-200">
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="h-9 w-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm shadow-sm shrink-0">
              AM
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-semibold text-slate-900 leading-tight truncate">Amogh</span>
              <span className="text-xs text-slate-500 mt-0.5 truncate">amogh2222@github</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* ─── Desktop Sidebar ────────────────────────────── */}
      <aside className="hidden md:flex w-64 border-r border-slate-200 bg-white/85 backdrop-blur-md h-full flex-col pt-6 pb-4 shadow-sm z-20 shrink-0">
        {navContent(false)}
      </aside>

      {/* ─── Mobile Top Navigation Bar ─────────────────── */}
      <header
        className="md:hidden flex items-center justify-between px-4 py-3 bg-white/90 backdrop-blur-md border-b border-slate-200 sticky top-0 z-40 w-full shadow-xs"
        style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top, 0px))" }}
      >
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center font-bold text-white text-xs shadow-xs">
            N
          </div>
          <span className="font-semibold text-base premium-gradient tracking-tight">NexusForge AI</span>
        </div>

        <button
          onClick={() => setIsMobileOpen(true)}
          className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 min-h-[44px] min-w-[44px] flex items-center justify-center transition-colors touch-manipulation"
          aria-label="Open navigation menu"
        >
          <Menu size={22} />
        </button>
      </header>

      {/* ─── Mobile Bottom Tab Bar (iOS / Android Thumb Bar) ─ */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-lg border-t border-slate-200/80 px-2 py-1 flex items-center justify-around shadow-[0_-4px_20px_rgba(0,0,0,0.04)]"
        style={{ paddingBottom: "max(0.35rem, env(safe-area-inset-bottom, 0px))" }}
      >
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const shortLabel =
            item.label === "Execution Sandbox"
              ? "Sandbox"
              : item.label === "Memory Explorer"
              ? "Memory"
              : item.label === "Agent Chat"
              ? "Chat"
              : item.label;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center justify-center py-1.5 px-2 rounded-xl transition-all min-w-[50px] min-h-[48px] touch-manipulation relative ${
                isActive ? "text-orange-600 font-semibold" : "text-slate-500 hover:text-slate-800"
              }`}
            >
              <item.icon
                size={20}
                className={`transition-transform duration-200 ${
                  isActive ? "scale-110 text-orange-500" : ""
                }`}
              />
              <span className="text-[10px] tracking-tight mt-0.5 whitespace-nowrap">
                {shortLabel}
              </span>
              {isActive && (
                <div className="absolute -bottom-0.5 w-4 h-0.5 bg-orange-500 rounded-full" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* ─── Mobile Slide-out Drawer ───────────────────── */}
      <AnimatePresence>
        {isMobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setIsMobileOpen(false)}
              className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs"
            />

            {/* Slide-out Panel */}
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 350, damping: 35 }}
              className="fixed inset-y-0 left-0 w-4/5 max-w-xs bg-white shadow-2xl flex flex-col z-10 border-r border-slate-100"
              style={{
                paddingTop: "max(1.5rem, env(safe-area-inset-top, 0px))",
                paddingBottom: "max(1.5rem, env(safe-area-inset-bottom, 0px))",
              }}
            >
              {navContent(true)}
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
