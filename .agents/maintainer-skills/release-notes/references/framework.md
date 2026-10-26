# Release Notes Writing & Remediation Framework

## 1. Purpose and quality standard

This framework governs how release notes are generated, reviewed, and improved from Git commits, pull requests, and code changes.

The objective is to produce release notes that accurately communicate meaningful changes in natural, precise, concise, and audience-appropriate language.

Release notes must not read like raw commit messages, awkward paraphrases of implementation details, or artificially simplified descriptions of technical behaviour.

**A good release note should communicate:**

1. **What changed**: the feature, behaviour, capability, or issue affected.
2. **How it changed**: what is new, different, improved, fixed, or removed.
3. **Why it matters**: the practical consequence, where relevant and supported.
4. **Who or what is affected**: the applicable feature, workflow, integration, or user, when important.

Not every release note needs all four elements explicitly. Include only what is useful, relevant, and verifiable.

### Core writing principles

Release notes should be:

- Natural, not mechanically constructed.
- Clear, not artificially simplified.
- Precise, not vague or unnecessarily technical.
- Concise, not stripped of essential meaning.
- Change-focused, not implementation-focused by default.
- Useful to the reader, not merely descriptive of development activity.
- Faithful to the actual changes, without speculation or invented benefits.
- Consistent in terminology, tense, formatting, and level of detail.

**Primary rule:** Interpret the change before writing about it. Never simply paraphrase commit messages into release-note sentences.

---

# 2. Writing problems to identify and rectify

## Criterion 1: Awkward or unnatural sentence construction

**Look for:**
- Sentences that sound grammatically assembled rather than naturally written.
- Unusual combinations of subjects, verbs, and objects.
- Complicated descriptions of otherwise straightforward changes.
- Awkward constructions such as "a check that X will not start."
- Sentences requiring multiple readings to understand.
- Unnecessary passive voice or convoluted negation.

**Problematic example:**

"A check that GitHub will not start is no longer called a failure."

**Possible revision, if this is the actual behaviour:**

"GitHub checks that fail to start are no longer reported as failed."

If the change specifically concerns checks that have not started yet, the wording should reflect that instead.

**Remediation:**
1. Determine what actually changed.
2. Identify the real subject and action.
3. Rewrite the sentence from the underlying behaviour, not the original wording.
4. Use natural subject-verb combinations.
5. Prefer direct statements over unnecessarily complicated constructions.

**Validation:** Would a technically informed reader understand the change immediately, without mentally reconstructing the sentence?

## Criterion 2: Mechanical paraphrasing of commit messages

**Look for:**
- Commit-message wording reproduced with superficial substitutions.
- Internal implementation descriptions presented as product announcements.
- Awkward literal interpretations of developer shorthand.
- Technical actions described without explaining the resulting behaviour.
- Descriptions that focus on the code change rather than what the software now does.

**Example:**

Commit: `fix: don't mark unstarted github checks as failure`

Poor release note:

"Checks which have not started in GitHub are not called failures anymore."

Better:

"GitHub checks that haven't started are no longer marked as failed."

**Remediation:**
- Extract the actual behavioural change.
- Separate implementation details from observable outcomes.
- Translate developer shorthand into standard terminology.
- Rewrite the meaning rather than individual words.
- Preserve technical specifics when they are important to the intended audience.

**Validation:** Does the release note describe the software change, rather than merely restating the developer's implementation task?

## Criterion 3: Artificially simplified or childish language

**Look for:**
- Overuse of basic vocabulary when established terminology is clearer.
- Awkward informal expressions such as "waits for your yes."
- Short, elementary sentences that sacrifice accuracy.
- Technical concepts explained in language that feels patronising.
- Avoidance of words such as *confirmation, validation, authentication,* or *configuration* when appropriate.

**Example:**

Poor: "The first upload waits for your yes."

Better: "The first upload now requires your confirmation."

**Remediation:**
- Replace forced simplicity with natural phrasing.
- Use established terminology appropriate for the audience.
- Preserve technical accuracy.
- Favour direct language over playful metaphors.

**Validation:** Is the sentence easy to understand because it is clearly written, rather than because it uses the simplest possible words?

## Criterion 4: Unnatural agency and inappropriate verbs

**Look for:**
- Processes or checks that "say" something.
- Uploads that "wait" for permission.
- Scripts that "judge" rules.
- Tools that "know," "decide," or "understand" something when those terms misrepresent their behaviour.
- Generic verbs that obscure the underlying operation.

**Example:**

Poor: "Scripts check rules they can judge."

