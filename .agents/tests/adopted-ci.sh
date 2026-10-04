#!/usr/bin/env sh
# adopted-ci.sh: guard the rule that an adopted project's own CI is its
# project check, and that every skill reading or editing the check reads the
# record of which file and job that is.
#
# Founding once copied the kit's checks.yml whenever it was missing, and every
# skill that touched the check assumed that file and its project-check job. On
# a project whose tests already ran in a workflow of its own, the placeholder
# failed on every pull request beside the working check, and /sync, the check
# floor, the boundary rules, the move onto the index and a run's install step
# would each have read or edited the wrong file. So founding records the check
# as one line in the capability profile, and each of those readers takes the
# file and job from it, with checks.yml only as the default for a line that
# names no file.
#
# The rules live as prose a coding agent reads, so this check reads them back
# and proves each one load-bearing. It also searches the readers for a bare
# checks.yml or project-check left outside the default, which is how one
# reader quietly going back to the fixed file would show. The bootstrap half is
# run on disk by adopted-ci-rehearsal.sh.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$ROOT/.agents/tests/lib/rule-shape.sh"

SKILLS="$ROOT/.agents/skills"
SETUP_DIR="$SKILLS/setup-ai-build-kit"
REF="$SETUP_DIR/references/project-check.md"
SETUP="$SETUP_DIR/SKILL.md"
BOOTSTRAP="$SETUP_DIR/scripts/bootstrap-project.sh"
CAPABILITY="$SETUP_DIR/references/capability-check.md"
FLOOR="$SETUP_DIR/references/check-floor.md"
BOUNDARY="$SETUP_DIR/references/boundary-rules.md"
REPORT="$SETUP_DIR/references/completion-report.md"
TEMPLATE="$SETUP_DIR/templates/foundation/AGENTS.md"
RECORD="$SETUP_DIR/templates/maintenance-record"
SYNC="$SKILLS/sync/SKILL.md"
MAINTAIN="$SKILLS/maintain/SKILL.md"
LONGER="$SKILLS/implement/references/running-longer.md"
WORKFLOW="$ROOT/WORKFLOW.md"

rs_init "Adopted CI checks"
rs_exists "$REF" "$SETUP" "$BOOTSTRAP" "$CAPABILITY" "$FLOOR" "$BOUNDARY" \
  "$REPORT" "$TEMPLATE" "$RECORD" "$SYNC" "$MAINTAIN" "$LONGER" "$WORKFLOW"

# The owner: which workflow counts, the job, the record, and the kit's steps.
rs_rule "a workflow counts on pull_request with a run: line containing test" \
  'runs on `pull_request`, and has a `run:` line containing the word `test`'
rs_rule "the bootstrap copies no checks.yml beside one and names it" \
  'copies no `checks\.yml` beside it and prints one line naming the file'
rs_rule "a pull request workflow that runs no tests is not a project check" \
  'a workflow on pull requests that runs no tests, such as a labeller, is not a project check'
rs_rule "a workflow only on push is not a pull request check" \
  'a workflow that runs only on `push` is not a pull request check'
rs_rule "founding says the push-only workflow stays as it is" \
  'say in one line that the project.s own workflow stays as it is'
rs_rule "the project's own checks.yml is kept and recorded" \
  'a `checks\.yml` the project already had, that is not the kit.s placeholder, is kept'
rs_rule "job rule 1: the job running the recorded test command" \
  'the job whose steps run the test command agents\.md.s stack section records'
rs_rule "job rule 2: the first job, by file name then job name" \
  'else the first job, by file name then job name, triggered on pull requests with a `run:` line containing `test`'
rs_rule "job rule 3: none, so checks.yml is copied and recorded" \
  'else none\. no job of the project.s runs tests, so copy the kit.s `checks\.yml` where it is missing and record it'
rs_rule "founding names the file and job in one line" \
  'say in one line which file and job you chose'
rs_rule "the kit's placeholder never counts" \
  'the kit.s own placeholder `checks\.yml`, whose `install and test` step says no tests have run, never counts'
rs_rule "several jobs and no test command: the first is named" \
  'a workflow with several jobs and no test command recorded yet takes the second rule'
rs_rule "the record's form" \
  '`project check: <workflow file>, job <job name>`'
rs_rule "the default record for a project with no CI" \
  'records `project check: \.github/workflows/checks\.yml, job project-check`'
rs_rule "a line naming no file means the default" \
  'a profile line that names no file means that same default'
rs_rule "the kit's two steps, copied word for word" \
  '`check sensitive-area map` and `check the agents\.md ceiling`\. offer once to add them to the chosen job, copied word for word'
