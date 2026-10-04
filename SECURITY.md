# Reporting a security problem

AI Build Kit is a set of instructions a coding agent follows. Those instructions
run shell commands in your project and handle the file where your keys and
passwords live, so a problem here can matter beyond the kit itself.

## Report it privately

Use GitHub's private vulnerability reporting on this repository: open the
Security tab and choose "Report a vulnerability". That message is visible only
to the maintainers.

Please do not open a public issue for a security problem. The public issue
tracker is the right place for everything else, and
[CONTRIBUTING.md](CONTRIBUTING.md) explains what to put in one.

## What helps

Say what you expected, what happened instead, and the smallest set of steps that
reproduces it. Name the kit version and how it was installed. Remove passwords,
tokens, personal data, and private project details before sending anything.

You do not need to prove the problem is exploitable, and you do not need to
suggest a fix. A clear description of behaviour that looks wrong is enough.

## What to expect

An acknowledgement, then an assessment of whether the report affects released
files or only the maintainer source. A fix that changes what the kit ships
arrives in a numbered release with public notes, and the notes will credit you
unless you would rather they did not.

This is a small project with no service behind it and no paid support, so there
is no response-time commitment. Reports are read and taken seriously.

## What is out of scope

The coding agents the kit runs on, and the services a project connects to,
belong to their own vendors. A problem in Claude Code, Cursor, Gemini CLI,
GitHub, or a service your project uses should go to that vendor. If the kit
tells people to use one of them in an unsafe way, that part is ours.
