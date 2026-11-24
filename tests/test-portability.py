"""Refuse test code that assumes macOS or an inherited temporary folder."""
import ast
from pathlib import Path
import shlex
import subprocess
import sys


TOOLS = {"taskpolicy", "sysctl", "memory_pressure", "caffeinate"}
COMMAND_KEYWORDS = {
    "subprocess.run": "args", "subprocess.Popen": "args", "subprocess.call": "args",
    "subprocess.check_call": "args", "subprocess.check_output": "args",
    "os.system": None, "os.popen": "cmd",
    "common.run_shell": "command", "run_shell": "command",
}


def mac_condition(node):
    """Return whether a recognised comparison selects macOS, or None."""
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return None
    left, right = ast.unparse(node.left), node.comparators[0]
    if left not in {"sys.platform", "platform.system()"}:
        return None
    if not isinstance(right, ast.Constant) or right.value not in {"darwin", "Darwin"}:
        return None
    if isinstance(node.ops[0], ast.Eq):
        return True
    if isinstance(node.ops[0], ast.NotEq):
        return False
    return None


def command_tool(node):
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        return None
    if isinstance(value, str):
        try:
            value = shlex.split(value)
        except ValueError:
            return None
    if not isinstance(value, (list, tuple)) or not value or not isinstance(value[0], str):
        return None
    tool = Path(value[0]).name
    return tool if tool in TOOLS or (tool == "getconf" and "DARWIN_USER_TEMP_DIR" in value) else None


class Portability(ast.NodeVisitor):
    def __init__(self):
        self.mac = False
        self.fakes = set()
        self.failures = []

    def visit_Subscript(self, node):
        if (isinstance(node.ctx, ast.Load) and ast.unparse(node.value) == "os.environ"
                and isinstance(node.slice, ast.Constant) and node.slice.value == "TMPDIR"):
            self.failures.append((node.lineno, "use tempfile.gettempdir() instead of requiring TMPDIR"))
        self.generic_visit(node)

    def visit_Call(self, node):
        name = ast.unparse(node.func)
        if name in COMMAND_KEYWORDS and not self.mac and name not in self.fakes:
            command = node.args[0] if node.args else next(
                (keyword.value for keyword in node.keywords
                 if keyword.arg is not None and keyword.arg == COMMAND_KEYWORDS[name]), None)
            tool = command_tool(command) if command is not None else None
            if tool:
                self.failures.append((node.lineno, tool + " needs a macOS platform check or a fake"))
        self.generic_visit(node)

    def visit_If(self, node):
        self.visit(node.test)
        condition = mac_condition(node.test)
        before = self.mac
        for body, selected in ((node.body, condition is True), (node.orelse, condition is False)):
            self.mac = before or selected
            for statement in body:
                self.visit(statement)
        self.mac = before

    def visit_FunctionDef(self, node):
        before = self.mac
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and decorator.args:
                name = ast.unparse(decorator.func)
                condition = mac_condition(decorator.args[0])
                if ((name == "unittest.skipUnless" and condition is True)
                        or (name == "unittest.skipIf" and condition is False)):
                    self.mac = True
        self.generic_visit(node)
        self.mac = before

    visit_ClassDef = visit_FunctionDef
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_With(self, node):
        before = self.fakes.copy()
        for item in node.items:
            call = item.context_expr
            if not isinstance(call, ast.Call):
                continue
            name = ast.unparse(call.func)
            if name in {"mock.patch", "unittest.mock.patch"} and call.args:
                target = call.args[0]
                if isinstance(target, ast.Constant) and isinstance(target.value, str):
                    self.fakes.add(target.value)
            elif name in {"mock.patch.object", "unittest.mock.patch.object"} and len(call.args) >= 2:
                target = call.args[1]
                if isinstance(target, ast.Constant) and isinstance(target.value, str):
                    self.fakes.add(ast.unparse(call.args[0]) + "." + target.value)
        self.generic_visit(node)
        self.fakes = before


def main(root):
    files = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z", "--",
                                     "kit/tests/*.py"], text=True).split("\0")
    failed = False
    for name in filter(None, files):
        path = root / name
        if not path.is_file():
            continue
        check = Portability()
        check.visit(ast.parse(path.read_text(), filename=name))
        for line, reason in check.failures:
            print("%s:%d: %s" % (name, line, reason))
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