rs_rule "the type check and linter where the job runs neither" \
  'with the type check and linter from `check-floor\.md` where the job runs neither'
rs_rule "the offer says it changes the project's own automation" \
  'say that this changes the project.s own automation, and what each step turns red on'
rs_rule "a yes adds them at the end and changes nothing else" \
  'on a yes, add them to the end of that job.s steps and change nothing else in the file'
rs_rule "a no adds nothing and marks the line" \
  'on a no, add nothing and append `; kit steps not added` to the profile line'
rs_rule "the completion report says /maintain measures them" \
  'the completion report then says that the ceiling and the map are measured only by `/maintain`'
rs_rule "a Windows runner is not offered the steps" \
  'where the job.s `runs-on` names a windows runner, do not offer them'
rs_guard "$REF" "project-check.md"

# The bootstrap script finds such a workflow and skips checks.yml. The
# rehearsal runs it; these prove the lines it rests on are there.
rs_require_load_bearing "the bootstrap looks for pull_request" "$BOOTSTRAP" 'pull_request'
rs_require_load_bearing "the bootstrap skips checks.yml beside the project's own CI" "$BOOTSTRAP" \
  'checks\.yml\) \[ -z "\$own_ci" \]'

# Founding: the reference, the default record, the recorded job, the resume.
rs_require_load_bearing "founding loads project-check.md" "$SETUP" \
  'load `references/project-check\.md`'
rs_require_load_bearing "founding records the default where it copies checks.yml" "$SETUP" \
  'record `project check: \.github/workflows/checks\.yml, job project-check` in the capability profile'
rs_require_load_bearing "founding configures only the recorded job" "$SETUP" \
  'configure only the job the `project check:` line records'
rs_require_load_bearing "founding leaves a project's own commands alone" "$SETUP" \
  'a job of the project.s own already runs its real commands'
rs_require_load_bearing "the resume check reads the recorded file" "$SETUP" \
  'a placeholder still in the file the capability profile.s `project check:` line records, which is `\.github/workflows/checks\.yml` only where that is the file recorded'

# The capability check names the line and points at its owner.
rs_require_load_bearing "the capability check points at the project check record" "$CAPABILITY" \
  'record the project check as the capability profile.s `project check:` line, as `project-check\.md` says'

# The founded AGENTS.md names the line's form in its profile placeholder.
rs_require_load_bearing "the template names the line's form" "$TEMPLATE" \
  '`project check: <workflow file>, job <job name>`'

# The completion report translates the record and the no.
rs_require_load_bearing "the report says the project's own check stays" "$REPORT" \
  'your project.s own automatic check stays the one that runs on every change'
rs_require_load_bearing "the report says /maintain measures what the steps would" "$REPORT" \
  'so /maintain measures both each month instead'

# Every reader takes the file and job from the record.
POINTER='the capability profile.s `project check:` line records'
rs_require_load_bearing "/sync step 1 reads the recorded workflow" "$SYNC" \
  'list --branch main --workflow <file> --limit 1 --json status,conclusion`, where `<file>` is the name of the workflow file'
rs_require_load_bearing "/sync step 1 finds the last green run in it" "$SYNC" \
  'list --branch main --workflow <file> --status success'
rs_require_load_bearing "/sync step 6 updates the recorded job" "$SYNC" \
  'update the job the capability profile.s `project check:` line records'
rs_require_load_bearing "/sync step 6 asks when the recorded file is gone" "$SYNC" \
  'where the recorded file no longer exists, or no longer has the recorded job, say that the recorded project check no longer exists and ask which workflow is the check now'
rs_require_load_bearing "/sync edits nothing until that is answered" "$SYNC" \
  'edit nothing until that is answered'
rs_require_load_bearing "the check floor sits in the recorded job" "$FLOOR" "$POINTER"
rs_require_load_bearing "the boundary rule sits in the recorded job" "$BOUNDARY" "$POINTER"
rs_require_load_bearing "a run installs from the recorded job" "$LONGER" "$POINTER"

# The index move reads the recorded job, and a no to the kit's steps stands.
awk '/^## Moving the instructions onto the index/{on=1; print; next} on && /^## /{on=0} on' \
  "$MAINTAIN" > "$rs_dir/index-move"
rs_require_load_bearing "the index move looks for the ceiling in the recorded job" "$rs_dir/index-move" \
  'the job the capability profile.s `project check:` line records'
