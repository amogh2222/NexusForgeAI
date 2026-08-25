"""
NexusForge AI — Text File Chunker
Sliding window chunker for non-code files (Markdown, YAML, configs, etc.)
"""
from pathlib import Path

import structlog

from rag.chunking.ast_chunker import CodeChunk

log = structlog.get_logger()

TEXT_EXTENSIONS = {
    ".md", ".txt", ".rst", ".yaml", ".yml", ".toml", ".ini",
    ".json", ".env", ".sh", ".bash", ".dockerfile", ".sql",
    ".html", ".css", ".scss", ".less", ".xml", ".csv",
}


class TextChunker:
    """
    Sliding window chunker for text, config, and documentation files.
    Uses line-based windowing with overlap for context continuity.
    """

    def __init__(
        self,
        window_lines: int = 50,
        overlap_lines: int = 10,
        min_chars: int = 50,
    ):
        self.window_lines = window_lines
        self.overlap_lines = overlap_lines
        self.min_chars = min_chars

    def chunk_file(self, content: str, file_path: str) -> list[CodeChunk]:
        """Chunk a text file using sliding window."""
        ext = Path(file_path).suffix.lower()
        language = ext.lstrip(".") or "text"
        lines = content.split("\n")

        # For very short files, return as single chunk
        if len(lines) <= self.window_lines:
            stripped = content.strip()
            if len(stripped) >= self.min_chars:
                return [CodeChunk(
                    content=content,
                    file_path=file_path,
                    language=language,
                    chunk_type="document",
                    start_line=1,
                    end_line=len(lines),
                )]
            return []

        chunks = []
        i = 0

        while i < len(lines):
            end = min(i + self.window_lines, len(lines))
            chunk_content = "\n".join(lines[i:end])

            if len(chunk_content.strip()) >= self.min_chars:
                chunks.append(CodeChunk(
                    content=chunk_content,
                    file_path=file_path,
                    language=language,
                    chunk_type="document",
                    start_line=i + 1,
                    end_line=end,
                ))

            if end >= len(lines):
                break
            i += self.window_lines - self.overlap_lines

        return chunks
