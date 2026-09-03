"use client";

import React, { useState } from "react";
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
    mermaid_diagram?: string;
  };
}

export function ArchitectureTopology({ scale, design }: ArchitectureTopologyProps) {
  const [activeTab, setActiveTab] = useState<"topology" | "mermaid">("topology");
  const [copied, setCopied] = useState(false);

  const formattedScale = scale.replace("_", " ").toUpperCase();

  const handleCopy = () => {
    if (!design.mermaid_diagram) return;
    navigator.clipboard.writeText(design.mermaid_diagram);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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

      {/* Main Content View */}
      {activeTab === "topology" ? (
        <div className="p-6 md:p-8 bg-gradient-to-b from-slate-900 to-slate-950">
          {/* Topology Pipeline Visualizer */}
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Level 1: Ingress (Users & Edge CDN) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-800/70 border border-indigo-500/30 shadow-md flex items-center gap-4">
                <div className="p-3 rounded-lg bg-indigo-500/20 text-indigo-400">
                  <Users size={24} />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Ingress Tier</div>
                  <div className="text-base font-bold text-white">Client Traffic ({formattedScale})</div>
                  <div className="text-xs text-slate-400 mt-0.5">Global HTTP/WebSocket Ingress</div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/70 border border-blue-500/30 shadow-md flex items-center gap-4">
                <div className="p-3 rounded-lg bg-blue-500/20 text-blue-400">
                  <Globe size={24} />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Edge Acceleration</div>
                  <div className="text-base font-bold text-white">CloudFront / Edge CDN</div>
                  <div className="text-xs text-slate-400 mt-0.5">TLS Termination & Static Asset Cache</div>
                </div>
              </div>
            </div>

            {/* Connecting Arrow */}
            <div className="flex justify-center">
              <div className="w-0.5 h-6 bg-gradient-to-b from-blue-500 to-emerald-500" />
            </div>

            {/* Level 2: Routing (Load Balancer & API Gateways) */}
            <div className="p-4 rounded-xl bg-slate-800/80 border border-emerald-500/30 shadow-md">
              <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-lg bg-emerald-500/20 text-emerald-400">
                    <Server size={24} />
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Routing Tier</div>
                    <div className="text-base font-bold text-white">AWS ALB / NGINX High-Availability</div>
                    <div className="text-xs text-slate-400 mt-0.5">Zero-Downtime Healthchecks & Path Routing</div>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-xs font-mono">
                    API Pod 1
                  </span>
                  <span className="px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-xs font-mono">
                    API Pod 2
                  </span>
                  <span className="px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-200 border border-emerald-500/40 text-xs font-mono font-semibold">
                    FastAPI Pod N [HPA Autoscaled]
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
                    <div className="text-sm font-bold text-white">Redis Cluster</div>
                  </div>
                </div>
                <div className="text-xs text-slate-400 leading-relaxed">
                  Session store, hot query cache, and rate-limiting counters (&lt;1ms response).
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/70 border border-purple-500/30 shadow-md">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2.5 rounded-lg bg-purple-500/20 text-purple-400">
                    <Database size={20} />
                  </div>
                  <div>
                    <div className="text-xs font-mono text-slate-400">Primary Database</div>
                    <div className="text-sm font-bold text-white">Aurora PostgreSQL</div>
                  </div>
                </div>
                <div className="text-xs text-slate-400 leading-relaxed">
                  Multi-AZ writer with read replica pool, connection pooling via PgBouncer.
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/70 border border-orange-500/30 shadow-md">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2.5 rounded-lg bg-orange-500/20 text-orange-400">
                    <Activity size={20} />
                  </div>
                  <div>
                    <div className="text-xs font-mono text-slate-400">Message Broker</div>
                    <div className="text-sm font-bold text-white">Kafka / Redis Streams</div>
                  </div>
                </div>
                <div className="text-xs text-slate-400 leading-relaxed">
                  Partitioned event streams for asynchronous agent orchestration & telemetry.
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
                <div>
                  <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Compute Pool</div>
                  <div className="text-base font-bold text-white">Celery AI Worker Swarm</div>
                  <div className="text-xs text-slate-400 mt-0.5">Isolated Docker Sandboxes & Async Execution</div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-800/70 border border-cyan-500/30 shadow-md flex items-center gap-4">
                <div className="p-3 rounded-lg bg-cyan-500/20 text-cyan-400">
                  <Archive size={24} />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">Storage & Telemetry</div>
                  <div className="text-base font-bold text-white">S3 Storage + Prometheus/Grafana</div>
                  <div className="text-xs text-slate-400 mt-0.5">Artifact persistence & live system telemetry</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Mermaid Code Spec View */
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
