# Shared part: the Next.js container and its health route

Every recipe that builds with Next.js and hosted Supabase links this part,
whichever host runs the app. The project always carries the same Dockerfile. On
a host that runs containers, it is what runs in production. On a host that
builds the app its own way, such as Vercel, the host ignores it, and it still
does two jobs: it gives a local check that matches production, and it keeps a
way off that host, so moving to a host that runs containers changes the host
and nothing else.

How it works: The Dockerfile builds Next.js with `output: "standalone"` in `next.config.ts` and runs `node server.js` with `HOSTNAME=0.0.0.0` and `PORT=3000`, so the server answers from outside the container. It starts from a Node Alpine image, which carries `wget`, because a host that checks health from inside the container needs `curl` or `wget`, and a `node:*-slim` image has neither. It carries no `HEALTHCHECK` line: on a host that runs its own health check, such a line takes precedence over the host's settings, and one check on one route is enough. The route at `/api/health` makes one real round trip to the database, a count on one table through the Supabase client, and answers 200 with `status`, `database`, `commit` and `project`, or 503 when the query fails. The commit comes from the host's commit variable, which each recipe's going-live section names, and the project is the reference in the Supabase address. The route sets `export const dynamic = "force-dynamic"`, so Next.js never answers it from a copy made at build time. Next.js fixes public variables when it builds, so the image is built with the public Supabase address and key passed as build arguments.
The container gets its values from `.env.container`, a file git ignores that holds only the names in `.env.example`. It never gets `.env.local`, because other tools write their own tokens there, and a host's command-line tool can leave a sign-in token in it.
How it is checked: Before anything goes live, the kit checks Docker is running with `docker info`, builds the image with `docker build -t app-check .`, runs it with `docker run -d --name app-check -p 3000:3000 --env-file .env.container app-check`, and reads `curl -fsS http://localhost:3000/api/health`: 200, `"database":"ok"`. It then builds a second image with the database address pointed nowhere, and the same route answers 503 rather than claiming the tool is up. Afterwards `docker rm -f app-check` removes the container. `.env.container` holds no name missing from `.env.example`, its values never leave the machine, and the kit never shows them.
Who runs it: the kit
