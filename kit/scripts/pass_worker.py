"""One end-of-loop pass on the commit selected by the supervisor."""
import json
import os
import sys
import time

import common
import loop
import pass_


def result(project, settings, head, since):
    try:
        report, text = pass_.run_pass(project, settings, since, head=head)
    except Exception as e:
        report, text = {"errors": [str(e)]}, "## End-of-loop pass\n\nThe pass did not run: %s: %s\n" % (type(e).__name__, e)
    heading, separator, rest = text.partition("\n")
    text = heading + "\n\nCommit: `%s`.\n" % head + separator + rest
    return dict(head=since if report.get("errors") else head, time=time.strftime("%Y-%m-%d %H:%M"),
                text=text, sessions=report.get("sessions", 0), reason="; ".join(report.get("errors", [])),
                defects=len(report.get("confirmed", [])),
                inbox=sum(i.endswith("(inbox)") for i in report.get("issues", [])))


def main(argv):
    project, settings, head, since = argv[0], json.loads(argv[1]), argv[2], argv[3]
    os.environ["LOOP_PASS_WORKER"] = str(os.getpid())
    needed = json.loads(argv[4]) if len(argv) > 4 else True
    with common.build_environment(project):
        saved = result(project, settings, head, since) if needed else loop.last_pass(project)
        base = common.default_branch(project)
        landed = common.git(["log", "--format=- %s", "origin/%s..%s" % (base, head)], cwd=project)
        with common.settings_environment(settings):
            saved["summary"] = loop.summary(project, settings, head, landed)
        path = common.build_file(project, "pass", "result")
        with open(path, "w") as f:
            json.dump(saved, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
