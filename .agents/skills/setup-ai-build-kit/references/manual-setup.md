# Guided manual setup

Use when a step can only be completed by a human: creating an account,
provisioning a service, approving access, setting a secret, completing billing,
or performing an irreversible cutover.

1. Explain why the step is needed in one sentence, and where the step names a
   tool or service the person may not know, say what that is in one plain
   sentence too.
2. Give one step at a time.
3. Open or provide the exact page when possible.
4. State exactly what the person should see.
5. Never ask for a secret to be pasted into chat.
6. Tell the person where to store the value directly.
7. Confirm the result before moving on.
8. Ask for approval immediately before an irreversible action.
9. State how to reverse or recover the action.
10. Record service ownership, billing ownership, and where credentials are
    managed, without recording the credential itself.

A generated script is optional for a repeated procedure. The conversational
steps are canonical so the process works in every harness.

## Saving identity and online sharing

Before the first saved project version, check whether Git already has a
suitable name and email configured for this project.

Never copy the latest repository author's identity. That person may be a
template author, collaborator, automation account, or someone unrelated to
the current user.

Explain: "Each checkpoint carries a name and email label showing who saved
it. This does not create an online account or upload anything."

When the project stays local, offer to configure an identity for this
project only, and make clear it does not change any other project.

When the selected build path will require an online repository, ask whether
the person already has:

1. an account with the chosen repository service;
2. access to the project repository;
3. working authentication from the current environment.

Do not assume any of these from the presence of a remote address.

Guide missing account or access setup one step at a time, using the numbered
steps above; never ask for a password, access token, recovery code, or
private key to be pasted into chat.

If the person declines online setup, record the missing capability and say
which shared or live step cannot proceed yet. Do not silently treat the
project as ready for that route.
