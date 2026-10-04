"""permission-matcher.py: a small stand-in for Claude Code's permission matcher.

Nothing here can run Claude Code's own matcher without a model, so the checks
that judge a project's permission rules share this one. It follows the rule
shape documented at https://code.claude.com/docs/en/permissions ("Wildcard
patterns" and "Bash"):

  - a rule matches the whole command text;
  - `*` may sit anywhere and stands for any text, spaces included;
  - everything else is literal, including a space before a `*`, and a colon
    anywhere but a final `:*`;
  - a final `:*` is the same as a final ` *`;
  - a final ` *` that is the rule's only wildcard also matches the bare
    command with nothing after it.

It is fed one command at a time. Claude Code also splits a compound command
and strips wrappers such as `timeout` and leading variable assignments before
it matches; none of the spellings the checks feed it needs that, so it is not
modelled.

A check calls self_test() first, which runs the examples in the
documentation's own table, so a matcher that drifted from the documentation
fails before it judges anything. Run on its own, this file runs that test.
"""

import re
import sys


def compile_rule(rule):
    m = re.fullmatch(r"Bash\((.*)\)", rule, re.S)
    if not m:
        return None
    body = m.group(1)
    if body.endswith(":*"):
        body = body[:-2] + " *"
    pattern = ".*".join(re.escape(part) for part in body.split("*"))
    bare = body[:-2] if body.count("*") == 1 and body.endswith(" *") else None
    return re.compile(pattern, re.S), bare


def matches(rule, command):
    compiled = compile_rule(rule)
    if compiled is None:
        return False
    pattern, bare = compiled
    return pattern.fullmatch(command) is not None or command == bare


def any_match(rules, command):
    return any(matches(rule, command) for rule in rules)


# The documentation's own table, row by row: a rule, the commands it matches,
# and the commands it does not.
DOCUMENTED = [
    ("Bash(npm run build)", ["npm run build"], ["npm run build --watch"]),
    ("Bash(npm run *)", ["npm run build", "npm run test --watch", "npm run"], ["npm install"]),
    ("Bash(git log * main)",
     ["git log --oneline main", "git log -5 main", "git log --output=<file> main"],
     ["git log main", "git push origin main"]),
    ("Bash(git * main)",
     ["git merge main", "git push origin main", "git -c core.fsmonitor=<script> diff main"],
     ["git log"]),
    ("Bash(* --version)", ["node --version", "bash -c 'echo hi' --version"], ["node -v"]),
    ("Bash(ls *)", ["ls -la", "ls"], ["lsof"]),
    ("Bash(ls*)", ["ls -la", "lsof"], []),
    ("Bash(* --help *)", ["npm --help x"], ["npm --help"]),
    ("Bash(ls:*)", ["ls -la", "ls"], ["lsof"]),
    ("Bash(git:* push)", [], ["git push", "git status push"]),
]


def self_test():
    """Return a list of problems; empty when the matcher agrees with the table."""
    problems = []
    for rule, yes, no in DOCUMENTED:
        for command in yes:
            if not matches(rule, command):
                problems.append("matcher: %s should match %r, as the documentation says" % (rule, command))
        for command in no:
            if matches(rule, command):
                problems.append("matcher: %s should not match %r, as the documentation says" % (rule, command))
    return problems


def section(text, heading):
    """The lines under a `## ` heading, up to the next one. None when absent.

    Two sections of blocked-commands.md carry lists that open with the same
    marker, so a reader that took the first match would read the push lists
    twice and the delete lists never.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("## ") and line[3:].strip() == heading:
            break
    else:
        return None
    body = []
    for line in lines[i + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def read_list(text, marker, keep, heading=None):
    """The backticked spellings in the bullet list that follows a marker line.

    A bullet may wrap onto indented lines. Only spellings for which keep()
    is true are returned, so prose in backticks is left out. With a heading,
    the marker is looked for only under that `## ` heading. None when the
    heading or the marker is not in the text.
    """
    if heading is not None:
        text = section(text, heading)
        if text is None:
            return None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            break
    else:
        return None
    items, current = [], None
    for line in lines[i + 1:]:
        if line.startswith("- "):
            if current is not None:
                items.append(current)
            current = line[2:].strip()
        elif line.startswith("  ") and current is not None:
            current += " " + line.strip()
        elif line.strip() == "" and current is None:
            continue
        else:
            break
    if current is not None:
        items.append(current)
    spellings = []
    for item in items:
        spellings += [s for s in re.findall(r"`([^`]+)`", item) if keep(s)]
    return spellings


if __name__ == "__main__":
    found = self_test()
    if found:
        print("\n".join(found))
        sys.exit(1)
    print("  ok: the matcher agrees with every example in the documentation's table")
