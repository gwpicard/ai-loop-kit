#!/usr/bin/env sh
# live-on-vercel.after-commit.sh: cut the branch behind the open pull request
# and write the host's list of deployments, once the first commit exists.
#
# live-on-vercel.sh wrote the project and recorded one open pull request. This
# pushes `main` to the remote next door, as a project on GitHub would have it,
# cuts the pull request's branch from `main`, makes the wording change, and
# pushes the branch. It leaves the project on `main` with nothing uncommitted.
#
# It then writes the state the stand-in host reads, beside the project rather
# than in it, so the kit never commits it. The host holds what the first launch
# left: a production build that failed, the working build that is live, and
# the pull request's preview. The remote keeps a log of every push to `main`,
# which is how the stand-in sees a merge and builds it.
#
# Usage: live-on-vercel.after-commit.sh <project-dir>

set -eu

project=${1:?project directory}
me=live-on-vercel.after-commit.sh

# Only a fresh replay project: its own repository, one commit made by the
# harness, and the remote next door. Anything else, this repository included,
# is refused before a branch is made.
top=$(git -C "$project" rev-parse --show-toplevel 2>/dev/null || true)
here=$(cd "$project" 2>/dev/null && pwd -P || true)
[ -n "$top" ] && [ "$(cd "$top" && pwd -P)" = "$here" ] || {
  echo "$me: $project is not the top of its own repository" >&2
  exit 1
}
[ "$(git -C "$project" rev-list --count --all)" = "1" ] \
  && [ "$(git -C "$project" log -1 --format=%s)" = "Project before the scenario" ] || {
  echo "$me: $project has history beyond the harness's first commit, so it is not a fresh replay project" >&2
  exit 1
}
[ "$(git -C "$project" remote get-url origin 2>/dev/null || true)" = "$project.git" ] || {
  echo "$me: $project has no remote next door" >&2
  exit 1
}
[ -f "$project/.gh-fixture.json" ] && [ -f "$project/lib/wording.ts" ] || {
  echo "$me: $project is not the project live-on-vercel.sh writes" >&2
  exit 1
}
[ ! -e "$project.host.json" ] || {
  echo "$me: $project.host.json already exists" >&2
  exit 1
}

# A bare repository keeps no log of its branches unless told to. The stand-in
# host reads that log to find each push to main.
git -C "$project.git" config core.logAllRefUpdates true
git -C "$project" branch -M main
git -C "$project" push -q origin main
live=$(git -C "$project" rev-parse main)

git -C "$project" checkout -q -b sign-in-button-wording main
python3 - "$project" <<'PY'
import os, sys

project = sys.argv[1]


def edit(name, old, new):
    path = os.path.join(project, name)
    text = open(path).read()
    if text.count(old) != 1:
        sys.exit("%s: the project changed, so this edit no longer fits" % name)
    open(path, "w").write(text.replace(old, new, 1))


edit("lib/wording.ts", 'signInButton: string = "Continue";',
     'signInButton: string = "Email me a sign-in link";')
edit("lib/wording.test.ts", '''  assert.ok(signInButton.length > 0);
});''', '''  assert.ok(signInButton.length > 0);
});

test("the sign-in button says an email is on its way", () => {
  assert.equal(signInButton, "Email me a sign-in link");
});''')
PY
git -C "$project" add -A
git -C "$project" commit -q -m "Say plainly what the sign-in button does"
git -C "$project" push -q origin sign-in-button-wording
branch=$(git -C "$project" rev-parse sign-in-button-wording)
git -C "$project" checkout -q main

[ -z "$(git -C "$project" status --porcelain)" ] || {
  echo "$me: the project was left with uncommitted changes" >&2
  exit 1
}

python3 - "$project" "$live" "$branch" <<'PY'
import json, subprocess, sys

project, live, branch = sys.argv[1:4]
pushes = subprocess.run(["git", "--git-dir", project + ".git", "log", "-g", "--format=%H",
                         "refs/heads/main"], capture_output=True, text=True).stdout.split()
if len(pushes) != 1:
    sys.exit("live-on-vercel.after-commit.sh: the remote logged %d pushes to main, not 1"
             % len(pushes))


def dep(ident, target, branch_name, commit, state, created):
    return {"id": "dpl_" + ident,
            "url": "noticeboard-%s-office-tools.vercel.app" % ident,
            "target": target, "branch": branch_name, "commit": commit, "source": "git",
            "state": state, "seen": True, "created": created, "before_run": True}


state = {
    "team": "office-tools",
    "project": "noticeboard",
    "user": "priya-office",
    "production_url": "noticeboard-office.vercel.app",
    "supabase_ref": "qwmhzkpvnbxlcrtdyefa",
    "public_key": "public-anon-key-stand-in",
    "env_names": ["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY",
                  "SUPABASE_SERVICE_ROLE_KEY"],
    "remote": project + ".git",
    "pushes_built": len(pushes),
    "deployments": [
        dep("6k3lidtl1", "production", "main", live, "ERROR", "2026-09-19T09:41:07Z"),
        dep("6ez2xstin", "production", "main", live, "READY", "2026-09-19T10:05:52Z"),
        dep("p4w8rnq2c", "preview", "sign-in-button-wording", branch, "READY",
            "2026-09-25T16:20:31Z"),
    ],
    "alias": "dpl_6ez2xstin",
}
with open(project + ".host.json", "w") as handle:
    json.dump(state, handle, indent=1)
PY
