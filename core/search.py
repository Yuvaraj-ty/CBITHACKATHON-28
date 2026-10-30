import re
from typing import List, Dict, Any


def tokenize(text: str) -> List[str]:
    """
    Splits text into lowercase alphanumeric tokens, handling snake_case and camelCase.
    """
    if not text:
        return []
    # Split camelCase (e.g. calculateTotal -> calculate Total)
    camel_split = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # Extract lowercase words
    tokens = re.findall(r'[a-zA-Z0-9_]+', camel_split.lower())
    # Further split snake_case tokens
    sub_tokens = []
    for t in tokens:
        sub_tokens.append(t)
        if '_' in t:
            sub_tokens.extend([part for part in t.split('_') if part])
    return list(set(sub_tokens))


def calculate_relevance(item: Dict[str, Any], query_tokens: List[str], raw_query: str) -> Dict[str, Any]:
    """
    Computes a relevance score and collects matching reasons for an indexed item.
    """
    score = 0
    matched_reasons = []

    name_lower = item["name"].lower()
    doc_lower = (item.get("docstring") or "").lower()
    source_lower = (item.get("source_code") or "").lower()
    path_lower = item.get("file_path", "").lower()
    args_lower = [a.lower() for a in item.get("args", [])]

    clean_raw_query = raw_query.strip().lower()

    # 1. Exact match on function/class name
    if clean_raw_query == name_lower or clean_raw_query == name_lower.split('.')[-1]:
        score += 150
        matched_reasons.append(f"Exact match on definition name '{item['name']}'")

    for token in query_tokens:
        if not token or len(token) < 2:
            continue

        token_matched = False

        # 2. Match in item name
        if token == name_lower or token in name_lower.split('.'):
            score += 60
            matched_reasons.append(f"Name matches keyword '{token}'")
            token_matched = True
        elif token in name_lower:
            score += 30
            matched_reasons.append(f"Name contains '{token}'")
            token_matched = True

        # 3. Match in arguments
        if token in args_lower:
            score += 20
            matched_reasons.append(f"Accepts parameter '{token}'")
            token_matched = True

        # 4. Match in docstring
        if token in doc_lower:
            occurrences = doc_lower.count(token)
            doc_score = min(25, occurrences * 10)
            score += doc_score
            matched_reasons.append(f"Docstring mentions '{token}' ({occurrences}x)")
            token_matched = True

        # 5. Match in file path
        if token in path_lower:
            score += 15
            matched_reasons.append(f"Located in matching file path '{item['file_path']}'")
            token_matched = True

        # 6. Match in source code body
        if token in source_lower:
            occurrences = source_lower.count(token)
            code_score = min(20, occurrences * 3)
            score += code_score
            if not token_matched:
                matched_reasons.append(f"Source code body uses '{token}' ({occurrences}x)")

    # Boost functions over raw class container if query is an action verb (optional nuance)
    if item["type"] in ("function", "method") and score > 0:
        score += 5

    return {
        "score": score,
        "matched_reasons": list(dict.fromkeys(matched_reasons))  # preserve order & deduplicate
    }


def search_index(items: List[Dict[str, Any]], query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Searches the indexed items using keyword matching and ranking.
    Returns the top_k ranked results.
    """
    if not query or not query.strip():
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    scored_results = []
    for item in items:
        ranking_info = calculate_relevance(item, query_tokens, query)
        if ranking_info["score"] > 0:
            result = dict(item)
            result["score"] = ranking_info["score"]
            result["matched_reasons"] = ranking_info["matched_reasons"]
            scored_results.append(result)

    # Sort descending by score, tie-breaker: shorter name or earlier line
    scored_results.sort(key=lambda x: (x["score"], -x["start_line"]), reverse=True)

    return scored_results[:top_k]
