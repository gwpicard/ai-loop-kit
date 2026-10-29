# Writing Quality Review and Remediation Framework

## Purpose

Review the writing for language that feels artificially simplified, vague, mechanically constructed, awkward, or unnatural.

The goal is **clear, precise, natural, and audience-appropriate writing**, not simply shorter sentences, simpler vocabulary, or a more casual tone.

For each issue, identify:

1. **What to look for:** the symptom or pattern.
2. **Why it is problematic:** how it affects understanding or quality.
3. **How to remedy it:** the available approaches for improving the wording.
4. **How to validate the change:** whether the revision actually improves the writing without changing its meaning.

---

## 1. Artificial or forced simplicity

**Look for:**
- Complex concepts reduced to overly basic words.
- Short sentences that sacrifice meaning or specificity.
- Childlike expressions in otherwise professional or technical writing.
- Avoidance of standard terminology despite its being appropriate for the audience.
- Language that appears simplified for its own sake.

**Example**

Before: "The first upload waits for your yes."

After: "The first upload requires your confirmation."

**Remedies:**
- Replace overly basic expressions with natural, established terminology.
- Use technical vocabulary when it communicates the concept more accurately.
- Prioritise ease of understanding over ease of reading individual words.
- Adjust complexity to the audience rather than enforcing simplicity universally.

**Key consideration:** Plain language does not mean elementary language.

## 2. Unnatural word choices and verb-subject relationships

**Look for:**
- Verbs that don't naturally fit their subjects or objects.
- Systems, processes, or tools described as performing oddly human actions.
- Words that are technically understandable but unusual in context.
- Phrasing that resembles a literal translation or awkward paraphrase.

**Example**

Before: "The tooling check says which tool is not ready."

After: "The tooling check identifies tools that are unavailable."

**Remedies:**
- Choose verbs that accurately describe the underlying operation.
- Use conventional expressions familiar to the audience.
- Replace forced personification when it introduces awkwardness or ambiguity.
- Prefer verbs such as *detects, identifies, reports, verifies, requires,* or *generates* when they accurately describe the action.

**Key consideration:** Personification is not inherently wrong. "The system warns users" is natural. The problem is unnatural or misleading word choice.

## 3. Semantic vagueness and low information density

**Look for:**
- Generic terms such as *thing, stuff, result, ready, check, do,* and *make* when more specific terms are needed.
- Sentences that sound meaningful without communicating much.
- Statements that leave readers unable to identify what actually happens.
- Multiple interpretations of the same phrase.

**Example**

Before: "You turn a request into one task with a result you can check."

After: "Each request becomes a defined task with an output that can be reviewed against its acceptance criteria."

**Remedies:**
- Identify the specific action, object, output, or condition being described.
- Replace generic language with the actual concept.
- Explain what is being checked and against which criteria.
- Remove words that add length without adding useful meaning.

**Key consideration:** Don't introduce specifics that aren't supported by the underlying product or process.

## 4. Ambiguous actions and missing operational detail

**Look for:**
- Sentences that describe an outcome but not the mechanism when the mechanism matters.
- Missing actors: who performs the action?
- Unclear sequence: what happens first, and what follows?
- Unspecified conditions: when does something happen?
- Claims that don't distinguish between checking, reporting, blocking, and enforcing.

**Example**

Before: "Scripts check rules they can judge."

After: "Validation scripts check whether objectively testable rules have been followed."

**Remedies:**
- Clarify the actor, action, target, and expected result.
- Specify important conditions or dependencies.
- Distinguish different operations rather than treating them as interchangeable.
- Add operational detail where it helps the reader understand functionality.

**Key consideration:** A script that checks a rule does not necessarily enforce that rule. Don't strengthen claims during editing.

## 5. Artificial conversational language

**Look for:**
- Forced friendliness or excessive casualness.
- Phrases such as "your yes" used in contexts where "approval" or "confirmation" is more natural.
- Oversimplified explanations that sound patronising.
- Attempts to make technical functionality sound playful without a clear reason.
- Informality that feels inconsistent with the surrounding content.

**Remedies:**
- Use straightforward, natural language without performing friendliness.
- Match tone to context: documentation, UI copy, marketing, and instructions require different treatment.
- Prefer conversational clarity over conversational gimmicks.
- Remove embellishments that distract from the actual message.

**Key consideration:** Natural writing can be warm and accessible without sounding overly familiar.

## 6. Mechanical or repetitive sentence construction

