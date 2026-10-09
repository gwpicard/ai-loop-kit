#!/usr/bin/env sh
# settings.sh: check that every guard has its second layer, and that the
# settings templates carry the sandbox, the write-blocks, the read-blocks and
# the hooks the design asks for.
#
# Layer one is a deny or ask rule in a settings template. Layer two is the
# guard hook, kit/hooks/guard.py. Both are matched offline: the rules by
# tests/lib/permission-matcher.py, the hook by running it on a real call in a
# throwaway project. The table is tests/fixtures/two-layer-rules.json. A rule
# that the guard does not read names the other layer that holds it, and the
# check prints that as a visible "single layer" line.
#
# Usage: tests/settings.sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE ROOT

command -v python3 >/dev/null 2>&1 || { echo "FAIL: python3 is needed" >&2; exit 1; }
exec python3 - "$ROOT" <<'PY'
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "tests" / "lib"))
sys.path.insert(0, str(root / "kit" / "scripts"))
sys.path.insert(0, str(root / "kit" / "hooks"))
matcher = __import__("permission-matcher")
import re  # noqa: E402
guard_module = __import__("guard")
from loop import paths as loop_paths  # noqa: E402

problems = []


def fail(message):
    problems.append(message)
    print("  FAIL: " + message)


def ok(message):
    print("  ok: " + message)


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        fail("%s cannot be read as JSON (%s). next: build P10" % (path, error))
        return None


T = root / "kit" / "templates"
templates = {
    "claude-settings": load(T / "claude-settings.json"),
    "builder-settings": load(T / "builder-settings.json"),
    "merge-ask-rules": None,
}
ask_file = load(T / "merge-ask-rules.json")
if ask_file is not None:
    templates["merge-ask-rules"] = {"permissions": {"ask": ask_file.get("ask", [])}}
hooks_json = load(root / "kit" / "hooks" / "hooks.json")
table = load(root / "tests" / "fixtures" / "two-layer-rules.json")
if table is None or any(v is None for v in templates.values()):
    print("settings.sh: the files above are missing, so nothing was checked")
    sys.exit(1)

print("Settings checks:")
found = matcher.self_test()
if found:
    for line in found:
        fail(line)
else:
    ok("the matcher agrees with every example in the documentation's table")

# --- a throwaway project, with a worktree --------------------------------------
base = os.path.realpath(tempfile.mkdtemp())
main = os.path.join(base, "project")
home = os.path.join(base, "home")
os.makedirs(main)
os.makedirs(home)
git_env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null",
               GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@example.com")


