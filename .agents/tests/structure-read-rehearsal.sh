#!/usr/bin/env sh
# structure-read-rehearsal.sh: run the quarterly structure read against a
# throwaway project whose history holds a visit, an old loop and a new one.
#
# The project's last full visit is dated in its maintenance record, and one loop
# between two files was already there on that date. After it, a second loop is
# added. The read has to derive the earlier structure again from the saved
# history, exactly as the shipped reference says, and name only the new loop,
# at the line where each file imports the other. Then the visit is recorded
# again and the read is run once more, which must say nothing at all.
#
# It also proves the earlier state costs nothing on disk: the project's working
# tree is the same after each read as before it.
#
# The engine is used from PATH when present and otherwise installed into a
# throwaway folder. A machine that can do neither fails here rather than
# skipping, since a rehearsal that passes by never running proves nothing.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
READ="$ROOT/.agents/skills/maintain/references/structure-read.md"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

command -v node >/dev/null 2>&1 || fail "node is needed to run this rehearsal"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

if ! command -v depcruise >/dev/null 2>&1; then
  echo "  depcruise not on PATH, installing it into a throwaway folder"
  mkdir -p "$WORK/engines"
  printf '{"name":"engines","private":true}\n' > "$WORK/engines/package.json"
  (cd "$WORK/engines" && npm install --no-audit --no-fund --silent dependency-cruiser@18) ||
    fail "could not install dependency-cruiser, so the read could not be rehearsed"
  PATH="$WORK/engines/node_modules/.bin:$PATH"
  export PATH
fi

node - "$READ" "$WORK" <<'NODE'
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync, spawnSync } = require('node:child_process');

const [readFile, work] = process.argv.slice(2);
const reference = fs.readFileSync(readFile, 'utf8');

// --- the commands, read from the shipped reference ---------------------------

