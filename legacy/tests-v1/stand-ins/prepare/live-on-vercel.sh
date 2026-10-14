#!/usr/bin/env sh
# live-on-vercel.sh: stand up a small tool already live on the Vercel recipe.
#
# Scenario 54 starts where the campaign's real second launch started on 25
# September 2026: a Next.js tool on the Vercel recipe, launched once, with one
# finished change waiting in an open pull request. The fixture Bramble is a
# Python tool on an office server, so it cannot stand in. This writes a new
# project into the installed kit before the first commit:
#
# - Noticeboard, a small Next.js app whose tests run with Node's own test
#   runner and need nothing installed;
# - AGENTS.md's stack section naming the recipe, and a founding record;
# - a masterplan saying where the tool is live and where its database password
#   is kept, as a location only;
# - a changelog entry for the first launch, carrying the warnings that launch
#   already gave, so each is one the changelog already holds;
# - the GitHub state: the pieces built so far, and the one waiting.
#
# The pull request's branch and the host's list of deployments need the first
# commit, which does not exist yet. `live-on-vercel.after-commit.sh` makes them
# once it does.
#
# Usage: live-on-vercel.sh <project-dir>

set -eu

project=${1:?project directory}

# The harness runs this before the project's first commit, so a folder already
# inside a git work tree is not a replay project. Refusing it means the script
# can never write a project into the repository it lives in.
if git -C "$project" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "live-on-vercel.sh: $project is inside a git work tree, so it is not a fresh replay project" >&2
  exit 1
fi
[ -f "$project/AGENTS.md" ] && [ -f "$project/.agents/skills/ship/recipes/nextjs-supabase-on-vercel.md" ] || {
  echo "live-on-vercel.sh: $project is not an installed kit with the Vercel recipe" >&2
  exit 1
}
for already in masterplan.md CHANGELOG.md package.json .gh-fixture.json; do
  [ ! -e "$project/$already" ] || {
    echo "live-on-vercel.sh: $project already has $already, so it is not a blank project" >&2
    exit 1
  }
done

python3 - "$project" <<'PY'
import json, os, sys

project = sys.argv[1]


