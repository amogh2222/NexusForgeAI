"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Users,
  Globe,
  Server,
  Cpu,
  Database,
  Layers,
  Activity,
  Archive,
  Copy,
  Check,
  Code,
  Eye,
  GitGraph,
} from "lucide-react";

interface ArchitectureTopologyProps {
  scale: string;
  design: {
    load_balancing?: string;
    database_strategy?: string;
    cache_layer?: string;
    queue_design?: string;
    cdn_strategy?: string;
    autoscaling?: string;
    monitoring?: string;
    cost_estimate?: string;
    mermaid_diagram?: string;
  };
}

export function ArchitectureTopology({ scale, design }: ArchitectureTopologyProps) {
  const [activeTab, setActiveTab] = useState<"topology" | "diagram" | "mermaid">("topology");
  const [copied, setCopied] = useState(false);
  const [diagramSvg, setDiagramSvg] = useState<string>("");
  const [diagramError, setDiagramError] = useState<string>("");
  const mermaidContainerRef = useRef<HTMLDivElement>(null);

  const formattedScale = scale.replace("_", " ").toUpperCase();

  const handleCopy = () => {
    if (!design.mermaid_diagram) return;
    navigator.clipboard.writeText(design.mermaid_diagram);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Helper to extract clean summary line from a multi-line design section
  const getSummary = (text?: string, fallback: string = "") => {
    if (!text) return fallback;
    const lines = text.split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));
    return lines[0] || fallback;
  };

  // Dynamically render Mermaid diagram using CDN when Diagram tab is chosen
  useEffect(() => {
    if (activeTab === "diagram" && design.mermaid_diagram) {
      let isMounted = true;
      const scriptId = "mermaid-cdn-script";
      
      const renderMermaid = () => {
        if ((window as any).mermaid) {
          try {
            (window as any).mermaid.initialize({
              startOnLoad: false,
              theme: "dark",
              securityLevel: "loose",
            });
            const cleanCode = (design.mermaid_diagram || "").trim();
            const id = `mermaid-render-${Date.now()}`;
            (window as any).mermaid.render(id, cleanCode)
              .then((result: any) => {
                if (isMounted) {
                  setDiagramSvg(result.svg);
                  setDiagramError("");
                }
              })
              .catch((err: any) => {
                if (isMounted) {
                  setDiagramError(String(err));
                }
              });
          } catch (e: any) {
            if (isMounted) setDiagramError(String(e));
          }
        }
      };

      if ((window as any).mermaid) {
        renderMermaid();
      } else if (!document.getElementById(scriptId)) {
        const script = document.createElement("script");
        script.id = scriptId;
        script.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
        script.onload = () => renderMermaid();
        script.onerror = () => {
          if (isMounted) setDiagramError("Failed to load Mermaid graphics library.");
        };
        document.head.appendChild(script);
      } else {
        const existing = document.getElementById(scriptId);
        if (existing) {
          existing.addEventListener("load", renderMermaid);
        }
      }

      return () => {
        isMounted = false;
      };
    }
  }, [activeTab, design.mermaid_diagram]);

  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-900/95 text-slate-100 shadow-2xl overflow-hidden">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 border-b border-slate-800 bg-slate-900">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <h3 className="font-semibold text-sm tracking-wide text-indigo-300">
            System Topology Flowchart
          </h3>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            {formattedScale}
          </span>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-lg border border-slate-700">
          <button
            onClick={() => setActiveTab("topology")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-all ${
              activeTab === "topology"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Eye size={13} />
            Visual Topology
          </button>
          <button
            onClick={() => setActiveTab("diagram")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-all ${
              activeTab === "diagram"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <GitGraph size={13} />
            Rendered Graph
          </button>
          <button
            onClick={() => setActiveTab("mermaid")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-all ${
              activeTab === "mermaid"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Code size={13} />
            Mermaid Spec
          </button>
        </div>
      </div>

      {/* 1. Main Visual Pipeline View */}
      {activeTab === "topology" && (
        <div className="p-6 md:p-8 bg-gradient-to-b from-slate-900 to-slate-950">
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Level 1: Ingress (Users & Edge CDN) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-800/70 border border-indigo-500/30 shadow-md flex items-center gap-4">
                <div className="p-3 rounded-lg bg-indigo-500/20 text-indigo-400">
                  <Users size={24} />
                </div>
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Ingress Tier</div>
                  <div className="text-base font-bold text-white truncate">Client Traffic ({formattedScale})</div>
                  <div className="text-xs text-slate-400 mt-0.5">Global HTTP/WebSocket Traffic</div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/70 border border-blue-500/30 shadow-md flex items-center gap-4">
                <div className="p-3 rounded-lg bg-blue-500/20 text-blue-400">
                  <Globe size={24} />
                </div>
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Edge Acceleration</div>
                  <div className="text-base font-bold text-white truncate">Edge CDN & Anycast DNS</div>
                  <div className="text-xs text-slate-300 mt-0.5 line-clamp-2">
                    {getSummary(design.cdn_strategy, "TLS Termination, Static Asset Caching, DDoS Protection")}
                  </div>
                </div>
              </div>
            </div>

            {/* Connecting Arrow */}
            <div className="flex justify-center">
              <div className="w-0.5 h-6 bg-gradient-to-b from-blue-500 to-emerald-500" />
            </div>

            {/* Level 2: Routing (Load Balancer & API Gateways) */}
            <div className="p-4 rounded-xl bg-slate-800/80 border border-emerald-500/30 shadow-md">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-lg bg-emerald-500/20 text-emerald-400">
                    <Server size={24} />
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Routing & Application Tier</div>
                    <div className="text-base font-bold text-white">Load Balancing & Gateway</div>
                    <div className="text-xs text-slate-300 mt-0.5">
                      {getSummary(design.load_balancing, "High-Availability Load Balancing with Healthchecks")}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-200 border border-emerald-500/40 text-xs font-mono">
                    {getSummary(design.autoscaling, "HPA Autoscaled Pods")}
                  </span>
                </div>
              </div>
            </div>

            {/* Connecting Arrow */}
            <div className="flex justify-center">
              <div className="w-0.5 h-6 bg-gradient-to-b from-emerald-500 to-amber-500" />
            </div>

            {/* Level 3: Distributed State & Caching Tier */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-slate-800/70 border border-amber-500/30 shadow-md">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2.5 rounded-lg bg-amber-500/20 text-amber-400">
                    <Layers size={20} />
                  </div>
                  <div>
                    <div className="text-xs font-mono text-slate-400">Cache Layer</div>
                    <div className="text-sm font-bold text-white">In-Memory Cache</div>
                  </div>
                </div>
                <div className="text-xs text-slate-300 leading-relaxed line-clamp-3">
                  {getSummary(design.cache_layer, "Distributed caching with sub-millisecond latency.")}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/70 border border-purple-500/30 shadow-md">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2.5 rounded-lg bg-purple-500/20 text-purple-400">
                    <Database size={20} />
                  </div>
                  <div>
                    <div className="text-xs font-mono text-slate-400">Database Layer</div>
                    <div className="text-sm font-bold text-white">Persistent Storage</div>
                  </div>
                </div>
                <div className="text-xs text-slate-300 leading-relaxed line-clamp-3">
                  {getSummary(design.database_strategy, "Clustered transactional storage with replicas.")}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/70 border border-orange-500/30 shadow-md">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2.5 rounded-lg bg-orange-500/20 text-orange-400">
                    <Activity size={20} />
                  </div>
                  <div>
                    <div className="text-xs font-mono text-slate-400">Async Message Broker</div>
                    <div className="text-sm font-bold text-white">Event Streams</div>
                  </div>
                </div>
                <div className="text-xs text-slate-300 leading-relaxed line-clamp-3">
                  {getSummary(design.queue_design, "Partitioned message queue for background workflows.")}
                </div>
              </div>
            </div>

            {/* Connecting Arrow */}
            <div className="flex justify-center">
              <div className="w-0.5 h-6 bg-gradient-to-b from-orange-500 to-violet-500" />
            </div>

            {/* Level 4: Background Execution & Observability */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-800/70 border border-violet-500/30 shadow-md flex items-center gap-4">
                <div className="p-3 rounded-lg bg-violet-500/20 text-violet-400">
                  <Cpu size={24} />
                </div>
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Worker Compute</div>
                  <div className="text-base font-bold text-white truncate">Celery Swarm & Sandboxes</div>
                  <div className="text-xs text-slate-300 mt-0.5 line-clamp-2">
                    {getSummary(design.autoscaling, "Isolated containerized sandbox execution workers.")}
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/70 border border-cyan-500/30 shadow-md flex items-center gap-4">
                <div className="p-3 rounded-lg bg-cyan-500/20 text-cyan-400">
                  <Archive size={24} />
                </div>
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Observability & Telemetry</div>
                  <div className="text-base font-bold text-white truncate">Prometheus & Grafana</div>
                  <div className="text-xs text-slate-300 mt-0.5 line-clamp-2">
                    {getSummary(design.monitoring, "OpenTelemetry distributed tracing, metrics, and alerting.")}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. Rendered SVG Mermaid Graph View */}
      {activeTab === "diagram" && (
        <div className="p-6 bg-slate-950 flex flex-col items-center justify-center min-h-[350px]">
          {diagramSvg ? (
            <div
              ref={mermaidContainerRef}
              dangerouslySetInnerHTML={{ __html: diagramSvg }}
              className="w-full max-w-3xl overflow-x-auto flex justify-center [&>svg]:max-w-full [&>svg]:h-auto"
            />
          ) : diagramError ? (
            <div className="text-center p-6 bg-red-950/40 border border-red-800/50 rounded-xl max-w-md">
              <p className="text-sm text-red-300 font-mono mb-2">Diagram rendering notice</p>
              <p className="text-xs text-slate-400 mb-4">{diagramError}</p>
              <button
                onClick={() => setActiveTab("mermaid")}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs rounded-lg text-slate-200 transition-colors"
              >
                View Raw Mermaid Spec
              </button>
            </div>
          ) : (
            <div className="text-slate-400 flex flex-col items-center gap-3">
              <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-xs font-mono">Rendering architectural graph...</p>
            </div>
          )}
        </div>
      )}

      {/* 3. Mermaid Code Spec View */}
      {activeTab === "mermaid" && (
        <div className="p-5 bg-slate-950 font-mono text-sm relative">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs text-slate-400">Mermaid Diagram Definition</span>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition-colors border border-slate-700"
            >
              {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy Spec"}
            </button>
          </div>
          <pre className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-emerald-400 overflow-x-auto text-xs leading-relaxed">
            <code>{design.mermaid_diagram || "graph TB\n    Client --> CDN --> LB --> API --> DB"}</code>
          </pre>
        </div>
      )}
    </div>
  );
}
