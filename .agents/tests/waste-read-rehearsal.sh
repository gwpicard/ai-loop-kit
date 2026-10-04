#!/usr/bin/env sh
# waste-read-rehearsal.sh: run the quarterly waste read against a throwaway
# project with one known copy, one unused export and one unused dependency,
# and read back that all three are named with a real file and line, that a
# clean project produces nothing, and that nothing was written into either.
#
# The commands come out of the shipped reference's table, so a table naming a
# command that does not work fails here. The findings are then checked the way
# the reference says: each needs a real line, and a name found anywhere else in
# the project is dropped. The project carries a decoy for that rule, an export
# the engine calls unused that a configuration file names.
#
# The engines are used from PATH when present and otherwise installed into a
# throwaway folder. A machine that can do neither fails here rather than
# skipping, since a rehearsal that passes by never running proves nothing.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
READ="$ROOT/.agents/skills/maintain/references/waste-read.md"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

command -v node >/dev/null 2>&1 || fail "node is needed to run this rehearsal"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

if ! command -v knip >/dev/null 2>&1 || ! command -v jscpd >/dev/null 2>&1; then
  echo "  knip or jscpd not on PATH, installing both into a throwaway folder"
  mkdir -p "$WORK/engines"
  printf '{"name":"engines","private":true}\n' > "$WORK/engines/package.json"
  (cd "$WORK/engines" && npm install --no-audit --no-fund --silent knip@6 jscpd@5) ||
    fail "could not install knip and jscpd, so the read could not be rehearsed"
  PATH="$WORK/engines/node_modules/.bin:$PATH"
  export PATH
fi

node - "$READ" "$WORK" <<'NODE'
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const [readFile, work] = process.argv.slice(2);

// --- the commands, read from the shipped table ------------------------------

