# Adopting a project that already exists

Most people who pick up this kit already built something: an app in an
all-in-one builder, a tool inside ChatGPT, a vibe-coded project that works
until you look closely. This route brings that project under the kit
instead of replacing it. The risk is inverted from a fresh start: the
danger isn't building the wrong thing, it's changing something whose
behaviour nobody ever wrote down.

## The route, step by step

1. Read before anything. Step 0 of this skill has already settled which
   branch it is on. Go through the existing code, and say back in plain
   language what the tool appears to do, who appears to use it, and
   what data it appears to hold. Guesses attached, like the interview:
   correcting a wrong guess brings the real picture out.

2. Interview against reality. The interview runs as normal, with one twist:
   the questions are about what the tool is supposed to do, asked next to
   what it actually does. Every gap between the two gets written down as
   either a piece for the plan (it should do X and doesn't) or a wart to
   record (it does Y and that's wrong, but people rely on it for now).

3. The fit check runs as normal. An adopted project answers the same
   consequence and ownership questions; a tool that already has outside
   users or real data arrives with a build path that reflects that, and the
   masterplan's build-path section says so.

4. Write the masterplan for the present that exists, warts included.
   "Uploads over 10MB fail silently" belongs in the masterplan if that is
   what the tool does today, because the masterplan describes the present,
   and the present was not built by this kit.

5. Pin down before changing. Any part of the code that is going to change
   gets pin-down tests first: tests that record what the tool does today,
   right or wrong, so tomorrow's changes cannot silently break behaviour
   someone depends on. Write them only where change is planned; the rest
   of the old code stays untouched and untested, on purpose.

6. Cut the plan from the gaps found in step 2, then stand up whatever is
   missing around the code: the documents, the branch flow, the hosting
   split if there is hosting. From here, everything runs normally: new
   work through /shape and /implement, breakage through /fix, and the old parts
   nobody touches stay exactly as they were.

## The one hard rule

Never rewrite or tidy old code that has no tests on it, however messy it
looks. Messy code that works is carrying knowledge nobody wrote down.
Pin it down first, or leave it alone.

## Classify existing behaviour

Every observed behaviour becomes one of:

- promised and should remain;
- accidental but currently relied on;
- broken and safe to fix;
- unknown and needs evidence;
- risky and needs path reassessment.

## Establish a smallest trustworthy surface

Do not attempt to test the whole legacy project.

Prioritise:

- the next area to change;
- data boundaries;
- permissions;
- external integrations;
- behaviours people already rely on;
- the current manual fallback.

## Reassess ownership

An adopted tool may already touch a sensitive area. Run the full consequence
and ownership check before normal building.

## Contain, do not beautify

Architecture cleanup is allowed only when:

- a current change is blocked by the existing shape;
- repeated bugs identify the same hot spot;
- the change can be verified through existing behaviour;
- the project path allows it.

## What to tell the person

Their earlier build was the right first step, and it did its job: it
proved the idea and taught them what the tool should be. Adopting it is
what graduating looks like, and nothing from here requires starting over.