def git(*args):
    subprocess.run(["git", "-C", main, *args], check=True, env=git_env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


git("init", "-q", "-b", "main")
Path(main, "README.md").write_text("# demo\n")
git("add", "README.md")
git("commit", "-q", "-m", "Start")
work = os.path.join(main, ".agents", "worktrees", "w1")
git("worktree", "add", "-q", work, "-b", "piece-1")
# The kit's throwaway env file in the worktree, which a builder may read.
Path(work, ".env").write_text(guard_module.THROWAWAY_MARKER + "\nPORT=3000\n")
kit = os.path.join(home, ".claude", "plugins", "cache", "marketplace", "ai-loop-kit", "0.1.0")
guard_env = {"CLAUDE_PLUGIN_ROOT": kit, "PATH": os.environ["PATH"], "HOME": home, "AI_LOOP_KIT_DATA": os.path.join(base, "data"),
             "AI_LOOP_KIT_RUN": "night-1", "PYTHONDONTWRITEBYTECODE": "1"}
paths = loop_paths.Paths.for_project(Path(main), env=guard_env)
values = {"main": main, "work": work, "home": home, "data": str(paths.data_dir), "kit": kit}
render_values = {"PROJECT_ROOT": main, "WORKTREE": work, "KIT_DIR": kit,
                 "DATA_DIR": str(paths.data_dir),
                 "HANDOFF_FILE": os.path.join(main, ".agents", "runs", "night-1", "handoff-p10.json")}


def render(node):
    if isinstance(node, str):
        for key, value in render_values.items():
            node = node.replace("{{%s}}" % key, value)
        return node
    if isinstance(node, list):
        return [render(x) for x in node]
    if isinstance(node, dict):
        return {k: render(v) for k, v in node.items()}
    return node


rendered = {name: render(t) for name, t in templates.items()}


def expand(text):
    for key, value in values.items():
        text = text.replace("{%s}" % key, value)
    return text


def attended_only(rule):
    """A rule for the person's own session. A builder's own worktree holds a throwaway .env, so
    the builder settings name the main folder's real path instead of these floating shapes."""
    return rule in {"Read(//**/.env)", "Read(//**/.env.*)"} or rule in {
        "Bash(%s *.env*)" % command
        for command in ("cat", "head", "tail", "less", "more", "grep", "rg", "sed", "awk", "bat", "cp", "source")
    }


def layer1(template, tool, text):
    """deny, ask or none, as the template's rules judge the call."""
    perms = rendered[template].get("permissions", {})
    if template == "builder-settings":
        base_rules = [r for r in rendered["claude-settings"]["permissions"].get("deny", [])
                      if not attended_only(r)]
        perms = {"deny": perms.get("deny", []) + base_rules, "ask": perms.get("ask", [])}
    if template == "merge-ask-rules":
        perms = {"deny": [], "ask": perms["ask"]}
    for kind in ("deny", "ask"):
        for rule in perms.get(kind, []):
            if tool == "Bash":
                hit = matcher.matches(rule, text)
            else:
                hit = matcher.file_rule_matches(rule, tool, text, work, work, home, kind)
            if hit:
                return kind
    return "none"


def guard(tool, text):
    key = "command" if tool == "Bash" else "file_path"
    payload = {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": tool,
               "tool_input": {key: text}, "cwd": work}
    result = subprocess.run([sys.executable, str(root / "kit" / "hooks" / "guard.py")],
                            input=json.dumps(payload), capture_output=True, text=True,
                            env=guard_env, check=False)
    if result.returncode == 2:
        return "deny"
    if result.returncode == 0 and '"permissionDecision": "ask"' in result.stdout:
        return "ask"
    return "none" if result.returncode == 0 else "fault"


# CR-02: inspect each template's own rules, without inherited attended denies.
for name in ("claude-settings", "builder-settings"):
    node = rendered[name]
    own_deny = node["permissions"]["deny"]
    for tool in ("Edit", "Write"):
        for relative in ("scripts/gate.py", "hooks/guard.py", "templates/builder-settings.json"):
            target = os.path.join(kit, relative)
            if not matcher.file_denied(own_deny, tool, target, work, main, home):
                fail("CR-02 %s lacks its own installed-root %s deny for %s" % (name, tool, relative))
    if kit not in node["sandbox"]["filesystem"].get("denyWrite", []):
        fail("CR-02 %s lacks its own installed-root sandbox write block" % name)
    if matcher.file_denied(own_deny, "Edit", work + "/src/app.py", work, main, home):
        fail("CR-02 %s blocks ordinary source edits" % name)
    if "~/.claude/plugins/cache/ai-loop-kit" in json.dumps(node):
        fail("CR-02 %s retains the guessed plugin-cache protection" % name)

if attended_only("Bash(unexpected *.env*)") or attended_only("Read(//**/.env-backup)"):
    fail("CR-02 the attended-only exemption hides an unrelated guard")

# --- the two-layer table ---------------------------------------------------------
single = 0
for entry in table["rules"]:
    text = expand(entry["input"])
    got1 = layer1(entry["template"], entry["tool"], text)
    if got1 != entry["layer1"]:
        fail("%s: the %s template gives %s for %s %r, and the table says %s"
             % (entry["id"], entry["template"], got1, entry["tool"], text, entry["layer1"]))
        continue
    got2 = guard(entry["tool"], text)
    if entry["guard"] == "none":
        if not entry.get("other_layer"):
            fail("%s: no guard refusal and no other layer named" % entry["id"])
        elif got2 != "none":
            fail("%s: the table says the guard passes it, and the guard says %s"
                 % (entry["id"], got2))
        else:
            single += 1
            print("  single layer: %s, held also by %s" % (entry["id"], entry["other_layer"]))
        continue
    if got2 != entry["guard"]:
        fail("%s: the guard gives %s for %s %r, and the table says %s"
             % (entry["id"], got2, entry["tool"], text, entry["guard"]))
    elif entry["layer1"] == "none":
        # The settings rules cannot say this spelling, so the guard stands alone for it.
        if "single layer" not in entry.get("other_layer", ""):
            fail("%s: no settings rule applies, and the row does not say 'single layer'" % entry["id"])
        else:
            single += 1
            print("  single layer: %s, the guard only (%s)" % (entry["id"], entry["other_layer"]))
    else:
        ok("%s: %s in the template and %s from the guard" % (entry["id"], got1, got2))
for entry in table["must_pass"]:
    text = expand(entry["input"])
    got1 = layer1(entry["template"], entry["tool"], text)
    got2 = guard(entry["tool"], text)
    if got1 != "none" or got2 != "none":
        fail("a harmless call is stopped: %s %r (template %s, guard %s)"
             % (entry["tool"], text, got1, got2))
    else:
        ok("passes both layers: %s %s" % (entry["tool"], text))
print("  %d of %d table rules rest on one rule layer and a named other layer"
      % (single, len(table["rules"])))

# --- the sandbox and the builder's own settings ----------------------------------
b = rendered["builder-settings"]
sb = b.get("sandbox", {})
perm = b.get("permissions", {})
checks = [
    (sb.get("enabled") is True, "builder sandbox is not enabled"),
    (sb.get("failIfUnavailable") is True, "builder sandbox lacks failIfUnavailable: true"),
    (sb.get("allowUnsandboxedCommands") is False, "builder sandbox lacks allowUnsandboxedCommands: false"),
    (sb.get("autoAllowBashIfSandboxed") is True, "builder sandbox does not auto-allow sandboxed commands"),
    (sb.get("network", {}).get("strictAllowlist") is True, "builder sandbox lacks network.strictAllowlist: true"),
    (bool(sb.get("network", {}).get("allowedDomains")), "builder sandbox names no allowed domain"),
    (perm.get("defaultMode") == "dontAsk", "builder defaultMode is not dontAsk"),
    (perm.get("disableBypassPermissionsMode") == "disable", "builder settings leave bypass mode on"),
    ("Skill" in perm.get("deny", []), "builder settings do not deny the Skill tool"),
    (b.get("autoMemoryEnabled") is False, "builder settings leave auto memory on"),
]
env_keys = set(b.get("env", {}))
checks.append((not env_keys & {"GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN"},
               "builder settings carry a GitHub credential"))
passed = 0
for good, message in checks:
    if good:
        passed += 1
    else:
        fail(message)
ok("builder settings: %d of %d sandbox, mode, memory and credential checks hold"
   % (passed, len(checks)))

c = rendered["claude-settings"]
csb = c.get("sandbox", {})
project_checks = [
    (csb.get("enabled") is True, "project sandbox is not enabled"),
    (csb.get("failIfUnavailable") is True, "project sandbox lacks failIfUnavailable: true"),
    (csb.get("allowUnsandboxedCommands") is False, "project sandbox lacks allowUnsandboxedCommands: false"),
    (c.get("permissions", {}).get("disableBypassPermissionsMode") == "disable",
     "project settings leave bypass mode on"),
    # An agent session never uses the person's GitHub sign-in, by any spelling:
    # the sandbox hides the gh config and the keychain from every command.
    ("~/.config/gh" in csb.get("filesystem", {}).get("denyRead", []),
     "the project sandbox does not read-block the gh config"),
    ("~/Library/Keychains" in csb.get("filesystem", {}).get("denyRead", []),
     "the project sandbox does not read-block the keychain"),
]
for good, message in project_checks:
    if not good:
        fail(message)
ok("project settings: %d sandbox and mode checks run" % len(project_checks))

fs = sb.get("filesystem", {})
deny_write = fs.get("denyWrite", [])
for anchor in (main, work):
    for rel in (".claude", ".github/workflows", ".githooks", ".agents/loop", ".agents/pieces"):
        want = os.path.join(anchor, rel)
        if want in deny_write:
            ok("write-blocked in the sandbox: " + want.replace(base, "<base>"))
        else:
            fail("the sandbox does not write-block " + want.replace(base, "<base>"))
if kit in deny_write:
    ok("write-blocked in the sandbox: the installed kit folder")
else:
    fail("the sandbox does not write-block the installed kit folder (it holds the hooks and the gate)")
handoff = render_values["HANDOFF_FILE"]
allow_write = fs.get("allowWrite", [])
if allow_write == [handoff]:
    ok("the sandbox allows one write outside the worktree: the hand-off file")
else:
    fail("allowWrite must hold only the hand-off file, and it holds %r" % allow_write)
for entry in deny_write:
    if handoff == entry or handoff.startswith(entry.rstrip("/") + "/"):
        fail("denyWrite %s would also block the hand-off file" % entry)
deny_read = fs.get("denyRead", [])
for label, want in [("the held-out folder and App key", str(paths.data_dir)),
                    ("the gh config", "~/.config/gh"),
                    ("the keychain", "~/Library/Keychains"),
                    ("the machine-local settings file", os.path.join(main, ".agents/loop/local.json"))]:
    if want in deny_read:
        ok("read-blocked in the sandbox: " + label)
    else:
        fail("the sandbox does not read-block %s (%s)" % (label, want))
for rule in templates["claude-settings"]["permissions"]["deny"]:
    if attended_only(rule):
        continue
    if rule not in templates["builder-settings"]["permissions"]["deny"]:
        fail("builder settings lack the project deny rule %s" % rule)
        break
else:
    ok("builder settings repeat every project deny rule, so they do not depend on discovery")

# Network: a builder holds no GitHub credential, so no GitHub host is reachable.
domains = sb.get("network", {}).get("allowedDomains", [])
github_hosts = [d for d in domains if d == "github.com" or d.endswith(".github.com")
                or d.endswith("githubusercontent.com")]
if github_hosts:
    fail("the builder's allowed domains name a GitHub host: %s" % ", ".join(github_hosts))
else:
    ok("no GitHub host is in the builder's allowed domains")

# The builder's Edit and Write tools must run under dontAsk, so they are allowed in the worktree.
allow = rendered["builder-settings"]["permissions"].get("allow", [])
for tool in ("Edit", "Write"):
    inside = work + "/src/app.py"
    outside = main + "/src/app.py"
    if any(matcher.file_rule_matches(rule, tool, inside, work, work, home, "allow") for rule in allow):
        ok("builder allow rules let the %s tool work inside its worktree" % tool)
    else:
        fail("builder allow rules do not let the %s tool work inside its worktree, so dontAsk "
             "refuses it" % tool)
    if any(matcher.file_rule_matches(rule, tool, outside, work, work, home, "allow") for rule in allow):
        fail("builder allow rules let the %s tool work outside its worktree" % tool)
    if any(matcher.file_rule_matches(rule, tool, work + "/.claude/settings.json", work, work, home,
                                     "allow") for rule in allow):
        ok("the %s allow rule is wide, and the deny rule on .claude still wins over it" % tool)

# No placeholder may survive rendering.
for name, node in rendered.items():
    left = re.findall(r"\{\{[A-Z_]+\}\}", json.dumps(node))
    if left:
        fail("%s still holds %s after rendering" % (name, sorted(set(left))))
    else:
        ok("%s has no placeholder left after rendering" % name)
for name, node in templates.items():
    unknown = set(re.findall(r"\{\{([A-Z_]+)\}\}", json.dumps(node))) - set(render_values)
    if unknown:
        fail("%s uses a placeholder that the renderer does not know: %s" % (name, sorted(unknown)))

# --- hooks -------------------------------------------------------------------------
def commands(hooks, event):
    out = []
    for group in (hooks or {}).get(event, []):
        out += [h.get("command", "") for h in group.get("hooks", [])]
    return out


def wired(hooks, event, script, label):
    if any(script in cmd for cmd in commands(hooks, event)):
        ok("%s wires %s on %s" % (label, script, event))
    else:
        fail("%s does not wire %s on %s" % (label, script, event))


bh = b.get("hooks")
wired(bh, "PreToolUse", "guard.py", "builder settings")
wired(bh, "PostToolUse", "command-log.py", "builder settings")
wired(bh, "PostToolUseFailure", "command-log.py", "builder settings")
pre = [g.get("matcher", "") for g in (bh or {}).get("PreToolUse", [])]
for tool in ("Bash", "Edit", "Write", "Read", "Grep", "Glob"):
    if not any(m in ("", "*") or tool in m.split("|") for m in pre):
        fail("the builder guard hook does not match the %s tool" % tool)
if "{{KIT_DIR}}" not in json.dumps(templates["builder-settings"]["hooks"]):
    fail("builder hook commands do not point at the kit folder with {{KIT_DIR}}")
hj = (hooks_json or {}).get("hooks", hooks_json)
wired(hj, "PreToolUse", "guard.py", "hooks.json")
wired(hj, "PostToolUse", "command-log.py", "hooks.json")
wired(hj, "PostToolUseFailure", "command-log.py", "hooks.json")
if "CLAUDE_PLUGIN_ROOT" not in json.dumps(hooks_json):
    fail("hooks.json does not use CLAUDE_PLUGIN_ROOT")
wired(c.get("hooks"), "SessionStart", "session-start.sh", "the settings template")

# --- merging keeps the person's rules ----------------------------------------------
merge = root / "kit" / "scripts" / "merge-settings.py"
# CR-02: the public merge CLI renders the same canonical root as setup and sessions.
Path(kit).mkdir(parents=True)
kit_link = Path(base, "installed-kit")
kit_link.symlink_to(kit, target_is_directory=True)
canonical_target = Path(base, "canonical-settings.json")
canonical_args = [sys.executable, str(merge), str(T / "claude-settings.json"),
                  str(canonical_target), "--set", "KIT_DIR=" + str(kit_link)]
canonical_merge = subprocess.run(canonical_args, capture_output=True, text=True,
                                 env=guard_env, check=False)
if canonical_merge.returncode:
    fail("CR-02 the direct symlink-root merge failed: " + canonical_merge.stderr)
else:
    canonical_text = canonical_target.read_text()
    canonical_settings = json.loads(canonical_text)
    if "Edit(/" + kit + "/**)" not in canonical_settings["permissions"]["deny"]:
        fail("CR-02 direct merge CLI lacks the canonical installed-root Edit deny")
    if kit not in canonical_settings["sandbox"]["filesystem"].get("denyWrite", []):
        fail("CR-02 direct merge CLI lacks the canonical installed-root sandbox block")
    if str(kit_link) in canonical_text or "{{" in canonical_text:
        fail("CR-02 direct merge CLI retains a symlink alias or placeholder")
    repeated = subprocess.run(canonical_args, capture_output=True, text=True,
                              env=guard_env, check=False)
    if repeated.returncode or canonical_target.read_text() != canonical_text:
        fail("CR-02 direct canonical merge is not idempotent")
relative_target = Path(base, "relative-settings.json")
relative_merge = subprocess.run(
    [sys.executable, str(merge), str(T / "claude-settings.json"), str(relative_target),
     "--set", "KIT_DIR=relative-kit"], capture_output=True, text=True, env=guard_env, check=False)
if relative_merge.returncode == 0 or relative_target.exists() or "KIT_DIR" not in relative_merge.stderr:
    fail("CR-02 direct merge CLI does not refuse a relative kit root before writing")

mine = Path(base, "mine.json")
mine.write_text(json.dumps({
    "permissions": {"allow": ["Bash(npm test:*)"], "deny": ["Bash(npm publish:*)"],
                    "defaultMode": "acceptEdits"},
    "model": "opus",
    "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo mine"}]}]},
}, indent=2) + "\n")
args = [sys.executable, str(merge), str(T / "claude-settings.json"), str(mine)]
r1 = subprocess.run(args, capture_output=True, text=True, env=guard_env, check=False)
if r1.returncode != 0:
    fail("merge-settings.py failed (%d): %s%s" % (r1.returncode, r1.stdout[-200:], r1.stderr[-200:]))
