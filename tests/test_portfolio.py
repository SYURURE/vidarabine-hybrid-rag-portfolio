from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("vidarabine_rag", ROOT / "src" / "vidarabine_rag.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = MODULE.read_json(ROOT / "config" / "portfolio_config.json")
        documents = MODULE.load_documents(ROOT / "data" / "sample" / "synthetic_documents.jsonl")
        cls.retriever = MODULE.HybridRetriever(documents, config)
        cls.config = config

    def test_injection_query_returns_injection_document_first(self) -> None:
        packet = self.retriever.search("デモ注射剤Vと仮想薬A")
        self.assertEqual(packet["evidence"][0]["source_id"], "SYN-003")

    def test_unrelated_query_is_blocked(self) -> None:
        packet = self.retriever.search("量子コンピューターの誤り訂正方式")
        self.assertFalse(packet["retrieval_summary"]["evidence_sufficient"])
        self.assertIn("sufficient_evidence_not_found", packet["warnings"])

    def test_synthetic_warning_is_added_to_answer(self) -> None:
        packet = self.retriever.search("仮想成分Vの製品一覧")
        response = MODULE.build_answer(packet, self.config, use_ollama=False)
        self.assertIn("synthetic_demo_data_not_medical_information", response["warnings"])

    def test_evaluation_set_passes(self) -> None:
        summary = MODULE.evaluate(
            self.retriever, ROOT / "data" / "sample" / "synthetic_questions.jsonl"
        )
        self.assertTrue(summary["all_tests_passed"], summary)

    def test_legacy_keyword_document_is_adapted(self) -> None:
        legacy = {
            "document_id": "LEGACY-001",
            "document_type": "section",
            "title": "互換性試験",
            "display_text": "表示用本文",
            "search_text": "検索用本文",
            "embedding_text": "埋め込み用本文",
            "exact_terms": ["互換", "試験"],
            "citation_label": "private source",
        }
        adapted = MODULE.adapt_document_schema(legacy, 1)
        self.assertEqual(adapted["id"], "LEGACY-001")
        self.assertEqual(adapted["text"], "表示用本文")
        self.assertEqual(adapted["keywords"], ["互換", "試験"])
        self.assertEqual(adapted["input_schema"], "legacy_keyword_or_chunk_export")


if __name__ == "__main__":
    unittest.main()
