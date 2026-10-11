# Setup

## Prerequisites

- Windows 11 with PowerShell 7 for the primary local workflow.
- Python 3.12 managed by `uv` 0.11.26.
- Docker Desktop/Engine with Compose v2.
- At least 10 GiB free disk; the planning assumption is approximately 4 GiB RAM available to the
  lab.

The first dependency and image installation requires internet access. Core operation should remain
usable offline after dependencies and images are cached; any stale vulnerability/source result must
be disclosed.

## Locked environment

From the repository root:

```powershell
uv sync --frozen --all-groups
Copy-Item .env.example .env
```

Replace every `CHANGE_ME` value in `.env`. Generate independent random values; do not reuse personal
or production credentials. One PowerShell option for generating a new value is:

```powershell
$bytes = [byte[]]::new(32)
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

Store the result only in `.env`. Do not paste it into issues, logs, screenshots, or documentation.
`COOKIE_SECURE=false` is allowed only for the documented loopback HTTP development environment. A
future non-loopback deployment requires TLS and a separate design review.

## Diagnose prerequisites

```powershell
./scripts/doctor.ps1
uv run python -m cyber_assess doctor
```

The checks report tool/runtime availability, Docker reachability, port 8000, writable local
directories, configuration presence, and source prerequisites without printing secret values.

## Initialize and start

```powershell
uv run python -m cyber_assess init --engagement ENG-001
uv run python -m cyber_assess lab up
uv run python -m cyber_assess lab seed --seed 42
```

Open `http://127.0.0.1:8000`. The database is intentionally not available on a host port. The app's
`/health` endpoint is a minimal liveness signal and must not expose database or secret details.

On the first successful seed, generated account passwords and TOTP secrets are saved to
`/app/runtime/initial-credentials.json` inside the private app runtime volume. Repeated seeding does
not overwrite that file. To retrieve it for your own local login, copy it to ignored runtime storage:

```powershell
New-Item -ItemType Directory -Force runtime | Out-Null
docker compose -p cybersecurity-itgc-lab cp app:/app/runtime/initial-credentials.json runtime/initial-credentials.json
```

View that local file privately. Do not include it in screenshots, terminal transcripts or exports.
The application uses generated credentials; personal passwords are unnecessary for this lab.

`init` refuses to overwrite an existing engagement. `lab stop` preserves data:

```powershell
uv run python -m cyber_assess lab stop
```

No automated cleanup command in this repository deletes unrelated files, containers, or volumes.
Any future reset command must display exact project-scoped targets and require an explicit flag.

## Validate the setup

```powershell
docker compose --env-file .env config --quiet
./scripts/check-repository.ps1
```

Expected command exit codes are `0` success, `1` execution failure, `2` invalid input/schema, `3`
missing prerequisite, and `4` integrity/publication-gate failure.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Docker check fails | Start Docker Desktop, wait for the engine, then rerun `doctor.ps1`. |
| Port 8000 is occupied | Stop the identified local process; do not publish the app on a broad interface. |
| Lock mismatch | Do not use an unlocked install. Reconcile `pyproject.toml` and `uv.lock` in a dedicated change. |
| Database is not healthy | Inspect `docker compose logs db`; never publish port 5432 as a shortcut. |
| OneDrive file contention | Keep database and runtime state in Docker volumes; source/docs may remain synchronized. |
