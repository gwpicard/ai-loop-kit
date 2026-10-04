#!/usr/bin/env sh
# trim-rehearsal.sh: run the trim against a throwaway project and read back
# what it did.
#
# The project starts from a saved commit, then a piece is built on top of it
# carrying one of everything the trim is meant to handle: a wrapper with one
# user and a test behind it, an export nothing calls, a dependency nothing
# imports, a wrapper with one user and no test, a dependency used once, a
# copied block, and a new function past the limit. Two things sit beside those
# that the trim must leave alone: an unused export that was there before the
# piece, and an old function already past the limit that the piece changed
# without making worse. One decoy is there to be got wrong: a file reached only
# through a path built at run time, which the engine calls unused and a search
# for its name cannot find. Removing it breaks a test, and the trim has to undo
# the removal rather than touch the test.
#
# The commands come from the shipped table and the line the person reads comes
# from the shipped fixed shape, so a table naming a command that does not work,
# or a line reworded in one place and not the other, fails here. The uses of a
# name are counted by reading the code directly, the last entry in the reach
# check's order, since no language server runs in a shell rehearsal.
#
# The engines are used from PATH when present and otherwise installed into a
# throwaway folder. A machine that can do neither fails here rather than
# skipping, since a rehearsal that passes by never running proves nothing.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TRIM="$ROOT/.agents/skills/section-builder/references/trim.md"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

command -v node >/dev/null 2>&1 || fail "node is needed to run this rehearsal"
command -v git >/dev/null 2>&1 || fail "git is needed to run this rehearsal"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

if ! command -v knip >/dev/null 2>&1 || ! command -v jscpd >/dev/null 2>&1; then
  echo "  knip or jscpd not on PATH, installing both into a throwaway folder"
  mkdir -p "$WORK/engines"
  printf '{"name":"engines","private":true}\n' > "$WORK/engines/package.json"
  (cd "$WORK/engines" && npm install --no-audit --no-fund --silent knip@6 jscpd@5) ||
    fail "could not install knip and jscpd, so the trim could not be rehearsed"
  PATH="$WORK/engines/node_modules/.bin:$PATH"
  export PATH
fi

if ! command -v lizard >/dev/null 2>&1; then
  command -v python3 >/dev/null 2>&1 || fail "python3 is needed to install lizard"
  echo "  lizard not on PATH, installing it into a throwaway folder"
  python3 -m venv "$WORK/lizard" && "$WORK/lizard/bin/pip" install -q 'lizard>=1.24,<2' ||
    fail "could not install lizard, so the trim could not be rehearsed"
  PATH="$WORK/lizard/bin:$PATH"
  export PATH
fi

node - "$TRIM" "$WORK" <<'NODE'
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const [trimFile, work] = process.argv.slice(2);
const shipped = fs.readFileSync(trimFile, 'utf8');

// --- the commands and the fixed line, read from the shipped reference -------

function command(row) {
  const line = shipped.split('\n').find(l => l.startsWith(`| ${row} |`));
  assert.ok(line, `trim.md has no "${row}" row`);
  const match = line.split('|')[2].match(/`([^`]+)`/);
  assert.ok(match, `the "${row}" row names no JavaScript command`);
  return match[1];
}
const unusedCode = command('Unused code');
const unusedDeps = command('Unused dependencies');
const copied = command('Copied code');
const limit = command('Function limit');
console.log(`  unused code: ${unusedCode}`);
console.log(`  unused dependencies: ${unusedDeps}`);
console.log(`  copied code: ${copied}`);
console.log(`  function limit: ${limit}`);
const limitValue = Number(limit.match(/--CCN (\d+)/)[1]);

const folded = shipped.replace(/\s+/g, ' ');
const tookOut = folded.match(/"(I took out <count> things this change did not need\. They are listed on the piece\.)"/);
assert.ok(tookOut, 'trim.md has lost its fixed line');
const alsoReported = folded.match(/add "(<count> more could be simpler, and are listed there too\.)"/);
assert.ok(alsoReported, 'trim.md has lost the line for what is only reported');

// --- a throwaway repository -------------------------------------------------

function sh(dir, cmd, args, allowFail = false) {
  const result = spawnSync(cmd, args, { cwd: dir, encoding: 'utf8', timeout: 180000 });
  assert.ifError(result.error);
  if (!allowFail && result.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} failed:\n${result.stdout}${result.stderr}`);
  }
  return result;
}
const git = (dir, ...args) => sh(dir, 'git', ['-c', 'user.name=Rehearsal',
  '-c', 'user.email=rehearsal@example.invalid', '-c', 'commit.gpgsign=false', ...args]).stdout.trim();

