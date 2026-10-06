"""The new-test lint: refuse the test smells a script can find reliably.

It reads text and runs nothing. It judges the lines a change adds, so a smell
that was already there is left alone, and a test whose assertion was taken away
is still seen. The smells are the "yes" rows of the design's checks table that
concern tests. Two of them, assertion roulette and magic numbers, are only
reported. They never refuse.

Python is read with `ast`, so a rule sees code and not the words in a string or a
comment. TypeScript and JavaScript are read with a small scanner that blanks
strings and comments, then with patterns. The patterns are cautious: a rule
fires on a shape that is a smell in nearly every project, and says nothing when it
cannot tell.

`kit/scripts/test-guard.sh` lists test files by path. This module keeps the same
idea of a test file (see `is_test_path`), and does not change that script.
"""

from __future__ import annotations

import ast
import bisect
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TypedDict


class Rule(str, Enum):
    NO_ASSERTION = "no_assertion"
    SKIP_ADDED = "skip_added"
    ASSERT_TRUE = "assert_true"
    DUPLICATE_ASSERTION = "duplicate_assertion"
    CONDITIONAL_LOGIC = "conditional_logic"
    SLEEP = "sleep"
    DEBUG_PRINT = "debug_print"
    OWN_MODULE_MOCK = "own_module_mock"
    CALL_COUNT = "call_count"
    TEST_DETECT = "test_detect"
    SNAPSHOT_REWRITTEN = "snapshot_rewritten"
    SUPPRESSION = "suppression"
    SWALLOWED_ERROR = "swallowed_error"
    DEBUG_LEFTOVER = "debug_leftover"
    ASSERTION_ROULETTE = "assertion_roulette"
    MAGIC_NUMBER = "magic_number"
    UNPARSED = "unparsed"


REPORT_ONLY = frozenset({Rule.ASSERTION_ROULETTE, Rule.MAGIC_NUMBER, Rule.UNPARSED})
REFUSING = frozenset(r for r in Rule if r not in REPORT_ONLY)
DEFAULT_RULES = frozenset(Rule)

ROULETTE_LIMIT = 5  # this many assertions with no message in one test
MAGIC_LIMIT = 3  # this many different bare numbers in the assertions of one test
PLAIN_NUMBERS = frozenset({0, 1, 2})

# rule: (severity, what is wrong, what to do)
RULE_INFO: dict[Rule, tuple[str, str, str]] = {
    Rule.NO_ASSERTION: (
        "refuse",
        "a test has no assertion, so nothing can turn it red",
        "add an assertion on the result, or delete the test",
    ),
    Rule.SKIP_ADDED: (
        "refuse",
        "a skip or expected-failure marker was added",
        "remove the marker and make the test pass, or delete the test and say why",
    ),
    Rule.ASSERT_TRUE: (
        "refuse",
        "an assertion that is always true",
        "assert something the code under test decides",
    ),
    Rule.DUPLICATE_ASSERTION: (
        "refuse",
        "the same condition is asserted twice in one test",
        "remove the second assertion or assert a different condition",
    ),
    Rule.CONDITIONAL_LOGIC: (
        "refuse",
        "a test has an if, a loop or a branch, so it may skip its own assertions",
        "split it into straight-line tests, or use the framework's parameter table",
    ),
    Rule.SLEEP: (
        "refuse",
        "a test sleeps, so it is slow and may be flaky",
        "wait on the event or the fake clock, not on the time",
    ),
    Rule.DEBUG_PRINT: (
        "refuse",
        "a debug print is left in a test",
        "remove the print, or assert on the value instead",
    ),
    Rule.OWN_MODULE_MOCK: (
        "refuse",
        "a test mocks a module of this project, so it tests the mock",
        "use the real module, and fake only the outside world",
    ),
    Rule.CALL_COUNT: (
        "refuse",
        "a test asserts how many times a call happened, which ties it to how the code works",
        "assert what the code returns or changes",
    ),
    Rule.TEST_DETECT: (
        "refuse",
        "code checks whether it is under test",
        "remove the check, and give the code a real setting if it must differ",
    ),
    Rule.SNAPSHOT_REWRITTEN: (
        "refuse",
        "a snapshot was rewritten in the same change as the code",
        "restore the snapshot, or make the code match it",
    ),
    Rule.SUPPRESSION: (
        "refuse",
        "a check is switched off by a suppression comment",
        "fix what the check found, and remove the comment",
    ),
    Rule.SWALLOWED_ERROR: (
        "refuse",
        "an error is caught and thrown away",
        "assert on the error, or let it fail the test",
    ),
    Rule.DEBUG_LEFTOVER: (
        "refuse",
        "a debug leftover: a breakpoint, a focus marker or a new TODO",
        "remove it",
    ),
    Rule.ASSERTION_ROULETTE: (
        "report",
        "many assertions with no message: a failure will not say which one broke",
        "split the test, or give each assertion a message",
    ),
    Rule.MAGIC_NUMBER: (
        "report",
        "bare numbers in the assertions, with no name to say what they mean",
        "give the numbers names",
    ),
    Rule.UNPARSED: (
        "report",
        "the file could not be read as code, so only the line rules ran",
        "fix the syntax error",
    ),
}


