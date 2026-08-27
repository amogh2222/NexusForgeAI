"""Utility functions."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text())

def format_timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