Better: "Validation scripts now check rules that can be evaluated automatically."

**Remediation:**
- Identify the actual operation.
- Use an appropriate verb: *detects, reports, verifies, validates, skips, prevents, generates, classifies,* etc.
- Keep conventional personification when natural and accurate.
- Avoid attributing human judgment to deterministic operations without justification.

**Validation:** Does the verb accurately communicate what the software does?

## Criterion 5: Semantic ambiguity and unclear references

**Look for:**
- Unclear relationships between the subject and action.
- Ambiguous references to checks, failures, statuses, tools, or processes.
- Missing distinctions between "not started," "failed to start," and "failed after starting."
- Pronouns or modifiers that could refer to multiple things.
- Statements with several plausible technical interpretations.

**Example:**

"GitHub will not start" could imply that GitHub itself cannot launch.

"GitHub checks will not start" could refer to workflows, jobs, or status checks.

These meanings are not interchangeable.

**Remediation:**
1. Identify the exact component.
2. Identify the original behaviour.
3. Identify the new behaviour.
4. Confirm any important conditions.
5. Rewrite using terminology that eliminates ambiguity.

**Validation:** Could two reasonable readers interpret the note as describing materially different changes? If yes, revise.

## Criterion 6: Vague descriptions and low information value

**Look for:**
- Generic expressions such as "improved handling," "better support," or "updated behaviour."
- Descriptions that do not identify what actually changed.
- Sentences that could apply to almost any feature.
- Claims of improvement without specifying the improvement.
- Redundant phrases that contribute no meaningful information.

**Example:**

Poor: "Improved error handling for GitHub checks."

Better, if confirmed by the change:

"GitHub checks that haven't started are no longer incorrectly classified as failures."

**Remediation:**
- Name the affected behaviour.
- Explain what is different.
- Specify important conditions.
- Replace generic improvements with verifiable changes.
- Remove filler words.

**Validation:** Can the reader identify a specific difference between the previous and new behaviour?

## Criterion 7: Excessive implementation detail

**Look for:**
- References to internal functions, classes, variables, or method names.
- Release notes that read like descriptions of code edits.
- Excessive explanation of internal refactoring.
- Implementation mechanics with no apparent relevance to the intended reader.

**Example:**

Poor: "Updated the status mapper to handle null check-run timestamps."

Better, if this describes the actual external behaviour:

"GitHub checks that haven't started are no longer incorrectly reported as failed."

**Remediation:**
- Determine whether the implementation detail matters to users.
- Describe the resulting behaviour.
- Preserve internal terminology only when relevant to developers, API consumers, or administrators.
- Exclude internal refactoring that has no meaningful external effect, unless the release notes explicitly cover internal changes.

**Validation:** Does the reader learn something meaningful about the release, not merely about the codebase?

## Criterion 8: Weak descriptions of change

**Look for:**
- Statements that describe how a feature works without identifying what changed.
- Notes that lack an obvious before/after distinction where one is needed.
- Generic present-tense descriptions indistinguishable from documentation.
- Passive statements that conceal the actual change.

**Example:**

Weak: "GitHub checks are monitored for their status."

Better: "GitHub checks that haven't started are no longer marked as failed."

**Remediation:**
- Make the changed behaviour explicit.
- Use natural change language such as *now, no longer, added, fixed, removed,* or *updated* where useful.
- Explain the before/after relationship when necessary.
- Avoid forcing "now" or "previously" into every entry.

**Validation:** Is it obvious what is different in this release?

## Criterion 9: Overstated, invented, or unsupported claims

**Look for:**
- Benefits inferred without evidence.
- Absolute claims such as "always," "never," or "fully" without verification.
- Performance, security, or reliability improvements not demonstrated by the change.
- Broader scope than the actual implementation supports.
- Descriptions that confuse an intended fix with a confirmed outcome.

**Example:**

Commit: `fix: handle missing check-run status`

Unsupported: "GitHub checks now always report accurate statuses."

Safer, if verified: "Fixed incorrect failure reporting when a GitHub check has not started."

**Remediation:**
- Verify the change against the code diff, PR description, tests, or other available evidence.
- Preserve exact conditions and limitations.
- Avoid inventing user benefits.
- Do not turn narrow fixes into broad guarantees.
- Flag uncertain behaviour for verification instead of guessing.

**Validation:** Can every material claim be traced to the underlying change?

## Criterion 10: Poor terminology and inconsistent naming

