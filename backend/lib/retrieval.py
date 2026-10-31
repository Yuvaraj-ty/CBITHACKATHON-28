"""Hybrid retrieval: BM25 lexical scoring + TF-IDF/LSA semantic vectors, fused and ranked per repo."""

import math
import re
import threading
from collections import Counter

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from lib.sqldb import query

STOP = set(
    "a an the is are was were be been of to in on for and or not with without by at as it its this that these those "
    "what which who whom how why where when do does did can could should would will shall may might i you we they "
    "me my our your their there here from into about explain show tell give please code function file repo repository "
    "project codebase work works working happens use used using get gets".split()
)
EXPANSIONS = {
    "auth": ["login", "authenticate", "password", "token", "session", "credential", "verify"],
    "authentication": ["auth", "login", "authenticate", "password", "token", "session", "credential"],
    "login": ["auth", "authenticate", "password", "credential", "session", "signin"],
    "register": ["registration", "signup", "create", "user"],
    "registration": ["register", "signup", "create", "user"],
    "database": ["db", "query", "sql", "cursor", "connection", "insert", "select"],
    "db": ["database", "query", "sql", "connection"],
    "error": ["exception", "raise", "throw", "catch", "fail"],
    "test": ["assert", "pytest", "expect", "spec"],
    "route": ["endpoint", "handler", "api", "request", "router"],
    "api": ["endpoint", "route", "request", "fetch", "http"],
    "form": ["submit", "input", "fetch", "event"],
    "config": ["settings", "env", "configuration"],
}


def _stem(w: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ers", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def tokenize(text: str) -> list[str]:
    out = []
    for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text):
        parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", tok).replace("_", " ").lower().split()
        whole = tok.lower()
        if len(parts) > 1 and whole not in STOP:
            out.append(whole)
        for p in parts:
            if len(p) > 1 and p not in STOP:
                out.append(_stem(p))
    return out


class RepoIndex:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.docs = [tokenize(f"{c['symbol_name'] or ''} {c['symbol_name'] or ''} {c['file_path']} {c['content']}") for c in chunks]
        self.tfs = [Counter(d) for d in self.docs]
        self.doc_sets = [set(d) for d in self.docs]
        n = len(self.docs)
        self.avgdl = (sum(len(d) for d in self.docs) / n) if n else 1
        df: Counter = Counter()
        for s in self.doc_sets:
            df.update(s)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.sym_parts = [set(tokenize(c["symbol_name"] or "")) for c in chunks]
        self.vectorizer = TfidfVectorizer(analyzer=lambda s: s, sublinear_tf=True)
        mat = self.vectorizer.fit_transform(self.docs) if n else None
        self.svd = None
        if mat is not None and n >= 8 and mat.shape[1] > 8:
            self.svd = TruncatedSVD(n_components=min(100, n - 1, mat.shape[1] - 1), random_state=0)
            self.vecs = normalize(self.svd.fit_transform(mat))
        elif mat is not None:
            self.vecs = normalize(mat.toarray())
        else:
            self.vecs = np.zeros((0, 1))

    def _bm25(self, terms: dict[str, float]) -> np.ndarray:
        k1, b = 1.4, 0.75
        scores = np.zeros(len(self.docs))
        for i, tf in enumerate(self.tfs):
            dl = len(self.docs[i]) or 1
            s = 0.0
            for t, w in terms.items():
                f = tf.get(t)
                if f:
                    s += w * self.idf.get(t, 0) * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / self.avgdl))
            scores[i] = s
        return scores

    def _semantic(self, qtokens: list[str]) -> np.ndarray:
        if not len(self.docs) or not qtokens:
            return np.zeros(len(self.docs))
        q = self.vectorizer.transform([qtokens])
        qv = normalize(self.svd.transform(q)) if self.svd is not None else normalize(q.toarray())
        return np.clip(self.vecs @ qv[0], 0, 1)

    def search(self, text: str, k: int = 6) -> list[dict]:
        qt = list(dict.fromkeys(tokenize(text)))
        if not qt or not self.docs:
            return []
        terms = {t: 1.0 for t in qt}
        for t in qt:
            for e in EXPANSIONS.get(t, []):
                terms.setdefault(_stem(e), 0.35)
        bm = self._bm25(terms)
        sem = self._semantic(qt + [t for t, w in terms.items() if w < 1])
        bm_norm = bm / bm.max() if bm.max() > 0 else bm
        sem_rng = sem.max() - sem.min()
        sem_norm = (sem - sem.min()) / sem_rng if sem_rng > 0 else sem
        qset = set(qt)
        lowered = text.lower()
        sym = np.array([
            1.0 if (c["symbol_name"] and (re.search(rf"\b{re.escape(c['symbol_name'].lower())}\b", lowered) or (parts and parts <= qset))) else 0.0
            for c, parts in zip(self.chunks, self.sym_parts)
        ])
        hybrid = 0.45 * bm_norm + 0.40 * sem_norm + 0.15 * sym
        order = np.argsort(-hybrid)
        hits, seen = [], set()
        for i in order:
            if len(hits) >= k:
                break
            if bm[i] <= 0 and sem[i] < 0.08:
                continue
            c = self.chunks[i]
            key = c["symbol_id"] or f"{c['file_path']}:{c['start_line']}"
            if key in seen:
                continue
            seen.add(key)
            matched = sorted(qset & self.doc_sets[i])
            hits.append({
                **c,
                "score": round(float(hybrid[i]), 4),
                "lexical": round(float(bm_norm[i]), 4),
                "lexical_coverage": round(len(matched) / len(qset), 4),
                "semantic": round(float(sem[i]), 4),
                "symbol_match": bool(sym[i]),
                "matched_terms": matched[:8],
            })
        return hits


