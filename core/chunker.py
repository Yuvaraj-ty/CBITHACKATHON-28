"""
Code chunker using tree-sitter grammars to extract functions, methods, classes,
imports, calls, and docstrings across Python, JavaScript, TypeScript, Java, and Go.
"""
import os
import re
from typing import List, Dict, Any, Optional, Set, Tuple, Iterator
import tree_sitter_language_pack as tsl

from core.languages import detect_language, LangConfig
from core.models import Chunk


def strip_quotes_and_semicolons(text: str) -> str:
    """Normalize import path or string by stripping quotes and trailing semicolons."""
    s = text.strip()
    if s.endswith(";"):
        s = s[:-1].strip()
    for q in ('"""', "'''", '"', "'", "`"):
        if s.startswith(q) and s.endswith(q) and len(s) >= 2 * len(q):
            s = s[len(q):-len(q)].strip()
            break
    return s


def strip_comment_markers(text: str) -> str:
    """Strip comment markers (//, /*, *, /**, ///) from contiguous comments."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        l = line.strip()
        if l.startswith("///"):
            l = l[3:].strip()
        elif l.startswith("//"):
            l = l[2:].strip()
        elif l.startswith("/**"):
            l = l[3:].strip()
        elif l.startswith("/*"):
            l = l[2:].strip()

        if l.endswith("*/"):
            l = l[:-2].strip()
        if l.startswith("*"):
            l = l[1:].strip()
        if l:
            cleaned.append(l)
    return "\n".join(cleaned)


def extract_python_docstring(body_node: Any) -> str:
    """Extract docstring from Python function or class body."""
    if not body_node:
        return ""
    for child in body_node.named_children:
        if child.type == "string":
            raw = child.text.decode("utf-8", errors="replace")
            return strip_quotes_and_semicolons(raw)
        elif child.type == "expression_statement":
            for sub in child.named_children:
                if sub.type == "string":
                    raw = sub.text.decode("utf-8", errors="replace")
                    return strip_quotes_and_semicolons(raw)
        else:
            # Stop if first statement is not a docstring
            break
    return ""


def extract_preceding_comments(target_node: Any) -> str:
    """
    Extract contiguous comment nodes ending on the line directly above target_node.
    Works for JS, TS, Java, and Go.
    """
    comments = []
    curr = target_node.prev_named_sibling
    expected_line = target_node.start_point.row - 1

    while curr and curr.type in ("comment", "line_comment", "block_comment"):
        if curr.end_point.row == expected_line:
            comments.append(curr.text.decode("utf-8", errors="replace"))
            expected_line = curr.start_point.row - 1
            curr = curr.prev_named_sibling
        else:
            break

    comments.reverse()
    if comments:
        return strip_comment_markers("\n".join(comments))
    return ""


def find_enclosing_class(node: Any, class_node_types: tuple) -> Optional[str]:
    """Find the name of an ancestor node matching class_node_types."""
    curr = node.parent
    while curr:
        if curr.type in class_node_types:
            name_node = curr.child_by_field_name("name")
            if name_node:
                return name_node.text.decode("utf-8", errors="replace")
        curr = curr.parent
    return None


def extract_calls(node: Any, lang_name: str) -> List[str]:
    """
    Traverse node and extract all function/method calls (final identifier only).
    """
    calls = []

    def visit(curr: Any) -> None:
        if lang_name == "python" and curr.type == "call":
            fn = curr.child_by_field_name("function")
            if fn:
                if fn.type == "attribute":
                    attr = fn.child_by_field_name("attribute")
                    if attr:
                        calls.append(attr.text.decode("utf-8", errors="replace"))
                else:
                    calls.append(fn.text.decode("utf-8", errors="replace"))

        elif lang_name in ("javascript", "typescript") and curr.type == "call_expression":
            fn = curr.child_by_field_name("function")
            if fn:
                if fn.type == "member_expression":
                    prop = fn.child_by_field_name("property")
                    if prop:
                        calls.append(prop.text.decode("utf-8", errors="replace"))
                else:
                    calls.append(fn.text.decode("utf-8", errors="replace"))

        elif lang_name == "java" and curr.type == "method_invocation":
            name = curr.child_by_field_name("name")
            if name:
                calls.append(name.text.decode("utf-8", errors="replace"))

        elif lang_name == "go" and curr.type == "call_expression":
            fn = curr.child_by_field_name("function")
            if fn:
                if fn.type == "selector_expression":
                    field = fn.child_by_field_name("field")
                    if field:
                        calls.append(field.text.decode("utf-8", errors="replace"))
                else:
                    calls.append(fn.text.decode("utf-8", errors="replace"))

        for child in curr.children:
            visit(child)

    visit(node)
    # Deduplicate and sort calls
    return sorted(list(set(calls)))


def extract_file_imports(root_node: Any, lang_name: str) -> List[str]:
    """
    Extract normalized import strings across the file according to per-language rules.
    """
    imports = []

    def visit(node: Any) -> None:
        if lang_name == "python":
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        imports.append(child.text.decode("utf-8", errors="replace"))
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            imports.append(name_node.text.decode("utf-8", errors="replace"))
            elif node.type == "import_from_statement":
                mod = node.child_by_field_name("module_name")
                if mod:
                    imports.append(mod.text.decode("utf-8", errors="replace"))

        elif lang_name in ("javascript", "typescript"):
            if node.type == "import_statement":
                src = node.child_by_field_name("source")
                if src:
                    imports.append(strip_quotes_and_semicolons(src.text.decode("utf-8", errors="replace")))
            elif node.type == "call_expression":
                fn = node.child_by_field_name("function")
                if fn and fn.text.decode("utf-8", errors="replace") == "require":
                    args = node.child_by_field_name("arguments")
                    if args and args.named_children:
                        arg_text = args.named_children[0].text.decode("utf-8", errors="replace")
                        imports.append(strip_quotes_and_semicolons(arg_text))

        elif lang_name == "java":
            if node.type == "import_declaration":
                for child in node.named_children:
                    if child.type in ("scoped_identifier", "identifier"):
                        imports.append(child.text.decode("utf-8", errors="replace"))

        elif lang_name == "go":
            if node.type == "import_declaration":
                def visit_import_spec(curr: Any) -> None:
                    if curr.type == "import_spec":
                        path = curr.child_by_field_name("path")
                        if path:
                            imports.append(strip_quotes_and_semicolons(path.text.decode("utf-8", errors="replace")))
                    for c in curr.children:
                        visit_import_spec(c)
                visit_import_spec(node)

        for child in node.children:
            visit(child)

    visit(root_node)
    # Deduplicate and sort imports
    return sorted(list(set(imports)))


def extract_signature(node: Any, source_lines: List[str]) -> str:
    """Extract a clean single-line signature from the definition start."""
    start_row = node.start_point.row
    if 0 <= start_row < len(source_lines):
        line = source_lines[start_row].strip()
        return line
    return ""


MAX_CHUNK_LINES = 80
WINDOW_SIZE = 60
WINDOW_OVERLAP = 10
WINDOW_STEP = WINDOW_SIZE - WINDOW_OVERLAP  # 50


def apply_windowing(chunks: List[Chunk]) -> List[Chunk]:
    """
    Splits any chunk spanning over 80 lines into overlapping windows
    of 60 lines with 10 lines of overlap, keeping the parent symbol,
    correct absolute line numbers, and a '#partN' suffix.
    """
    result: List[Chunk] = []

    for chunk in chunks:
        chunk_lines = chunk.code.splitlines()
        total_lines = len(chunk_lines)

        # Only split if chunk has more than 80 lines
        if total_lines <= MAX_CHUNK_LINES:
            result.append(chunk)
            continue

        part_num = 1
        for start_idx in range(0, total_lines, WINDOW_STEP):
            end_idx = min(total_lines, start_idx + WINDOW_SIZE)
            window_lines = chunk_lines[start_idx:end_idx]
            window_code = "\n".join(window_lines)

            # Calculate absolute line numbers in the original source
            w_start_line = chunk.start_line + start_idx
            w_end_line = chunk.start_line + end_idx - 1

            # Window signature: first line of window or parent signature
            w_sig = window_lines[0].strip()[:100] if window_lines else chunk.signature
            w_calls = [c for c in chunk.calls if c in window_code]

            window_chunk = Chunk(
                id=f"{chunk.id}#part{part_num}",
                file_path=chunk.file_path,
                symbol=f"{chunk.symbol}#part{part_num}",
                kind=chunk.kind,
                start_line=w_start_line,
                end_line=w_end_line,
                signature=w_sig,
                docstring=chunk.docstring if part_num == 1 else "",
                code=window_code,
                imports=chunk.imports,
                calls=w_calls,
                language=chunk.language,
            )
            result.append(window_chunk)
            part_num += 1

            if end_idx >= total_lines:
                break

    return result


FALLBACK_WINDOW_SIZE = 40
FALLBACK_WINDOW_OVERLAP = 5
FALLBACK_WINDOW_STEP = FALLBACK_WINDOW_SIZE - FALLBACK_WINDOW_OVERLAP  # 35

DEF_HEURISTIC_PATTERN = re.compile(
    r'^\s*(?:(?:export|async|static|final|abstract|override|default)\s+)*'
    r'(?:(?:public|private|protected)\s+)?'
    r'(?:(?:def|function|func|fn|class|interface|struct|public|private)\b)'
    r'(?:\s*\([^)]*\))?'                 # optional receiver like (s *Server)
    r'(?:\s+[\w\<\>\[\]\*&]+)*'          # optional return types/qualifiers
    r'\s+([A-Za-z_][A-Za-z0-9_]*)'       # identifier
    r'\s*([({:])'                         # opening paren, brace, or colon
)

TYPE_HEURISTIC_PATTERN = re.compile(
    r'^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:struct|interface)\s*[\{]'
)


def detect_file_language(rel_path: str, explicit_lang: Optional[str] = None) -> str:
    """Determine language from explicit parameter or file extension, falling back to 'text'."""
    if explicit_lang and explicit_lang not in ("unknown", ""):
        return explicit_lang
    cfg = detect_language(rel_path)
    if cfg:
        return cfg.name
    _, ext = os.path.splitext(rel_path)
    if ext:
        clean_ext = ext.lstrip(".").lower()
        ext_map = {
            "py": "python",
            "js": "javascript",
            "mjs": "javascript",
            "cjs": "javascript",
            "jsx": "javascript",
            "ts": "typescript",
            "tsx": "tsx",
            "java": "java",
            "go": "go",
            "rs": "rust",
            "c": "c",
            "cpp": "cpp",
            "cc": "cpp",
            "cxx": "cpp",
            "h": "c",
            "hpp": "cpp",
            "rb": "ruby",
            "php": "php",
            "cs": "csharp",
            "sh": "shell",
            "bash": "shell",
            "zsh": "shell",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "toml": "toml",
            "xml": "xml",
            "html": "html",
            "css": "css",
            "sql": "sql",
            "md": "markdown",
            "txt": "text",
        }
        return ext_map.get(clean_ext, clean_ext if clean_ext.isalnum() else "text")
    return "text"


def fallback_chunk(
    source_text: str,
    rel_path: str = "",
    language: Optional[str] = None,
    chunk_id: str = "C1",
) -> List[Chunk]:
    """
    Fallback chunker for files with no grammar or a parse failure.
    Uses a regex heuristic to detect likely definitions (def|function|func|fn|class|interface|struct|public|private).
    If no definitions are found, splits the file into 40-line windows with 5 lines of overlap.
    Sets kind="module" for window chunks and derives language from file extension (or "text").
    Never crashes, ensuring every text file is searchable.
    """
    # Support both signatures: fallback_chunk(source_text, rel_path, language) and legacy fallback_chunk(rel_path, source_text, language)
    if ("\n" in rel_path and "\n" not in source_text) or (
        not ("\n" in source_text) and any(source_text.endswith(ext) for ext in [
            ".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".h",
            ".txt", ".md", ".json", ".yaml", ".yml", ".sh", ".rb", ".php", ".cs", ".unknown"
        ])
    ):
        source_text, rel_path = rel_path, source_text

    resolved_lang = detect_file_language(rel_path, language)
    lines = source_text.splitlines()
    total_lines = len(lines)

    if total_lines == 0:
        return [
            Chunk(
                id=chunk_id,
                file_path=rel_path,
                symbol="<module>",
                kind="module",
                start_line=1,
                end_line=1,
                signature="",
                docstring="",
                code="",
                imports=[],
                calls=[],
                language=resolved_lang,
            )
        ]

    # 1. Regex heuristic to detect likely definitions
    raw_defs = []
    for idx, line in enumerate(lines):
        m = DEF_HEURISTIC_PATTERN.search(line) or TYPE_HEURISTIC_PATTERN.search(line)
        if m:
            symbol = m.group(1)
            raw_line = line.strip()
            # Determine kind from header keywords
            if any(k in raw_line for k in ("class", "struct", "interface", "type")):
                kind = "class"
            elif any(k in raw_line for k in ("public", "private", "protected")):
                kind = "method"
            else:
                kind = "function"
            raw_defs.append((idx + 1, symbol, kind, raw_line[:100]))

    # 2. If definitions were found, emit chunks for each definition
    if raw_defs:
        chunks: List[Chunk] = []
        for i, (start_line, symbol, kind, sig) in enumerate(raw_defs):
            if i + 1 < len(raw_defs):
                next_start = raw_defs[i + 1][0]
                end_line = next_start - 1
            else:
                end_line = total_lines

            # Trim trailing blank lines
            while end_line > start_line and not lines[end_line - 1].strip():
                end_line -= 1

            chunk_code = "\n".join(lines[start_line - 1 : end_line])
            cid = f"C{i + 1}"
            chunks.append(
                Chunk(
                    id=cid,
                    file_path=rel_path,
                    symbol=symbol,
                    kind=kind,
                    start_line=start_line,
                    end_line=end_line,
                    signature=sig,
                    docstring="",
                    code=chunk_code,
                    imports=[],
                    calls=[],
                    language=resolved_lang,
                )
            )
        # Apply standard 80-line windowing to any definition exceeding 80 lines
        return apply_windowing(chunks)

    # 3. If no definitions found: split into 40-line windows with 5 lines of overlap
    if total_lines <= FALLBACK_WINDOW_SIZE:
        sig = lines[0].strip()[:100] if lines else ""
        return [
            Chunk(
                id=chunk_id,
                file_path=rel_path,
                symbol="<module>",
                kind="module",
                start_line=1,
                end_line=total_lines,
                signature=sig,
                docstring="",
                code=source_text,
                imports=[],
                calls=[],
                language=resolved_lang,
            )
        ]

    window_chunks: List[Chunk] = []
    part_num = 1
    for start_idx in range(0, total_lines, FALLBACK_WINDOW_STEP):
        end_idx = min(total_lines, start_idx + FALLBACK_WINDOW_SIZE)
        w_lines = lines[start_idx:end_idx]
        w_code = "\n".join(w_lines)
        w_start = start_idx + 1
        w_end = end_idx
        w_sig = w_lines[0].strip()[:100] if w_lines else ""

        cid = f"{chunk_id}#part{part_num}" if chunk_id else f"C{part_num}#part{part_num}"
        window_chunks.append(
            Chunk(
                id=cid,
                file_path=rel_path,
                symbol=f"<module>#part{part_num}",
                kind="module",
                start_line=w_start,
                end_line=w_end,
                signature=w_sig,
                docstring="",
                code=w_code,
                imports=[],
                calls=[],
                language=resolved_lang,
            )
        )
        part_num += 1
        if end_idx >= total_lines:
            break

    return window_chunks


def chunk_file(
    file_path: str,
    code: str,
    id_start: int = 1,
) -> List[Chunk]:
    """
    Chunks a single file into AST definitions (functions, methods, classes)
    using tree-sitter grammars and per-language extraction rules.
    Falls back to fallback_chunk() on errors or unsupported languages.
    """
    lang_cfg: Optional[LangConfig] = detect_language(file_path)
    if not lang_cfg:
        return fallback_chunk(code, file_path, language="unknown", chunk_id=f"C{id_start}")

    try:
        parser = tsl.get_parser(lang_cfg.ts_name)
        code_bytes = code.encode("utf-8")
        tree = parser.parse(code_bytes)
        root = tree.root_node

        # If root node has severe error across the file, fall back
        if root.has_error:
            error_children = [c for c in root.children if c.type == "ERROR"]
            if root.type == "ERROR" or (len(error_children) > 0 and len(error_children) >= max(1, len(root.children) // 2)):
                return fallback_chunk(code, file_path, language=lang_cfg.name, chunk_id=f"C{id_start}")

        source_lines = code.splitlines()
        file_imports = extract_file_imports(root, lang_cfg.name)
        chunks: List[Chunk] = []
        curr_id = id_start

        def next_chunk_id() -> str:
            nonlocal curr_id
            cid = f"C{curr_id}"
            curr_id += 1
            return cid

        # Traverse AST and collect chunks
        def visit(node: Any) -> None:
            # 1. Functions & Methods
            if node.type in lang_cfg.function_nodes:
                emit_function_chunk(node)

            # 2. JS/TS arrow functions & function expressions
            elif lang_cfg.name in ("javascript", "typescript") and node.type in ("arrow_function", "function_expression", "function"):
                emit_js_arrow_or_expr_chunk(node)

            # 3. Classes & Interfaces / Go type_spec
            elif node.type in lang_cfg.class_nodes:
                emit_class_chunk(node)

            for child in node.children:
                visit(child)

        def emit_function_chunk(node: Any) -> None:
            # Name extraction
            name_node = node.child_by_field_name("name")
            if not name_node:
                return
            base_name = name_node.text.decode("utf-8", errors="replace")

            # Check Go method_declaration
            if lang_cfg.name == "go" and node.type == "method_declaration":
                rcv = node.child_by_field_name("receiver")
                rcv_type = ""
                if rcv:
                    for param in rcv.named_children:
                        t_node = param.child_by_field_name("type")
                        if t_node:
                            rcv_type = t_node.text.decode("utf-8", errors="replace").lstrip("*").strip()
                            break
                symbol = f"{rcv_type}.{base_name}" if rcv_type else base_name
                kind = "method"
            else:
                # Check method prefixing via ancestor class
                enclosing_class = find_enclosing_class(node, lang_cfg.class_nodes)
                if enclosing_class:
                    symbol = f"{enclosing_class}.{base_name}"
                    kind = "method"
                else:
                    symbol = base_name
                    kind = "function"

            doc_target = node
            stmt = node
            if lang_cfg.name in ("javascript", "typescript"):
                if node.parent and node.parent.type == "export_statement":
                    doc_target = node.parent
                    stmt = node.parent

            # Docstring extraction
            if lang_cfg.name == "python":
                body = node.child_by_field_name("body")
                docstring = extract_python_docstring(body)
            else:
                docstring = extract_preceding_comments(doc_target)

            start_line = stmt.start_point.row + 1
            end_line = stmt.end_point.row + 1
            node_code = "\n".join(source_lines[start_line - 1 : end_line])
            signature = extract_signature(stmt, source_lines)
            calls = extract_calls(node, lang_cfg.name)

            chunks.append(
                Chunk(
                    id=next_chunk_id(),
                    file_path=file_path,
                    symbol=symbol,
                    kind=kind,
                    start_line=start_line,
                    end_line=end_line,
                    signature=signature,
                    docstring=docstring,
                    code=node_code,
                    imports=file_imports,
                    calls=calls,
                    language=lang_cfg.name,
                )
            )

        def emit_js_arrow_or_expr_chunk(node: Any) -> None:
            # Only emit if parent is variable_declarator
            if not (node.parent and node.parent.type == "variable_declarator"):
                return

            name_node = node.parent.child_by_field_name("name")
            if not name_node:
                return
            base_name = name_node.text.decode("utf-8", errors="replace")

            # Check enclosing class
            enclosing_class = find_enclosing_class(node, lang_cfg.class_nodes)
            if enclosing_class:
                symbol = f"{enclosing_class}.{base_name}"
                kind = "method"
            else:
                symbol = base_name
                kind = "function"

            # Determine outer declaration for signature, docstrings, lines
            var_decl = node.parent.parent  # lexical_declaration or variable_declaration
            export_stmt = var_decl.parent if (var_decl and var_decl.parent and var_decl.parent.type == "export_statement") else None
            stmt = export_stmt if export_stmt else (var_decl if var_decl else node)

            docstring = extract_preceding_comments(stmt)
            start_line = stmt.start_point.row + 1
            end_line = stmt.end_point.row + 1
            node_code = "\n".join(source_lines[start_line - 1 : end_line])
            signature = extract_signature(stmt, source_lines)
            calls = extract_calls(node, lang_cfg.name)

            chunks.append(
                Chunk(
                    id=next_chunk_id(),
                    file_path=file_path,
                    symbol=symbol,
                    kind=kind,
                    start_line=start_line,
                    end_line=end_line,
                    signature=signature,
                    docstring=docstring,
                    code=node_code,
                    imports=file_imports,
                    calls=calls,
                    language=lang_cfg.name,
                )
            )

        def emit_class_chunk(node: Any) -> None:
            # Go type_spec special rule
            if lang_cfg.name == "go" and node.type == "type_spec":
                t_field = node.child_by_field_name("type")
                if not (t_field and t_field.type in ("struct_type", "interface_type")):
                    return

            name_node = node.child_by_field_name("name")
            if not name_node:
                return
            class_name = name_node.text.decode("utf-8", errors="replace")

            stmt = node
            doc_target = node
            if lang_cfg.name == "go" and node.type == "type_spec":
                if node.parent and node.parent.type == "type_declaration":
                    stmt = node.parent
                    doc_target = node.parent
            elif lang_cfg.name in ("javascript", "typescript"):
                if node.parent and node.parent.type == "export_statement":
                    stmt = node.parent
                    doc_target = node.parent

            # Docstring extraction
            if lang_cfg.name == "python":
                body = node.child_by_field_name("body")
                docstring = extract_python_docstring(body)
            else:
                docstring = extract_preceding_comments(doc_target)

            start_line = stmt.start_point.row + 1
            end_line = stmt.end_point.row + 1
            node_code = "\n".join(source_lines[start_line - 1 : end_line])
            signature = extract_signature(stmt, source_lines)
            calls = extract_calls(node, lang_cfg.name)

            chunks.append(
                Chunk(
                    id=next_chunk_id(),
                    file_path=file_path,
                    symbol=class_name,
                    kind="class",
                    start_line=start_line,
                    end_line=end_line,
                    signature=signature,
                    docstring=docstring,
                    code=node_code,
                    imports=file_imports,
                    calls=calls,
                    language=lang_cfg.name,
                )
            )

        visit(root)

        # If no chunks emitted (e.g. script without definitions), emit fallback module chunk
        if not chunks:
            return fallback_chunk(code, file_path, language=lang_cfg.name, chunk_id=f"C{id_start}")

        return apply_windowing(chunks)

    except Exception:
        # Never crash
        return fallback_chunk(code, file_path, language=lang_cfg.name if lang_cfg else "unknown", chunk_id=f"C{id_start}")
