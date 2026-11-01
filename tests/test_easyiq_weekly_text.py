"""Fictitious, offline regression cases for EasyIQ's general weekly text."""
import ast
import datetime
import html
from pathlib import Path
import unittest
import urllib.parse
from bs4 import BeautifulSoup

CLIENT = Path(__file__).resolve().parents[1] / "custom_components/aula/client.py"
tree = ast.parse(CLIENT.read_text(encoding="utf-8"))
helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "easyiq_weekplan_events")
ns = {"datetime": datetime, "html": html, "BeautifulSoup": BeautifulSoup, "urllib": urllib}
exec(compile(ast.Module(body=[helper], type_ignores=[]), str(CLIENT), "exec"), ns)
events = ns["easyiq_weekplan_events"]

class TestWeeklyText(unittest.TestCase):
    def test_group_note_when_show_is_false(self):
        payload = {"Show": False, "Beskrivelse": "Generelt om ugen", "WeekPlans": [
            {"ActivityName": "5Z", "Text": "<p>Example trip at 08.30</p><p>Read pages 10 and 11.</p>", "IsVisible": True}
        ]}
        note = events(payload, "2026-W45")[0]
        self.assertEqual(note["Title"], "Generelt om ugen (5Z)")
        self.assertIn("Read pages 10 and 11.", note["Description"])
        self.assertEqual(note["StartTime"], "2026-11-02T00:00:00")
        self.assertEqual(note["EndTime"], "2026-11-08T00:00:00")
        self.assertTrue(note["IsAllDay"])

    def test_top_level_note(self):
        note = events({"Show": True, "Text": "<p>Class news</p>", "IsVisible": True}, "2026-W45")[0]
        self.assertIn("Class news", note["Description"])

    def test_multiple_classes_remain_separate(self):
        payload = {"WeekPlans": [
            {"ActivityName": "5Z", "Text": "First class"},
            {"ActivityName": "6Z", "Text": "Second class"},
        ]}
        self.assertEqual(len(events(payload, "2026-W45")), 2)

    def test_hidden_empty_and_malformed_notes_are_ignored(self):
        for payload in [None, [], {"WeekPlans": "bad"}, {"WeekPlans": [None, {"Text": ""}, {"Text": "unpublished", "IsVisible": False}]}]:
            self.assertEqual(events(payload, "2026-W45"), [])

    def test_active_html_is_removed_and_links_preserved(self):
        body = '<p onclick="bad()">Hello<script>bad()</script><a href="javascript:bad()">No</a><a href="https://example.com">Yes</a></p>'
        rendered = events({"Show": True, "Text": body}, "2026-W45")[0]["Description"]
        self.assertNotIn("bad()", rendered)
        self.assertNotIn("onclick", rendered)
        self.assertIn("Hello", rendered)
        self.assertIn("https://example.com", rendered)

    def test_iso_year_boundary(self):
        self.assertEqual(events({"Show": True, "Text": "Example"}, "2026-W01")[0]["StartTime"], "2025-12-29T00:00:00")

if __name__ == "__main__":
    unittest.main()
