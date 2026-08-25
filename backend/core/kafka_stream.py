"""
NexusForge AI — Kafka Event Stream
Distributed agent orchestration via Apache Kafka.
"""
from __future__ import annotations

import json
import structlog
from typing import Any, Callable

log = structlog.get_logger()

class KafkaEventStream:
    """Pub/Sub mechanism for agent state transitions using aiokafka."""

    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self._bootstrap_servers = bootstrap_servers
        self._producer = None
        self._consumer = None

    async def connect_producer(self):
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap_servers)
            await self._producer.start()
            log.info("kafka.producer_connected")
        except ImportError:
            log.warning("kafka.aiokafka_missing", hint="pip install aiokafka")
        except Exception as e:
            log.warning("kafka.producer_error", error=str(e))

    async def connect_consumer(self, topic: str, group_id: str = "nexusforge"):
        try:
            from aiokafka import AIOKafkaConsumer
            self._consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self._bootstrap_servers,
                group_id=group_id
            )
            await self._consumer.start()
            log.info("kafka.consumer_connected", topic=topic)
        except Exception as e:
            log.warning("kafka.consumer_error", error=str(e))

    async def publish(self, topic: str, event_type: str, payload: dict):
        if not self._producer:
            log.debug("kafka.publish_skipped", reason="no_producer")
            return

        message = {
            "type": event_type,
            "payload": payload
        }
        await self._producer.send_and_wait(topic, json.dumps(message).encode('utf-8'))

    async def consume_loop(self, handler: Callable[[str, dict], Any]):
        if not self._consumer:
            log.debug("kafka.consume_skipped", reason="no_consumer")
            return

        try:
            async for msg in self._consumer:
                data = json.loads(msg.value.decode('utf-8'))
                await handler(data.get("type"), data.get("payload"))
        except Exception as e:
            log.error("kafka.consume_loop_error", error=str(e))

    async def stop(self):
        if self._producer:
            await self._producer.stop()
        if self._consumer:
            await self._consumer.stop()
