"""Unit tests for kit/scripts/loop/evidence.py."""

import json
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

    def test_the_chain_is_the_one_the_gate_writes(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}, {"n": 2}])
        previous = ""
        for line in self.file.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            chain = value.pop("chain")
            self.assertEqual(chain, gate.chain_of(previous, value))
            previous = chain

    def test_dry_run_writes_nothing(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}], dry_run=True)
        self.assertFalse(self.file.exists())

    def test_the_record_sits_where_paths_says(self) -> None:
        evidence.append(self.paths, 3, [{"n": 1}])
        self.assertTrue(self.file.is_file())
        self.assertEqual(self.file.parent, self.paths.piece_dir(3))


if __name__ == "__main__":
    unittest.main()
