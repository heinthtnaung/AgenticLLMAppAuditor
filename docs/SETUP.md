# Setting up

What `audit` needs on the machine, how to install it, and the advisory database
it scans against. [The README](../README.md) has the short version, and
[USAGE.md](USAGE.md) what to do once it runs.

## Prerequisites

What a scan shells out to. "Tested with" is what is installed on the
development machine; no minimum is set for any tool but Python.

| Tool | For | Tested with | Minimum |
|---|---|---|---|
| Python | the CLI, the engine and the tests | 3.11.11 | 3.11, the `requires-python` in `pyproject.toml` |
| [Syft](https://github.com/anchore/syft) | building the SBOM | 1.52.0 | none set; the lock-file table in [USAGE.md](USAGE.md) was measured on 1.52 |
| [Trivy](https://trivy.dev) | the advisory database and the CVE join | 0.74.0 | none set; how the cache is found was measured on 0.74 |
| [Ollama](https://ollama.com) | the models: the council, escalation and the explanation, on this machine or a server `AUDITOR_REMOTE_SERVER=yes` names (optional) | 0.34.3 | none set |
| git | cloning a repository to audit (optional) | 2.43.0 | none set |
| npm | writing a missing `package-lock.json` (optional) | not recorded | none set |
| pytest | the tests (development only) | 9.1.1, pinned in `pyproject.toml` and `requirements.txt` | pinned |

The runtime is the standard library alone, so installing the package pulls in
no dependency. On the development machine Syft and Trivy came from Homebrew;
each project's page has its install steps.

## Installing

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

The install fetches a build backend, so it needs the corporate proxy **on**,
like `git clone`. `-e` installs in place, so an edit to `src/` takes effect
without reinstalling. Uninstalled, `PYTHONPATH=src python -m cli.main` runs the
same code and prints the same report.

## The advisory database is a separate step

```bash
trivy image --download-db-only
```

```
2026-09-22T12:06:33+08:00	INFO	[vulndb] Need to update DB
2026-09-22T12:06:33+08:00	INFO	[vulndb] Downloading vulnerability DB...
2026-09-22T12:06:33+08:00	INFO	[vulndb] Downloading artifact...	repo="mirror.gcr.io/aquasec/trivy-db:2"
2026-09-22T12:06:38+08:00	INFO	[vulndb] Artifact successfully downloaded	repo="mirror.gcr.io/aquasec/trivy-db:2"
```

Progress bar elided. The download is 116 MiB and lands in Trivy's cache:
`$TRIVY_CACHE_DIR` if that is set, else `$XDG_CACHE_HOME/trivy`, else
`~/.cache/trivy`.

**`audit` finds the cache the same way and hands it to the scan.** It reads the
same two variables in the same order, a relative `TRIVY_CACHE_DIR` taken from
where you run it, dates the database it finds there, and passes that directory
to Trivy as `--cache-dir`, so the database dated is the database scanned. Set
either variable for `audit` and set it for the download and for `trivy version`
too, or they read different caches. A relative `XDG_CACHE_HOME`, or no `HOME`
with neither variable set, is refused with `audit: …` and exit `2` rather than
followed into a temporary directory.

**A `cache.dir` in a `trivy.yaml` is never read.** The download follows one in
the directory it runs from, and `audit`'s `--cache-dir` overrides it, so a
cache moved that way is downloaded to and never scanned. Move it with a
variable.

It is a separate step because scans run offline, with `--skip-db-update`, so
that a scan is reproducible and pinned to a known database. Running `trivy`
yourself without that flag can update the cache as a side effect, and every
audit after it reads the newer database; to update it on purpose, run the
download above with the proxy on.

The cost of that choice: **Trivy alone, given an empty cache, produces a clean
report rather than an error.** It finds no advisories, exits 0, and nothing in
its output says the database was missing. So `audit` reads the database's own
build date, `UpdatedAt` in `db/metadata.json` inside that cache, before anything
is scanned, and exits `2` with nothing on stdout when that file is missing,
unreadable or carries no build date. A build date with no database beside it
gets past that check, and then Trivy refuses the offline scan, so `audit`
exits `2` with Trivy's own error.

**A stale database is not refused.** It is there and it has a date, so the run
goes ahead and every report carries that date: `advisory database built` in
the text header, `run.advisory_database.built_at` in JSON, and on the HTML page.
Nothing compares it with today, because `src/` reads no clock, so whether it is
too old is yours to judge. `trivy version` shows it beside the date Trivy calls
it due for an update:

```bash
trivy version
```

```
Version: 0.74.0
Vulnerability DB:
  Version: 2
  UpdatedAt: 2026-09-23 20:20:57.734988316 +0000 UTC
  NextUpdate: 2026-09-24 20:20:57.734987855 +0000 UTC
  DownloadedAt: 2026-09-24 06:03:45.881932713 +0000 UTC
```

## What `audit` asks Trivy

One offline run finds both the advisories and the secrets. For
`audit fetched/vulnscout`, it is:

```bash
trivy fs --format json --scanners vuln,secret --secret-config= --skip-db-update --offline-scan --disable-telemetry --skip-version-check --cache-dir ~/.cache/trivy fetched/vulnscout
```

`--scanners vuln,secret` asks for both scanners in one pass: the secret rules
are built into Trivy and read no database, so they add no download and no
network. `--secret-config=`, an empty path, is Trivy's way of saying built-in
rules only. Left to its default, Trivy reads a `trivy-secret.yaml` from wherever
`audit` is run, and one there that disables a rule makes the same tree report
fewer secrets with nothing said; that was measured on 0.74.0. The cache is the
one the preflight dated, as above.

## Fetching and scanning pull in opposite directions

The repository is an argument because fetching it needs the corporate proxy
**on** and scanning needs it **off**, so a command doing both would flip that
state mid-run. The advisory database download is out of band for the same
reason. Fetch once with the proxy on; scan what is on disk, offline, as often as
you like. The proxy section below puts both directions in a table.

The repository this project audits, and every example is recorded against, is
`https://github.com/savoirfairelinux/vulnscout`, cloned into `fetched/vulnscout`
and checked out at `df874ef0669e4a861a2480d7dda18a9fcb6d4d66`. The README's
quick start has the two commands.

## The proxy on this machine

A corporate HTTP proxy is set, and the two cases pull in opposite directions.

| Talking to | Proxy |
|---|---|
| a local service — Ollama, a dev server, anything on loopback | **off** |
| the internet — `git clone`, `trivy image --download-db-only` | **on** |

Before running anything that talks to a local service:

```bash
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
```

Without it, `urllib` sends loopback requests to the proxy, which answers 502.
The failure reads as the local service being down, which sends you looking in
the wrong place.

**This project and Ollama's own command line need none of it.** `audit`, the
live test and the measurement scripts reach Ollama through
`src/council/transport.py`, which opens every request with no proxy. With the
proxy set and `NO_PROXY` unset, a council run made all 40 of its calls and
`ollama ps` answered normally, so the `ollama` command does not send 127.0.0.1
to the proxy either. A server `AUDITOR_REMOTE_SERVER=yes` names is reached the
same way, directly and never through the proxy, though it sits on the network
rather than loopback (`docs/USAGE.md`). Other tools pointed at a local service,
such as `curl` or Python's `urllib` outside this project's transport, may still
need the export.
