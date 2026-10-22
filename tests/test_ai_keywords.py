import unittest

from workbench.analysis import compare, extract


class AiKeywordTests(unittest.TestCase):
    def test_ai_aliases(self):
        skills = extract("智能体、检索增强生成、Function Calling、LangGraph、DeepSeek、MCP、提示词")
        self.assertEqual(set(skills), {"Agent", "RAG", "工具调用", "LangGraph", "DeepSeek", "MCP", "Prompt"})

    def test_no_false_substrings(self):
        self.assertNotIn("RAG", extract("storage fragmented"))
        self.assertNotIn("Agent", extract("reagent"))

    def test_ai_report_with_evidence(self):
        report = compare("需要 Python、RAG 和 LangGraph", "用 Python 做过 RAG 原型")
        self.assertEqual(report["coverage"], 67)
        self.assertEqual(report["missing"][0]["skill"], "LangGraph")
