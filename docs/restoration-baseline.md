# Restoration baseline

Recorded on July 13, 2026 from clean commit
`73329c8d01686063aced204ab8a25770c0ba61a0` before installing project
dependencies.

## Import probe

The bounded import probe used non-secret placeholder values and the host's
default Python 3.14.6:

```sh
env OPENAI_API_KEY=baseline-openai EXA_API_KEY=baseline-exa API_KEY=sk_v1_baseline \
  python3 -c 'import signal; signal.alarm(10); import main; print("main imported")'
```

It exited with status 1 at the first import:

```text
ModuleNotFoundError: No module named 'fastapi'
```

No provider client was imported or called because execution stopped on line 1
of `main.py`.

## Repository baseline

- `requirements.txt` and `environment.yml` describe different environments and
  neither supplies a frozen transitive dependency graph.
- There is no test suite, CI workflow, Dockerfile, or canonical verification
  command.
- `main.py`, `services/auth_service.py`, and `workflow/exa_search.py` read
  settings and construct shared services during import. Importing the app is
  therefore coupled to provider credentials and client setup.
- The supported restoration environment is Python 3.12.13 with uv 0.8.18. The
  lockfile replaces both legacy dependency manifests.

The probe is diagnostic evidence only. It does not prove provider access or a
working request path. The legacy root-level entrypoint remains outside the
supported path while the replacement `src/slipshark` service is built and
tested in later restoration tasks.