class Finding(TypedDict):
    rule: str
    severity: str
    file: str
    line: int
    message: str
    next: str


def refusals(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f["severity"] == "refuse"]


def reports(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f["severity"] != "refuse"]


# --- what a path is -----------------------------------------------------------

CODE_SUFFIXES = {
    ".py": "py",
    ".ts": "ts",
    ".tsx": "ts",
    ".mts": "ts",
    ".cts": "ts",
    ".js": "ts",
    ".jsx": "ts",
    ".mjs": "ts",
    ".cjs": "ts",
}
SNAPSHOT_SUFFIXES = (".snap", ".ambr", ".approved.txt")


def language_of(path: str) -> str | None:
    return CODE_SUFFIXES.get(Path(path).suffix)


def is_test_path(path: str) -> bool:
    """The same idea of a test file as kit/scripts/test-guard.sh."""
    if any(f"/{part}/" in f"/{path}" for part in ("test", "tests", "__tests__", "spec")):
        return True
    name = path.rsplit("/", 1)[-1]
    if ".test." in name or ".spec." in name or name.startswith("test_"):
        return True
    stem = name.rsplit(".", 1)[0]
    return stem.endswith(("_test", "_spec"))


def is_snapshot_path(path: str) -> bool:
    return "__snapshots__/" in f"{path}" or path.endswith(SNAPSHOT_SUFFIXES)


# --- reading a diff -----------------------------------------------------------


@dataclass
class FileChange:
    """The lines of the new file a change added, and the lines beside a deletion."""

    added: set[int] = field(default_factory=set)
    touched: set[int] = field(default_factory=set)


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_diff(diff: str) -> dict[str, FileChange]:
    """Read `git diff --unified=0` into the lines each file added."""
    changed: dict[str, FileChange] = {}
    current: FileChange | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].split("\t")[0]
            if path == "/dev/null":
                current = None
            else:
                current = changed.setdefault(path.removeprefix("b/"), FileChange())
            continue
        match = HUNK.match(line)
        if match and current is not None:
            start = int(match.group(1))
            count = 1 if match.group(2) is None else int(match.group(2))
            if count == 0:
                current.touched.update({start, start + 1})
            else:
                current.added.update(range(start, start + count))
    return changed


# --- the scanner ------------------------------------------------------------


def mask(text: str, language: str) -> str:
    """The text with the inside of strings and comments blanked. Same length, same lines."""
    out = list(text)
    n = len(text)
    py = language == "py"

    def blank(start: int, end: int) -> None:
        for k in range(start, min(end, n)):
            if out[k] != "\n":
                out[k] = " "

    i = 0
    while i < n:
        c = text[i]
        if (py and c == "#") or (not py and text.startswith("//", i)):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif not py and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
        elif c in "'\"" or (not py and c == "`"):
            quote = c * 3 if py and text.startswith(c * 3, i) else c
            j = i + len(quote)
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text.startswith(quote, j):
                    break
                if len(quote) == 1 and c != "`" and text[j] == "\n":
                    break
                j += 1
            blank(i + len(quote), j)
            i = min(j, n) + len(quote)
        else:
            i += 1
    return "".join(out)


def match_close(text: str, start: int, opener: str, closer: str) -> int:
    """The index of the bracket that closes the one at `start`, or -1."""
    depth = 0
    for k in range(start, len(text)):
        if text[k] == opener:
            depth += 1
        elif text[k] == closer:
            depth -= 1
            if depth == 0:
                return k
    return -1


