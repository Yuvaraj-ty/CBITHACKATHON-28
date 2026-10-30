import os
import json
import tempfile
import streamlit as st

from core.scanner import extract_zip_safely, scan_repository
from core.search import search_index
from core.explainer import explain_result

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="CodeLens — Intelligent Repository Search",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom developer-focused CSS
st.markdown("""
<style>
    .badge-func {
        background-color: #0284c7;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-class {
        background-color: #7c3aed;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-method {
        background-color: #059669;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-score {
        background-color: #eab308;
        color: #111827;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
    }
    .file-badge {
        font-family: monospace;
        color: #60a5fa;
        font-size: 13px;
    }
    .line-badge {
        font-family: monospace;
        color: #f87171;
        font-size: 13px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
if "index_data" not in st.session_state:
    st.session_state.index_data = None
if "repo_name" not in st.session_state:
    st.session_state.repo_name = None


# ---------------------------------------------------------
# Sidebar: Configuration & Repository Upload
# ---------------------------------------------------------
with st.sidebar:
    st.title("🔍 CodeLens")
    st.caption("AST-Powered Python Repository Search")
    st.markdown("---")

    # API Configuration (Optional)
    st.subheader("⚙️ AI Configuration")
    st.info("💡 **API key is optional!** CodeLens works 100% out of the box with built-in AST heuristics.", icon="ℹ️")

    api_provider = st.selectbox("AI Provider", ["Gemini", "OpenAI"], index=0)
    api_key_input = st.text_input(
        f"{api_provider} API Key (Optional)",
        type="password",
        help="Optional: Enter an API key for LLM-powered explanations, or leave blank to use the built-in analyzer."
    )

    st.markdown("---")
    st.subheader("📦 Repository Source")

    # Demo quick-load button
    if os.path.exists("sample_repo.zip"):
        if st.button("🚀 Load Pre-packaged Sample Repo", use_container_width=True):
            with st.spinner("Extracting and parsing sample repository AST..."):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    extract_zip_safely("sample_repo.zip", tmp_dir)
                    st.session_state.index_data = scan_repository(tmp_dir)
                    st.session_state.repo_name = "sample_repo.zip"
                    st.success("Sample repository indexed!")

    # File uploader for user ZIP
    uploaded_file = st.file_uploader(
        "Upload Repository (.zip)",
        type=["zip"],
        help="Upload a ZIP file of any Python repository. node_modules, .git, and build folders are automatically ignored."
    )

    if uploaded_file is not None:
        if st.session_state.repo_name != uploaded_file.name:
            with st.spinner(f"Extracting and indexing `{uploaded_file.name}`..."):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    extract_zip_safely(uploaded_file, tmp_dir)
                    st.session_state.index_data = scan_repository(tmp_dir)
                    st.session_state.repo_name = uploaded_file.name
                    st.success(f"Successfully indexed {uploaded_file.name}!")

    if st.session_state.index_data:
        st.markdown("---")
        st.subheader("📥 Export Index")
        index_json_str = json.dumps(st.session_state.index_data, indent=2)
        st.download_button(
            label="Download Index (JSON)",
            data=index_json_str,
            file_name="codelens_index.json",
            mime="application/json",
            use_container_width=True
        )


# ---------------------------------------------------------
# Main Panel
# ---------------------------------------------------------
st.header("⚡ CodeLens — Repository Explorer & Search")

if not st.session_state.index_data:
    st.markdown("""
    ### Welcome to CodeLens!
    CodeLens performs static AST inspection on Python repositories to index functions, methods, and classes with exact line precision.

    #### Quick Start:
    1. Click **'🚀 Load Pre-packaged Sample Repo'** in the sidebar for an instant demo.
    2. Or upload your own GitHub repository ZIP file.
    3. Search any keyword or function name to inspect code and line numbers.
    """)
else:
    # ---------------------------------------------------------
    # Repository Stats Overview
    # ---------------------------------------------------------
    summary = st.session_state.index_data["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Repository", st.session_state.repo_name)
    c2.metric("Python Files Scanned", summary["total_files"])
    c3.metric("Functions & Methods", summary["total_functions"])
    c4.metric("Classes Indexed", summary["total_classes"])

    with st.expander("📂 View Scanned Python Files"):
        st.write(summary.get("scanned_files", []))

    st.markdown("---")

    # ---------------------------------------------------------
    # Search Section
    # ---------------------------------------------------------
    st.subheader("🔎 Keyword Search & Ranking")

    col_search, col_btn = st.columns([4, 1])
    with col_search:
        search_query = st.text_input(
            "Search query",
            placeholder="e.g. 'token', 'charge', 'refund', 'user', 'calculate', 'metrics'",
            label_visibility="collapsed"
        )

    # Quick suggestion chips
    suggestions = ["token", "charge", "refund", "user", "metrics", "calculate"]
    st.write("**Quick suggestions:** " + " • ".join([f"`{s}`" for s in suggestions]))

    if not search_query.strip():
        st.info("👆 Enter a keyword above or select one of the suggestions to find and rank relevant functions and classes.")
    else:
        # Perform Search
        items = st.session_state.index_data.get("items", [])
        results = search_index(items, search_query, top_k=5)

        if not results:
            st.warning(f"No definitions found matching **'{search_query}'**. Try another keyword.")
        else:
            st.success(f"Found **{len(results)}** top matching results for **'{search_query}'** (ranked by AST relevance):")

            for idx, item in enumerate(results, start=1):
                badge_class = {
                    "function": "badge-func",
                    "class": "badge-class",
                    "method": "badge-method"
                }.get(item["type"], "badge-func")

                with st.container():
                    st.markdown(f"### #{idx}. `{item['name']}`")

                    meta_col1, meta_col2, meta_col3 = st.columns([2, 3, 1])
                    with meta_col1:
                        st.markdown(
                            f"<span class='{badge_class}'>{item['type']}</span> "
                            f"<span class='badge-score'>Score: {item['score']}</span>",
                            unsafe_allow_html=True
                        )
                    with meta_col2:
                        st.markdown(
                            f"<span class='file-badge'>📁 {item['file_path']}</span> : "
                            f"<span class='line-badge'>Lines {item['start_line']}–{item['end_line']}</span>",
                            unsafe_allow_html=True
                        )
                    with meta_col3:
                        if item.get("args"):
                            st.caption(f"Params: `{', '.join(item['args'])}`")

                    # Match Signals
                    if item.get("matched_reasons"):
                        st.markdown("**Matched signals:** " + " • ".join([f"`{r}`" for r in item["matched_reasons"]]))

                    # Source Code display
                    st.code(item["source_code"], language="python", line_numbers=True)

                    # AI / Heuristic Explanation
                    explanation_info = explain_result(
                        item,
                        search_query,
                        api_key=api_key_input,
                        provider=api_provider
                    )

                    with st.expander(f"💡 Why is this relevant? [{explanation_info['mode']}]", expanded=True):
                        st.markdown(explanation_info["explanation"])

                    st.markdown("---")
