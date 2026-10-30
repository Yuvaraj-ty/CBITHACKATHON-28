"""Language registry: maps file extensions to tree-sitter grammars and node types."""
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class LangConfig:
    name: str                 # our display name, stored in Chunk.language
    ts_name: str              # grammar name for tree_sitter_language_pack.get_parser
    extensions: tuple
    function_nodes: tuple     # emitted as kind="function" (or "method" if inside a class)
    class_nodes: tuple        # emitted as kind="class"
    import_nodes: tuple
    call_nodes: tuple

PYTHON = LangConfig(
    name="python", ts_name="python", extensions=(".py",),
    function_nodes=("function_definition",),
    class_nodes=("class_definition",),
    import_nodes=("import_statement", "import_from_statement"),
    call_nodes=("call",),
)

JAVASCRIPT = LangConfig(
    name="javascript", ts_name="javascript", extensions=(".js", ".jsx", ".mjs", ".cjs"),
    function_nodes=("function_declaration", "generator_function_declaration",
                    "method_definition"),   # arrow functions handled specially, see below
    class_nodes=("class_declaration",),
    import_nodes=("import_statement",),     # require() handled via call_nodes
    call_nodes=("call_expression",),
)

TYPESCRIPT = LangConfig(
    name="typescript", ts_name="typescript", extensions=(".ts",),
    function_nodes=("function_declaration", "generator_function_declaration",
                    "method_definition"),
    class_nodes=("class_declaration", "abstract_class_declaration",
                 "interface_declaration"),
    import_nodes=("import_statement",),
    call_nodes=("call_expression",),
)

TSX = LangConfig(
    name="typescript", ts_name="tsx", extensions=(".tsx",),   # same display name
    function_nodes=TYPESCRIPT.function_nodes,
    class_nodes=TYPESCRIPT.class_nodes,
    import_nodes=TYPESCRIPT.import_nodes,
    call_nodes=TYPESCRIPT.call_nodes,
)

JAVA = LangConfig(
    name="java", ts_name="java", extensions=(".java",),
    function_nodes=("method_declaration", "constructor_declaration"),
    class_nodes=("class_declaration", "interface_declaration",
                 "enum_declaration", "record_declaration"),
    import_nodes=("import_declaration",),
    call_nodes=("method_invocation",),      # name field holds the method name
)

GO = LangConfig(
    name="go", ts_name="go", extensions=(".go",),
    function_nodes=("function_declaration", "method_declaration"),
    class_nodes=("type_spec",),             # struct/interface definitions live in type_spec
    import_nodes=("import_declaration",),   # contains import_spec -> path field
    call_nodes=("call_expression",),
)

LANGUAGES = {c.name + ":" + c.ts_name: c for c in (PYTHON, JAVASCRIPT, TYPESCRIPT, TSX, JAVA, GO)}
_EXT_MAP = {ext: cfg for cfg in LANGUAGES.values() for ext in cfg.extensions}

def detect_language(file_path: str):
    """Return the LangConfig for a file, or None (-> fallback chunker)."""
    return _EXT_MAP.get(Path(file_path).suffix.lower())

SUPPORTED_EXTENSIONS = tuple(_EXT_MAP)