import os
import json
import math
import re
from typing import List, Dict, Tuple
from openai import OpenAI


class RAGService:
    """
    Simple Retrieval-Augmented Generation (RAG) system.
    Uses TF-IDF-style cosine similarity for retrieval (no external vector DB needed)
    and OpenAI for answer generation.
    """

    def __init__(self, api_key: str = None):
        self.client = OpenAI(
            api_key=api_key or os.getenv('GAPGPT_API_KEY') or os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('GAPGPT_BASE_URL', 'https://api.gapgpt.app/v1')
        )
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o')
        # In-memory document store: { doc_id: { chunks: [...], tfidf: [...] } }
        self.document_store: Dict[str, Dict] = {}

    # ------------------------------------------------------------------ #
    #  Indexing                                                            #
    # ------------------------------------------------------------------ #

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunks.append(" ".join(words[start:end]))
            start += chunk_size - overlap
        return chunks

    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace + punctuation tokenizer (works for Persian & English)."""
        return re.findall(r'\w+', text.lower())

    def _compute_tfidf(self, chunks: List[str]) -> List[Dict[str, float]]:
        """Compute TF-IDF vectors for a list of text chunks."""
        tokenized = [self._tokenize(c) for c in chunks]
        N = len(chunks)

        # IDF
        df: Dict[str, int] = {}
        for tokens in tokenized:
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1
        idf = {t: math.log((N + 1) / (v + 1)) + 1 for t, v in df.items()}

        vectors = []
        for tokens in tokenized:
            tf: Dict[str, float] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            length = len(tokens) or 1
            vec = {t: (cnt / length) * idf.get(t, 1) for t, cnt in tf.items()}
            vectors.append(vec)
        return vectors

    def _cosine(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        common = set(a) & set(b)
        if not common:
            return 0.0
        dot = sum(a[t] * b[t] for t in common)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        return dot / (norm_a * norm_b + 1e-9)

    def index_document(self, doc_id: str, text: str) -> int:
        """Index a document and return the number of chunks created."""
        chunks = self._chunk_text(text)
        tfidf = self._compute_tfidf(chunks)
        self.document_store[doc_id] = {"chunks": chunks, "tfidf": tfidf}
        return len(chunks)

    def list_documents(self) -> List[str]:
        return list(self.document_store.keys())

    def delete_document(self, doc_id: str) -> bool:
        if doc_id in self.document_store:
            del self.document_store[doc_id]
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Retrieval                                                           #
    # ------------------------------------------------------------------ #

    def _retrieve(self, query: str, doc_id: str = None, top_k: int = 5) -> List[Tuple[str, float]]:
        """Return top-k (chunk, score) pairs from the specified doc or all docs."""
        q_vec = self._compute_tfidf([query])[0]
        results = []

        docs = {doc_id: self.document_store[doc_id]} if doc_id and doc_id in self.document_store \
               else self.document_store

        for d in docs.values():
            for chunk, vec in zip(d["chunks"], d["tfidf"]):
                score = self._cosine(q_vec, vec)
                results.append((chunk, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------ #
    #  Generation                                                          #
    # ------------------------------------------------------------------ #

    def query(self, question: str, doc_id: str = None, top_k: int = 5) -> Dict:
        """Retrieve relevant chunks and generate an answer."""
        if not self.document_store:
            return {"answer": "هیچ سندی هنوز فهرست‌بندی نشده است. ابتدا یک سند آپلود کنید.",
                    "sources": [], "question": question}

        relevant = self._retrieve(question, doc_id, top_k)
        context = "\n\n---\n\n".join(chunk for chunk, _ in relevant if _ > 0.01)

        if not context.strip():
            context = "اطلاعاتی در اسناد موجود یافت نشد."

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": (
                    "You are a helpful assistant that answers questions based ONLY on the provided context. "
                    "If the answer is not in the context, say so clearly. "
                    "You can answer in Persian or English depending on the question language."
                )},
                {"role": "user", "content": (
                    f"Context:\n{context}\n\n"
                    f"Question: {question}\n\n"
                    "Answer based strictly on the context above."
                )}
            ],
            max_tokens=1024,
            temperature=0.3
        )

        return {
            "question": question,
            "answer": response.choices[0].message.content,
            "sources": [{"chunk": chunk[:200] + "...", "score": round(score, 4)}
                        for chunk, score in relevant if score > 0.01],
            "doc_id": doc_id
        }