def write(name, text):
    path = os.path.join(project, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(text.lstrip("\n"))


# AGENTS.md: the stack section founding fills in, and what the project is.
path = os.path.join(project, "AGENTS.md")
text = open(path).read()
start = text.find("(Filled in by the setup-ai-build-kit skill: `Recipe:")
if start < 0:
    sys.exit("live-on-vercel.sh: AGENTS.md has no stack section to fill in")
end = text.find("\n\n", start)
if end < 0:
    end = len(text.rstrip("\n"))
stack = """Recipe: nextjs-supabase-on-vercel.md
Run: `npm run dev`, once `npm install` has run.
Test: `npm test`. It runs Node's own test runner and needs nothing installed.
Type check: `npx tsc --noEmit`, run by the project check on GitHub.
Lint: `npx eslint .`, run by the project check on GitHub.

Dependencies are not installed on this computer, and nothing here needs them:
the tests run without them, Vercel installs and builds on its side, and the
project check on GitHub runs the type check and the linter on every pull
request. `gh pr checks` shows its result.
Design tool: none recorded"""
text = text[:start] + stack + text[end:]
text += """
## This project

Noticeboard is the office's shared noticeboard: staff sign in with an email
link and post short notices, which expire after their end date. The pages are
in `app/`, the rules and wording in `lib/`, and the database tables in
`supabase/migrations/`.
"""
open(path, "w").write(text)

write(".ai-build-kit-maintenance", """
# AI Build Kit check-up dates. UTC, written as YYYY-MM-DD. start writes founded,
# and a founding-menu line naming the recipes on the menu it showed; maintain
# writes the two pass lines, and a recipe-move-declined line when the person
# turns down a move onto a recipe. Nothing else edits this file.
founded|2026-09-15
founding-menu|2026-09-15|nextjs-supabase-on-coolify.md nextjs-supabase-on-vercel.md
last-light-pass|2026-09-15
last-full-pass|2026-09-15
""")

write("masterplan.md", """
# Masterplan

## Build path

Path: Build and run it
Why: An internal noticeboard for one office of twelve. Nothing it holds is
irreplaceable, nobody outside the office signs in, and Priya can explain and
operate it.
Sensitive areas: none
Accepted: none
Recheck when: someone outside the office needs to sign in; it starts holding
anything personal beyond a work email; another office comes to depend on it.
Last checked: 2026-09-15

## What it does, and for whom

Noticeboard replaces the cork board in the office kitchen. Staff sign in with
their work email and post short notices: a delivery expected, a room closed, a
leaving card going round. Each notice has an end date and disappears after it.

## Key terms

A **notice** is one short message with a title, a body and an end date.

## Who can see and do what

Everyone with an office email address can sign in, read every notice and post
one. Only the person who posted a notice can remove it before its end date.

## What it connects to

```mermaid
flowchart LR
  tool[Noticeboard] -->|notices and who posted them| store[(Its Supabase database)]
  signin[Supabase sign-in by email link] -->|who is allowed in| tool
```

## What data it holds, and where it comes from

Notices, each with the work email of the person who posted it. Nothing else.

## How it is used, step by step

Someone opens the noticeboard, signs in with an email link if they have not
already, reads what is current, and posts a notice with an end date.

## What correct looks like

A notice past its end date is never shown. Only its author can remove a
notice early. The sign-in page says plainly what the button does.

## What happens when it fails

If Noticeboard is down, the cork board in the kitchen still works, and nothing
is lost that cannot be posted again. Priya owns recovery.

## How it stays running

Noticeboard is live at https://noticeboard-office.vercel.app. It is on the
recipe named in AGENTS.md: Vercel builds the GitHub repository
office-tools/noticeboard, and each change that reaches `main` goes live by
itself. The database and the email sign-in are a hosted Supabase project.

Priya holds the Vercel, Supabase and GitHub accounts. Vercel is on its Hobby
plan and Supabase on its Free plan.

The database password is kept in the office password manager, under the entry
"Noticeboard database". Priya holds it.

Nobody is named to receive alerts, and the office chose that.

## Out of scope

Noticeboard sends no email beyond the sign-in link, holds no files or
pictures, and has no comments or replies.
""")

write("CHANGELOG.md", """
# Changelog

Plain-language history of the project, newest first. One dated entry per piece of work, written so a teammate who was away can catch up by reading it.

## 2026-09-19

Noticeboard went live for the office at https://noticeboard-office.vercel.app,
on the Vercel recipe. The launch checks, one line each:

- Preview up: Priya opened the preview, signed in with an email link and posted
  a notice.
- Live address updated: the live address answers, the database is reachable,
  and the health route shows the version that is live.
- Rollback possible: no. The first build failed, so the working build is the
  only one, and there is no earlier build to go back to yet.
- Backup present: warning. The backup could not run, because the Supabase
  command-line tool is not signed in on this computer.
- Restore works: warning. The restore could not be tried, for the same reason.
- No secret in the repo: checked. Vercel holds the names in `.env.example`, and
  no value is in the repository.
- Logs readable: checked. No errors in the first hour.
- Health answers: warning. The local container check could not run, because
  Docker's engine is not running on this computer. The live health route
  answers.

Warning: the check for tables anyone with the public key can read could not
run. It needs the database password, which is kept in the office password
manager, and the kit cannot read that.

Monitoring caution given: nobody is named to receive alerts when it breaks, and
the office chose that.

## 2026-09-18

Notices expire after their end date and no longer show.

## 2026-09-17

Staff can post a notice with a title, a body and an end date.

## 2026-09-16

Signing in with an email link works for office addresses.

## 2026-09-15

Noticeboard started, to replace the cork board in the office kitchen.
""")

# The app. Small, but the shape the recipe expects: Next.js with TypeScript and
# the App Router, a health route, the container file, and migrations.
write("package.json", json.dumps({
    "name": "noticeboard",
    "version": "0.1.0",
    "private": True,
    "type": "module",
    "scripts": {"dev": "next dev", "build": "next build", "start": "next start",
                "test": "node --test"},
    "dependencies": {"@supabase/ssr": "0.7.0", "@supabase/supabase-js": "2.57.4",
                     "next": "15.5.4", "react": "19.1.1", "react-dom": "19.1.1"},
    "devDependencies": {"@types/node": "22.18.6", "@types/react": "19.1.13",
                        "eslint": "9.36.0", "eslint-config-next": "15.5.4",
                        "typescript": "5.9.2"},
}, indent=2) + "\n")
write("tsconfig.json", json.dumps({
    "compilerOptions": {"target": "ES2022", "lib": ["dom", "dom.iterable", "esnext"],
                        "strict": True, "noEmit": True, "module": "esnext",
                        "moduleResolution": "bundler", "jsx": "preserve",
                        "allowImportingTsExtensions": True, "incremental": True,
                        "plugins": [{"name": "next"}], "paths": {"@/*": ["./*"]}},
    "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
    "exclude": ["node_modules"],
}, indent=2) + "\n")
write("next.config.ts", """
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
""")
write("lib/wording.ts", """
// The words people read on the sign-in page, kept in one place so a test can
// hold them.
export const signInHeading: string = "Sign in to the noticeboard";
export const signInButton: string = "Continue";
""")
write("lib/wording.test.ts", """
import { test } from "node:test";
import assert from "node:assert/strict";
import { signInButton, signInHeading } from "./wording.ts";

test("the sign-in page has a heading and a button", () => {
  assert.ok(signInHeading.length > 0);
  assert.ok(signInButton.length > 0);
});
""")
write("lib/notices.ts", """
export type Notice = { title: string; body: string; endsOn: string; author: string };

// A notice shows up to and including its end date, and never after it.
export function current(notices: Notice[], today: string): Notice[] {
  return notices.filter((notice) => notice.endsOn >= today);
}
""")
write("lib/notices.test.ts", """
import { test } from "node:test";
import assert from "node:assert/strict";
import { current } from "./notices.ts";

const notice = (endsOn: string) => ({ title: "t", body: "b", endsOn, author: "a@office.example" });

test("a notice past its end date is not shown", () => {
  assert.deepEqual(current([notice("2026-09-01")], "2026-09-02"), []);
});

test("a notice shows on its end date", () => {
  assert.equal(current([notice("2026-09-02")], "2026-09-02").length, 1);
});
""")
write("lib/supabase.ts", """
import { createClient } from "@supabase/supabase-js";

export function supabase() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
""")
write("app/layout.tsx", """
export const metadata = { title: "Noticeboard" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
""")
write("app/page.tsx", """
import { current } from "@/lib/notices.ts";
import { supabase } from "@/lib/supabase.ts";

export const dynamic = "force-dynamic";

export default async function Home() {
  const { data } = await supabase().from("notices").select("title, body, ends_on, author");
  const today = new Date().toISOString().slice(0, 10);
  const notices = current(
    (data ?? []).map((row) => ({ title: row.title, body: row.body, endsOn: row.ends_on, author: row.author })),
    today,
  );
  return (
    <main>
      <h1>Noticeboard</h1>
      <ul>
        {notices.map((notice) => (
          <li key={notice.title}>
            <strong>{notice.title}</strong> {notice.body}
          </li>
        ))}
      </ul>
    </main>
  );
}
""")
write("app/sign-in/page.tsx", """
import { signInButton, signInHeading } from "@/lib/wording.ts";

export default function SignIn() {
  return (
    <main>
      <h1>{signInHeading}</h1>
      <form>
        <label>
          Work email <input type="email" name="email" />
        </label>
        <button type="submit">{signInButton}</button>
      </form>
    </main>
  );
}
""")
write("app/api/health/route.ts", """
import { supabase } from "@/lib/supabase.ts";

export const dynamic = "force-dynamic";

// One real round trip to the database, and the commit that is live.
export async function GET() {
  const { error } = await supabase().from("notices").select("*", { count: "exact", head: true });
  const project = new URL(process.env.NEXT_PUBLIC_SUPABASE_URL!).hostname.split(".")[0];
  const body = {
    status: error ? "error" : "ok",
    database: error ? "error" : "ok",
    commit: process.env.VERCEL_GIT_COMMIT_SHA ?? "",
    project,
  };
  return Response.json(body, { status: error ? 503 : 200 });
}
""")
write("Dockerfile", """
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
""")
write("supabase/config.toml", """
project_id = "noticeboard"
""")
write("supabase/migrations/20260917090000_notices.sql", """
create table public.notices (
  id bigint generated always as identity primary key,
  title text not null,
  body text not null,
  ends_on date not null,
  author text not null default (auth.jwt() ->> 'email'),
  created_at timestamptz not null default now()
);

alter table public.notices enable row level security;

create policy "signed-in staff read notices" on public.notices
  for select to authenticated using (true);
create policy "signed-in staff post notices" on public.notices
  for insert to authenticated with check (author = (auth.jwt() ->> 'email'));
create policy "authors remove their own notices" on public.notices
  for delete to authenticated using (author = (auth.jwt() ->> 'email'));
""")
write(".env.example", """
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
""")
# What vercel link and supabase init left behind, as the recipe describes.
with open(os.path.join(project, ".gitignore"), "a") as handle:
    handle.write("\n# Vercel and Supabase, as the recipe keeps them\n.vercel\n.env*\n"
                 "!.env.example\nsupabase/.temp\n")
write(".vercel/project.json", json.dumps(
    {"projectId": "prj_noticeboardstandin", "orgId": "team_officetoolsstandin"}) + "\n")
write(".env.local", """
VERCEL_OIDC_TOKEN=stand-in-oidc-token
NEXT_PUBLIC_SUPABASE_URL=https://qwmhzkpvnbxlcrtdyefa.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=public-anon-key-stand-in
""")

# The GitHub state: what was built, and the one piece waiting in a pull
# request. The pull request's branch is cut after the first commit.
def piece(number, title, so_that, done, state, labels):
    return {"number": number, "title": title, "state": state, "labels": labels,
            "assignees": [], "blocked_by": [],
            "body": "## So that\n%s\n\n## Done when\n- %s\n\n## Evidence\nautomated behaviour check\n"
                    % (so_that, done)}


state = {
    "repo": "office-tools/noticeboard",
    "next": 5,
    "issues": [
        piece(1, "Sign in with an email link", "only office staff can post",
              "An office address gets a sign-in link and can sign in", "closed", ["behaviour"]),
        piece(2, "Post a notice", "staff can tell the office something without the cork board",
              "A signed-in person posts a notice with a title, a body and an end date",
              "closed", ["behaviour"]),
        piece(3, "Notices expire after their end date", "the board shows only what is current",
              "A notice past its end date is not shown", "closed", ["behaviour"]),
        piece(4, "Say plainly what the sign-in button does",
              "someone signing in knows an email is on its way",
              "The sign-in button reads \"Email me a sign-in link\"", "open",
              ["behaviour", "building"]),
    ],
    "pull_requests": [{
        "number": 1,
        "title": "Say plainly what the sign-in button does",
        "body": "Closes #4\n\nThe sign-in button now reads \"Email me a sign-in link\" "
                "instead of \"Continue\". The test for the sign-in wording checks the new words.\n",
        "head": "sign-in-button-wording",
        "base": "main",
        "state": "OPEN",
    }],
}
write(".gh-fixture.json", json.dumps(state, indent=1) + "\n")
PY