class Lines:
    """Turn an offset into a line number."""

    def __init__(self, text: str) -> None:
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def of(self, offset: int) -> int:
        return bisect.bisect_right(self.starts, offset)


@dataclass
class Scope:
    """Which lines of a file the change added or touched. None means all of them."""

    added: set[int] | None = None
    touched: set[int] = field(default_factory=set)

    def adds(self, line: int) -> bool:
        return self.added is None or line in self.added

    def touches(self, first: int, last: int) -> bool:
        if self.added is None:
            return True
        marked = self.added | self.touched
        return any(line in marked for line in range(first, last + 1))


class Collector:
    def __init__(self, path: str, rules: frozenset[Rule]) -> None:
        self.path = path
        self.rules = rules
        self.found: dict[tuple[str, int], Finding] = {}

    def add(self, rule: Rule, line: int) -> None:
        if rule not in self.rules:
            return
        severity, message, hint = RULE_INFO[rule]
        self.found.setdefault(
            (rule.value, line),
            {
                "rule": rule.value,
                "severity": severity,
                "file": self.path,
                "line": line,
                "message": message,
                "next": hint,
            },
        )

    def result(self) -> list[Finding]:
        return sorted(self.found.values(), key=lambda f: (f["line"], f["rule"]))


# --- rules shared by both languages -----------------------------------------

TEST_DETECT_PATTERNS = [
    re.compile(r"NODE_ENV\s*[!=]==?\s*['\"]test['\"]"),
    re.compile(r"process\.env\.(?:JEST_WORKER_ID|VITEST_WORKER_ID|VITEST)\b"),
    re.compile(r"\bPYTEST_CURRENT_TEST\b"),
    re.compile(r"['\"](?:pytest|_pytest|unittest)['\"]\s+(?:not\s+)?in\s+sys\.modules"),
    re.compile(r"\b(?:IS_TESTING|isTestEnv|is_testing|running_under_test|RUNNING_TESTS)\b"),
]

PY_SUPPRESSION = re.compile(
    r"#\s*(?:noqa\b|type:\s*ignore\b|pylint:\s*disable\b|pragma:\s*no\s*cover\b|nosec\b"
    r"|mypy:\s*ignore)"
)
TS_SUPPRESSION = re.compile(
    r"(?://|/\*)\s*(?:eslint-disable|@ts-ignore|@ts-nocheck|@ts-expect-error"
    r"|istanbul\s+ignore|c8\s+ignore|biome-ignore)"
)
PY_TODO = re.compile(r"#\s*(?:TODO|FIXME|XXX|HACK)\b")
TS_TODO = re.compile(r"(?://|/\*|^\s*\*)\s*(?:TODO|FIXME|XXX|HACK)\b")

