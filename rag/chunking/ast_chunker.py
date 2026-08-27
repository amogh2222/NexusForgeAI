"""
NexusForge AI — AST-Based Code Chunker
Uses tree-sitter to chunk code at function/class boundaries.
Research-validated: DO NOT use RecursiveCharacterTextSplitter on code.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class CodeChunk:
    """A single chunk of code with rich metadata."""
    content: str
    file_path: str
    language: str
    chunk_type: str          # "function", "class", "method", "module", "block"
    start_line: int
    end_line: int
    parent_name: Optional[str] = None   # Enclosing class name for methods
    node_name: Optional[str] = None     # Function/class name
    docstring: Optional[str] = None
    token_estimate: int = 0
    chunk_id: str = ""

    def __post_init__(self):
        self.token_estimate = len(self.content.split()) * 4 // 3  # rough estimate
        if not self.chunk_id:
            import hashlib
            self.chunk_id = hashlib.sha256(
                f"{self.file_path}:{self.start_line}:{self.content[:100]}".encode()
            ).hexdigest()[:16]

    def to_chroma_document(self) -> dict:
        return {
            "id": self.chunk_id,
            "document": self.content,
            "metadata": {
                "file_path": self.file_path,
                "language": self.language,
                "chunk_type": self.chunk_type,
                "start_line": self.start_line,
                "end_line": self.end_line,
                "parent_name": self.parent_name or "",
                "node_name": self.node_name or "",
                "token_estimate": self.token_estimate,
            },
        }


class ASTChunker:
    """
    Tree-sitter based AST chunker for Python, JavaScript, TypeScript, and Go.
    Extracts semantically meaningful units: functions, classes, methods.
    """

    SUPPORTED_LANGUAGES = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
    }

    def __init__(self, max_chunk_tokens: int = 1024, min_chunk_tokens: int = 50):
        self.max_chunk_tokens = max_chunk_tokens
        self.min_chunk_tokens = min_chunk_tokens
        self._parsers: dict = {}
        self._languages_loaded: set = set()

    def _get_parser(self, language: str):
        """Lazily load tree-sitter parsers."""
        if language in self._parsers:
            return self._parsers[language]

        try:
            from tree_sitter import Language, Parser

            if language == "python":
                import tree_sitter_python as ts_lang
                lang = Language(ts_lang.language())
            elif language in ("javascript",):
                import tree_sitter_javascript as ts_lang
                lang = Language(ts_lang.language())
            elif language == "typescript":
                import tree_sitter_typescript as ts_lang
                lang = Language(ts_lang.language_typescript())
            elif language == "go":
                import tree_sitter_go as ts_lang
                lang = Language(ts_lang.language())
            else:
                return None

            parser = Parser(lang)
            self._parsers[language] = parser
            log.info("ast_chunker.parser_loaded", language=language)
            return parser

        except ImportError as e:
            log.warning("ast_chunker.parser_unavailable", language=language, error=str(e))
            return None

    def chunk_file(self, content: str, file_path: str) -> list[CodeChunk]:
        """Chunk a single file using AST analysis."""
        ext = Path(file_path).suffix.lower()
        language = self.SUPPORTED_LANGUAGES.get(ext)

        if not language:
            # Fall back to line-based chunking for unsupported types
            return self._line_based_chunk(content, file_path, "unknown")

        parser = self._get_parser(language)
        if parser is None:
            return self._line_based_chunk(content, file_path, language)

        try:
            tree = parser.parse(bytes(content, "utf-8"))
            return self._extract_chunks(tree, content, file_path, language)
        except Exception as e:
            log.error("ast_chunker.parse_error", file=file_path, error=str(e))
            return self._line_based_chunk(content, file_path, language)

    def _extract_chunks(self, tree, content: str, file_path: str, language: str) -> list[CodeChunk]:
        """Walk the AST and extract meaningful chunks."""
        chunks = []

        # Node types to extract per language
        target_types = {
            "python": {"function_definition", "class_definition", "decorated_definition"},
            "javascript": {"function_declaration", "class_declaration", "arrow_function", "method_definition"},
            "typescript": {"function_declaration", "class_declaration", "method_definition", "function_signature"},
            "go": {"function_declaration", "method_declaration", "type_declaration"},
        }

        lang_targets = target_types.get(language, set())
        extracted_ranges = set()

        def walk(node, parent_class: Optional[str] = None):
            if node.type in lang_targets:
                start_line = node.start_point[0]
                end_line = node.end_point[0]

                # Avoid overlapping chunks
                range_key = (start_line, end_line)
                if range_key in extracted_ranges:
                    return
                extracted_ranges.add(range_key)

                chunk_content = content[node.start_byte:node.end_byte]
                token_est = len(chunk_content.split()) * 4 // 3

                # Skip chunks that are too small
                if token_est < self.min_chunk_tokens:
                    return

                # Split oversized chunks
                if token_est > self.max_chunk_tokens:
                    sub_chunks = self._split_large_node(
                        chunk_content, file_path, language, start_line, parent_class
                    )
                    chunks.extend(sub_chunks)
                    return

                # Extract node name
                node_name = self._extract_node_name(node, language)
                chunk_type = self._classify_node(node.type, parent_class)

                chunks.append(CodeChunk(
                    content=chunk_content,
                    file_path=file_path,
                    language=language,
                    chunk_type=chunk_type,
                    start_line=start_line + 1,
                    end_line=end_line + 1,
                    parent_name=parent_class,
                    node_name=node_name,
                ))

                # For class nodes, recurse with class context
                new_parent = node_name if "class" in node.type else parent_class
                for child in node.children:
                    walk(child, new_parent)
            else:
                for child in node.children:
                    walk(child, parent_class)

        walk(tree.root_node)

        # If no chunks extracted (e.g., script-style file), chunk the whole file
        if not chunks:
            return self._line_based_chunk(content, file_path, language)

        return chunks

    def _extract_node_name(self, node, language: str) -> Optional[str]:
        """Extract the name identifier from an AST node."""
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8") if isinstance(child.text, bytes) else child.text
        return None

    def _classify_node(self, node_type: str, parent_class: Optional[str]) -> str:
        if "class" in node_type:
            return "class"
        if parent_class and "function" in node_type:
            return "method"
        if "function" in node_type or "method" in node_type:
            return "function"
        return "block"

    def _split_large_node(
        self,
        content: str,
        file_path: str,
        language: str,
        start_line: int,
        parent_name: Optional[str],
    ) -> list[CodeChunk]:
        """Split a large node into overlapping sub-chunks."""
        lines = content.split("\n")
        chunks = []
        window_lines = 80  # ~1024 tokens at avg line length
        overlap_lines = 10

        i = 0
        while i < len(lines):
            end = min(i + window_lines, len(lines))
            chunk_content = "\n".join(lines[i:end])
            if len(chunk_content.strip()) > 0:
                chunks.append(CodeChunk(
                    content=chunk_content,
                    file_path=file_path,
                    language=language,
                    chunk_type="block",
                    start_line=start_line + i + 1,
                    end_line=start_line + end,
                    parent_name=parent_name,
                ))
            i += window_lines - overlap_lines

        return chunks

    def _line_based_chunk(
        self,
        content: str,
        file_path: str,
        language: str,
        window_lines: int = 60,
        overlap_lines: int = 10,
    ) -> list[CodeChunk]:
        """Fallback: sliding window line-based chunking."""
        lines = content.split("\n")
        chunks = []
        i = 0

        while i < len(lines):
            end = min(i + window_lines, len(lines))
            chunk_content = "\n".join(lines[i:end])
            stripped = chunk_content.strip()

            if len(stripped) > 20:  # Skip near-empty chunks
                chunks.append(CodeChunk(
                    content=chunk_content,
                    file_path=file_path,
                    language=language,
                    chunk_type="block",
                    start_line=i + 1,
                    end_line=end,
                ))

            if end >= len(lines):
                break
            i += window_lines - overlap_lines

        return chunks