rs_require_load_bearing "the index move respects a no to the kit's steps" "$rs_dir/index-move" \
  'where that line ends `; kit steps not added`'

# No reader names checks.yml or project-check as the only place. The default
# rule, the template's own path and the name of the reference that owns the
# record are the ways either may still appear.
DEFAULT='\(`\.github/workflows/checks\.yml`, job `project-check`, where that line names no file\)'
bare_names() {
  rs_fold "$1" | sed -E "s@$DEFAULT@@g; s@templates/foundation/checks\.yml@@g; s@project-check\.md@@g" |
    grep -oE 'checks\.yml|project-check' || true
}
for reader in "$SYNC" "$FLOOR" "$BOUNDARY" "$LONGER" "$rs_dir/index-move"; do
  name=$(basename "$(dirname "$reader")")/$(basename "$reader")
  [ "$reader" = "$rs_dir/index-move" ] && name="the index move"
  found=$(bare_names "$reader")
  [ -z "$found" ] || rs_fail "$name names $found outside the default rule"
  rs_ok "$name names no bare checks.yml"
done
# The search itself has to be able to fail.
cp "$FLOOR" "$rs_dir/floor-mutant"
echo 'They sit in `jobs.project-check` in `.github/workflows/checks.yml`.' >> "$rs_dir/floor-mutant"
[ -n "$(bare_names "$rs_dir/floor-mutant")" ] || \
  rs_fail "a bare checks.yml added to a reader was not caught"
rs_ok "a bare checks.yml added to a reader is caught"
# And the default rule itself is where every reader says it.
for reader in "$SYNC" "$FLOOR" "$BOUNDARY" "$LONGER" "$rs_dir/index-move"; do
  rs_fold "$reader" | grep -qE "$DEFAULT" || \
    rs_fail "$(basename "$reader") does not give the default rule"
done
rs_ok "every reader gives the default rule"

# /maintain: the offer to a project founded before the record.
rs_reset
rs_rule "the monthly visit runs the offer" \
  '21\. run "recording the project.s own check" below'
rs_rule "only while checks.yml holds the placeholder" \
  'where `\.github/workflows/checks\.yml` no longer holds the kit.s placeholder `install and test` step, say nothing'
rs_rule "a line naming checks.yml is no reason to stop" \
  'a `project check:` line that names `checks\.yml`, or no file, is no reason to stop'
rs_rule "a line naming the other workflow leaves only the removal" \
  'where the line already names that other workflow, the record is done, and the offer below is only the removal of the placeholder'
rs_rule "only beside another workflow that runs tests on pull requests" \
  'where no other workflow in `\.github/workflows/` runs on `pull_request` with a `run:` line containing `test`'
rs_rule "an earlier no stands until the workflows change" \
  'where no commit dated after that line.s date has changed `\.github/workflows/`, the earlier no stands'
rs_rule "the job is chosen as the reference says" \
  'choose the job as the installed `setup-ai-build-kit` skill.s `references/project-check\.md` says'
rs_rule "the offer names three changes, each on its own yes" \
  'offer three changes, each taken only on its own yes'
rs_rule "removing the placeholder is one of them" \
  'remove the placeholder `checks\.yml`, which turns red on every pull request and checks nothing'
rs_rule "the kit's steps change the project's own automation" \
  'saying that this changes the project.s own automation'
rs_rule "the other two only after a yes to the record" \
  'the other two are asked only alongside the record, and happen only after a yes to it'
rs_rule "a no is recorded" \
  '`project-check-declined\|<yyyy-mm-dd>\|<file>`'
rs_rule "the offer returns only when the workflows change" \
  'offers again only when the workflow files change'
rs_guard "$MAINTAIN" "the maintain skill"
rs_require_order "the offer comes before recording the visit" "$MAINTAIN" \
  '^21\. Run "Recording the project' '^22\. Record the visit'

# The maintenance record's header names the declined line. Its lines are
# comments, so a folded line break leaves a `# ` between words.
rs_require_load_bearing "the header names the project-check-declined line" "$RECORD" \
  'project-check-declined (# )?line'

# WORKFLOW.md tells it.
rs_require_load_bearing "WORKFLOW says an adopted project's own CI stays its check" "$WORKFLOW" \
  'where it already runs its tests on every pull request, that automation stays its project check'
rs_require_load_bearing "WORKFLOW says founding adds no failing check beside it" "$WORKFLOW" \
  'adds no failing check beside it'
rs_require_load_bearing "WORKFLOW tells the offer to an older project" "$WORKFLOW" \
  'is offered once to record its own as the check and remove the placeholder'

rs_done
