"""Tree-sitter source analysis: symbols, calls, imports and per-function execution flow."""

import re
from functools import lru_cache

from tree_sitter_language_pack import get_parser

EXT_LANG = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".mts": "typescript", ".tsx": "tsx", ".java": "java", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".go": "go",
}
TEXT_LANG = {
    ".md": "markdown", ".json": "json", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".html": "markup",
    ".css": "css", ".scss": "css", ".sql": "sql", ".sh": "bash", ".rb": "ruby", ".php": "php", ".rs": "rust",
    ".kt": "kotlin", ".swift": "swift", ".cs": "csharp", ".txt": "text", ".vue": "markup", ".ini": "ini",
    ".cfg": "ini", ".xml": "markup", ".gradle": "groovy", ".env.example": "text",
}
PARSED_LANGUAGES = ["Python", "JavaScript", "TypeScript", "Java", "C", "C++", "Go"]

_JS = {
    "function_declaration": "function", "generator_function_declaration": "function", "method_definition": "method",
    "class_declaration": "class", "abstract_class_declaration": "class", "interface_declaration": "interface",
    "arrow_function": "function", "function_expression": "function", "function": "function",
}
SYMBOL_TYPES = {
    "python": {"function_definition": "function", "class_definition": "class"},
    "javascript": _JS, "typescript": _JS, "tsx": _JS,
    "java": {"method_declaration": "method", "constructor_declaration": "method", "class_declaration": "class",
             "interface_declaration": "interface", "enum_declaration": "class"},
    "c": {"function_definition": "function", "struct_specifier": "struct"},
    "cpp": {"function_definition": "function", "class_specifier": "class", "struct_specifier": "struct"},
    "go": {"function_declaration": "function", "method_declaration": "method"},
}
CALL_TYPES = {
    "python": {"call"}, "javascript": {"call_expression", "new_expression"}, "typescript": {"call_expression", "new_expression"},
    "tsx": {"call_expression", "new_expression"}, "java": {"method_invocation", "object_creation_expression"},
    "c": {"call_expression"}, "cpp": {"call_expression"}, "go": {"call_expression"},
}
IMPORT_TYPES = {
    "python": {"import_statement", "import_from_statement"}, "javascript": {"import_statement"},
    "typescript": {"import_statement"}, "tsx": {"import_statement"}, "java": {"import_declaration"},
    "c": {"preproc_include"}, "cpp": {"preproc_include"}, "go": {"import_declaration"},
}
ANON_FN = {"arrow_function", "function_expression", "function"}
CLASS_KINDS = {"class", "interface", "struct"}
WRAPPERS = {"export_statement", "lexical_declaration", "variable_declaration", "variable_declarator", "decorated_definition"}


@lru_cache(maxsize=None)
def _parser(lang: str):
    return get_parser(lang)


def detect_language(path: str) -> str | None:
    p = path.lower()
    for ext, lang in EXT_LANG.items():
        if p.endswith(ext):
            return lang
    for ext, lang in TEXT_LANG.items():
        if p.endswith(ext):
            return lang
    return None


def is_parsed(lang: str | None) -> bool:
    return lang in SYMBOL_TYPES