**Look for:**
- Different words for the same component or behaviour.
- Nonstandard descriptions of statuses or workflows.
- Incorrect use of established platform terminology.
- Confusion between a job, workflow, check, status, and execution.
- Casual substitutes for established product terminology.

**Remediation:**
- Use the product's official terminology.
- Match platform-specific names to the actual feature involved.
- Maintain consistent capitalisation and naming.
- Avoid unnecessary jargon, but retain terms readers need to recognise.
- Distinguish technically different concepts instead of treating them as synonyms.

**Validation:** Is the terminology both technically accurate and recognizable to the intended reader?

## Criterion 11: Unnecessary verbosity and repetitive phrasing

**Look for:**
- Multiple sentences describing one small change.
- Repeated phrases such as "this means that" or "it is now possible to."
- Long introductory clauses that delay the main point.
- Multiple descriptions of the same effect.
- Excessive explanations of simple fixes.

**Example:**

Poor: "An issue has been resolved where GitHub checks that had not yet started were previously being treated as failures, and this behaviour has now been changed."

Better: "GitHub checks that haven't started are no longer marked as failed."

**Remediation:**
- State the change directly.
- Remove redundant background.
- Prefer one self-contained sentence for a small change.
- Expand only when the conditions, migration steps, or consequences justify it.

**Validation:** Can the note be shortened without sacrificing clarity or accuracy?

## Criterion 12: Robotic or formulaic release-note language

**Look for:**
- Every entry beginning with "Updated," "Improved," or "Fixed an issue where."
- Identical sentence patterns across multiple notes.
- Awkward attempts to turn every commit into a declarative sentence.
- Repeated generic references to "functionality," "behaviour," or "support."
- Writing that sounds like a list of automated paraphrases.

**Remediation:**
- Choose sentence structure based on the actual change.
- Favour natural phrasing over rigid templates.
- Vary construction where it improves flow.
- Use direct, change-focused statements.
- Retain consistent formatting and terminology without enforcing identical syntax.

**Validation:** Does each note communicate its change naturally, without sounding generated from a fixed sentence formula?

## Criterion 13: Incorrect relevance or prioritisation

**Look for:**
- Minor internal refactors presented as major product changes.
- Important fixes buried beneath housekeeping updates.
- Multiple notes about the same underlying change.
- Trivial commit details that offer no meaningful reader value.
- Breaking changes described without appropriate prominence.

**Remediation:**
- Evaluate reader impact before including a commit.
- Combine related commits into one coherent note.
- Exclude internal-only work from user-facing notes unless the audience needs it.
- Prioritise breaking changes, security-relevant changes, important fixes, and meaningful features.
- Distinguish release-note relevance from commit volume.

**Validation:** Would a reader benefit from knowing this information in the release notes?

## Criterion 14: Missing conditions, scope, or compatibility implications

**Look for:**
- Descriptions that omit when a change applies.
- Broad statements about behaviour that only affects certain workflows.
- Missing configuration requirements.
- Breaking changes without explanation of the affected users.
- Omitted migration or action requirements.

**Remediation:**
- Add essential conditions.
- Identify affected versions, platforms, integrations, or configurations where needed.
- Explain required user action for breaking changes.
- Include limitations when necessary to avoid misleading claims.
- Avoid expanding simple notes with conditions that don't affect understanding.

**Validation:** Does the note create a misleading impression about the scope or applicability of the change?

---

# 3. Release-note transformation rules

Commit descriptions are **inputs to interpretation, not final copy**.

Use the following transformation process for each candidate release note.

### Step 1: Establish the actual change

Identify:

- Affected component or feature.
- Previous behaviour, if relevant and known.
- New behaviour.
- Conditions under which the change applies.
- Whether the change is user-visible.
- Available evidence supporting the description.

Use code changes, tests, PR context, and documentation where available. A commit title alone may be insufficient.

### Step 2: Classify the change

Choose the most accurate category:

| Category | Include when |
|---|---|
| Added | A new capability or feature was introduced. |
| Changed | Existing behaviour was modified. |
| Fixed | Incorrect behaviour was corrected. |
| Improved | An existing capability was enhanced in a demonstrable way. |
| Deprecated | Functionality remains available but is scheduled or intended for removal. |
| Removed | Previously available functionality was removed. |
| Security | A security-relevant change can be accurately and appropriately disclosed. |
| Breaking | Existing integrations, configurations, workflows, or expected behaviour may require user action. |

Do not assume that the prefix of a commit message determines its release-note category.

### Step 3: Select the communication level

Decide whether the release note should emphasise:

