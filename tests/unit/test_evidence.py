"""Unit tests for kit/scripts/loop/evidence.py."""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit" / "scripts"))

import gate  # noqa: E402
from loop import evidence  # noqa: E402
from loop.paths import Paths  # noqa: E402


class Chain(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(tempfile.mkdtemp())
        self.paths = Paths.for_project(base / "p", data_base=base / "data", kit_folder=base / "k")
        self.file = self.paths.piece_dir(3) / "evidence.jsonl"

    def test_append_and_read(self) -> None:
        evidence.append(self.paths, 3, [{"kind": "a", "n": 1}, {"kind": "b", "n": 2}])
        evidence.append(self.paths, 3, [{"kind": "c", "n": 3}])
        entries = evidence.read(self.paths, 3)
        self.assertEqual([e["kind"] for e in entries], ["a", "b", "c"])

    def test_empty_record_reads_as_empty(self) -> None:
        self.assertEqual(evidence.read(self.paths, 3), [])

    def test_an_edited_entry_is_refused(self) -> None:
        evidence.append(self.paths, 3, [{"kind": "a", "n": 1}, {"kind": "b", "n": 2}])
        text = self.file.read_text(encoding="utf-8").replace('"n": 1', '"n": 9')
        self.file.write_text(text, encoding="utf-8")
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.read(self.paths, 3)
        self.assertIn("line 1", str(caught.exception))
        self.assertTrue(caught.exception.next_command)

    def test_a_removed_middle_entry_is_refused(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}, {"n": 2}, {"n": 3}])
        lines = self.file.read_text(encoding="utf-8").splitlines(keepends=True)
        self.file.write_text(lines[0] + lines[2], encoding="utf-8")
        with self.assertRaises(evidence.EvidenceError):
            evidence.read(self.paths, 3)

    def test_append_refuses_to_extend_a_broken_chain(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}])
        self.file.write_text(
            self.file.read_text(encoding="utf-8").replace('"n": 1', '"n": 2'), encoding="utf-8"
        )
        with self.assertRaises(evidence.EvidenceError):
            evidence.append(self.paths, 3, [{"n": 3}])

    def test_a_cut_off_last_line_is_set_aside(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}])
        with open(self.file, "a", encoding="utf-8") as handle:
            handle.write('{"n": 2, "chai')
        notes = evidence.append(self.paths, 3, [{"n": 3}])
        self.assertTrue(notes)
        self.assertEqual([e["n"] for e in evidence.read(self.paths, 3)], [1, 3])

    def test_a_record_in_the_gates_unkeyed_format_reads_and_is_marked_unkeyed(self) -> None:
        self.file.parent.mkdir(parents=True)
        previous = ""
        lines = ""
        for n in (1, 2):
            chain = gate.chain_of(previous, {"n": n})
            lines += json.dumps({"n": n, "chain": chain}, sort_keys=True) + "\n"
            previous = chain
        self.file.write_text(lines, encoding="utf-8")
        self.assertEqual([e["n"] for e in evidence.read(self.paths, 3)], [1, 2])
        report = evidence.inspect(self.paths, 3)
        self.assertEqual(report["unkeyed"], 2)
        self.assertEqual(report["keyed"], 0)
        evidence.append(self.paths, 3, [{"n": 3}])
        report = evidence.inspect(self.paths, 3)
        self.assertEqual((report["unkeyed"], report["keyed"]), (2, 1))
        self.assertEqual([e["n"] for e in evidence.read(self.paths, 3)], [1, 2, 3])

    def test_dry_run_writes_nothing(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}], dry_run=True)
        self.assertFalse(self.file.exists())

    def _two(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}, {"n": 2}, {"n": 3}])

    def test_cutting_the_tail_is_refused(self) -> None:
        self._two()
        lines = self.file.read_text(encoding="utf-8").splitlines(keepends=True)
        self.file.write_text("".join(lines[:2]), encoding="utf-8")
        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.read(self.paths, 3)
        self.assertIn("shorter", str(caught.exception))
        with self.assertRaises(evidence.EvidenceError):
            evidence.append(self.paths, 3, [{"n": 4}])

    def test_a_rewrite_with_a_valid_unkeyed_chain_is_refused(self) -> None:
        self._two()
        previous = ""
        lines = ""
        for n in (1, 2, 3):
            chain = gate.chain_of(previous, {"n": n, "forged": True})
            lines += json.dumps({"n": n, "forged": True, "chain": chain}, sort_keys=True) + "\n"
            previous = chain
        self.file.write_text(lines, encoding="utf-8")
        with self.assertRaises(evidence.EvidenceError):
            evidence.read(self.paths, 3)

    def test_a_forged_mac_is_refused(self) -> None:
        self._two()
        text = self.file.read_text(encoding="utf-8")
        lines = text.splitlines()
        first = json.loads(lines[0])
        first["mac"] = "0" * 64
        lines[0] = json.dumps(first, sort_keys=True)
        self.file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(evidence.EvidenceError):
            evidence.read(self.paths, 3)

    def test_the_key_sits_in_the_data_folder_with_mode_0600(self) -> None:
        self._two()
        key = self.paths.data_dir / "evidence.key"
        self.assertTrue(key.is_file())
        self.assertEqual(key.stat().st_mode & 0o777, 0o600)
        self.assertFalse(str(key).startswith(str(self.paths.root)))
        self.assertNotIn(key.read_text(encoding="utf-8").strip(), self.file.read_text("utf-8"))

    def test_the_head_sits_beside_the_key_and_counts_the_entries(self) -> None:
        self._two()
        head = json.loads((self.paths.data_dir / "evidence-heads" / "3.json").read_text("utf-8"))
        self.assertEqual(head["count"], 3)
        last = json.loads(self.file.read_text("utf-8").splitlines()[-1])["mac"]
        self.assertEqual(head["last"], last)

    def test_a_missing_head_or_key_is_refused(self) -> None:
        self._two()
        (self.paths.data_dir / "evidence-heads" / "3.json").unlink()
        with self.assertRaises(evidence.EvidenceError):
            evidence.read(self.paths, 3)
        other = Path(tempfile.mkdtemp())
        paths = Paths.for_project(other / "p", data_base=other / "d", kit_folder=other / "k")
        evidence.append(paths, 3, [{"n": 1}])
        (paths.data_dir / "evidence.key").unlink()
        with self.assertRaises(evidence.EvidenceError):
            evidence.read(paths, 3)

    def test_a_cut_off_line_is_kept_in_a_sibling_file_and_reported(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}])
        fragment = '{"n": 2, "ma'
        with open(self.file, "a", encoding="utf-8") as handle:
            handle.write(fragment)
        report = evidence.inspect(self.paths, 3)
        self.assertEqual(report["interrupted_bytes"], len(fragment))
        notes = evidence.append(self.paths, 3, [{"n": 3}])
        self.assertTrue(any("interrupted" in note for note in notes))
        kept = [p for p in self.file.parent.iterdir() if "interrupted" in p.name]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_text(encoding="utf-8"), fragment)
        self.assertNotIn(fragment, self.file.read_text(encoding="utf-8"))
        self.assertTrue(any(p.name in note for note in notes for p in kept))

    def test_a_whole_last_entry_that_lost_its_newline_is_refused_not_erased(self) -> None:
        self._two()
        text = self.file.read_text(encoding="utf-8")
        self.file.write_text(text.rstrip("\n"), encoding="utf-8")
        with self.assertRaises(evidence.EvidenceError):
            evidence.append(self.paths, 3, [{"n": 4}])
        self.assertEqual(self.file.read_text(encoding="utf-8"), text.rstrip("\n"))

    def test_no_kit_file_outside_the_gate_calls_evidence_append(self) -> None:
        allowed = {
            ROOT / "kit" / "scripts" / "gate.py",
            ROOT / "kit" / "scripts" / "loop" / "evidence.py",
        }
        pattern = re.compile(
            r"evidence\s*\.\s*append\b|from\s+loop\.evidence\s+import\b[^\n]*\bappend\b"
            r"|from\s+\.?evidence\s+import\b[^\n]*\bappend\b"
        )
        found = []
        for path in (ROOT / "kit").rglob("*"):
            if path.is_file() and path not in allowed and path.suffix in {
                ".py", ".sh", ".md", ".json", ""
            }:
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                if pattern.search(text):
                    found.append(str(path.relative_to(ROOT)))
        self.assertEqual(found, [], "only the gate may write the piece record")

    def test_the_pattern_catches_a_caller(self) -> None:
        pattern_hits = re.compile(r"evidence\s*\.\s*append\b")
        self.assertTrue(pattern_hits.search("evidence.append(paths, 1, [])"))

    def test_the_record_sits_where_paths_says(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}])
        self.assertTrue(self.file.is_file())
        self.assertEqual(self.file.parent, self.paths.piece_dir(3))


if __name__ == "__main__":
    unittest.main()
