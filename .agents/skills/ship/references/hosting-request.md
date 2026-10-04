# The hosting request

Used by ship when the tool will run on a server this session cannot reach. The
request lives in the masterplan's "How it stays running" section. The person
carries it to whoever runs the server, and carries the answer back.

## Writing it

Write the request there, filled from the project itself rather than by asking
the person:

```
Hosting request
Repo:          <url>, branch <branch>
Lane:          internal (private network) | public (internet)
Port:          <port the tool listens on>
Env vars:      <names only>
Persist:       <paths that must survive a restart, or none>
Healthcheck:   <path, or none>
Build:         Dockerfile at root, image has curl or wget | lock file or requirements.txt, plus a Procfile | neither yet
Bind:          0.0.0.0 | reads HOST and PORT | 127.0.0.1 (not hostable yet)
```

Take the lane from the fit check: internal unless somebody outside the team
signs in or relies on it. Take Build from the files at the project's root,
and Bind from the address the server listens on when it starts. The server
builds and checks the tool from those two facts, so read them from the code
rather than from a plan. A tool that listens only on 127.0.0.1 cannot be
reached from outside its container: say so once, and record it. Env vars
carry names only; values are entered on the server. Never write a value, key, password or token into the request.

Where the project does not say, write `none` rather than guess. A project
on a recipe always has a health route, because the recipe's health section
names one, so there Healthcheck is that path and never `none`. Print the
same block in the reply, so the person can paste it, and say once: "This
tool needs a home. Take this request to whoever runs the server. Paste what
they send back here, and I will record it for the next /ship."

## Recording the answer

Whenever the person pastes an answer, in this session or a later one,
record its address and names under the request, and leave out any secret
value it carries.

## A later /ship

On a later /ship, read the recorded hosting request back instead of asking
again. Where no address is recorded under it, the request went out and no
answer came back. Say so plainly, print the request again for the person to
carry, and ask them to paste the answer here when it arrives. Where the
project has changed a field since, update that line from the project and
print the request again for the person to carry.
