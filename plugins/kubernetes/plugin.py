"""
NexusForge AI — Kubernetes Plugin
Integrates Kubernetes API for cluster introspection and deployment management.
"""
from __future__ import annotations

from typing import Any

import structlog

from plugins.base import NexusPlugin, PluginMetadata

log = structlog.get_logger()


class KubernetesPlugin(NexusPlugin):
    """Kubernetes integration: pods, services, deployments."""

    ACTIONS = [
        "list_pods", "get_pod_logs",
        "list_deployments", "get_deployment_status",
        "list_services"
    ]

    def __init__(self) -> None:
        self._core_v1 = None
        self._apps_v1 = None
        self._namespace: str = "default"

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="kubernetes",
            version="1.0.0",
            description="Kubernetes cluster introspection and management",
            author="NexusForge AI",
            capabilities=["infra", "deploy", "observability"],
            config_schema={
                "kubeconfig_path": {"type": "string", "required": False},
                "in_cluster": {"type": "boolean", "required": False, "default": False},
                "default_namespace": {"type": "string", "required": False, "default": "default"},
            },
        )

    async def initialize(self, config: dict) -> bool:
        try:
            from kubernetes import client, config as k8s_config

            if config.get("in_cluster"):
                k8s_config.load_incluster_config()
            else:
                k8s_config.load_kube_config(config_file=config.get("kubeconfig_path"))

            self._core_v1 = client.CoreV1Api()
            self._apps_v1 = client.AppsV1Api()
            self._namespace = config.get("default_namespace", "default")
            
            log.info("kubernetes_plugin.initialized", namespace=self._namespace)
            return True
        except ImportError:
            log.warning("kubernetes_plugin.kubernetes_missing", hint="pip install kubernetes")
            return False
        except Exception as e:
            log.warning("kubernetes_plugin.init_failed", error=str(e))
            return False

    async def health_check(self) -> dict:
        if not self._core_v1:
            return {"status": "error", "reason": "not initialized"}
        try:
            # simple ping to cluster
            version = self._core_v1.get_code().git_version
            return {
                "status": "ok",
                "version": version,
                "namespace": self._namespace,
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def execute(self, action: str, params: dict) -> Any:
        if not self._core_v1 or not self._apps_v1:
            return {"error": "Plugin not initialized"}

        ns = params.get("namespace", self._namespace)

        match action:
            case "list_pods":
                pods = self._core_v1.list_namespaced_pod(ns)
                return [
                    {
                        "name": p.metadata.name,
                        "status": p.status.phase,
                        "ip": p.status.pod_ip,
                        "node": p.spec.node_name,
                        "created_at": p.metadata.creation_timestamp.isoformat() if p.metadata.creation_timestamp else None
                    }
                    for p in pods.items[:params.get("limit", 20)]
                ]

            case "get_pod_logs":
                logs = self._core_v1.read_namespaced_pod_log(
                    name=params["pod_name"],
                    namespace=ns,
                    tail_lines=params.get("lines", 100)
                )
                return {"logs": logs}

            case "list_deployments":
                deps = self._apps_v1.list_namespaced_deployment(ns)
                return [
                    {
                        "name": d.metadata.name,
                        "replicas": d.spec.replicas,
                        "available_replicas": d.status.available_replicas or 0,
                        "image": d.spec.template.spec.containers[0].image if d.spec.template.spec.containers else "unknown"
                    }
                    for d in deps.items[:params.get("limit", 20)]
                ]

            case "get_deployment_status":
                d = self._apps_v1.read_namespaced_deployment(params["deployment_name"], ns)
                return {
                    "name": d.metadata.name,
                    "ready_replicas": d.status.ready_replicas or 0,
                    "updated_replicas": d.status.updated_replicas or 0,
                    "conditions": [{"type": c.type, "status": c.status, "message": c.message} for c in (d.status.conditions or [])]
                }

            case "list_services":
                svcs = self._core_v1.list_namespaced_service(ns)
                return [
                    {
                        "name": s.metadata.name,
                        "type": s.spec.type,
                        "cluster_ip": s.spec.cluster_ip,
                        "ports": [{"port": p.port, "target_port": p.target_port} for p in (s.spec.ports or [])]
                    }
                    for s in svcs.items[:params.get("limit", 20)]
                ]

            case _:
                return {"error": f"Unknown action: {action}"}

    def get_actions(self) -> list[str]:
        return self.ACTIONS