function quoted(pattern, what) {
  const match = reference.replace(/\s+/g, ' ').match(pattern);
  assert.ok(match, `structure-read.md no longer names ${what}`);
  return match[1];
}
const engine = quoted(/1\. `(depcruise [^`]+)`/, 'its first engine');
const findCommit = quoted(/`(git rev-list -1 --before="<date> 23:59:59" HEAD)`/, 'how it finds the earlier commit');
const copyCommand = quoted(/`(git archive <commit> \| tar -x -C <temporary folder>)`/, 'how it copies the earlier project');
console.log(`  engine: ${engine}`);

// --- the project and its history --------------------------------------------

const project = path.join(work, 'project');
fs.mkdirSync(path.join(project, 'src'), { recursive: true });
const git = (args, date) => execFileSync('git', args, {
  cwd: project, encoding: 'utf8',
  env: {
    ...process.env,
    GIT_AUTHOR_NAME: 'Rehearsal', GIT_AUTHOR_EMAIL: 'rehearsal@example.invalid',
    GIT_COMMITTER_NAME: 'Rehearsal', GIT_COMMITTER_EMAIL: 'rehearsal@example.invalid',
    ...(date ? { GIT_AUTHOR_DATE: date, GIT_COMMITTER_DATE: date } : {}),
  },
}).trim();
const put = (name, lines) => fs.writeFileSync(path.join(project, name), lines.join('\n') + '\n');

git(['init', '-q', '-b', 'main']);
put('src/index.js', [
  "import { placeOrder } from './orders.js';",
  "import { pay } from './payments.js';",
  'placeOrder(); pay();',
]);
// A loop that was already there at the last visit.
put('src/payments.js', ["import { refund } from './refunds.js';", 'export const pay = () => refund;']);
put('src/refunds.js', ["import { pay } from './payments.js';", 'export const refund = () => pay;']);
put('src/orders.js', ['export const placeOrder = () => 1;']);
put('src/invoices.js', ['export const invoice = () => 2;']);
git(['add', '-A']);
git(['commit', '-q', '-m', 'Founding'], '2026-06-01T10:00:00');

// The last full visit, on the day of that commit.
put('.ai-build-kit-maintenance', ['last-light-pass: 2026-06-01', 'last-full-pass: 2026-06-01']);
git(['add', '-A']);
git(['commit', '-q', '-m', 'Record the visit'], '2026-06-01T16:00:00');

// After the visit, orders and invoices start to depend on each other.
put('src/orders.js', [
  '// Orders are placed here.',
  '',
  "import { invoice } from './invoices.js';",
  'export const placeOrder = () => invoice();',
]);
put('src/invoices.js', ["import { placeOrder } from './orders.js';", 'export const invoice = () => placeOrder;']);
git(['add', '-A']);
git(['commit', '-q', '-m', 'Invoice every order'], '2026-08-15T10:00:00');

// --- the read ---------------------------------------------------------------

function tree() {
  return git(['status', '--porcelain', '--untracked-files=all']);
}

function loops(folder) {
  const words = engine.replace('<source folder>', 'src').split(' ');
  const result = spawnSync(words[0], words.slice(1), { cwd: folder, encoding: 'utf8', timeout: 120000 });
  assert.ifError(result.error);
  assert.equal(result.status, 0, `the engine failed: ${result.stderr}`);
  const found = new Map();
  for (const mod of JSON.parse(result.stdout).modules) {
    for (const dep of mod.dependencies) {
      if (!dep.circular) continue;
      const members = [mod.source, ...dep.cycle.map(step => step.name)];
      const key = [...new Set(members)].sort().join(' ');
      if (!found.has(key)) found.set(key, [...new Set(members)]);
    }
  }
  return found;
}

function importLine(from, to) {
  const lines = fs.readFileSync(path.join(project, from), 'utf8').split('\n');
  const target = './' + path.basename(to);
  return lines.findIndex(line => line.includes(`'${target}'`)) + 1;
}

function read() {
  const record = fs.readFileSync(path.join(project, '.ai-build-kit-maintenance'), 'utf8');
  const date = record.match(/^last-full-pass: (\S+)$/m)[1];
  const commit = git(findCommit.replace('<date>', date).replace(/"/g, '').split(' ').slice(1)
    .reduce((args, word) => {
      // Rejoin the date and time the shell would have kept together.
      if (/^\d\d:\d\d:\d\d$/.test(word)) args[args.length - 1] += ' ' + word;
      else args.push(word);
      return args;
    }, []));
  const earlier = fs.mkdtempSync(path.join(work, 'earlier-'));
  const shell = copyCommand.replace('<commit>', commit).replace('<temporary folder>', earlier);
  execFileSync('sh', ['-c', shell], { cwd: project });
  const before = loops(earlier);
  fs.rmSync(earlier, { recursive: true, force: true });

  const said = [];
  for (const [key, members] of loops(project)) {
    if (before.has(key)) continue;
    const [first, second] = members;
    said.push(`Since the last visit, ${first} and ${second} have started to depend on each other, `
      + `at line ${importLine(first, second)} and line ${importLine(second, first)}. `
      + 'A change to either can now break the other.');
  }
  return said;
}

const treeBefore = tree();
const said = read();
console.log(said.map(line => `    ${line}`).join('\n'));

assert.equal(said.length, 1, `expected one new loop, got ${said.length}`);
assert.match(said[0], /src\/(orders|invoices)\.js and src\/(orders|invoices)\.js have started to depend on each other/);
console.log('  ok: the loop added since the last visit is named');
const expected = said[0].startsWith('Since the last visit, src/orders.js')
  ? 'at line 3 and line 1' : 'at line 1 and line 3';
assert.ok(said[0].includes(expected), `the import lines are wrong: ${said[0]}`);
console.log('  ok: each file is named at the line where it imports the other');
assert.ok(!said.some(line => /payments|refunds/.test(line)), 'the loop that was already there was reported as new');
console.log('  ok: the loop that was already there at the last visit is not news');
assert.ok(!said.some(line => /\d\s*%|score|grade/i.test(line)), 'a score reached the report');
console.log('  ok: no score, grade or percentage');
assert.equal(tree(), treeBefore, 'the read left something in the project');
console.log('  ok: the earlier state was read from history and nothing was written into the project');

// The next visit is recorded, and nothing changes after it.
put('.ai-build-kit-maintenance', ['last-light-pass: 2026-09-01', 'last-full-pass: 2026-09-01']);
git(['add', '-A']);
git(['commit', '-q', '-m', 'Record the next visit'], '2026-09-01T10:00:00');
const quiet = read();
assert.deepEqual(quiet, [], `an unchanged project should produce nothing, got: ${quiet.join(' | ')}`);
console.log('  ok: with nothing changed since the last visit, the read says nothing');
assert.equal(tree(), '', 'the second read left something in the project');

console.log('\nstructure-read-rehearsal.sh: the new loop named, an unchanged project silent');
NODE
