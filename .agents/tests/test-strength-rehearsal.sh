#!/usr/bin/env sh
# test-strength-rehearsal.sh: show a weak test missing a real boundary error.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)

node - "$ROOT" <<'NODE'
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = process.argv[2];
const project = fs.mkdtempSync(path.join(os.tmpdir(), 'test-strength-'));
const sourceFile = path.join(project, 'delivery.cjs');
const testFile = path.join(project, 'delivery.test.cjs');
const pieceFile = path.join(project, 'piece.md');
const original = 'module.exports = total => total >= 50;\n';
const breakages = [
  {
    source: 'module.exports = total => total > 50;\n',
    miss: 'An order of exactly 50 lost free delivery, and the tests still passed.',
  },
  {
    source: 'module.exports = total => total < 50;\n',
    miss: 'Free delivery was given to small orders instead of larger ones.',
  },
];

function runTest() {
  const result = spawnSync(process.execPath, [testFile], {
    cwd: project,
    encoding: 'utf8',
    timeout: 10000,
  });
  assert.ifError(result.error);
  assert.equal(result.signal, null, 'a stopped run must not count as a catch');
  return result;
}

try {
  fs.writeFileSync(sourceFile, original);
  fs.writeFileSync(testFile, [
    "const assert = require('node:assert/strict');",
    "const hasFreeDelivery = require('./delivery.cjs');",
    'assert.equal(hasFreeDelivery(49), false);',
    'assert.equal(hasFreeDelivery(51), true);',
    '',
  ].join('\n'));
  assert.equal(runTest().status, 0, 'the unchanged behaviour must pass');

  let caught = 0;
  const misses = [];
  for (const breakage of breakages) {
    fs.writeFileSync(sourceFile, breakage.source);
    const syntax = spawnSync(process.execPath, ['--check', sourceFile]);
    assert.equal(syntax.status, 0, 'each deliberate breakage must be valid code');
    const result = runTest();
    if (result.status === 0) {
      misses.push(breakage.miss);
      const boundary = spawnSync(process.execPath, ['-e',
        "process.stdout.write(String(require('./delivery.cjs')(50)))"], {
        cwd: project, encoding: 'utf8',
      });
      assert.equal(boundary.status, 0);
      assert.equal(boundary.stdout, 'false', 'the missed change must damage behaviour');
    } else {
      assert.equal(result.status, 1);
      assert.match(result.stderr, /AssertionError/);
      caught += 1;
    }
  }
  assert.equal(caught, 1, 'the tests must catch one deliberate breakage');
  assert.equal(misses.length, 1, 'the weak test must miss the boundary error');

  fs.writeFileSync(pieceFile, '# Check free delivery\n\n## Worth knowing\n\n'
    + misses.map(miss => `- ${miss}`).join('\n') + '\n');
  assert.match(fs.readFileSync(pieceFile, 'utf8'), /exactly 50 lost free delivery/);

  const rules = fs.readFileSync(path.join(root,
    '.agents/skills/section-builder/references/test-strength.md'), 'utf8')
    .replace(/\s+/g, ' ');
  const template = rules.match(/"(The tests were checked by breaking the code on purpose <tried> times\. They caught <caught>\. The <missed> they missed are listed on the piece\.)"/);
  assert.ok(template, 'the report must come from the shipped rule');
  const report = template[1]
    .replace('<tried>', String(breakages.length))
    .replace('<caught>', String(caught))
    .replace('The <missed> they missed are', 'The one they missed is');
  assert.equal(report, 'The tests were checked by breaking the code on purpose 2 times. They caught 1. The one they missed is listed on the piece.');

  fs.writeFileSync(sourceFile, original);
  assert.equal(runTest().status, 0, 'the intact code must still pass afterwards');
  console.log(report);
  console.log('test-strength-rehearsal.sh: weak-test miss and observed report passed');
} finally {
  for (const file of [sourceFile, testFile, pieceFile]) {
    if (fs.existsSync(file)) fs.unlinkSync(file);
  }
  fs.rmdirSync(project);
}
NODE
