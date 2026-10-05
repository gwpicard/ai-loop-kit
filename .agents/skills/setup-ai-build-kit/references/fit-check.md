# The fit check

The fit check chooses the project's current **build path** and names each
sensitive area the work touches, with the caution that goes with it. It runs:

- during /setup-ai-build-kit;
- when a request changes users, data, money, autonomy, promises, or reliance;
- before the first /ship;
- during quarterly /maintain;
- before a handover.

## Consequence questions

Ask one at a time, with a best guess attached. These decide the path.

1. Will anyone outside the team sign in or rely on it?
2. Will real money move through it or be calculated for real decisions?
3. Does a contract, client promise, uptime expectation, or deadline depend on
   it?
4. Will it hold personal or sensitive data beyond ordinary work contact
   details?
5. Does it give or enforce regulated, legal, medical, financial, employment,
   or safety-related decisions?
6. Will it begin on data the team cannot afford to lose or corrupt?
7. Will it act automatically on another system, send consequential messages,
   change records, or do anything difficult to reverse?
8. If it stops or gives a wrong answer, does important work stop or
   meaningful harm follow?

## Ownership questions

9. Is there a manual fallback?
10. Can the team explain the main flows and permissions without reading code?
11. Can the team identify where data, credentials, service ownership, and
    bills live?
12. Is there a named person responsible for alerts, backups, access, and
    recovery?
13. Is the system still simple enough that a new agent could understand it
    from the records alone?
14. Are integrations, background jobs, permissions, and migrations limited
    enough for the team to operate confidently?

These decide setup tasks, never the path. A no to any of them becomes a
founding task: a piece on the plan where there is work to do (write down the
manual fallback, name who reads the alerts), or a line in the masterplan's
"How it stays running" section where there is only a fact to record. Founding
carries on. A team that cannot yet explain or recover its tool has a gap to
close, which is a different thing from work that touches a sensitive area.

The fit check owns the present ownership facts in "How it stays running".
Keep those facts only there. The changelog records only that the ownership
check ran and when, without copying its answers. A later ownership check reads
that section and returns any missing or changed fact to this rule.

For a credential, the fact is where it lives: a file path, a password manager
entry's name, or an environment variable's name, and never its value. AGENTS.md's
Secrets rule says how a later session reads it and what it says when the
location is unknown.

## The three build paths

Use these three names everywhere, and do not alternate between path, tier,
level, mode, verdict, or maturity class. Choose the first that matches, after
redesign has been considered.

### 1. Build with care

Some of the work touches a sensitive area: personal or sensitive data, money,
sign-in and permissions, automatic action on people or other systems,
irreplaceable live data, or a regulated decision. A yes to question 1, 2, 4,
5, 6 or 7 that redesign cannot remove puts the project here. The masterplan
names each area in the tool's own words and the caution beside it. Everything
outside those areas is built exactly as Build and run it. Inside one, the
caution is done before merge or activation, or the person accepts on the
record.

### 2. Build and run it

People rely on the tool, no sensitive area is touched, consequences are
limited and recoverable, and the manual fallback is real. A yes to question 3
or 8 lands here rather than above: it says the tool is relied on, not what it
touches, and what it asks for is the operational readiness /ship requires
before first live use. This is the kit's primary target path.

### 3. Explore privately

Nobody relies on it, data is disposable, actions are reversible, and the work
exists to answer questions or learn.

## Sensitive areas

Six areas, fixed. Each carries a default caution, which is what would normally
prevent the harm. The fit check names the area in the tool's own words (the
client notes, the refund button, the nurses' protocol) and writes the caution
beside it. Change a caution only where the tool's own facts make a different
one right, and say why.

