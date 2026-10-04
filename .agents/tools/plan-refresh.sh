#!/usr/bin/env sh
# plan-refresh.sh: the maintainer's way into the plan printout helper.
#
# The helper itself ships inside the setup-ai-build-kit skill, at
# templates/foundation/plan-refresh.sh, because every route that installs the
# kit carries the skills and nothing else. Founding copies it into a project at
# .agents/tools/plan-refresh.sh. This wrapper stays in this repository so the old
# path still works here. The release allowlist leaves it out.

set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec sh "$here/../skills/setup-ai-build-kit/templates/foundation/plan-refresh.sh" "$@"