**Look for:**
- Repeated short declarative sentences with the same rhythm.
- Excessive repetition of "You...", "The system...", or "It...".
- Identical sentence patterns across consecutive sections.
- Unnecessary fragmentation of closely related ideas.
- Writing that feels assembled from isolated statements rather than developed as coherent prose.

**Remedies:**
- Vary sentence length and structure where useful.
- Combine closely related statements.
- Introduce natural transitions where relationships need clarification.
- Restructure paragraphs around logical progression rather than sentence-by-sentence uniformity.
- Preserve short sentences where they communicate an important point efficiently.

**Key consideration:** Variation is a tool, not a requirement. Consistency can be valuable in procedural documentation.

## 7. Weak, generic, or imprecise verbs

**Look for:**
- Overreliance on *do, make, get, have, put, say,* and *check*.
- Generic verbs that hide what a system actually does.
- Weak constructions where a precise verb could express the meaning more directly.
- Repetition of the same verb to describe genuinely different operations.

**Remedies:**
- Identify the actual operation being performed.
- Use verbs that distinguish between detecting, validating, generating, transforming, reporting, and approving.
- Prefer active constructions when they clarify responsibility.
- Avoid replacing simple verbs with elaborate ones unless precision or naturalness improves.

**Key consideration:** "Check" is not a bad word. It is a bad choice when the reader needs to know whether the operation validates, detects, reports, or prevents something.

## 8. Missing context and unclear significance

**Look for:**
- Statements that describe a feature without explaining its purpose.
- Technical details disconnected from their benefit or outcome.
- Instructions that assume knowledge the reader may not have.
- Constraints mentioned without enough context to understand their role.

**Remedies:**
- Add the reason or consequence when relevant.
- Connect a feature to its practical function.
- Explain unusual constraints.
- Introduce concepts before relying on them.
- Avoid adding explanatory filler when the purpose is already obvious.

**Example**

Before: "The kit checks tools before building."

After: "The kit checks required tools before building so missing dependencies can be identified early."

## 9. Awkward phrasing that is grammatically correct

**Look for:**
- Sentences that make sense only after rereading.
- Word combinations a fluent writer would rarely choose.
- Unnatural prepositions, modifiers, or word order.
- Phrasing that sounds like a sentence has been paraphrased repeatedly.
- Expressions that are technically valid but don't match normal usage in the subject area.

**Remedies:**
- Rewrite the sentence from the intended meaning rather than editing words individually.
- Use standard constructions and terminology.
- Read the sentence aloud to check its rhythm and naturalness.
- Compare alternative phrasings based on clarity and precision, not novelty.
- Remove unnecessarily unusual expressions.

**Key consideration:** Grammatically correct is not the same as idiomatic, clear, or well-written.

## 10. Loss of precision during simplification or rewriting

**Look for:**
- Important conditions removed to make a sentence shorter.
- Scope changing from *first time* to *every time*, or from *some* to *all*.
- Possibilities rewritten as certainties.
- Capabilities described as guarantees.
- Distinct operations treated as equivalent.
- New technical claims added to make the sentence sound more authoritative.

**Example**

Original: "The first upload requires your approval."

Incorrect rewrite: "Nothing is ever uploaded without your approval."

These are not necessarily equivalent. The original could describe a one-time authorisation; the rewrite promises approval for every upload.

**Remedies:**
- Preserve the original scope, conditions, and limitations.
- Check whether the rewrite makes a stronger or weaker claim.
- Verify technical terminology and behaviour.
- Separate stylistic improvement from factual or functional changes.
- Flag missing information instead of inventing it.

**Key consideration:** Better-sounding writing that changes the meaning is not an improvement.

## 11. Excessive abstraction and generic benefit statements

**Look for:**
- Claims such as "improves the workflow," "makes things easier," or "provides better results" without concrete explanation.
- Abstract nouns replacing identifiable actions.
- Sentences that could describe almost any product or feature.
- Repeated promises of efficiency, simplicity, or reliability without supporting detail.

**Remedies:**
- Replace generic benefits with specific actions or effects.
- Identify what changes for the user.
- Connect benefits to actual capabilities.
- Remove claims that can't be substantiated.

**Key consideration:** Specificity is more persuasive than generic positivity.

## 12. Inconsistent register and audience alignment