**User behaviour:** What users can now do or experience differently.

**System behaviour:** How the software now responds to specific conditions.

**Technical behaviour:** Changes to APIs, configuration, integrations, data formats, or other details relevant to technical readers.

Choose the level appropriate to the release-note audience.

### Step 4: Write the statement

Use the clearest natural construction for the change.

Useful patterns include:

- "[Feature] now supports [capability]."
- "[Component] no longer [incorrect behaviour]."
- "Fixed [specific problem] when [condition]."
- "[Action] now requires [condition]."
- "Added [capability] to [component]."
- "[Component] now [behaviour] instead of [previous behaviour]."
- "Removed [obsolete capability]."

These are optional structures, not mandatory templates. Do not force every change into one.

### Step 5: Validate meaning

Check that the note does not:

- Change the meaning of the commit.
- Introduce an unsupported feature or outcome.
- Overstate the scope of the change.
- Misrepresent technical behaviour.
- Confuse one status, operation, or component with another.
- Omit conditions necessary for accuracy.

### Step 6: Edit for natural language

Check that the sentence:

- Sounds natural when read aloud.
- Uses idiomatic subject-verb relationships.
- Uses appropriate terminology.
- Avoids artificial simplicity.
- Makes the change immediately understandable.
- Avoids unnecessary implementation details.
- Does not sound like a mechanically paraphrased commit.

---

# 4. Examples of problematic release notes and remediation

The following are illustrative rewrites. Their technical claims must be verified against the actual changes before publication.

| Problematic writing | Improved release note |
|---|---|
| "A check that GitHub will not start is no longer called a failure." | "GitHub checks that fail to start are no longer reported as failed." |
| "The tooling check says which tool is not ready before the kit builds anything." | "The kit now reports missing tools before starting the build." |
| "The first upload waits for your yes." | "The first upload now requires confirmation." |
| "Scripts check rules they can judge." | "Validation scripts now check rules that can be evaluated automatically." |
| "An issue was fixed where the configuration file was not being found correctly." | "Fixed configuration-file detection in the affected workflow." |
| "Improved the handling of errors that happen when connecting." | "Connection errors now display more specific messages." |
| "The system can now make the output more easy to read." | "Generated output now uses clearer formatting." |
| "A change was made so invalid inputs do not go through." | "Invalid inputs are now rejected before processing." |
| "Fixed a problem where retries did not happen like they should." | "Fixed missing retries after failed requests." |
| "The tool gives a warning if the file is not there." | "The tool now warns when a required file is missing." |

**Important:** A linguistically better sentence is not necessarily a factually correct release note. For example, "not started" and "failed to start" describe different states. The implementation must determine which one is appropriate.

---

# 5. Remediation methods

Reviewers should select the correction method that addresses the actual issue rather than rewriting every sentence automatically.

| Method | Use when | Corrective action |
|---|---|---|
| Semantic reconstruction | The original sentence is awkward or confusing | Rebuild the sentence from the verified technical meaning. |
| Terminology correction | Technical terms are inaccurate or inconsistent | Replace them with established, correct terminology. |
| Behavioural translation | The note describes implementation rather than outcome | Describe observable software behaviour. |
| Clarification | Multiple meanings are possible | Make the component, action, or condition explicit. |
| Simplification | Wording is unnecessarily complicated | Remove complexity without weakening precision. |
| Precision enhancement | Wording is too generic | Add supported, specific information. |
| Tone correction | Language feels childish, robotic, or artificially casual | Use natural, professional language. |
| Consolidation | Multiple commits describe one change | Produce one coherent release-note entry. |
| Scope correction | The note claims more than the implementation supports | Narrow the statement to verified behaviour. |
| Reclassification | The note is assigned the wrong category | Categorise it by the actual nature of the change. |
| Omission | The change is irrelevant or purely internal | Exclude it from user-facing notes. |
| Verification request | Available evidence cannot establish the meaning | Flag the change rather than inventing an interpretation. |

---

# 6. Review severity and prioritisation

Use three severity levels to guide remediation.

### Critical: Must fix before publication

- Technically incorrect statements.
- Fabricated or unsupported claims.
- Ambiguous wording that materially changes meaning.
- Incorrect scope, conditions, or compatibility claims.
- Misleading statements about failures, permissions, security, or data handling.
- Breaking changes missing essential action requirements.

**Action:** Verify the underlying change and rewrite or withhold the note.

### Major: Should fix before publication

