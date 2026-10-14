"""
retrieval.py
------------
Dependency-free hybrid retrieval for clause-level evidence.

Implements two classic information-retrieval scorers in pure Python:
  * BM25        -> rewards exact keyword/section-number matches
                  (scheme rules are full of specific words like "AAY", "80%")
  * TF-IDF cosine -> captures semantic-ish term overlap

Scores from both are min-max normalised and linearly combined, so a clause that
is strong on either signal is surfaced. This mirrors the "dense + BM25 hybrid,
re-ranker" design in the project specification.
"""
import math
import re
from collections import Counter

from . import config

_TOKEN_RE = re.compile(r"[a-z0-9%]+")

# Words that carry little discriminative signal in this domain.
_STOPWORDS = {
    "the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "is", "are",
    "be", "by", "with", "as", "at", "it", "this", "that", "must", "shall",
    "will", "any", "all", "from", "under", "into", "than", "not", "no",
}


def tokenize(text: str):
    """Lowercase word tokenizer with light stopword removal."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class HybridRetriever:
    """Clause-level hybrid retriever built over an in-memory corpus."""

    def __init__(self, documents: list):
        # documents: list of dicts with at least {"doc_id", "text", "scheme_id", "type"}
        self.documents = documents
        self.tokenized = [tokenize(d["text"]) for d in documents]
        self._build()

    # -- index construction ---------------------------------------------------
    def _build(self):
        self.N = len(self.documents)
        self.doc_freq = Counter()
        for toks in self.tokenized:
            for term in set(toks):
                self.doc_freq[term] += 1
        self.avgdl = (sum(len(t) for t in self.tokenized) / self.N) if self.N else 0.0

        # Precompute BM25 term frequencies + lengths
        self.tfs = [Counter(toks) for toks in self.tokenized]
        self.doc_len = [len(toks) for toks in self.tokenized]

        # Inverse document frequency for TF-IDF
        self.idf = {
            term: math.log((1 + self.N) / (1 + df)) + 1.0
            for term, df in self.doc_freq.items()
        }

    # -- scorers --------------------------------------------------------------
    def _bm25(self, query_tokens, k1=1.5, b=0.75):
        scores = [0.0] * self.N
        for term in query_tokens:
            if term not in self.doc_freq:
                continue
            df = self.doc_freq[term]
            idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)
            for i in range(self.N):
                tf = self.tfs[i].get(term, 0)
                if tf == 0:
                    continue
                denom = tf + k1 * (1 - b + b * self.doc_len[i] / (self.avgdl or 1))
                scores[i] += idf * (tf * (k1 + 1)) / denom
        return scores

    def _tfidf(self, query_tokens):
        # Document norms
        doc_vecs = []
        for toks in self.tokenized:
            tf = Counter(toks)
            vec = {term: (count / len(toks)) * self.idf.get(term, 0.0)
                   for term, count in tf.items()} if toks else {}
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            doc_vecs.append((vec, norm))

        qtf = Counter(query_tokens)
        qvec = {term: (count / len(query_tokens)) * self.idf.get(term, 0.0)
                for term, count in qtf.items()} if query_tokens else {}
        qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1.0

        scores = []
        for vec, norm in doc_vecs:
            dot = sum(qvec.get(term, 0.0) * w for term, w in vec.items())
            scores.append(dot / (qnorm * norm))
        return scores

    @staticmethod
    def _normalise(scores):
        if not scores:
            return scores
        lo, hi = min(scores), max(scores)
        if hi - lo < 1e-12:
            return [0.0 for _ in scores]
        return [(s - lo) / (hi - lo) for s in scores]

    # -- public API -----------------------------------------------------------
    def search(self, query: str, top_k: int = None, scheme_id: str = None,
               clause_types: list = None):
        """Return the top-k clauses relevant to `query`.

        Optionally restricted to a scheme and/or clause types
        (e.g. only "eligibility"/"entitlement").
        """
        top_k = top_k or config.TOP_K
        query_tokens = tokenize(query)
        if not query_tokens:
            # No usable query -> fall back to the first clauses of the scheme
            query_tokens = ["eligibility", "entitlement"]

        bm25 = self._normalise(self._bm25(query_tokens))
        dense = self._normalise(self._tfidf(query_tokens))

        candidates = []
        for i, doc in enumerate(self.documents):
            if scheme_id and doc.get("scheme_id") != scheme_id:
                continue
            if clause_types and doc.get("type") not in clause_types:
                continue
            combined = (config.BM25_WEIGHT * bm25[i]) + (config.DENSE_WEIGHT * dense[i])
            # Small prior boost for clauses of the right type when filtering
            candidates.append((combined, doc))

        candidates.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, doc in candidates[:top_k]:
            results.append({
                "doc_id": doc["doc_id"],
                "scheme_id": doc.get("scheme_id"),
                "type": doc.get("type"),
                "text": doc["text"],
                "score": round(score, 4),
                "source": doc.get("source"),
            })
        return results
