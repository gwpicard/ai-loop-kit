"""One end-of-loop pass on the commit selected by the supervisor."""
import json
import sys
import time

import common
import pass_


def result(project, settings, head, since):
    try:
        report, text = pass_.run_pass(project, settings, since, head=head)
    except Exception as e:
        report, text = {"errors": [str(e)]}, "## End-of-loop pass\n\nThe pass did not run: %s: %s\n" % (type(e).__name__, e)
    heading, separator, rest = text.partition("\n")
    text = heading + "\n\nCommit: `%s`.\n" % head + separator + rest
    return dict(head=since if report.get("errors") else head, time=time.strftime("%Y-%m-%d %H:%M"),
                text=text, defects=len(report.get("confirmed", [])),
                inbox=sum(i.endswith("(inbox)") for i in report.get("issues", [])))


def main(argv):
    project, settings, head, since = argv[0], json.loads(argv[1]), argv[2], argv[3]
    saved = result(project, settings, head, since)
    path = common.build_file(project, "pass", "result")
    with open(path, "w") as f:
        json.dump(saved, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