**Look for:**
- Sudden shifts between technical, casual, corporate, and instructional language.
- Elementary explanations alongside unexplained specialist vocabulary.
- Terminology that is too vague for experts or too specialised for general users.
- Different names for the same concept without a reason.
- Overly formal wording used to describe simple actions.

**Remedies:**
- Establish the intended reader's level of familiarity.
- Choose and maintain a consistent register.
- Define essential terminology when needed.
- Use the same term for the same concept throughout.
- Allow different sections to vary in technical depth when their purpose requires it.

---

## Remediation strategies: how to decide what to change

Not every writing problem needs the same intervention.

| Strategy | Use when | Action |
|---|---|---|
| **Substitution** | One word or expression is unnatural | Replace it with a more idiomatic or precise alternative. |
| **Clarification** | Meaning is ambiguous | Make the actor, action, condition, or outcome explicit. |
| **Specification** | Language is too generic | Replace vague concepts with supported, concrete details. |
| **Restructuring** | The sentence is awkward or mechanically constructed | Rebuild it around the intended meaning. |
| **Consolidation** | Related ideas are unnecessarily fragmented | Combine sentences into a clearer explanation. |
| **Expansion** | Essential context is missing | Add the minimum detail necessary for comprehension. |
| **Reduction** | A sentence is padded or repetitive | Remove redundant or low-value wording. |
| **Terminology correction** | Vocabulary misrepresents the actual operation | Replace it with technically accurate terminology. |
| **Tone adjustment** | Language is too casual, childish, formal, or robotic | Align the register with the audience and context. |
| **Meaning verification** | The rewrite risks changing the original claim | Compare conditions, scope, certainty, and implied guarantees. |

## Recommended review process

**Pass 1: Understand the intended meaning.** Before editing, establish what the text is actually supposed to communicate. Identify the actors, operations, outcomes, conditions, and intended audience.

**Pass 2: Diagnose the writing.** Review the text against the 12 criteria above. Mark anything unnatural, ambiguous, generic, repetitive, imprecise, or misaligned with the audience.

**Pass 3: Select the appropriate remedy.** Don't automatically rewrite the entire sentence. Decide whether it needs substitution, clarification, restructuring, expansion, reduction, or a combination.

**Pass 4: Rewrite for meaning and naturalness.** Produce wording that communicates the original intent naturally and precisely. Prefer conventional language over inventive phrasing, but avoid needlessly replacing simple words with technical jargon.

**Pass 5: Validate the revised text.** Check the revision against the original meaning and the intended audience. Ensure that no unsupported facts, guarantees, conditions, or functionality have been introduced.

**Pass 6: Review the surrounding passage.** Read the revised sentence in context. Check consistency of tone, terminology, sentence rhythm, and logical flow. A sentence can work independently but feel unnatural within a paragraph.

---

## Final quality-control checklist

Before approving any revised passage, ask:

- [ ] **Clarity:** Can the intended reader understand it without unnecessary interpretation?
- [ ] **Precision:** Do the words accurately describe the actual concept, action, or behaviour?
- [ ] **Naturalness:** Does the phrasing sound idiomatic rather than mechanically simplified or paraphrased?
- [ ] **Specificity:** Is the text sufficiently concrete for its purpose?
- [ ] **Meaning preservation:** Has the original scope, certainty, and technical meaning been retained?
- [ ] **Audience fit:** Does the vocabulary match the reader's knowledge and the content's purpose?
- [ ] **Tone:** Is the writing professional or conversational to the appropriate degree, without forced friendliness?
- [ ] **Information value:** Does each sentence contribute a useful idea, instruction, or explanation?
- [ ] **Coherence:** Do sentences connect logically, with a natural rhythm and consistent terminology?
- [ ] **Efficiency:** Could anything be removed without losing important meaning?
- [ ] **Factual integrity:** Are all descriptions and claims supported by the underlying information?
- [ ] **Readability:** Can the passage be understood on a first reading without sounding unnatural or oversimplified?

## Acceptance standard

A successful revision should be:

**Natural without being casual.**

**Simple without being simplistic.**

**Precise without being unnecessarily technical.**

**Concise without omitting important information.**

**Readable without sounding mechanically constructed.**

**Faithful to the original meaning without reproducing its weaknesses.**

The objective is not to maximise simplicity, technicality, brevity, or sophistication. It is to find the most natural and accurate expression of the intended meaning for the intended reader.

If a rewrite sounds more polished but communicates less, changes the claim, or introduces unnecessary complexity, it should not be considered an improvement.