function write(dir, files) {
  for (const [name, text] of Object.entries(files)) {
    const full = path.join(dir, name);
    if (text === null) { fs.rmSync(full, { force: true }); continue; }
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, text);
  }
}

function projectFiles(dir) {
  const out = [];
  (function walk(d) {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      if (entry.name === 'node_modules' || entry.name === '.git') continue;
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) walk(full);
      else out.push(path.relative(dir, full));
    }
  })(dir);
  return out.sort();
}

const hashOf = (dir, files) => crypto.createHash('sha256')
  .update(files.map(f => f + '\0' + fs.readFileSync(path.join(dir, f), 'utf8')).join('\0')).digest('hex');
const testsPass = dir => sh(dir, 'node', ['--test'], true).status === 0;
const pkg = extra => JSON.stringify({
  name: 'shop', private: true, type: 'module', main: 'src/index.js',
  scripts: { test: 'node --test' }, ...extra,
}, null, 2) + '\n';

// A function past the limit: one path per test, plus the one through the end.
const branchy = (name, returns) => [
  `export function ${name}(value) {`,
  ...Array.from({ length: limitValue + 1 }, (_, i) =>
    `  if (value === ${i}) return '${returns}${i}';`),
  `  return '${returns}';`,
  '}',
].join('\n') + '\n';

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
].join('\n') + '\n';

const test = (file, name, body) => ({
  [file]: `import { test } from 'node:test';\nimport assert from 'node:assert/strict';\n${body}\ntest('${name}', ${name === 'refund' ? 'async ' : ''}() => {\n  ${
    { total: "assert.equal(total([{ quantity: 2, price: 1.5 }]), 3);",
      grade: "assert.equal(grade(3), 'grade3');",
      label: "assert.equal(totalLabel([{ quantity: 2, price: 1.5 }]), '3.00');",
      refund: "assert.equal(await dispatch('refund', 'order'), 'refunded');",
      risk: "assert.equal(risk(2), 'risk2');",
      tax: 'assert.equal(tax(10), 2);' }[name]}\n});\n`,
});

// The project before the piece: one unused export and one function already
// past the limit, both there before anybody started.
const start = {
  '.gitignore': 'node_modules/\n',
  'package.json': pkg({}),
  'src/index.js': "import { total } from './pricing.js';\nimport { grade } from './grade.js';\nconsole.log(total([]), grade(1));\n",
  'src/pricing.js': block('total') + '\nexport function legacyRound(value) {\n  return Math.round(value);\n}\n',
  'src/grade.js': branchy('grade', 'grade'),
  ...test('test/pricing.test.js', 'total', "import { total } from '../src/pricing.js';"),
  ...test('test/grade.test.js', 'grade', "import { grade } from '../src/grade.js';"),
};