# (rule, pattern) read on the masked line, so a word in a string or a comment is ignored.
PY_LINE_RULES: list[tuple[Rule, re.Pattern[str]]] = [
    (
        Rule.SKIP_ADDED,
        re.compile(
            r"@\s*(?:pytest\.mark\.(?:skip|skipif|xfail)|unittest\.(?:skip|skipIf|skipUnless"
            r"|expectedFailure))\b|\b(?:pytest\.skip|pytest\.xfail|self\.skipTest)\s*\("
        ),
    ),
    (Rule.SLEEP, re.compile(r"\bsleep\s*\(")),
    (Rule.DEBUG_PRINT, re.compile(r"(?<![\w.])print\s*\(")),
    (
        Rule.CALL_COUNT,
        re.compile(
            r"\.call_count\b|\.assert_called_once(?:_with)?\b|\.assert_called_times\b"
            r"|len\(\s*[\w.]*\.(?:call_args_list|mock_calls)\s*\)"
        ),
    ),
    (
        Rule.DEBUG_LEFTOVER,
        re.compile(r"\bbreakpoint\s*\(|\bi?pdb\.set_trace\b|^\s*(?:import|from)\s+i?pdb\b"),
    ),
]
TS_LINE_RULES: list[tuple[Rule, re.Pattern[str]]] = [
    (
        Rule.SKIP_ADDED,
        re.compile(
            r"\b(?:it|test|describe|context)\.skip\b|\b(?:it|test)\.fails\b"
            r"|\bx(?:it|test|describe)\s*\("
        ),
    ),
    (
        Rule.SLEEP,
        re.compile(
            r"\bsleep\s*\(|\bwaitForTimeout\s*\(|\bnew\s+Promise\b[^;]*\bsetTimeout\b"
            r"|\bcy\.wait\(\s*\d"
        ),
    ),
    (Rule.DEBUG_PRINT, re.compile(r"\bconsole\.(?:log|debug|info|dir|table|trace)\s*\(")),
    (
        Rule.CALL_COUNT,
        re.compile(
            r"\.(?:toHaveBeenCalledTimes|toBeCalledTimes|toHaveBeenCalledOnce)\b"
            r"|\.mock\.calls\.length\b|\.callCount\b|\.calledOnce\b|\.calledTwice\b"
        ),
    ),
    (
        Rule.DEBUG_LEFTOVER,
        re.compile(r"\bdebugger\b|\b(?:it|test|describe)\.only\b|\b(?:fit|fdescribe)\s*\("),
    ),
    (
        Rule.ASSERT_TRUE,
        re.compile(
            r"\bexpect\(\s*true\s*\)\.(?:toBeTruthy\(\s*\)|(?:toBe|toEqual|toStrictEqual)"
            r"\(\s*true\s*\))|\bassert(?:\.ok)?\(\s*true\s*\)"
            r"|\bexpect\(\s*(\d+|false|null)\s*\)\.(?:toBe|toEqual|toStrictEqual)\(\s*\1\s*\)"
        ),
    ),
]
# Read on the raw line, because the text of a string matters.
TS_SAME_STRING = re.compile(r"\bexpect\(\s*(['\"])(.*?)\1\s*\)\.(?:toBe|toEqual)\(\s*\1\2\1\s*\)")
PY_PATCH = re.compile(r"\bpatch(?:\.object|\.dict)?\(\s*f?['\"]([\w.]+)['\"]")
PY_SETATTR = re.compile(r"\bmonkeypatch\.setattr\(\s*['\"]([\w.]+)['\"]")
PY_PATCH_OBJECT = re.compile(r"\b(?:patch\.object|monkeypatch\.setattr)\(\s*([A-Za-z_]\w*)\s*,")
TS_MOCK = re.compile(r"\b(?:jest|vi)\.(?:mock|doMock|unstable_mockModule)\(\s*['\"]([^'\"]+)['\"]")
TS_OWN_PATH = re.compile(r"^(?:\.|/|@/|~/|src/)")
TS_EMPTY_CATCH = re.compile(
    r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}|\.catch\(\s*\(?\w*\)?\s*=>\s*\{\s*\}\s*\)"
)
TS_TEST_CALL = re.compile(
    r"(?<![\w.$])(?:it|test)(?:\.(?:only|skip|concurrent|fails|failing))?\s*\("
)
TS_ASSERTION = re.compile(
    r"\bexpect\s*[.(]|\bassert\w*\s*[.(]|\.should\b|\bfail\s*\("
    r"|\bt\.(?:is|true|false|deepEqual|throws|truthy|falsy|not|assert|pass)\w*\s*\("
    r"|\bexpectTypeOf\b"
)
TS_ASSERT_LINE = re.compile(r"(?m)^\s*(?:await\s+)?(?:expect|assert)\w*\s*[.(][^\n]*")
TS_CONDITIONAL = re.compile(r"\b(?:if|while|switch)\s*\(|\bfor\s*(?:await\s*)?\(|\belse\b")
TS_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
TS_FUNCTION = re.compile(r"(?<![\w.$])(?:async\s+)?function\s+(\w+)\s*\(")
TS_ARROW = re.compile(
    r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*"
    r"(?::\s*[^=;{]+?)?\s*=>"
)


def _source_rules(raw_lines: list[str], scope: Scope, add: Callable[[Rule, int], None]) -> None:
    """A file that is not a test: only the check for code that knows it is under test."""
    for number, line in enumerate(raw_lines, 1):
        if scope.adds(number) and any(p.search(line) for p in TEST_DETECT_PATTERNS):
            add(Rule.TEST_DETECT, number)


# --- Python -------------------------------------------------------------------

_ASSERT_PREFIXES = ("assert", "expect", "verify", "fail", "raises", "warns")


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _py_has_assertion(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            return True
        if isinstance(child, ast.Call) and _call_name(child).lower().startswith(_ASSERT_PREFIXES):
            return True
    return False


def _py_assertions(node: ast.AST) -> list[ast.AST]:
    found: list[ast.AST] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Assert) or (
            isinstance(child, ast.Call) and _call_name(child).startswith("assert")
        ):
            found.append(child)
    return sorted(found, key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))


