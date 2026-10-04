#!/usr/bin/env python3
# grade-parse.py: turn one grader's raw output into a result file.
#
# The grader returns a single JSON object. Where that text does not parse the
# run is refused and left out of the rate, because a half-graded run counted as
# a pass is exactly the fault that a strict parser exists to prevent.
#
# Two narrow exceptions are recovered here. The first is a grader that wrote a
# whole grading and then ended its turn one closing brace short. The second is
# the mirror: a whole grading followed by a stray closing brace. Every verdict,
# held, and held_note are already present; only a brace is wrong. That run is
# complete and is graded. A run truncated anywhere earlier is still refused, and the
# difference is enforced rather than trusted. Do not widen this into a lenient
# parser: the point is that a grading cut off in the middle never counts.

import json
import sys

MAX_TRAILING_BRACES = 5


def complete_grading(obj):
    # A whole grading carries every field the contract names, and held_note is
    # the last of them. If the object parses and held_note is present and set,
    # with verdicts and held before it, nothing up to the end was truncated.
    if not isinstance(obj, dict):
        return False
    verdicts = obj.get("verdicts")
    if not isinstance(verdicts, dict) or not verdicts:
        return False
    if "held" not in obj:
        return False
    note = obj.get("held_note")
    return isinstance(note, str) and note.strip() != ""


def recover_trailing_braces(text):
    # Append one closing brace at a time, up to a small ceiling, and accept the
    # first result that both parses and carries every named field. Anything else
    # returns None and stays refused.
    for count in range(1, MAX_TRAILING_BRACES + 1):
        try:
            candidate = json.loads(text + ("}" * count))
        except Exception:
            continue
        if complete_grading(candidate):
            candidate["recovered"] = (
                "closed %d trailing brace%s the grader left open"
                % (count, "" if count == 1 else "s")
            )
            return candidate
    return None


MAX_EXTRA_BRACES = 2


def recover_extra_braces(text):
    # The mirror case: a whole grading followed by a stray closing brace or two.
    # Take one off at a time and accept the first result that parses and carries
    # every named field. Only braces are removed, so a grading followed by any
    # other text stays refused.
    trimmed = text
    for count in range(1, MAX_EXTRA_BRACES + 1):
        if not trimmed.endswith("}"):
            return None
        trimmed = trimmed[:-1].rstrip()
        try:
            candidate = json.loads(trimmed)
        except Exception:
            continue
        if complete_grading(candidate):
            candidate["recovered"] = (
                "removed %d extra closing brace%s after the grading"
                % (count, "" if count == 1 else "s")
            )
            return candidate
    return None


def parse(raw_path, number):
    try:
        outer = json.load(open(raw_path))
    except Exception:
        return {"scenario": int(number), "error": "grader produced no output"}

    text = (outer.get("result") or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    recovered = recover_trailing_braces(text) or recover_extra_braces(text)
    if recovered is not None:
        return recovered

    return {
        "scenario": int(number),
        "error": "grader output was not JSON",
        "raw": text[:2000],
    }


def main():
    raw_path, out_path, number = sys.argv[1], sys.argv[2], sys.argv[3]
    json.dump(parse(raw_path, number), open(out_path, "w"))


if __name__ == "__main__":
    main()