// The piece as built.
const piece = {
  'package.json': pkg({ dependencies: { 'left-pad': '1.3.0', 'tiny-words': '1.0.0' } }),
  'node_modules/tiny-words/package.json': '{"name":"tiny-words","version":"1.0.0","type":"module","main":"index.js"}\n',
  'node_modules/tiny-words/index.js': 'export function toWords(n) {\n  return String(n);\n}\n',
  'src/index.js': [
    "import { total, totalLabel } from './pricing.js';",
    "import { grade } from './grade.js';",
    "import { reportTotal } from './report.js';",
    "import { amountInWords } from './words.js';",
    "import { printTotal } from './cli.js';",
    "import { dispatch } from './dispatch.js';",
    "import { risk } from './risk.js';",
    "console.log(total([]), totalLabel([]), grade(1), reportTotal([]), amountInWords(2), risk(1));",
    'printTotal([]);',
    "console.log(await dispatch('refund', 'order'));",
    '',
  ].join('\n'),
  // A wrapper with one user, which a test runs: folded.
  'src/format.js': 'export function formatMoney(value) {\n  return value.toFixed(2);\n}\n',
  // An export nothing calls: removed. totalLabel is a wrapper too, but with
  // two users, so it stays.
  'src/pricing.js': "import { formatMoney } from './format.js';\n\n" + block('total') +
    '\nexport function legacyRound(value) {\n  return Math.round(value);\n}\n' +
    '\nexport function totalLabel(items) {\n  return formatMoney(total(items));\n}\n' +
    '\nexport function legacyTotal(items) {\n  return items.length;\n}\n',
  // The old function past the limit, changed without adding a path.
  'src/grade.js': branchy('grade', 'grade').replace("return 'grade';", "return 'ungraded';"),
  // A copy of an existing block with its names changed: reported only.
  'src/report.js': block('reportTotal').replace(/\bsum\b/g, 'running').replace(/\bitem\b/g, 'line'),
  // A dependency used once: reported only.
  'src/words.js': "import { toWords } from 'tiny-words';\n\nexport function amountInWords(n) {\n  const words = toWords(n);\n  return words.toUpperCase();\n}\n",
  // A wrapper with one user and no test: reported, not folded.
  'src/cli.js': "import { total } from './pricing.js';\n\nexport function pad(label) {\n  return label.padStart(12);\n}\n\nexport function printTotal(items) {\n  const text = String(total(items));\n  console.log(pad(text));\n}\n",
  // The decoy: reached only through a path built at run time.
  'src/dispatch.js': 'export async function dispatch(action, thing) {\n  const handler = await import(`./handlers/${action}-${thing}.js`);\n  return handler.run();\n}\n',
  'src/handlers/refund-order.js': "export function run() {\n  return 'refunded';\n}\n",
  // A new function past the limit: reported only.
  'src/risk.js': branchy('risk', 'risk'),
  ...test('test/label.test.js', 'label', "import { totalLabel } from '../src/pricing.js';"),
  ...test('test/dispatch.test.js', 'refund', "import { dispatch } from '../src/dispatch.js';"),
  ...test('test/risk.test.js', 'risk', "import { risk } from '../src/risk.js';"),
};

// --- reading the change -----------------------------------------------------

// Lines this change added or changed, per file, from the saved difference.
function changedLines(dir, base) {
  const out = {};
  let file = null;
  for (const line of git(dir, 'diff', '-U0', base, '--', '.').split('\n')) {
    if (line.startsWith('+++ ')) {
      file = line === '+++ /dev/null' ? null : line.slice(6);
      if (file) out[file] = new Set();
    }
    const hunk = line.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@/);
    if (hunk && file) {
      const from = Number(hunk[1]);
      const count = hunk[2] === undefined ? 1 : Number(hunk[2]);
      for (let n = from; n < from + count; n++) out[file].add(n);
    }
  }
  return out;
}

const read = (dir, file) => fs.readFileSync(path.join(dir, file), 'utf8');
const exists = (dir, file) => fs.existsSync(path.join(dir, file));
const sourceFiles = dir => projectFiles(dir).filter(f => f.endsWith('.js'));

// The function starting at a line, as its lines and its body.
function functionAt(text, startLine) {
  const lines = text.split('\n');
  let end = startLine - 1;
  while (end < lines.length && lines[end] !== '}') end++;
  return { from: startLine, to: end + 1, body: lines.slice(startLine, end).map(l => l.trim()) };
}

// Whole-name uses of a name, by reading the code, outside the lines given. A
// hyphen does not end a name here, so pad is not found inside left-pad.
function usesOf(dir, name, except) {
  const needle = new RegExp(`(?<![\\w$-])${name.replace(/[-.$]/g, '\\$&')}(?![\\w$-])`);
  const uses = [];
  for (const file of projectFiles(dir)) {
    read(dir, file).split('\n').forEach((text, i) => {
      if (except(file, i + 1, text)) return;
      if (/^\s*import\b/.test(text)) return;
      if (needle.test(text)) uses.push({ file, line: i + 1 });
    });
  }
  return uses;
}