def _is_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant)


def _py_always_true(node: ast.AST) -> bool:
    if isinstance(node, ast.Assert):
        test = node.test
        if isinstance(test, ast.Constant):
            return bool(test.value)
        if (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and _is_constant(test.left)
            and _is_constant(test.comparators[0])
        ):
            return ast.dump(test.left) == ast.dump(test.comparators[0])
        return False
    if isinstance(node, ast.Call):
        name = _call_name(node)
        args = node.args
        if name in ("assertTrue", "assert_") and len(args) >= 1:
            return isinstance(args[0], ast.Constant) and bool(args[0].value)
        if name in ("assertEqual", "assertEquals") and len(args) >= 2:
            return _is_constant(args[0]) and ast.dump(args[0]) == ast.dump(args[1])
    return False


def _py_key(node: ast.AST) -> str:
    if isinstance(node, ast.Assert):
        return "assert " + ast.dump(node.test)
    return ast.dump(node)


def _py_has_message(node: ast.AST) -> bool:
    if isinstance(node, ast.Assert):
        return node.msg is not None
    if isinstance(node, ast.Call):
        return any(k.arg == "msg" for k in node.keywords)
    return False


def _py_numbers(nodes: Iterable[ast.AST]) -> set[float]:
    found: set[float] = set()
    for root in nodes:
        for child in ast.walk(root):
            if (
                isinstance(child, ast.Constant)
                and isinstance(child.value, (int, float))
                and not isinstance(child.value, bool)
                and abs(child.value) not in PLAIN_NUMBERS
            ):
                found.add(abs(child.value))
    return found


def _py_own_names(tree: ast.AST, own: frozenset[str]) -> set[str]:
    """The names this file brings in from the project's own modules."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in own:
                    names.add(alias.asname or alias.name.split(".")[0])
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
            and node.module.split(".")[0] in own
        ):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _py_swallowed(tree: ast.AST, scope: Scope, add: Callable[[Rule, int], None]) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and all(
            isinstance(s, ast.Pass)
            or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
            for s in node.body
        ):
            if scope.adds(node.lineno):
                add(Rule.SWALLOWED_ERROR, node.lineno)
        elif isinstance(node, ast.With):
            for item in node.items:
                call = item.context_expr
                is_suppress = isinstance(call, ast.Call) and _call_name(call) == "suppress"
                if is_suppress and scope.adds(node.lineno):
                    add(Rule.SWALLOWED_ERROR, node.lineno)


def _py_test(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    helpers: set[str],
    scope: Scope,
    add: Callable[[Rule, int], None],
) -> None:
    first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
    last = node.end_lineno or node.lineno
    changed = scope.touches(first, last)
    calls = {_call_name(c) for c in ast.walk(node) if isinstance(c, ast.Call)}
    if changed and not _py_has_assertion(node) and not calls & helpers:
        add(Rule.NO_ASSERTION, node.lineno)
    asserts = _py_assertions(node)
    seen: set[str] = set()
    for item in asserts:
        line = getattr(item, "lineno", node.lineno)
        if scope.adds(line) and _py_always_true(item):
            add(Rule.ASSERT_TRUE, line)
        key = _py_key(item)
        if key in seen and changed:
            add(Rule.DUPLICATE_ASSERTION, line)
        seen.add(key)
    branches = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Match)
    for child in ast.walk(node):
        if isinstance(child, branches) and scope.adds(child.lineno):
            add(Rule.CONDITIONAL_LOGIC, child.lineno)
    if changed:
        bare = [a for a in asserts if not _py_has_message(a)]
        if len(bare) >= ROULETTE_LIMIT:
            add(Rule.ASSERTION_ROULETTE, node.lineno)
        if len(_py_numbers(asserts)) >= MAGIC_LIMIT:
            add(Rule.MAGIC_NUMBER, node.lineno)


def _py_lint(
    text: str, own: frozenset[str], scope: Scope, add: Callable[[Rule, int], None]
) -> None:
    raw_lines = text.splitlines()
    masked_lines = mask(text, "py").splitlines()
    try:
        tree: ast.AST | None = ast.parse(text)
    except SyntaxError:
        tree = None
        add(Rule.UNPARSED, 1)
    own_names = _py_own_names(tree, own) if tree is not None else set()
    for number, raw in enumerate(raw_lines, 1):
        if not scope.adds(number):
            continue
        masked = masked_lines[number - 1] if number <= len(masked_lines) else ""
        for rule, pattern in PY_LINE_RULES:
            if pattern.search(masked):
                add(rule, number)
        if PY_SUPPRESSION.search(raw):
            add(Rule.SUPPRESSION, number)
        if PY_TODO.search(raw):
            add(Rule.DEBUG_LEFTOVER, number)
        targets = [m.group(1) for p in (PY_PATCH, PY_SETATTR) for m in p.finditer(raw)]
        if any(t.split(".")[0] in own for t in targets) or any(
            m.group(1) in own_names or m.group(1) in own for m in PY_PATCH_OBJECT.finditer(raw)
        ):
            add(Rule.OWN_MODULE_MOCK, number)
    if tree is None:
        return
    _py_swallowed(tree, scope, add)
    functions = [
        n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    helpers = {n.name for n in functions if not n.name.startswith("test") and _py_has_assertion(n)}
    for func in functions:
        if func.name.startswith("test"):
            _py_test(func, helpers, scope, add)


# --- TypeScript and JavaScript --------------------------------------------------


@dataclass
class TsTest:
    first: int  # the line of the test call
    body_first: int  # the line the body starts on
    last: int
    body: str  # masked
    raw: str


def _ts_body(masked: str, start: int) -> tuple[int, int] | None:
    """The span of the function body that follows a test call's opening bracket."""
    close = match_close(masked, start, "(", ")")
    if close < 0:
        return None
    inside = masked[start:close]
    arrow = inside.find("=>")
    word = re.search(r"\bfunction\b", inside)
    if arrow >= 0 and (word is None or arrow < word.start()):
        k = start + arrow + 2
        while k < close and masked[k].isspace():
            k += 1
        if k < close and masked[k] == "{":
            end = match_close(masked, k, "{", "}")
            return (k + 1, end) if end >= 0 else None
        return (k, close)
    if word is not None:
        k = masked.find("{", start + word.end(), close)
        if k >= 0:
            end = match_close(masked, k, "{", "}")
            return (k + 1, end) if end >= 0 else None
    return None


