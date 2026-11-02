import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from triage import parse_response
from evaluate_alerts import metrics

class TestTriage(unittest.TestCase):
    def test_valid(self):
        event = {"classification":"benign","confidence":88,"attack_type":"none","explanation":"normal"}
        self.assertEqual(parse_response(json.dumps(event)), event)
    def test_invalid_label(self):
        with self.assertRaises(ValueError):
            parse_response('{"classification":"ignore","confidence":80,"attack_type":"","explanation":""}')
    def test_invalid_confidence(self):
        with self.assertRaises(ValueError):
            parse_response('{"classification":"benign","confidence":101,"attack_type":"","explanation":""}')
    def test_metrics(self):
        rows = [{"expected":"malicious","predicted":"malicious"},{"expected":"benign","predicted":"malicious"},
                {"expected":"benign","predicted":"benign"},{"expected":"malicious","predicted":"benign"}]
        self.assertEqual(metrics(rows)["f1"], 0.5)
    def test_empty(self):
        self.assertEqual(metrics([])["accuracy"], 0)
if __name__ == "__main__":
    unittest.main()
