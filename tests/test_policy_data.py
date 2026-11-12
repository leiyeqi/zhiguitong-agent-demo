import json
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "policies.json"

class PolicyDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA, encoding="utf-8") as f:
            cls.policies = json.load(f)

    def test_policy_records_have_required_fields(self):
        for p in self.policies:
            for key in ["id", "title", "domain", "version", "effective_date", "sections"]:
                self.assertIn(key, p)
            self.assertTrue(p["sections"])

    def test_policy_ids_and_sections_are_present(self):
        ids = {p["id"] for p in self.policies}
        self.assertIn("CORP-LOAN-001", ids)
        self.assertIn("OPS-ACCOUNT-003", ids)
        for p in self.policies:
            for section in p["sections"]:
                self.assertIn("id", section)
                self.assertIn("title", section)
                self.assertIn("content", section)

if __name__ == "__main__":
    unittest.main()