else:
    m = json.loads(mine.read_text())
    p = m.get("permissions", {})
    if "Bash(npm publish:*)" in p.get("deny", []) and "Bash(npm test:*)" in p.get("allow", []) \
            and p.get("defaultMode") == "acceptEdits" and m.get("model") == "opus":
        ok("merging keeps the person's own rules and values")
    else:
        fail("merging lost something the person had: %r" % m)
    if all(rule in p.get("deny", []) for rule in templates["claude-settings"]["permissions"]["deny"]):
        ok("merging adds every deny rule of the template")
    else:
        fail("merging dropped a deny rule of the template")
    if "echo mine" in json.dumps(m.get("hooks")) and "session-start.sh" in json.dumps(m.get("hooks")):
        ok("merging keeps the person's hook beside the kit's")
    else:
        fail("merging lost a hook")
    before = mine.read_text()
    r2 = subprocess.run(args, capture_output=True, text=True, env=guard_env, check=False)
    if r2.returncode == 0 and mine.read_text() == before:
        ok("merging twice changes nothing the second time")
    else:
        fail("merging is not idempotent")
# A scalar of the person's that overrides a kit guard value is reported on stderr.
override = Path(base, "override.json")
override.write_text(json.dumps({"sandbox": {"enabled": False}}) + "\n")
r4 = subprocess.run([sys.executable, str(merge), str(T / "claude-settings.json"), str(override)],
                    capture_output=True, text=True, env=guard_env, check=False)