def evidence_quality(hits: list[dict]) -> dict:
    if not hits:
        return {"score": 0.0, "level": "insufficient", "factors": {}, "insufficient": True,
                "note": "No source code matched this question."}
    top = hits[:3]
    lexical = max(h["lexical_coverage"] for h in top)
    semantic = max(h["semantic"] for h in top)
    symbol = 1.0 if any(h["symbol_match"] for h in hits) else 0.0
    best = hits[0]["score"]
    agreement = min(1.0, sum(1 for h in hits if h["score"] >= 0.5 * best and h["lexical_coverage"] >= 0.3) / 3)
    context = min(1.0, sum(h["end_line"] - h["start_line"] + 1 for h in top) / 40)
    score = 0.30 * lexical + 0.25 * semantic + 0.15 * symbol + 0.15 * agreement + 0.15 * context
    insufficient = lexical < 0.2 and semantic < 0.15
    level = "insufficient" if insufficient else ("high" if score >= 0.6 else "medium" if score >= 0.38 else "low")
    return {
        "score": round(score, 3), "level": level, "insufficient": insufficient,
        "factors": {"lexical": round(lexical, 3), "semantic": round(semantic, 3), "symbol": symbol,
                    "agreement": round(agreement, 3), "context": round(context, 3)},
        "note": "Measures how well the retrieved code matches your question - not a guarantee the explanation is correct.",
    }


def reason_for(hit: dict) -> str:
    parts = []
    if hit.get("symbol_name"):
        parts.append(f"Defines `{hit['symbol_name']}` ({hit.get('symbol_kind') or 'code'})")
    else:
        parts.append(f"Section of {hit['file_path']}")
    if hit.get("symbol_match"):
        parts.append("its name matches your question")
    if hit.get("matched_terms"):
        parts.append("contains terms: " + ", ".join(hit["matched_terms"][:5]))
    if hit.get("semantic", 0) >= 0.35:
        parts.append(f"conceptually similar (semantic {hit['semantic']:.2f})")
    return "; ".join(parts) + "."


_cache: dict[str, RepoIndex] = {}
_lock = threading.Lock()


def get_index(repo_id: str) -> RepoIndex:
    with _lock:
        idx = _cache.get(repo_id)
    if idx is None:
        idx = RepoIndex(query("SELECT * FROM chunks WHERE repo_id = ? ORDER BY file_path, start_line", (repo_id,)))
        with _lock:
            _cache[repo_id] = idx
    return idx


def drop_index(repo_id: str) -> None:
    with _lock:
        _cache.pop(repo_id, None)
