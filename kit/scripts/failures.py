"""Decide whether a judge failed for the right reason: an assertion about an item."""
from __future__ import annotations

import re

_WRONG_TEST_REASON = re.compile(
    r"^\s*(?:E\s+)?(?:SyntaxError|IndentationError|ModuleNotFoundError|"
    r"ImportError|FileNotFoundError):|^ERROR collecting(?:\s|$)", re.MULTILINE)
# Every failure begins a block: pytest, unittest, vitest, jest, TAP, minitest or a summary line.
_BLOCK = re.compile(r"^(?:_+ .+ _+$|={3,}|(?:FAIL|ERROR): |(?:FAILED|ERROR) \S|\s*FAIL\s+\S|"
                    r"\s*● |\s*not ok\b|(?:ok|PASS)\b|\s*\d+\) (?:Failure|Error):)")
_ASSERTION = re.compile(
    r"^\s*(?:E\s+)?(?:[\w.]*\.)?AssertionError\b|^\s*E\s+assert\b|^\s*expect\(received\)|"
    r"^FAIL: |^\s*\d+\) Failure:|ERR_ASSERTION|"
    r"^(?:FAILED|ERROR) .* - (?:AssertionError|assert\b)", re.MULTILINE)
_PLAIN_FAIL = re.compile(r"^(?!.*\b(?!AssertionError\b)[A-Z]\w*(?:Error|Exception)\b).*"
                         r"(?:\bFAIL\b|\bnot ok\b)")


def judge_has_runner_error(output: str, code: int) -> bool:
    """Recognise a missing test command or a broken test module."""
    return ((code == 127 and "command not found" in output)
            or bool(_WRONG_TEST_REASON.search(output)))


def judge_assertion_failed(output: str, item: str) -> bool:
    """Accept a block that names the item and asserts, or is one plain FAIL line."""
    named = re.compile(rf"(?<![A-Za-z0-9]){re.escape(item)}(?![0-9])")
    blocks: list[list[str]] = [[]]
    for line in output.splitlines():
        if _BLOCK.match(line):
            blocks.append([])
        blocks[-1].append(line)
    return any(named.search(text := "\n".join(block)) and (
        _ASSERTION.search(text) or (len(block) == 1 and _PLAIN_FAIL.match(text)))
        for block in blocks)