| Area | What counts | Default caution |
|---|---|---|
| Personal or sensitive data | Facts about a person beyond ordinary work contact details: health, pay, home address, identity documents, anything a person would mind a colleague reading. | A person who did not build the tool reviews who can see what, before real data goes in. |
| Money | Real money moving through the tool, or figures people act on as if they were the bill. | A managed payment provider holds card details so the tool never sees them, and the owner of the money checks the first real figures against a case they know. |
| Sign-in and permissions | Anyone outside the team signing in, or rules that keep one person's things from another's. | A managed sign-in service so the tool never stores a password, and a person who did not build it reviews who can reach what, before outside users sign in. |
| Automatic action on people or other systems | The tool sends messages, changes records elsewhere, or does anything on its own that is hard to take back. | A person approves each action until a live run has shown it right, and one switch turns it off. |
| Irreplaceable live data | The only copy of something the team cannot recreate. | A backup taken and restored once, and the change rehearsed on a copy, before the original is touched. |
| Regulated decisions | Medical, legal, financial, employment, or safety decisions the tool gives or enforces. | Somebody qualified in that field signs off the rule before anyone acts on it. |

Where a caution is a person, the rule under "The notice holds" applies
unchanged: that person looks, or the person carries on past the notice and the
risk is accepted on the record. Where a caution is a backup, a copy, a
rehearsal, a managed service, or an approval step, it is the kit's to do. Do it
as part of the work, or check it was done, and record the result on the area's
line. Work inside a named area is flagged work, and that word keeps its meaning
in every skill.

## Redesign before the notice

Before naming a sensitive area, ask whether the risk can be removed:

- use a copy instead of live data;
- remove automated action;
- keep a human approval step;
- remove regulated advice;
- reduce external access;
- use a managed service;
- keep a manual fallback;
- narrow the promise.

A redesign that genuinely removes the area changes the answers, so run the
check again. A redesign that keeps the surface and drops the caution does not.

## The risk notice

The kit refuses nothing, and it does not stop where the person can judge the
risk. A notice is due only where work touches a sensitive area that survives
redesign and whose caution has not been done: personal or sensitive data,
money, sign-in and permissions, automatic action on people or other systems,
irreplaceable live data, or a regulated decision. Say so before that work goes
ahead, on any build path. Work outside every named area gets no
notice, no acceptance, and no recorded exception, whatever its path. Most work
on most projects is like this. Build and run it, the primary path, is defined
by no sensitive area applying, so it has nothing to notice.

A notice says five things:

- who is exposed, named as people rather than as a risk;
- what happens to them when it goes wrong;
- what would normally prevent that;
- what the person can do: have that done first, take the flagged thing out of
  scope, or carry on, in which case you record that they accepted the risk and
  the work goes ahead;
- that you flag what you can recognise and will miss things.

"This is risky" is not a notice. Naming a cost, a delay, or a rule of the kit's
own is not a notice either. Say who gets hurt.

Give it once, in full, in one reply. Do not spread it across several replies,
and do not repeat it in every reply after. A notice given when the work was
first scoped, with no acceptance recorded since, is given again when the work
is actually built, because that is the moment it can still change what the
person decides. Once an acceptance is recorded for an area, do not give the
notice for that area again; say in one line what was accepted and when.

A sensitive area is exposure from the list above, not any imperfection
somebody might be annoyed by. A vanished booking, a stack choice, a save that
stays on one machine, an integration not connected yet: these are design
points, so raise them in ordinary words in the ordinary place. A notice given
for ordinary work teaches the person to skip notices, which is paid for by the
one that names a real exposure and now looks like all the others.

When the answer to a broken thing is to build a replacement, the notice covers
the replacement, not the fault. Describing the fault accurately while saying
nothing about what replaces it is the same failure as saying nothing.

### The notice holds

Once given, do not soften it, drop it, or recast a named control into something
you can satisfy yourself. Offering to re-read your own work does not meet it
however it is described.

Where the notice names who should look, that is a person: the owner of the thing
at risk, or somebody who does that work for a living. No session meets it. Not a
fresh one, not a clean one, not a separate one, not a subagent, and not the
project's own review method however independent that method is of the builder.
Those exist so that work is not reviewed by the thing that wrote it, which is a
different job from the one a named reviewer was named for, and the two are not
interchangeable because they happen to share the word review.

The kit does not decide it has satisfied this. Either the named person has looked
and that is recorded, or they have not and the person carries on past the
notice, with the acceptance on the record. Saying an in-project method already covers it is the recast this rule
exists to refuse, and it is the form the recast actually takes: not a refusal to
review, but a redefinition of what the review was.