def _ts_tests(masked: str, raw: str, lines: Lines) -> list[TsTest]:
    tests: list[TsTest] = []
    for match in TS_TEST_CALL.finditer(masked):
        span = _ts_body(masked, match.end() - 1)
        if span is None:
            continue
        tests.append(
            TsTest(
                lines.of(match.start()),
                lines.of(span[0]),
                lines.of(span[1]),
                masked[span[0] : span[1]],
                raw[span[0] : span[1]],
            )
        )
    return tests


def _ts_helpers(masked: str) -> set[str]:
    names: set[str] = set()
    for pattern in (TS_FUNCTION, TS_ARROW):
        for match in pattern.finditer(masked):
            k = match.end()
            if pattern is TS_FUNCTION:
                k = masked.find("{", k)
            else:
                while k < len(masked) and masked[k].isspace():
                    k += 1
            if k < 0 or k >= len(masked):
                continue
            if masked[k] == "{":
                end = match_close(masked, k, "{", "}")
                body = masked[k : end if end >= 0 else len(masked)]
            else:
                end = masked.find("\n", k)
                body = masked[k : end if end >= 0 else len(masked)]
            if TS_ASSERTION.search(body):
                names.add(match.group(1))
    return names


def _ts_test_rules(
    test: TsTest,
    helpers: set[str],
    scope: Scope,
    add: Callable[[Rule, int], None],
) -> None:
    changed = scope.touches(test.first, test.last)
    calls_helper = any(re.search(rf"\b{re.escape(h)}\s*\(", test.body) for h in helpers)
    if changed and not TS_ASSERTION.search(test.body) and not calls_helper:
        add(Rule.NO_ASSERTION, test.first)
    seen: set[str] = set()
    for match in TS_ASSERT_LINE.finditer(test.raw):
        key = re.sub(r"\s+", "", match.group(0)).removeprefix("await").rstrip(";")
        if key in seen and changed:
            add(Rule.DUPLICATE_ASSERTION, test.body_first + test.raw.count("\n", 0, match.start()))
        seen.add(key)
    for offset, body_line in enumerate(test.body.split("\n")):
        number = test.body_first + offset
        if scope.adds(number) and TS_CONDITIONAL.search(body_line):
            add(Rule.CONDITIONAL_LOGIC, number)
    if changed:
        asserts = [m.group(0) for m in TS_ASSERT_LINE.finditer(test.body)]
        if len(asserts) >= ROULETTE_LIMIT:
            add(Rule.ASSERTION_ROULETTE, test.first)
        numbers = {float(n) for line in asserts for n in TS_NUMBER.findall(line)} - {
            float(p) for p in PLAIN_NUMBERS
        }
        if len(numbers) >= MAGIC_LIMIT:
            add(Rule.MAGIC_NUMBER, test.first)