def _t(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", "replace")


def _clean(s: str, n: int) -> str:
    return re.sub(r"\s+", " ", s).strip()[:n]


def _declarator_name(node, src):
    cur = node
    for _ in range(12):
        d = cur.child_by_field_name("declarator")
        if d is None:
            break
        cur = d
    if cur.type == "qualified_identifier":
        n = cur.child_by_field_name("name")
        if n is not None:
            return _t(n, src)
    return _t(cur, src)


def _symbol_name(node, lang, src):
    if lang in ("c", "cpp") and node.type == "function_definition":
        return _declarator_name(node, src)
    if node.type in ANON_FN:
        p = node.parent
        if p is not None and p.type in ("variable_declarator", "public_field_definition", "field_definition", "pair", "assignment_expression"):
            n = p.child_by_field_name("name") or p.child_by_field_name("key") or p.child_by_field_name("left") or p.child_by_field_name("property")
            if n is not None:
                return _t(n, src).split(".")[-1].strip("'\"")
        return None
    n = node.child_by_field_name("name")
    return _t(n, src) if n is not None else None


def _params(node, lang, src) -> str:
    p = node.child_by_field_name("parameters")
    if p is None and lang in ("c", "cpp"):
        d = node.child_by_field_name("declarator")
        while d is not None and d.type != "function_declarator":
            d = d.child_by_field_name("declarator")
        if d is not None:
            p = d.child_by_field_name("parameters")
    if p is None and node.type == "arrow_function":
        p = node.child_by_field_name("parameter")
    return _clean(_t(p, src), 240) if p is not None else ""


def _returns(node, kind, src) -> str:
    if kind in CLASS_KINDS:
        return ""
    for f in ("return_type", "result", "type"):
        r = node.child_by_field_name(f)
        if r is not None:
            return _clean(_t(r, src), 120).lstrip(":").strip()
    return ""


def _is_doc(n) -> bool:
    return n.type == "string" or (n.type == "expression_statement" and n.named_child_count > 0 and n.named_children[0].type == "string")


def _doc(node, lang, src) -> str:
    if lang == "python":
        body = node.child_by_field_name("body")
        if body is not None and body.named_child_count:
            first = body.named_children[0]
            if _is_doc(first):
                return _clean(_t(first, src).strip("\"' \n"), 300)
        return ""
    target = node
    while target.parent is not None and target.parent.type in WRAPPERS:
        target = target.parent
    prev = target.prev_named_sibling
    if prev is not None and "comment" in prev.type:
        txt = re.sub(r"^\s*(/\*\*?|\*/|\*|//+)", "", _t(prev, src), flags=re.M)
        return _clean(txt.replace("*/", ""), 300)
    return ""


def _callee(node, src):
    f = (node.child_by_field_name("function") or node.child_by_field_name("name")
         or node.child_by_field_name("constructor") or node.child_by_field_name("type"))
    if f is None:
        return None
    txt = re.sub(r"<[^<>]*>", "", _t(f, src))
    ids = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", txt)
    return ids[-1] if ids else None


def extract(content: str, lang: str) -> dict:
    """Return {symbols: [...], imports: [...]} with 1-based line numbers taken from the parse tree."""
    src = content.encode("utf-8")
    tree = _parser(lang).parse(src)
    types, calls, imps = SYMBOL_TYPES[lang], CALL_TYPES[lang], IMPORT_TYPES.get(lang, set())
    symbols: list[dict] = []
    imports: list[str] = []
    stack = [(tree.root_node, None)]
    while stack:
        node, enc = stack.pop()
        t = node.type
        new_enc = enc
        if t in imps:
            imports.append(_clean(_t(node, src), 200))
            continue
        if t in types and not (t in ("struct_specifier", "class_specifier") and node.child_by_field_name("body") is None):
            name = _symbol_name(node, lang, src)
            if name:
                kind = types[t]
                if kind == "function" and enc is not None and symbols[enc]["kind"] in CLASS_KINDS:
                    kind = "method"
                first_line = _t(node, src).split("\n", 1)[0]
                symbols.append({
                    "name": name[:120], "kind": kind,
                    "start_line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1,
                    "params": _params(node, lang, src), "returns": _returns(node, kind, src),
                    "docstring": _doc(node, lang, src), "signature": _clean(first_line, 200),
                    "parent": symbols[enc]["name"] if enc is not None else None, "calls": [],
                })
                new_enc = len(symbols) - 1
        elif t in calls and enc is not None:
            c = _callee(node, src)
            if c and c not in symbols[enc]["calls"]:
                symbols[enc]["calls"].append(c)
        for ch in reversed(node.children):
            stack.append((ch, new_enc))
    return {"symbols": symbols, "imports": imports[:60]}


# ---------------------------------------------------------------- execution flow
IF_TYPES = {"if_statement"}
LOOP_TYPES = {"for_statement", "while_statement", "for_in_statement", "do_statement", "enhanced_for_statement",
              "for_range_loop", "foreach_statement", "for_of_statement"}
RETURN_TYPES = {"return_statement", "raise_statement", "throw_statement"}
TRY_TYPES = {"try_statement"}
HANDLER_TYPES = {"except_clause", "catch_clause", "finally_clause"}
SWITCH_TYPES = {"switch_statement", "match_statement", "expression_switch_statement", "type_switch_statement"}
BLOCK_TYPES = {"block", "statement_block", "compound_statement", "statement_list"}
MAX_FLOW_NODES = 70


def _stmts(n):
    if n is None:
        return []
    if n.type in BLOCK_TYPES:
        out = []
        for c in n.named_children:
            if "comment" in c.type:
                continue
            out.extend(_stmts(c) if c.type in BLOCK_TYPES else [c])
        return out
    return [n]


def _has_call(node, lang) -> bool:
    calls = CALL_TYPES[lang]
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type in calls:
            return True
        stack.extend(n.children)
    return False


def _find_fn(root, start_line, types):
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in types and n.start_point[0] + 1 == start_line:
            return n
        if n.start_point[0] + 1 <= start_line <= n.end_point[0] + 1:
            stack.extend(n.children)
    return None


def build_flow(content: str, lang: str, start_line: int, name: str) -> dict:
    src = content.encode("utf-8")
    tree = _parser(lang).parse(src)
    fn = _find_fn(tree.root_node, start_line, SYMBOL_TYPES[lang])
    if fn is None:
        return {"nodes": [], "edges": []}
    nodes: list[dict] = []
    edges: list[dict] = []

    def line(n):
        return n.start_point[0] + 1, n.end_point[0] + 1

    def label(n, prefix=""):
        return (prefix + _clean(_t(n, src).split("\n", 1)[0], 72)).rstrip(":{ ")

    def add(kind, text, s, e):
        nid = f"n{len(nodes)}"
        nodes.append({"id": nid, "kind": kind, "label": text, "start_line": s, "end_line": e})
        return nid

    def link(incoming, target):
        for src_id, lab in incoming:
            edges.append({"id": f"e{len(edges)}", "source": src_id, "target": target, "label": lab or ""})

    start = add("start", f"Start: {name}()", *line(fn))
    end = add("end", "End", fn.end_point[0] + 1, fn.end_point[0] + 1)

    def walk_block(stmts, incoming):
        pending: list = []

        def flush(inc):
            if not pending:
                return inc
            s, e = line(pending[0])[0], line(pending[-1])[1]
            kind = "call" if any(_has_call(p, lang) for p in pending) else "step"
            text = label(pending[0]) + (f"  (+{len(pending) - 1} more)" if len(pending) > 1 else "")
            nid = add(kind, text, s, e)
            link(inc, nid)
            pending.clear()
            return [(nid, "")]

        for s in stmts:
            if len(nodes) >= MAX_FLOW_NODES:
                break
            simple = s.type not in IF_TYPES | LOOP_TYPES | RETURN_TYPES | TRY_TYPES | SWITCH_TYPES and s.type != "with_statement"
            if simple:
                if pending and (len(pending) >= 3 or _has_call(s, lang) != _has_call(pending[0], lang)):
                    incoming = flush(incoming)
                pending.append(s)
                continue
            incoming = flush(incoming)
            incoming = walk_stmt(s, incoming)
            if not incoming:
                return []
        return flush(incoming)

    def walk_alts(alts, from_id):
        if not alts:
            return [(from_id, "false")]
        a = alts[0]
        if a.type == "elif_clause":
            cid = add("condition", label(a.child_by_field_name("condition") or a, "elif "), *line(a))
            link([(from_id, "false")], cid)
            return walk_block(_stmts(a.child_by_field_name("consequence")), [(cid, "true")]) + walk_alts(alts[1:], cid)
        body = a.child_by_field_name("body") or (a.named_children[0] if a.named_child_count else None)
        return walk_block(_stmts(body), [(from_id, "false")])

    def walk_stmt(s, incoming):
        t = s.type
        if t in IF_TYPES:
            cond = s.child_by_field_name("condition")
            cid = add("condition", label(cond, "if ") if cond is not None else label(s), *line(s))
            link(incoming, cid)
            then_exits = walk_block(_stmts(s.child_by_field_name("consequence")), [(cid, "true")])
            return then_exits + walk_alts(s.children_by_field_name("alternative"), cid)
        if t in LOOP_TYPES:
            lid = add("loop", label(s), *line(s))
            link(incoming, lid)
            body_exits = walk_block(_stmts(s.child_by_field_name("body")), [(lid, "each")])
            link([(e, "next") for e, _ in body_exits], lid)
            return [(lid, "done")]
        if t in RETURN_TYPES:
            rid = add("return", label(s), *line(s))
            link(incoming, rid)
            link([(rid, "")], end)
            return []
        if t in TRY_TYPES:
            tid = add("step", "try", *line(s))
            link(incoming, tid)
            exits = walk_block(_stmts(s.child_by_field_name("body")), [(tid, "")])
            for h in s.named_children:
                if h.type in HANDLER_TYPES:
                    hid = add("condition", label(h), *line(h))
                    link([(tid, "on error" if h.type != "finally_clause" else "finally")], hid)
                    blk = next((c for c in h.named_children if c.type in BLOCK_TYPES), None)
                    exits += walk_block(_stmts(blk), [(hid, "")])
            return exits
        if t == "with_statement":
            wid = add("step", label(s), *line(s))
            link(incoming, wid)
            return walk_block(_stmts(s.child_by_field_name("body")), [(wid, "")])
        sid = add("condition", label(s), *line(s))
        link(incoming, sid)
        return [(sid, "")]

    body = fn.child_by_field_name("body")
    if body is not None and body.type not in BLOCK_TYPES and fn.type == "arrow_function":
        rid = add("return", "return " + label(body), *line(body))
        link([(start, "")], rid)
        link([(rid, "")], end)
    else:
        stmts = _stmts(body)
        if lang == "python" and stmts and _is_doc(stmts[0]):
            stmts = stmts[1:]  # skip docstring
        exits = walk_block(stmts, [(start, "")])
        link(exits, end)
    return {"nodes": nodes, "edges": edges}
