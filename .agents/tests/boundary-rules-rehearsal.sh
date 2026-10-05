#!/usr/bin/env sh
# boundary-rules-rehearsal.sh: found a throwaway Build with care project with a
# named area, hold its boundary in the project check, and watch the check go
# red on an import that crosses it and green once the import is gone. The
# boundary line sits under its area in the project's area map, the Areas
# section of docs/working-rules.md, and the area points at the masterplan's
# sensitive area by name.
#
# Everything the rule is made from comes out of shipped files. The boundary
# line, with the person's sentence recorded on it, is written in the shape the
# reference gives. The configuration is the reference's own template, filled
# from that line. The command is the reference's table row. The workflow starts
# from the shipped template. So a template that cannot produce a working rule,
# or a recorded line the template cannot be filled from, fails here.
#
# The red check has to carry the person's sentence word for word, since that
# is the whole reason the rule reads as theirs rather than as tool output.
#
# The engine is used from PATH when present and otherwise installed into a
# throwaway folder. A machine that can do neither fails here rather than
# skipping, since a rehearsal that passes by never running proves nothing.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
RULES="$ROOT/.agents/skills/setup-ai-build-kit/references/boundary-rules.md"
FOUNDATION="$ROOT/.agents/skills/setup-ai-build-kit/templates/foundation"

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
    fail "could not install dependency-cruiser, so the rule could not be rehearsed"
  PATH="$WORK/engines/node_modules/.bin:$PATH"
  export PATH
fi

node - "$RULES" "$FOUNDATION" "$WORK" <<'NODE'
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const [rulesFile, foundation, work] = process.argv.slice(2);
const rules = fs.readFileSync(rulesFile, 'utf8');

// --- what the reference ships -------------------------------------------------