// A test runs a file when a test file imports it, the reach check's last resort.
const testedFiles = dir => new Set(projectFiles(dir).filter(f => f.startsWith('test/'))
  .flatMap(f => [...read(dir, f).matchAll(/from '\.\.\/(src\/[^']+)'/g)].map(m => m[1])));

function runEngine(dir, line) {
  const report = path.join(work, 'jscpd-report');
  const words = line.replace('<temporary folder>', report).split(' ');
  const result = sh(dir, words[0], words.slice(1), true);
  if (words[0] === 'jscpd') {
    const json = JSON.parse(fs.readFileSync(path.join(report, 'jscpd-report.json'), 'utf8'));
    fs.rmSync(report, { recursive: true, force: true });
    return json;
  }
  return JSON.parse(result.stdout);
}

// lizard's figures for each function in the named files, keyed by name.
function complexity(dir, files) {
  if (!files.length) return {};
  const [cmd, ...rest] = limit.replace('<changed files>', files.join(' ')).split(' ');
  const out = {};
  for (const row of sh(dir, cmd, rest).stdout.trim().split('\n').filter(Boolean)) {
    const cells = row.split(',');
    out[`${cells[6].replace(/"/g, '')}:${cells[7].replace(/"/g, '')}`] =
      { ccn: Number(cells[1]), from: Number(cells[9]), to: Number(cells[10]) };
  }
  return out;
}

// --- the list ---------------------------------------------------------------

function gather(dir, base) {
  const changed = changedLines(dir, base);
  const isChanged = (file, line) => Boolean(changed[file] && changed[file].has(line));
  const edits = [];
  const reports = [];

  // 1. Unused, with the second look: a name found anywhere outside its own
  // definition is dropped.
  for (const issue of runEngine(dir, unusedCode).issues) {
    for (const item of issue.exports) {
      if (!isChanged(issue.file, item.line)) continue;
      const own = functionAt(read(dir, issue.file), item.line);
      const elsewhere = usesOf(dir, item.name, (f, n) => f === issue.file && n >= own.from && n <= own.to);
      if (elsewhere.length) continue;
      edits.push({ kind: 'unused export', file: issue.file, line: item.line, name: item.name });
    }
    for (const item of issue.files || []) {
      if (!changed[item.name]) continue;
      const name = path.basename(item.name, '.js');
      if (usesOf(dir, name, f => f === item.name).length) continue;
      edits.push({ kind: 'unused file', file: item.name, line: 1, name });
    }
  }
  for (const issue of runEngine(dir, unusedDeps).issues) {
    for (const item of issue.dependencies) {
      if (!isChanged(issue.file, item.line)) continue;
      if (usesOf(dir, item.name, f => f === issue.file).length) continue;
      edits.push({ kind: 'unused dependency', file: issue.file, line: item.line, name: item.name });
    }
  }

  // 3. One user: a wrapper this change added that one place uses.
  const tested = testedFiles(dir);
  for (const file of sourceFiles(dir)) {
    read(dir, file).split('\n').forEach((text, i) => {
      const def = text.match(/^export function (\w+)\((\w+)\) \{$/);
      if (!def || !isChanged(file, i + 1)) return;
      const fn = functionAt(read(dir, file), i + 1);
      if (fn.body.length !== 1 || !fn.body[0].startsWith('return ')) return;
      const users = usesOf(dir, def[1], (f, n) => f === file && n >= fn.from && n <= fn.to);
      if (users.length !== 1) return;
      const user = users[0];
      const found = { kind: 'one user', file, line: i + 1, name: def[1], param: def[2],
        expr: fn.body[0].replace(/^return /, '').replace(/;$/, ''), user };
      if (tested.has(user.file)) edits.push(found);
      else reports.push({ ...found, kind: 'untested fold' });
    });
  }

  // 4. A dependency this change added that one file uses.
  const deps = JSON.parse(read(dir, 'package.json')).dependencies || {};
  for (const name of Object.keys(deps)) {
    const line = read(dir, 'package.json').split('\n').findIndex(l => l.includes(`"${name}"`)) + 1;
    if (!isChanged('package.json', line)) continue;
    const importers = sourceFiles(dir).filter(f => read(dir, f).includes(`from '${name}'`));
    if (importers.length === 1) reports.push({ kind: 'one-use dependency', file: 'package.json', line, name, user: importers[0] });
  }

  // 5. A copied block on lines this change added.
  for (const clone of runEngine(dir, copied).duplicates) {
    for (const [mine, theirs] of [[clone.firstFile, clone.secondFile], [clone.secondFile, clone.firstFile]]) {
      if (!isChanged(mine.name, mine.start)) continue;
      reports.push({ kind: 'copy', file: mine.name, line: mine.start, other: `${theirs.name} at line ${theirs.start}` });
      break;
    }
  }

  // 6. A function past the limit, and an old one only when this change raised it.
  const touched = sourceFiles(dir).filter(f => changed[f] && !f.startsWith('test/'));
  const now = complexity(dir, touched);
  const before = {};
  const old = path.join(work, 'before');
  fs.mkdirSync(old, { recursive: true });
  for (const file of touched) {
    const shown = sh(dir, 'git', ['show', `${base}:${file}`], true);
    if (shown.status !== 0) continue;
    fs.mkdirSync(path.dirname(path.join(old, file)), { recursive: true });
    fs.writeFileSync(path.join(old, file), shown.stdout);
    Object.assign(before, complexity(old, [file]));
  }
  fs.rmSync(old, { recursive: true, force: true });
  for (const [key, fn] of Object.entries(now)) {
    if (fn.ccn <= limitValue) continue;
    const [file, name] = key.split(':');
    if (![...Array(fn.to - fn.from + 1)].some((_, k) => isChanged(file, fn.from + k))) continue;
    if (before[key] && fn.ccn <= before[key].ccn) continue;
    reports.push({ kind: 'over the limit', file, line: fn.from, name, isNew: !before[key] });
  }

  return { edits, reports };
}

// --- the edits the trim may make: remove, and fold ----------------------------

function removeFunction(dir, file, line) {
  const text = read(dir, file);
  const fn = functionAt(text, line);
  const lines = text.split('\n');
  lines.splice(fn.from - 1, fn.to - fn.from + 1 + (lines[fn.to] === '' ? 1 : 0));
  const rest = lines.join('\n').replace(/\n+$/, '\n');
  if (!/\bfunction\b/.test(rest)) fs.rmSync(path.join(dir, file));
  else fs.writeFileSync(path.join(dir, file), rest);
}

function argumentAt(text, from) {
  let depth = 0;
  for (let i = from; i < text.length; i++) {
    if (text[i] === '(') depth++;
    if (text[i] === ')') { if (depth === 0) return text.slice(from, i); depth--; }
  }
  throw new Error('unbalanced call');
}

function apply(dir, edit) {
  switch (edit.kind) {
    case 'unused export': return removeFunction(dir, edit.file, edit.line);
    case 'unused file': return fs.rmSync(path.join(dir, edit.file));
    case 'unused dependency': {
      const json = JSON.parse(read(dir, 'package.json'));
      delete json.dependencies[edit.name];
      return fs.writeFileSync(path.join(dir, 'package.json'), JSON.stringify(json, null, 2) + '\n');
    }
    case 'one user': {
      let text = read(dir, edit.user.file);
      const call = text.indexOf(`${edit.name}(`);
      const arg = argumentAt(text, call + edit.name.length + 1);
      const body = edit.expr.replace(new RegExp(`\\b${edit.param}\\b`, 'g'), `(${arg})`);
      text = text.slice(0, call) + body + text.slice(call + edit.name.length + arg.length + 2);
      text = text.split('\n').filter(l => !new RegExp(`^import \\{ ${edit.name} \\} from`).test(l)).join('\n')
        .replace(/^\n+/, '');
      fs.writeFileSync(path.join(dir, edit.user.file), text);
      return removeFunction(dir, edit.file, edit.line);
    }
    default: throw new Error(`the trim may not make a ${edit.kind} edit`);
  }
}

// --- the pass ---------------------------------------------------------------

const words = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
const say = (n, capital) => { const w = words[n] || String(n); return capital ? w[0].toUpperCase() + w.slice(1) : w; };

function trim(dir, base) {
  // Step 1: the piece as built, in its own commit.
  git(dir, 'add', '-A');
  git(dir, 'commit', '-q', '-m', 'Build the piece');
  const built = git(dir, 'rev-parse', 'HEAD');

  const { edits, reports } = gather(dir, base);
  const applied = [];
  const wrongCalls = [];
  for (const edit of edits) {
    const touched = [edit.file, edit.user && edit.user.file].filter(Boolean);
    const saved = Object.fromEntries(touched.map(f => [f, exists(dir, f) ? read(dir, f) : null]));
    apply(dir, edit);
    if (testsPass(dir)) applied.push(edit);
    else { write(dir, saved); wrongCalls.push(edit); }
  }

  // Step 6: the list once more over the result. Nothing it finds is applied.
  const treeBefore = hashOf(dir, projectFiles(dir));
  const again = gather(dir, base);
  assert.equal(hashOf(dir, projectFiles(dir)), treeBefore, 'the second run changed the code');
  const known = new Set([...applied, ...wrongCalls, ...reports].map(r => `${r.kind}:${r.file}:${r.name}`));
  const newlyFound = [...again.edits, ...again.reports].filter(r => !known.has(`${r.kind}:${r.file}:${r.name}`));

  // Step 7: the whole suite, then the trim on its own.
  assert.ok(testsPass(dir), 'the tests failed after the trim');
  let trimmed = null;
  if (git(dir, 'status', '--porcelain')) {
    git(dir, 'add', '-A');
    git(dir, 'commit', '-q', '-m', 'Take out what the piece did not need');
    trimmed = git(dir, 'rev-parse', 'HEAD');
  }

  const listed = reports.length + newlyFound.length;
  let line = '';
  if (applied.length) {
    line = tookOut[1].replace('<count> things', applied.length === 1 ? 'one thing' : `${say(applied.length)} things`);
    if (listed) line += ' ' + alsoReported[1].replace('<count>', say(listed, true));
  } else if (listed) {
    line = `${say(listed, true)} things in this change could be simpler. They are listed on the piece.`;
  }

  const onPiece = [
    ...applied.map(e => e.kind === 'one user'
      ? `Folded ${e.name} into ${e.user.file}, the one place that used it.`
      : `Took out ${e.name} from ${e.file} at line ${e.line}, which nothing used.`),
    ...wrongCalls.map(e => `Tried taking out ${e.name} from ${e.file}; a test failed, so it stayed.`),
    ...reports.map(r => ({
      'untested fold': `${r.name} in ${r.file} at line ${r.line} has one user, but no test runs it, so it was left.`,
      'one-use dependency': `${r.name} is brought in for one use, in ${r.user}.`,
      copy: `The code in ${r.file} at line ${r.line} repeats ${r.other}.`,
      'over the limit': `The ${r.isNew ? 'new' : 'changed'} ${r.name} in ${r.file} at line ${r.line} is harder to follow than the usual limit.`,
    })[r.kind]),
    ...newlyFound.map(r => `Found on the second look: ${r.kind} ${r.name || ''} in ${r.file}.`),
  ];
  return { built, trimmed, applied, wrongCalls, reports, newlyFound, line, onPiece };
}

// --- the piece with something to take out --------------------------------------

function freshProject(name) {
  const dir = path.join(work, name);
  fs.mkdirSync(dir, { recursive: true });
  git(dir, 'init', '-q');
  write(dir, start);
  git(dir, 'add', '-A');
  git(dir, 'commit', '-q', '-m', 'Start');
  return { dir, base: git(dir, 'rev-parse', 'HEAD') };
}

const { dir, base } = freshProject('project');
write(dir, piece);
const testFiles = projectFiles(dir).filter(f => f.startsWith('test/'));
const testsBefore = hashOf(dir, testFiles);
assert.ok(testsPass(dir), 'the piece as built should pass its tests');

const result = trim(dir, base);
console.log(`    person reads: ${result.line}`);
console.log(result.onPiece.map(l => `    on the piece: ${l}`).join('\n'));

const names = list => list.map(e => e.name);
assert.deepEqual(names(result.applied).sort(), ['formatMoney', 'left-pad', 'legacyTotal'],
  `expected three edits kept, got ${names(result.applied).join(', ')}`);
assert.ok(!exists(dir, 'src/format.js') && read(dir, 'src/pricing.js').includes('(total(items)).toFixed(2)'),
  'the tested one-user wrapper was not folded into its user');
console.log('  ok: a wrapper with one user and a test is folded into that user');
assert.ok(!read(dir, 'src/pricing.js').includes('legacyTotal'), 'the unused export is still there');
console.log('  ok: an export the change added and nothing calls is taken out');
assert.ok(!('left-pad' in JSON.parse(read(dir, 'package.json')).dependencies), 'the unused dependency is still listed');
console.log('  ok: a dependency the change added and nothing imports is taken out');

assert.ok(read(dir, 'src/pricing.js').includes('legacyRound'), 'an unused export from before the piece was touched');
console.log('  ok: an unused export from before the piece is left alone');
assert.ok(read(dir, 'src/pricing.js').includes('export function totalLabel'), 'a wrapper with two users was folded');
console.log('  ok: a wrapper with two users is left alone');

assert.deepEqual(names(result.wrongCalls), ['refund-order'], 'the file reached at run time was not the wrong call');
assert.ok(exists(dir, 'src/handlers/refund-order.js'), 'the wrong call was not undone');
console.log('  ok: a removal that breaks a test is undone and recorded as a wrong call');
assert.equal(hashOf(dir, testFiles), testsBefore, 'a test was changed');
console.log('  ok: no test was changed');

const reported = kind => result.reports.filter(r => r.kind === kind).map(r => r.name || r.file);
assert.deepEqual(reported('untested fold'), ['pad'], 'the untested wrapper was not only reported');
assert.ok(read(dir, 'src/cli.js').includes('export function pad'), 'the untested wrapper was folded');
console.log('  ok: a wrapper no test runs is reported, not folded');
assert.deepEqual(reported('one-use dependency'), ['tiny-words'], 'the one-use dependency was not reported');
assert.ok('tiny-words' in JSON.parse(read(dir, 'package.json')).dependencies, 'the one-use dependency was removed');
console.log('  ok: a dependency used once is reported, not removed');
assert.deepEqual(reported('copy'), ['src/report.js'], 'the copied block was not reported at its new place');
assert.ok(exists(dir, 'src/report.js'), 'the copied block was changed');
console.log('  ok: a copied block is reported, not changed');
assert.deepEqual(reported('over the limit'), ['risk'], 'only the new function past the limit should be reported');
console.log('  ok: a new function past the limit is reported, and an old one the change did not worsen is not');

const limitLine = result.onPiece.find(l => l.includes('usual limit'));
assert.ok(!/\d/.test(limitLine.replace(/line \d+/, '')), `a score reached the piece: ${limitLine}`);
assert.ok(!/\d/.test(result.line), `a number reached the person's line: ${result.line}`);
assert.ok(!/knip|jscpd|lizard|vulture|deptry|ccn|complexity/i.test(result.line + result.onPiece.join(' ')),
  'an engine name or a score word reached what the person reads');
assert.equal(result.line,
  'I took out three things this change did not need. They are listed on the piece. Four more could be simpler, and are listed there too.');
console.log('  ok: the person reads the shipped line, with no score or engine name');
assert.deepEqual(result.newlyFound, [], 'the second look found something new');
console.log('  ok: the second run over the result applies nothing');

assert.ok(result.trimmed, 'the trim was not saved');
assert.equal(git(dir, 'rev-parse', 'HEAD~1'), result.built, 'the trim is not the commit after the piece');
git(dir, 'revert', '--no-edit', 'HEAD');
assert.equal(git(dir, 'diff', result.built, 'HEAD', '--stat'), '', 'undoing the trim did not bring back the piece as built');
console.log('  ok: the trim sits in its own commit, and undoing it brings back the piece as built');

// --- the piece with nothing to take out ----------------------------------------

const clean = freshProject('clean');
write(clean.dir, {
  'src/tax.js': 'export function tax(amount) {\n  const rate = 0.2;\n  return Math.round(amount * rate * 100) / 100;\n}\n',
  'src/index.js': "import { total } from './pricing.js';\nimport { grade } from './grade.js';\nimport { tax } from './tax.js';\nconsole.log(total([]), grade(1), tax(10));\n",
  ...test('test/tax.test.js', 'tax', "import { tax } from '../src/tax.js';"),
});
const quiet = trim(clean.dir, clean.base);
assert.equal(quiet.line, '', `a clean change should say nothing, got: ${quiet.line}`);
assert.deepEqual(quiet.onPiece, [], 'a clean change put something on the piece');
assert.equal(quiet.trimmed, null, 'a clean change made a trim commit');
console.log('  ok: a clean change says nothing and makes no commit');

console.log('\ntrim-rehearsal.sh: kept edits, undone wrong call, reports and silence all held');
NODE
