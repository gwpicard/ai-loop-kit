# Reporting a security problem

AI Loop Kit is a set of scripts and instructions that a coding agent follows.
They run shell commands in your project and they handle the file where your
keys and passwords live. A fault here can reach beyond the kit.

## Report it privately

Use GitHub's private vulnerability reporting on this repository. Open the
Security tab and choose "Report a vulnerability". Only the maintainers can read
that message.

Do not open a public issue for a security problem. Use the public tracker for
everything else. `CONTRIBUTING.md` says what to put in an issue.

## What helps

Say what you expected, what happened and the shortest steps that show it. Name
the commit you used. Remove passwords, tokens, personal data and private
project details before you send anything.

You do not need to prove that the problem is exploitable. You do not need to
suggest a fix. A clear description of behaviour that looks wrong is enough.

## What to expect

You will get an acknowledgement. Then the maintainer will assess the report. If
the report is right, the maintainer will fix it in a pull request. Tell us if
you want credit for the report, and we will name you.

This is a small project with no paid support. There is no response-time
promise. Every report is read.

## What is out of scope

The coding agents the kit runs on, and the services a project connects to,
belong to their own vendors. Send a fault in Claude Code, GitHub or a service
your project uses to that vendor. If the kit tells people to use one of them in
an unsafe way, that part is ours.