const recorded = rules.match(/```md\n(\s+boundary: .+)\n```/);
assert.ok(recorded, 'boundary-rules.md no longer shows a recorded boundary line');
const template = rules.match(/```js\n([\s\S]+?)\n```/);
assert.ok(template, 'boundary-rules.md no longer carries a configuration template');
const row = rules.split('\n').find(l => l.startsWith('| JavaScript and TypeScript |'));
assert.ok(row, 'boundary-rules.md has no JavaScript row');
// A founded project has the engine as its own dependency, so `npx` finds it
// there. Here it is on PATH instead, so the command runs without it.
const checkCommand = row.split('|')[3].match(/`([^`]+)`/)[1]
  .replace(/^npx /, '').replace('<source folder>', 'src');
console.log(`  check command: ${checkCommand}`);

// --- founding: the project, its masterplan, its area map, its held boundary --

const project = path.join(work, 'project');
const put = (name, text) => {
  fs.mkdirSync(path.dirname(path.join(project, name)), { recursive: true });
  fs.writeFileSync(path.join(project, name), text);
};

// The recorded line from the reference, pointed at this project's files.
const boundaryLine = recorded[1].replace('src/billing/charge.ts', 'src/billing/charge.js');
put('masterplan.md', [
  '# Masterplan', '', '## Build path', '',
  'Path: Build with care',
  'Sensitive areas:',
  '  money: the refund button; caution: the owner checks the first refunds; not yet done',
  '',
].join('\n'));
put('docs/working-rules.md', [
  '# Working rules', '', '## Areas', '',
  '- billing: src/billing/',
  '  sensitive: money',
  boundaryLine,
  '- reports: src/reports/, src/index.js',
  '- project records: docs/',
  '',
].join('\n'));

put('src/billing/charge.js', "import { ledger } from './ledger.js';\nexport const charge = () => ledger;\n");
put('src/billing/ledger.js', 'export const ledger = [];\n');
put('src/reports/sum.js', "import { charge } from '../billing/charge.js';\nexport const sum = () => charge();\n");
put('src/index.js', "import { sum } from './reports/sum.js';\nsum();\n");

// Fill the template from what the area map records.
const map = fs.readFileSync(path.join(project, 'docs/working-rules.md'), 'utf8');
const [, area, folder] = map.match(/^- (\w[\w ]*): (\S+)$/m);
const held = map.match(/^\s+boundary: reached only through (\S+); held by the check: "(.+)"$/m);
assert.ok(held, 'the recorded boundary line could not be read back');
const [, entry, sentence] = held;
const asPattern = p => p.replace(/\./g, '[.]');
const config = template[1]
  .replace('<area>', area)
  .replace("<the person\\'s sentence>", sentence.replace(/'/g, "\\'"))
  .replace(/<area folder>/g, asPattern(folder))
  .replace('<entry file>', asPattern(entry));
assert.ok(!/<[a-z ]+>/.test(config), `a placeholder was left in the configuration:\n${config}`);
put('.dependency-cruiser.cjs', config + '\n');

// The workflow founding writes: the placeholder goes, the boundary step comes in.
const workflow = fs.readFileSync(path.join(foundation, 'checks.yml'), 'utf8')
  .replace(/      - name: Install and test[\s\S]*$/, [
    '      - name: Boundary rules',
    `        run: ${checkCommand}`,
    '',
  ].join('\n'));
put('.github/workflows/checks.yml', workflow);
put('.agents/tools/area-map.py', fs.readFileSync(path.join(foundation, 'area-map.py'), 'utf8'));
put('AGENTS.md', fs.readFileSync(path.join(foundation, 'AGENTS.md'), 'utf8'));

// The area map step reads the folders Git tracks, so the project is a
// repository with its files in Git's index, as founding leaves it.
for (const args of [['init', '-q'], ['add', '-A']]) {
  const git = spawnSync('git', args, { cwd: project, encoding: 'utf8' });
  assert.equal(git.status, 0, `git ${args.join(' ')} failed: ${git.stderr}`);
}

// --- running the check the way the hosted runner would ----------------------

function runCheck() {
  const steps = [];
  let name = null;
  for (const line of fs.readFileSync(path.join(project, '.github/workflows/checks.yml'), 'utf8').split('\n')) {
    const n = line.match(/^ *- name: (.+)$/);
    if (n) { name = n[1]; continue; }
    const r = line.match(/^ *run: (.+)$/);
    if (r) steps.push([name, r[1]]);
  }
  for (const [step, command] of steps) {
    const result = spawnSync('sh', ['-c', command], { cwd: project, encoding: 'utf8', timeout: 120000 });
    assert.ifError(result.error);
    if (result.status !== 0) return { step, output: result.stdout + result.stderr };
  }
  return { step: null, output: '' };
}

let result = runCheck();
assert.equal(result.step, null, `the check was red on the day the rule was added, at ${result.step}:\n${result.output}`);
console.log('  ok: the rule passes on the project as it stands');

// A change reaches the ledger without going through the charge step.
put('src/reports/sum.js', "import { ledger } from '../billing/ledger.js';\nexport const sum = () => ledger.length;\n");
result = runCheck();
assert.equal(result.step, 'Boundary rules', `expected the Boundary rules step to go red, got '${result.step}'`);
console.log('  ok: an import that crosses the boundary turns the check red at Boundary rules');
assert.ok(result.output.includes(sentence), `the red check did not carry the person's sentence:\n${result.output}`);
console.log(`  ok: the red check carries the person's sentence: "${sentence}"`);
assert.ok(result.output.includes('src/reports/sum.js'), 'the red check did not name the importing file');
console.log('  ok: the red check names the file that crossed it');
assert.ok(!/\d\s*%|score|grade/i.test(result.output), 'a score reached the output');
console.log('  ok: no score, grade or percentage');

put('src/reports/sum.js', "import { charge } from '../billing/charge.js';\nexport const sum = () => charge();\n");
result = runCheck();
assert.equal(result.step, null, `the check stayed red once the import was gone, at ${result.step}`);
console.log('  ok: the check goes green once the crossing import is gone');

console.log('\nboundary-rules-rehearsal.sh: red on a crossing import, with the person\'s sentence, green once it is gone');
NODE
