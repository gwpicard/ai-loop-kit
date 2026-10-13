# fake-registry

A stand-in for the package registries. It holds no network code. Tests point
`dependency-check.py --registry` at this folder.

Layout, which mirrors what the real registries answer:

- `npm/<name>.json`: what npm answers for a package (`time` and `versions`).
  A scoped name has its own folder, `npm/@scope/name.json`.
- `pypi/<name>/<version>.json`: what PyPI answers for one release (`info` and
  `urls`).

The packages and what each one is for:

| Package | Why it is here |
|---|---|
| `old-mit`, `dual`, `@scope/pkg`, `legacy-licence` | old and allowed |
| `old-gpl` | old, licence not allowed |
| `fresh-mit` | released on 1 October 2026, too new on 6 October 2026 |
| `no-licence` | no licence given |
| `oldpy`, `classpy` | old and allowed (by expression, and by classifier) |
| `freshpy` | released on 2 October 2026, too new |
| `weirdpy`, `nolicencepy` | licence not allowed, and no licence |

The tests pass `--now 2026-10-06T00:00:00Z` so the ages never drift.
