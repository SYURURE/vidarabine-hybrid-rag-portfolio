#!/usr/bin/env python3
"""Public, corpus-agnostic hybrid RAG demonstrator derived from a vidarabine exercise.

The repository intentionally contains no source-book or CD-derived text.  The
default corpus is synthetic and exists only to exercise the retrieval, evidence
gate, citation and evaluation paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


APP_VERSION = "1.0.0-public-portfolio"


class RagError(RuntimeError):
    """Raised for a user-actionable portfolio error."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise RagError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RagError(f"Invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RagError(f"JSON root must be an object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError as exc:
        raise RagError(f"File not found: {path}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RagError(f"Invalid JSONL: {path}, line {line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise RagError(f"JSONL row must be an object: {path}, line {line_number}")
        rows.append(row)
    return rows


def adapt_document_schema(row: dict[str, Any], row_number: int) -> dict[str, Any]:
    """Accept the public schema and the legacy keyword/chunk export schema.

    The adapter only maps fields in memory.  It does not modify or copy the
    user-supplied corpus.
    """
    document_id = next(
        (
            str(row.get(key, "")).strip()
            for key in ("id", "document_id", "chunk_id", "record_id", "product_id", "table_id")
            if str(row.get(key, "")).strip()
        ),
        f"ROW-{row_number:05d}",
    )
    text = next(
        (
            str(row.get(key, "")).strip()
            for key in (
                "text",
                "display_text",
                "text_original",
                "source_text_original",
                "embedding_text",
                "search_text",
            )
            if str(row.get(key, "")).strip()
        ),
        "",
    )
    section = next(
        (
            str(row.get(key, "")).strip()
            for key in ("section", "document_type", "chunk_type", "section_title", "table_type", "section_id")
            if str(row.get(key, "")).strip()
        ),
        "",
    )
    raw_keywords = row.get("keywords", row.get("exact_terms", []))
    keywords = [str(value) for value in raw_keywords] if isinstance(raw_keywords, list) else []
    source_label = next(
        (
            str(row.get(key, "")).strip()
            for key in ("source_label", "citation_label", "source_file")
            if str(row.get(key, "")).strip()
        ),
        "user-supplied private corpus",
    )
    return {
        "id": document_id,
        "title": str(row.get("title", row.get("section_title", ""))),
        "section": section,
        "text": text,
        "search_text": str(row.get("search_text", "")),
        "embedding_text": str(row.get("embedding_text", "")),
        "keywords": keywords,
        "synthetic": bool(row.get("synthetic", False)),
        "source_label": source_label,
        "input_schema": (
            "public"
            if "id" in row and "text" in row
            else "legacy_keyword_or_chunk_export"
        ),
    }


def load_documents(path: Path) -> list[dict[str, Any]]:
    return [adapt_document_schema(row, index) for index, row in enumerate(read_jsonl(path), 1)]


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower().strip()


def lexical_tokens(text: str) -> list[str]:
    normalized = normalize(text)
    words = re.findall(r"[a-z0-9]+|[\u3040-\u30ff\u3400-\u9fff]+", normalized)
    tokens: list[str] = []
    for word in words:
        tokens.append(word)
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", word):
            tokens.extend(word[index : index + 2] for index in range(max(0, len(word) - 1)))
    return tokens


def hashed_vector(text: str, dimensions: int) -> dict[int, float]:
    counts = Counter(lexical_tokens(text))
    vector: dict[int, float] = {}
    for token, count in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % dimensions
        sign = 1.0 if digest[8] % 2 == 0 else -1.0
        vector[index] = vector.get(index, 0.0) + sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector.values()))
    return {key: value / norm for key, value in vector.items()} if norm else {}


def cosine_sparse(left: dict[int, float], right: dict[int, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(key, 0.0) for key, value in left.items())


class OllamaClient:
    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                value = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RagError(f"Ollama request failed: {exc}") from exc
        if not isinstance(value, dict):
            raise RagError("Ollama returned an unexpected response.")
        return value

    def embeddings(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        response = self._post("embed", {"model": model, "input": list(texts), "truncate": False})
        rows = response.get("embeddings")
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise RagError("Ollama embedding count did not match the input count.")
        return [[float(value) for value in row] for row in rows]

    def chat(self, model: str, system: str, user: str, temperature: float) -> str:
        response = self._post(
            "chat",
            {
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "options": {"temperature": temperature},
            },
        )
        message = response.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RagError("Ollama chat response did not contain message.content.")
        return message["content"].strip()


def cosine_dense(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise RagError("Embedding dimensions do not match.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


@dataclass(frozen=True)
class RankedDocument:
    document: dict[str, Any]
    score: float
    keyword_rank: int | None
    vector_rank: int | None


class HybridRetriever:
    def __init__(self, documents: list[dict[str, Any]], config: dict[str, Any]) -> None:
        if not documents:
            raise RagError("The corpus is empty.")
        self.documents = documents
        self.config = config
        ids = [str(row.get("id", "")).strip() for row in documents]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise RagError("Each corpus row must have a unique, non-empty id.")
        for row in documents:
            if not isinstance(row.get("text"), str) or not row["text"].strip():
                raise RagError(f"Document {row.get('id')} has no text.")

    @staticmethod
    def searchable_text(row: dict[str, Any]) -> str:
        keywords = row.get("keywords", [])
        keyword_text = " ".join(str(item) for item in keywords) if isinstance(keywords, list) else ""
        return " ".join(
            [
                str(row.get("title", "")),
                str(row.get("section", "")),
                keyword_text,
                str(row.get("search_text", "")),
                str(row.get("embedding_text", "")),
                str(row["text"]),
            ]
        )

    def keyword_scores(self, query: str) -> list[tuple[str, float]]:
        query_normalized = normalize(query)
        query_tokens = Counter(lexical_tokens(query))
        scores: list[tuple[str, float]] = []
        for row in self.documents:
            text = normalize(self.searchable_text(row))
            document_tokens = Counter(lexical_tokens(text))
            overlap = sum(min(count, document_tokens.get(token, 0)) for token, count in query_tokens.items())
            phrase_bonus = 3.0 if query_normalized and query_normalized in text else 0.0
            keyword_bonus = sum(
                2.0 for value in row.get("keywords", []) if normalize(str(value)) in query_normalized
            )
            scores.append((str(row["id"]), float(overlap) + phrase_bonus + keyword_bonus))
        return sorted(scores, key=lambda item: (-item[1], item[0]))

    def vector_scores(self, query: str) -> list[tuple[str, float]]:
        retrieval = self.config["retrieval"]
        backend = retrieval.get("vector_backend", "portable")
        texts = [self.searchable_text(row) for row in self.documents]
        if backend == "portable":
            dimensions = int(retrieval.get("portable_dimensions", 1024))
            query_vector = hashed_vector(query, dimensions)
            values = [cosine_sparse(query_vector, hashed_vector(text, dimensions)) for text in texts]
        elif backend == "ollama":
            ollama = self.config["ollama"]
            client = OllamaClient(str(ollama["base_url"]), int(ollama["request_timeout_seconds"]))
            vectors = client.embeddings(str(ollama["embedding_model"]), [query, *texts])
            values = [cosine_dense(vectors[0], vector) for vector in vectors[1:]]
        else:
            raise RagError(f"Unsupported vector_backend: {backend}")
        pairs = [(str(row["id"]), value) for row, value in zip(self.documents, values)]
        return sorted(pairs, key=lambda item: (-item[1], item[0]))

    def search(self, query: str) -> dict[str, Any]:
        if not query.strip():
            raise RagError("Question must not be empty.")
        retrieval = self.config["retrieval"]
        top_k = int(retrieval["top_k"])
        candidate_count = int(retrieval["candidate_top_n_per_method"])
        rrf_k = int(retrieval["rrf_k"])
        keyword_weight = float(retrieval["keyword_weight"])
        vector_weight = float(retrieval["vector_weight"])

        keyword = self.keyword_scores(query)[:candidate_count]
        vector = self.vector_scores(query)[:candidate_count]
        keyword_ranks = {document_id: rank for rank, (document_id, _) in enumerate(keyword, 1)}
        vector_ranks = {document_id: rank for rank, (document_id, _) in enumerate(vector, 1)}
        keyword_raw = dict(keyword)
        vector_raw = dict(vector)
        by_id = {str(row["id"]): row for row in self.documents}

        ranked: list[RankedDocument] = []
        for document_id in set(keyword_ranks) | set(vector_ranks):
            score = 0.0
            if document_id in keyword_ranks:
                score += keyword_weight / (rrf_k + keyword_ranks[document_id])
            if document_id in vector_ranks:
                score += vector_weight / (rrf_k + vector_ranks[document_id])
            ranked.append(
                RankedDocument(by_id[document_id], score, keyword_ranks.get(document_id), vector_ranks.get(document_id))
            )
        ranked.sort(key=lambda item: (-item.score, str(item.document["id"])))

        minimum_keyword = float(retrieval["minimum_keyword_score"])
        minimum_vector = float(retrieval["minimum_vector_similarity"])
        evidence: list[dict[str, Any]] = []
        for item in ranked:
            document_id = str(item.document["id"])
            if keyword_raw.get(document_id, 0.0) < minimum_keyword and vector_raw.get(document_id, 0.0) < minimum_vector:
                continue
            evidence.append(
                {
                    "source_id": document_id,
                    "title": item.document.get("title", ""),
                    "section": item.document.get("section", ""),
                    "text": item.document["text"],
                    "synthetic": bool(item.document.get("synthetic", False)),
                    "rrf_score": round(item.score, 8),
                    "keyword_rank": item.keyword_rank,
                    "vector_rank": item.vector_rank,
                    "keyword_score": round(keyword_raw.get(document_id, 0.0), 6),
                    "vector_similarity": round(vector_raw.get(document_id, 0.0), 6),
                }
            )
            if len(evidence) >= top_k:
                break

        warnings: list[str] = []
        if re.search(r"最新|現在|今日|いま", query):
            warnings.append("latest_information_not_verified")
        if re.search(r"私|患者|体重|何mg|投与量を決め", normalize(query)):
            warnings.extend(["individual_patient_advice_not_supported", "manual_review_required"])
        sufficient = bool(evidence)
        if not sufficient:
            warnings.append("sufficient_evidence_not_found")
        return {
            "schema_version": "1.0",
            "app_version": APP_VERSION,
            "question": query,
            "retrieval_summary": {
                "method": "weighted_reciprocal_rank_fusion",
                "vector_backend": retrieval.get("vector_backend", "portable"),
                "evidence_sufficient": sufficient,
                "evidence_count": len(evidence),
            },
            "warnings": list(dict.fromkeys(warnings)),
            "evidence": evidence,
        }


def build_answer(packet: dict[str, Any], config: dict[str, Any], use_ollama: bool) -> dict[str, Any]:
    evidence = packet["evidence"]
    if not packet["retrieval_summary"]["evidence_sufficient"]:
        return {
            "answer": "提供されたコーパス内では、質問に直接対応する根拠を確認できませんでした。",
            "evidence_ids": [],
            "warnings": packet["warnings"],
            "generated_by": "safety_gate",
        }
    if any(item.get("synthetic") for item in evidence):
        synthetic_warning = "synthetic_demo_data_not_medical_information"
        if synthetic_warning not in packet["warnings"]:
            packet["warnings"].append(synthetic_warning)

    if not use_ollama:
        selected = evidence[: int(config["answer"]["maximum_evidence_items"])]
        answer = "\n".join(f"- [{item['source_id']}] {item['text']}" for item in selected)
        return {
            "answer": answer,
            "evidence_ids": [item["source_id"] for item in selected],
            "warnings": packet["warnings"],
            "generated_by": "deterministic_extractive_demo",
        }

    ollama = config["ollama"]
    context = "\n\n".join(f"[{item['source_id']}] {item['text']}" for item in evidence)
    system = (
        "提供された根拠だけを使用し、日本語で簡潔に答えてください。"
        "根拠IDを角括弧で引用してください。根拠にない医療知識を加えないでください。"
        "合成データは実際の医療情報ではないと明記してください。"
    )
    user = f"質問:\n{packet['question']}\n\n根拠:\n{context}"
    client = OllamaClient(str(ollama["base_url"]), int(ollama["request_timeout_seconds"]))
    answer = client.chat(str(ollama["answer_model"]), system, user, float(ollama["temperature"]))
    mentioned = [item["source_id"] for item in evidence if f"[{item['source_id']}]" in answer]
    if not mentioned:
        packet["warnings"].append("answer_did_not_cite_evidence_id")
    return {
        "answer": answer,
        "evidence_ids": mentioned,
        "warnings": list(dict.fromkeys(packet["warnings"])),
        "generated_by": f"ollama:{ollama['answer_model']}",
    }


def evaluate(retriever: HybridRetriever, question_path: Path) -> dict[str, Any]:
    outcomes: list[dict[str, Any]] = []
    for row in read_jsonl(question_path):
        question_id = str(row.get("id", ""))
        packet = retriever.search(str(row.get("question", "")))
        actual_ids = [item["source_id"] for item in packet["evidence"]]
        expected_ids = [str(value) for value in row.get("expected_source_ids", [])]
        blocked_expected = bool(row.get("blocked_expected", False))
        if blocked_expected:
            passed = not packet["retrieval_summary"]["evidence_sufficient"]
        else:
            passed = any(value in actual_ids for value in expected_ids)
        outcomes.append(
            {
                "id": question_id,
                "passed": passed,
                "expected_source_ids": expected_ids,
                "actual_source_ids": actual_ids,
                "warnings": packet["warnings"],
            }
        )
    passed_count = sum(bool(row["passed"]) for row in outcomes)
    return {
        "app_version": APP_VERSION,
        "question_count": len(outcomes),
        "passed_count": passed_count,
        "failed_count": len(outcomes) - passed_count,
        "all_tests_passed": passed_count == len(outcomes),
        "results": outcomes,
    }


def default_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1]
    private_corpus = root / "data" / "private" / "vidarabine_documents.jsonl"
    sample_corpus = root / "data" / "sample" / "synthetic_documents.jsonl"
    return root / "config" / "portfolio_config.json", private_corpus if private_corpus.exists() else sample_corpus


def parser() -> argparse.ArgumentParser:
    config_default, corpus_default = default_paths()
    root = Path(__file__).resolve().parents[1]
    result = argparse.ArgumentParser(description="Vidarabine hybrid-RAG public portfolio demonstrator")
    result.add_argument("--config", type=Path, default=config_default)
    result.add_argument("--corpus", type=Path, default=corpus_default)
    subparsers = result.add_subparsers(dest="command", required=True)
    search_parser = subparsers.add_parser("search", help="Return a grounded evidence packet")
    search_parser.add_argument("question")
    answer_parser = subparsers.add_parser("answer", help="Return an extractive or Ollama-generated answer")
    answer_parser.add_argument("question")
    answer_parser.add_argument("--use-ollama", action="store_true")
    evaluation_parser = subparsers.add_parser("evaluate", help="Evaluate retrieval against a JSONL question set")
    evaluation_parser.add_argument(
        "--questions", type=Path, default=root / "data" / "sample" / "synthetic_questions.jsonl"
    )
    subparsers.add_parser("inspect", help="Validate the selected corpus without printing its text")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = read_json(args.config)
        documents = load_documents(args.corpus)
        retriever = HybridRetriever(documents, config)
        if args.command == "inspect":
            schemas = Counter(str(row.get("input_schema", "unknown")) for row in documents)
            output = {
                "app_version": APP_VERSION,
                "corpus_path": str(args.corpus.resolve()),
                "document_count": len(documents),
                "synthetic_document_count": sum(bool(row.get("synthetic")) for row in documents),
                "input_schemas": dict(sorted(schemas.items())),
                "status": "ready",
            }
        elif args.command == "search":
            output = retriever.search(args.question)
        elif args.command == "answer":
            packet = retriever.search(args.question)
            output = {"packet": packet, "response": build_answer(packet, config, args.use_ollama)}
        else:
            output = evaluate(retriever, args.questions)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if output.get("all_tests_passed", True) else 1
    except RagError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