- Awkward or unnatural sentence construction.
- Mechanical paraphrasing of commit messages.
- Artificially simplified language.
- Generic descriptions with insufficient information.
- Excessive implementation detail.
- Unclear explanation of what changed.
- Incorrect or inconsistent terminology.

**Action:** Rewrite using the appropriate remediation method and validate the result.

### Minor: Editorial refinement

- Unnecessary verbosity.
- Repetitive openings.
- Slightly awkward rhythm.
- Minor tone inconsistencies.
- Redundant context or wording.
- Nonessential stylistic inconsistencies.

**Action:** Refine where the change meaningfully improves readability. Avoid unnecessary editing.

---

# 7. Recommended end-to-end review workflow

**Pass 1: Analyse source changes**

Review the commits, diffs, PRs, and available context. Identify actual behaviour changes and distinguish user-facing improvements from internal maintenance.

**Pass 2: Extract release-worthy information**

Select changes that matter to the audience. Group related commits, remove duplicates, and classify each change.

**Pass 3: Draft from verified meaning**

Write release notes from the extracted facts. Do not simply rewrite or paraphrase commit messages.

**Pass 4: Diagnose writing quality**

Evaluate each entry using the 14 criteria in this framework. Identify semantic, structural, stylistic, and technical issues.

**Pass 5: Apply remediation**

Use the least complicated intervention that solves the issue. Rewrite completely when the original construction is fundamentally unnatural.

**Pass 6: Verify factual accuracy**

Compare every meaningful claim against the source evidence. Confirm component names, status definitions, conditions, scope, and impact. Flag unresolved ambiguity.

**Pass 7: Review the full release**

Check consistency, grouping, ordering, terminology, repetition, and the overall balance between detail and readability.

**Pass 8: Final publication review**

Remove unsupported claims, redundant notes, unnecessary implementation details, and wording that does not meet the acceptance standard.

---

# 8. Final quality-control checklist

Every release-note entry should pass the following checks before publication.

### Meaning and factual accuracy

- [ ] The underlying change has been understood.
- [ ] The note accurately reflects the implementation.
- [ ] The affected component or behaviour is correctly identified.
- [ ] Important conditions and limitations are preserved.
- [ ] No unverified benefits or guarantees have been introduced.
- [ ] Technical terminology is accurate.

### Natural writing quality

- [ ] The sentence reads naturally and idiomatically.
- [ ] Subject-verb relationships are clear and appropriate.
- [ ] The writing is not artificially simplified.
- [ ] There is no awkward personification or unnatural word choice.
- [ ] The language is neither childish nor unnecessarily formal.
- [ ] The sentence does not sound like a mechanical paraphrase.

### Communication quality

- [ ] The note clearly identifies what changed.
- [ ] The note is specific enough to be informative.
- [ ] The description is appropriate for the intended audience.
- [ ] Implementation details are included only when relevant.
- [ ] The note provides useful information rather than generic filler.
- [ ] The change is communicated as directly as possible.

### Release-level quality

- [ ] The entry is relevant to the release-note audience.
- [ ] Related commits have been consolidated where appropriate.
- [ ] Duplicate information has been removed.
- [ ] The category and priority are appropriate.
- [ ] Terminology and formatting are consistent.
- [ ] Breaking changes and required user actions are clearly communicated.

---

# 9. Acceptance standard

A release note is acceptable when a reader can understand the actual change on the first reading, without needing to interpret developer shorthand or mentally reconstruct awkward wording.

The final writing should be:

**Natural, not robotic.**

**Precise, not vague.**

**Accessible, not childish.**

**Technical when necessary, not by default.**

**Concise, not incomplete.**

**Change-focused, not code-focused.**

**Accurate, not speculative.**

### Non-negotiable principles

1. **Understand before rewriting.** Never substitute fluent wording for understanding the source change.
2. **Preserve meaning.** Do not change technical behaviour, scope, or guarantees for the sake of better prose.
3. **Write naturally.** Avoid unusual sentence constructions that exist only because they mirror developer shorthand.
4. **Communicate the change.** The reader should understand what is different in this release.
5. **Prefer precision over forced simplicity.** Use terminology that communicates the behaviour correctly.
6. **Avoid unsupported benefits.** Do not invent impact, performance gains, or improvements.
7. **Prioritise reader value.** Not every commit needs a release note.
8. **Don't rewrite for its own sake.** Leave already clear, natural, accurate sentences alone.

**Final editorial test:**

*Would an experienced technical writer, familiar with the product and its intended audience, naturally describe this change in this way?*

If not, reconsider the sentence construction, terminology, and underlying interpretation before publication.