const table = fs.readFileSync(readFile, 'utf8');
function command(row) {
  const line = table.split('\n').find(l => l.startsWith(`| ${row} |`));
  assert.ok(line, `waste-read.md has no "${row}" row`);
  const cell = line.split('|')[2];
  const match = cell.match(/`([^`]+)`/);
  assert.ok(match, `the "${row}" row names no JavaScript command`);
  return match[1];
}
const copied = command('Copied code');
const unusedCode = command('Unused code');
const unusedDeps = command('Unused dependencies');
console.log(`  copied code: ${copied}`);
console.log(`  unused code: ${unusedCode}`);
console.log(`  unused dependencies: ${unusedDeps}`);

// --- the project --------------------------------------------------------------

const block = name => [
  `export function ${name}(items) {`,
  '  let sum = 0;',
  '  for (const item of items) {',
  '    if (item.quantity > 0 && item.price > 0) {',
  '      sum += item.quantity * item.price;',
  '    } else {',
  "      console.warn('skipping an empty line', item.name);",
  '    }',
  '  }',
  '  return Math.round(sum * 100) / 100;',
  '}',
].join('\n');

function write(dir, files) {
  fs.rmSync(dir, { recursive: true, force: true });
  for (const [name, text] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(dir, name)), { recursive: true });
    fs.writeFileSync(path.join(dir, name), text);
  }
}

function listing(dir) {
  const out = [];
  (function walk(d) {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) walk(full);
      else out.push(path.relative(dir, full) + ':' + fs.statSync(full).size);
    }
  })(dir);
  return out.sort().join('\n');
}

const wasteful = {
  'package.json': JSON.stringify({
    name: 'shop', private: true, type: 'module', main: 'src/index.js',
    dependencies: { 'left-pad': '1.3.0' },
  }, null, 2) + '\n',
  'routes.json': JSON.stringify({ '/orders': 'handleOrders' }, null, 2) + '\n',
  'src/index.js': [
    "import { total } from './pricing.js';",
    "import { reportTotal } from './report.js';",
    "import { handleOrders } from './handlers.js';",
    'console.log(total([]), reportTotal([]), handleOrders);',
    '',
  ].join('\n'),
  // The copy has different names, which is what a pasted and renamed block
  // looks like, so only the ignore-identifiers setting can find it.
  'src/pricing.js': block('total') + '\n\nexport function discount(price) {\n  return price * 0.9;\n}\n',
  'src/report.js': block('reportTotal')
    .replace(/\bsum\b/g, 'running').replace(/\bitem\b/g, 'line') + '\n',
  // Reached through routes.json by name, which no engine sees.
  'src/handlers.js': "export function handleOrders() {\n  return 'orders';\n}\n\nexport function handleRefunds() {\n  return 'refunds';\n}\n",
};

// The clean project: no copy, nothing unused, no unused dependency.
const clean = {
  'package.json': JSON.stringify({
    name: 'shop', private: true, type: 'module', main: 'src/index.js',
  }, null, 2) + '\n',
  'src/index.js': "import { total } from './pricing.js';\nconsole.log(total([]));\n",
  'src/pricing.js': block('total') + '\n',
};

// --- the read ---------------------------------------------------------------

function run(dir, line) {
  const report = path.join(work, 'jscpd-report');
  const words = line.replace('<temporary folder>', report).split(' ');
  const result = spawnSync(words[0], words.slice(1), { cwd: dir, encoding: 'utf8', timeout: 120000 });
  assert.ifError(result.error);
  if (words[0] === 'jscpd') {
    const json = JSON.parse(fs.readFileSync(path.join(report, 'jscpd-report.json'), 'utf8'));
    fs.rmSync(report, { recursive: true, force: true });
    return json;
  }
  return JSON.parse(result.stdout);
}

function lineOf(file, text) {
  const lines = fs.readFileSync(file, 'utf8').split('\n');
  const index = lines.findIndex(l => l.includes(text));
  return index + 1;
}

// A name found anywhere other than its own definition is dropped, the rule the
// reference calls searching the whole project for the name.
function usedElsewhere(dir, name, definedIn) {
  const needle = new RegExp(`\\b${name}\\b`);
  const files = listing(dir).split('\n').map(l => l.split(':')[0]);
  return files.some(file => {
    if (file === definedIn) return false;
    return needle.test(fs.readFileSync(path.join(dir, file), 'utf8'));
  });
}

function read(dir) {
  const findings = [];
  for (const clone of run(dir, copied).duplicates) {
    findings.push({
      kind: 'copied code',
      file: clone.firstFile.name, line: clone.firstFile.start,
      other: `${clone.secondFile.name} at line ${clone.secondFile.start}`,
    });
  }
  for (const issue of run(dir, unusedCode).issues) {
    for (const item of issue.exports) {
      if (usedElsewhere(dir, item.name, issue.file)) continue;
      findings.push({ kind: 'unused export', file: issue.file, line: item.line, name: item.name });
    }
    for (const item of issue.files || []) {
      findings.push({ kind: 'unused file', file: item.name || issue.file, line: 1 });
    }
  }
  for (const issue of run(dir, unusedDeps).issues) {
    for (const item of issue.dependencies) {
      if (usedElsewhere(dir, item.name, issue.file)) continue;
      findings.push({
        kind: 'unused dependency', file: issue.file, name: item.name,
        line: lineOf(path.join(dir, issue.file), `"${item.name}"`),
      });
    }
  }
  // Every finding has to point at a line that exists.
  for (const f of findings) {
    const lines = fs.readFileSync(path.join(dir, f.file), 'utf8').split('\n');
    assert.ok(f.line >= 1 && f.line <= lines.length, `${f.file} has no line ${f.line}`);
  }
  return findings.map(f => {
    switch (f.kind) {
      case 'copied code': return `The same code is written twice, in ${f.file} at line ${f.line} and ${f.other}.`;
      case 'unused export': return `${f.name} in ${f.file} at line ${f.line} is never used.`;
      case 'unused file': return `${f.file} is never used.`;
      default: return `The project lists ${f.name} as something it needs, at ${f.file} line ${f.line}, and nothing uses it.`;
    }
  });
}

// --- the wasteful project -----------------------------------------------------

const project = path.join(work, 'project');
write(project, wasteful);
const before = listing(project);
const said = read(project);
console.log(said.map(s => `    ${s}`).join('\n'));

assert.ok(said.some(s => /written twice, in src\/(pricing|report)\.js at line 1 and src\/(pricing|report)\.js at line 1/.test(s)),
  'the renamed copy was not named with both places');
console.log('  ok: the renamed copy is named with both files and lines');
assert.ok(said.includes('discount in src/pricing.js at line 13 is never used.'),
  'the unused export was not named at its line');
console.log('  ok: the unused export is named at its line');
assert.ok(said.some(s => /lists left-pad .* at package\.json line \d+, and nothing uses it/.test(s)),
  'the unused dependency was not named with its line');
console.log('  ok: the unused dependency is named with its line in the package file');
assert.ok(!said.some(s => s.includes('handleOrders')), 'the export a configuration file names was not dropped');
assert.ok(said.some(s => s.includes('handleRefunds')), 'a genuinely unused export beside the decoy was lost');
console.log('  ok: an export named in a configuration file is dropped, its unused neighbour is kept');
assert.ok(!said.some(s => /\d\s*%|percent/i.test(s)), 'a percentage reached the report');
console.log('  ok: no percentage reaches the report');
assert.equal(listing(project), before, 'the read wrote something into the project');
console.log('  ok: nothing was written into the project');

// --- the clean project ------------------------------------------------------

write(project, clean);
const cleanBefore = listing(project);
const cleanSaid = read(project);
assert.deepEqual(cleanSaid, [], `a clean project should produce nothing, got: ${cleanSaid.join(' | ')}`);
console.log('  ok: a clean project produces nothing to say');
assert.equal(listing(project), cleanBefore, 'the read wrote something into the clean project');
console.log('  ok: nothing was written into the clean project');

console.log('\nwaste-read-rehearsal.sh: all three kinds named, clean project silent');
NODE