def _ts_lint(
    text: str, own: frozenset[str], scope: Scope, add: Callable[[Rule, int], None]
) -> None:
    raw_lines = text.splitlines()
    masked = mask(text, "ts")
    masked_lines = masked.splitlines()
    lines = Lines(text)
    for number, raw in enumerate(raw_lines, 1):
        if not scope.adds(number):
            continue
        shown = masked_lines[number - 1] if number <= len(masked_lines) else ""
        for rule, pattern in TS_LINE_RULES:
            if pattern.search(shown):
                add(rule, number)
        if TS_SAME_STRING.search(raw):
            add(Rule.ASSERT_TRUE, number)
        if TS_SUPPRESSION.search(raw):
            add(Rule.SUPPRESSION, number)
        if TS_TODO.search(raw):
            add(Rule.DEBUG_LEFTOVER, number)
        for found in TS_MOCK.finditer(raw):
            target = found.group(1)
            if TS_OWN_PATH.match(target) or target.split("/")[0] in own:
                add(Rule.OWN_MODULE_MOCK, number)
    for match in TS_EMPTY_CATCH.finditer(masked):
        line = lines.of(match.start())
        if scope.adds(line):
            add(Rule.SWALLOWED_ERROR, line)
    helpers = _ts_helpers(masked)
    for test in _ts_tests(masked, text, lines):
        _ts_test_rules(test, helpers, scope, add)


# --- the entry points ---------------------------------------------------------


def lint_text(
    path: str,
    text: str,
    *,
    added: set[int] | None = None,
    touched: set[int] | None = None,
    own_modules: frozenset[str] = frozenset(),
    rules: frozenset[Rule] = DEFAULT_RULES,
    is_test: bool | None = None,
) -> list[Finding]:
    """Judge one file. `added` is the lines the change added; None judges the whole file."""
    language = language_of(path)
    if language is None:
        return []
    scope = Scope(added, set(touched or ()))
    collector = Collector(path, rules)
    if not (is_test_path(path) if is_test is None else is_test):
        _source_rules(text.splitlines(), scope, collector.add)
    elif language == "py":
        _py_lint(text, own_modules, scope, collector.add)
    else:
        _ts_lint(text, own_modules, scope, collector.add)
    return collector.result()


def lint_changes(
    changes: Sequence[tuple[str, str]], *, rules: frozenset[Rule] = DEFAULT_RULES
) -> list[Finding]:
    """Judge the changed files, as (status, path): a snapshot rewritten beside code."""
    if Rule.SNAPSHOT_REWRITTEN not in rules:
        return []
    code = [
        p
        for _, p in changes
        if not is_snapshot_path(p) and not is_test_path(p) and language_of(p) is not None
    ]
    if not code:
        return []
    out: list[Finding] = []
    for status, path in changes:
        if is_snapshot_path(path) and status[:1] in ("M", "D", "T"):
            single = Collector(path, rules)
            single.add(Rule.SNAPSHOT_REWRITTEN, 0)
            out.extend(single.result())
    return out


PLAIN_DIRS = {"tests", "test", "spec", "docs", "node_modules", "venv", "env", "build", "dist"}


def detect_own_modules(root: Path) -> frozenset[str]:
    """The names of the Python packages and modules this project holds."""

    def names(folder: Path) -> set[str]:
        found: set[str] = set()
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            return found
        for entry in entries:
            if entry.name.startswith((".", "_")) or entry.name in PLAIN_DIRS:
                continue
            if entry.is_file() and entry.suffix == ".py":
                found.add(entry.stem)
            elif entry.is_dir() and ((entry / "__init__.py").exists() or any(entry.glob("*.py"))):
                found.add(entry.name)
        return found

    return frozenset(names(root) | names(root / "src"))
