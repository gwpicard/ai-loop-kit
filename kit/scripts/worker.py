"""One build in its own process: python3 worker.py <project> <issue> <replies as JSON>.
The loop starts it, polls it, and reads the result file it leaves in .lite/builds."""
import json
import os
import sys

import common
import loop


def main(argv):
    project, number, replies = os.path.abspath(argv[0]), int(argv[1]), json.loads(argv[2])
    last = loop.build_attempts(project, number, replies)
    os.makedirs(os.path.dirname(common.build_file(project, number, "result")), exist_ok=True)
    with open(common.build_file(project, number, "result"), "w") as f:
        json.dump({"last": last}, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