An acceptance is never the caution done. The area's line says `accepted`, not
`done`, and the launch report says which caution did not happen.

Pushback is not evidence about the risk. Cost, a deadline, the size of the team,
the person's own willingness to be responsible, and what other tools are said to
allow all change what the person decides. None of them changes who is exposed.

Never propose a relaxation and act on it in the same breath. An area is named
as sensitive on your own judgement. Its caution is dropped only when the person
carries on after hearing the notice.

### Carrying on is accepting

Once the full notice has been given, any instruction to go on with the flagged
work is the person accepting the named risk. "Go ahead", "build it anyway",
"try it again", and "it is on me, build it" all count. Do not ask
a second question to get a cleaner yes, and do not turn an answer down because
it does not repeat the notice back. The person has heard who is exposed, and
the choice is theirs.

Four things are not carrying on:

- silence, or a reply that does not ask for the flagged work, such as a
  question, a change of subject, or "I am not sure";
- an answer from a choice form or menu that came back with no option selected,
  or with only a note that does not ask for the flagged work. A selected option
  whose words ask for the flagged work counts, as a typed reply does;
- an instruction given before the notice. A person who has not been told
  cannot have accepted. Give the notice in full in that reply, and build when
  they carry on after it;
- an instruction about other work. Going on with the work outside the area is
  not going on with the area.

Where no notice was due, there is nothing to accept and nothing to record.
Agreement to a plan is not acceptance of a risk. An `Accepted:` line written
against an ordinary decision makes the record meaningless, so do not write one.

Before you write anything, find the notice in one of your own replies: the
reply that named who is exposed and what happens to them. Remembering that you
meant to give it is not finding it. Where you cannot point to that reply, the
person has not been told, so give the notice in full now and build when they
carry on after it.

When the person carries on, write the `Accepted:` line in the masterplan's
build-path section, described under "Write it down" below, with the date and
their own words, and change the area's own line to `accepted` with the date.
Add both before the flagged work starts, not after it lands. Read the
build-path section back, and let the line being there decide whether the work
starts. Then build what was asked for, without asking again.

Their own words are the words the person typed in this conversation, quoted
exactly, in quotation marks. Do not paraphrase them or sum them up. Name only
people the person named: a team, a reviewer or an approval they never mentioned
does not go in the line. Where they carried on by choosing an option in a form
or menu, quote the option's words and say it was a selected option. Where they
carried on over several messages, quote the one that asks for the flagged work.
Where the words hold a secret or a personal detail about somebody, quote the
rest and mark the cut with `[removed]`. The project's Secrets rule already says
a secret is never written down.

In the same save as the `Accepted:` line, read the rest of the masterplan for
every sentence the acceptance makes untrue: one that says the flagged thing is
excluded, off, kept out, or waiting for the caution. Correct each one to match,
in the present tense, and say the risk was accepted. A sentence like that in
another record, such as AGENTS.md or a concept file, is corrected in the same
save, and the reply names that record. Say in one line which sentences changed.
Where no sentence is made untrue, change nothing else and say nothing extra.

All of this happens in the reply that answers the person carrying on: write
the line, read it back, and start the work. Do not end that reply on a
question that asks their permission again, such as whether they are sure,
whether it should really switch on, or whether they want the version that
waits for the check after all. Each of those is the second question in other
words, and a person who has to answer it has been stopped. A real question
about scope, whose answer changes what gets built, may still be asked.

The acceptance reaches what that notice named, in that area, and nothing else.
It does not switch on anything the notice did not name, and it does not settle
another area's caution, which needs its own notice. Where the plan holds a lock
whose only purpose is to wait for this caution, such as a rule that stays off
until a named person signs it, the acceptance opens that lock. Change the plan
in the same reply and say so in one line, which can be the same line that
names the corrected sentences. Do not keep the lock and ask for a
further yes to open it. Keep it only if the person asks you to. The named
person has still not looked, and the record still says accepted, never done.

## Full fit check

Run every question, in the situations listed at the top of this file, and
whenever several project characteristics changed together.

## Delta fit check

For a single change-triggered reassessment:

1. ask the consequence questions affected by the proposed change;
2. name any sensitive area the change touches, and its caution;
3. recheck the ownership questions the change affects, and record a new no as
   a founding task;
4. apply the decision order;
5. update `Recheck when` and `Last checked`, and add an `Accepted:` line if a
   risk was accepted along the way.

Run the full check instead when the affected area cannot be bounded confidently.

## Write it down

Whatever the outcome, it goes in the masterplan's build path section:

```md
## Build path

Path: <Explore privately | Build and run it | Build with care>
Why: <one or two sentences>
Sensitive areas: <none, or one line per area beneath this one>
Accepted: <none, or one line per accepted risk>
Recheck when: <specific triggers>
Last checked: YYYY-MM-DD
```

Each named area gets its own line under `Sensitive areas:`, indented two
spaces. A line carries the area, what in this tool touches it, its caution,
and where the caution stands: `not yet done`, `done` with the date, or
`accepted` with the date of the matching `Accepted:` line. The line carries no
paths. The map lives in the Areas section of `docs/working-rules.md`, outside
the masterplan; a sensitive area points into it by name.

```md
Sensitive areas:
  regulated decisions: the treatment recommendation; caution: a clinician signs off the protocol before nurses act on it; not yet done
  irreplaceable live data: the maintenance history import; caution: a backup restored once and the import rehearsed on a copy; done 2026-08-12
```

Each accepted risk gets its own line, and lines are added rather than replaced.
A line carries the date, the caution that did not happen, and the words the
person carried on with, with their name:

```md
Accepted: 2026-08-12, review of who can see the client notes not done; Priya carried on after the notice: "we cannot pay for a review, build it"
```

An acceptance drops a caution. It does not move the path or take the area off
the list, because the exposure is still there; the area's own line changes to
`accepted 2026-08-12` so the two point at each other. The path moves only by
running the fit check again, when a redesign has removed the area.

The agent reads that section first in every session.

## The area map

The map covers the whole project and exists on every build path. A piece's
`Boundary:` and `Reaches:` lines name areas, so an area has to name real places
in the code. Each area is one line in the `## Areas` section of
`docs/working-rules.md`, written `- <name>: <path>, <path>`, with folders and
files as paths. An area whose folder does not exist yet is written
`- <name>: none yet`, and the piece that creates the folder adds its path in
the same save. An area name holds no comma and no colon, because a piece separates
areas with commas and ends a reached area's name with a colon.

Under an area, at most one indented `sensitive: <name>` line names the line
under `Sensitive areas:` it belongs to. Only Build with care names sensitive
areas, so only there does an area carry one. At most one indented
`boundary:` line names one boundary the area must not cross, and the project
check can hold that boundary once the person agrees; `boundary-rules.md` says
how.

```md
## Areas

- treatment rules: src/recommendations/, src/rules/treatment.ts
  sensitive: regulated decisions
  boundary: reached only through src/rules/treatment.ts
- maintenance import: src/imports/maintenance/
  sensitive: irreplaceable live data
- reporting: src/reporting/
- project records: docs/
```

Every tracked folder belongs to an area: the folder is listed, a folder above
it is listed, or each file and folder directly inside it belongs to one.
Hidden top-level folders, files at the project root and `changes/` belong to
none. There is no exempt list beyond hidden top-level folders, root files and
`changes/`, because an exempt list is where an unclaimed folder hides. A
folder the map cannot sensibly own, such as vendored code, is listed under an
area named for what it is: `- vendored libraries: vendor/`.

Read each area and its home back in plain words at founding. For example:
"Billing is the refund button, and it lives in the billing folder." Where the
project uses a language Bearer covers, offer its local data scan to find files
that handle personal data. Bearer is free to run under the Elastic License 2.0
and is not open source. The scan is optional; the map and its check are not.

Write the map in the same save as any code move that changes it. The project
check runs `python3 .agents/tools/area-map.py check`, which turns red, naming
the folder or the line, on a folder no area claims, a listed path that has
gone, a path listed under two areas, and a `sensitive:` line and a
`Sensitive areas:` line that do not point at each other. `area-map.py which
<path>` names the area a path belongs to, and `area-map.py areas` lists every
area with its sensitive area, so no skill reads the map by hand.