if r4.returncode == 0 and "sandbox.enabled" in r4.stderr and "kit" in r4.stderr \
        and json.loads(override.read_text())["sandbox"]["enabled"] is False \
        and "sandbox.enabled" in r4.stdout:
    ok("a person's sandbox.enabled that overrides the kit's value is reported on stderr and in the JSON")
else:
    fail("an override of a kit guard value was not reported: %d %r %r"
         % (r4.returncode, r4.stderr[-200:], r4.stdout[-200:]))
quiet = subprocess.run(args, capture_output=True, text=True, env=guard_env, check=False)
if "sandbox" not in quiet.stderr and "overrid" not in quiet.stderr:
    ok("a merge with no override says nothing on stderr about overrides")
else:
    fail("a merge with no override reported one: %r" % quiet.stderr)
bad = Path(base, "bad.json")
bad.write_text("{not json")
r3 = subprocess.run([sys.executable, str(merge), str(T / "claude-settings.json"), str(bad)],
                    capture_output=True, text=True, env=guard_env, check=False)
if r3.returncode != 0 and bad.read_text() == "{not json" and "next:" in r3.stderr:
    ok("a target that is not JSON is left untouched, and the error names the next step")
else:
    fail("a target that is not JSON was not refused cleanly")

print("")
if problems:
    print("settings.sh: %d check(s) failed" % len(problems))
    sys.exit(1)
print("settings.sh: all checks passed (scratch: %s)" % base)
PY
