"""
NexusForge AI — AWS Plugin
Integrates AWS API for infrastructure introspection and management via boto3.
"""
from __future__ import annotations

from typing import Any

import structlog

from plugins.base import NexusPlugin, PluginMetadata

log = structlog.get_logger()


class AWSPlugin(NexusPlugin):
    """AWS integration: EC2, S3, IAM."""

    ACTIONS = [
        "list_ec2_instances",
        "list_s3_buckets",
        "get_caller_identity",
    ]

    def __init__(self) -> None:
        self._session = None
        self._ec2 = None
        self._s3 = None
        self._sts = None
        self._region: str = "us-east-1"

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="aws",
            version="1.0.0",
            description="AWS infrastructure introspection",
            author="NexusForge AI",
            capabilities=["infra", "cloud"],
            config_schema={
                "aws_access_key_id": {"type": "string", "required": False, "secret": True},
                "aws_secret_access_key": {"type": "string", "required": False, "secret": True},
                "aws_session_token": {"type": "string", "required": False, "secret": True},
                "region_name": {"type": "string", "required": False, "default": "us-east-1"},
            },
        )

    async def initialize(self, config: dict) -> bool:
        try:
            import boto3

            self._region = config.get("region_name", "us-east-1")

            # If keys are not provided, boto3 uses standard credential chain (env vars, ~/.aws/credentials)
            kwargs = {"region_name": self._region}
            if "aws_access_key_id" in config and "aws_secret_access_key" in config:
                kwargs["aws_access_key_id"] = config["aws_access_key_id"]
                kwargs["aws_secret_access_key"] = config["aws_secret_access_key"]
                if "aws_session_token" in config:
                    kwargs["aws_session_token"] = config["aws_session_token"]

            self._session = boto3.Session(**kwargs)
            self._ec2 = self._session.client("ec2")
            self._s3 = self._session.client("s3")
            self._sts = self._session.client("sts")

            log.info("aws_plugin.initialized", region=self._region)
            return True
        except ImportError:
            log.warning("aws_plugin.boto3_missing", hint="pip install boto3")
            return False
        except Exception as e:
            log.warning("aws_plugin.init_failed", error=str(e))
            return False

    async def health_check(self) -> dict:
        if not self._sts:
            return {"status": "error", "reason": "not initialized"}
        try:
            identity = self._sts.get_caller_identity()
            return {
                "status": "ok",
                "account": identity.get("Account"),
                "arn": identity.get("Arn"),
                "region": self._region,
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def execute(self, action: str, params: dict) -> Any:
        if not self._session:
            return {"error": "Plugin not initialized"}

        match action:
            case "list_ec2_instances":
                # params can contain filters
                filters = params.get("filters", [])
                response = self._ec2.describe_instances(Filters=filters)
                instances = []
                for reservation in response.get("Reservations", []):
                    for inst in reservation.get("Instances", []):
                        instances.append({
                            "instance_id": inst.get("InstanceId"),
                            "instance_type": inst.get("InstanceType"),
                            "state": inst.get("State", {}).get("Name"),
                            "public_ip": inst.get("PublicIpAddress"),
                            "private_ip": inst.get("PrivateIpAddress"),
                            "launch_time": inst.get("LaunchTime").isoformat() if inst.get("LaunchTime") else None
                        })
                return instances[:params.get("limit", 20)]

            case "list_s3_buckets":
                response = self._s3.list_buckets()
                buckets = response.get("Buckets", [])
                return [
                    {
                        "name": b.get("Name"),
                        "creation_date": b.get("CreationDate").isoformat() if b.get("CreationDate") else None
                    }
                    for b in buckets
                ]

            case "get_caller_identity":
                identity = self._sts.get_caller_identity()
                return {
                    "account": identity.get("Account"),
                    "arn": identity.get("Arn"),
                    "user_id": identity.get("UserId"),
                }

            case _:
                return {"error": f"Unknown action: {action}"}

    def get_actions(self) -> list[str]:
        return self.ACTIONS
