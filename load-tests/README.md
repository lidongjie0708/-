# BlogsLike Load Tests

These scripts use k6. The safest local option on Windows is Docker, because it avoids installing k6 globally.

## 1. Confirm services

- Java API: `http://localhost:9199/api`
- Python Agent: `http://localhost:8081`
- Redis 8: `localhost:6380`
- RabbitMQ: `localhost:5672`
- MySQL: `localhost:3306`

For k6 running inside Docker, scripts use:

- `JAVA_BASE=http://host.docker.internal:9199/api`
- `AGENT_BASE=http://host.docker.internal:8081`

## 2. Prepare k6

Pull the image once:

```powershell
docker pull grafana/k6
```

## 3. Run small tests first

From the repository root:

```powershell
docker run --rm -v "${PWD}:/work" -w /work grafana/k6 run load-tests/k6/likes.js
docker run --rm -v "${PWD}:/work" -w /work grafana/k6 run load-tests/k6/blogs.js
docker run --rm -v "${PWD}:/work" -w /work grafana/k6 run load-tests/k6/rag.js
docker run --rm -v "${PWD}:/work" -w /work grafana/k6 run load-tests/k6/analytics.js
docker run --rm -v "${PWD}:/work" -w /work grafana/k6 run load-tests/k6/mixed.js
```

## 4. Run and save reports

The wrapper scripts save every run under `reports/k6/<timestamp>-<script>/`:

- `console.txt`: the full terminal output.
- `summary.json`: k6 structured summary from `--summary-export`.
- `meta.json`: script name, target endpoints, VU settings, and timing knobs.

PowerShell:

```powershell
.\load-tests\run-k6.ps1 -Script likes -Vus 40 -Users 40 -Blogs 40 -Hold 2m -ThinkSeconds 0.2 -Label step-01
.\load-tests\run-k6.ps1 -Script mixed -Vus 10 -Users 10 -Blogs 10 -Hold 2m -ThinkSeconds 1 -Label realistic
```

Bash:

```bash
load-tests/run-k6.sh likes VUS=40 USERS=40 BLOGS=40 HOLD=2m THINK_SECONDS=0.2 LABEL=step-01
load-tests/run-k6.sh mixed VUS=10 USERS=10 BLOGS=10 HOLD=2m THINK_SECONDS=1 LABEL=realistic
```

When testing from a separate load generator, override the service endpoints:

```bash
load-tests/run-k6.sh mixed JAVA_BASE=http://10.0.0.10:9199/api AGENT_BASE=http://10.0.0.10:8081 VUS=10 USERS=10 BLOGS=10 HOLD=2m THINK_SECONDS=1
```

Generated reports are ignored by git. Copy the key numbers into the final benchmark report, or archive the `reports/k6`
directory separately.

## 5. Increase load gradually

Example:

```powershell
docker run --rm -e VUS=20 -e HOLD=3m -v "${PWD}:/work" -w /work grafana/k6 run load-tests/k6/likes.js
```

Useful knobs:

- `VUS`: virtual users, default is conservative.
- `HOLD`: steady load duration.
- `USERS`: number of generated test users.
- `BLOGS`: number of seed blogs.
- `THINK_SECONDS`: delay between user actions.
- `JAVA_BASE`: override Java API base URL.
- `AGENT_BASE`: override Python Agent base URL.

Recommended per-round manual notes:

- server and load-generator machine specs
- script and parameter set
- `http_req_failed`, `http_req_duration` avg/p90/p95/max, requests, req/s, checks
- service CPU/memory peak from `docker stats` or cloud monitoring
- RabbitMQ queue backlog, model throttling, and timeout observations

## Notes

- Likes should use multiple users and multiple blogs. One user repeatedly liking one blog mostly tests duplicate-like handling.
- RAG and analytics may call external LLM/embedding services. Start with low concurrency to avoid cost and provider throttling.
- These scripts create test users and blogs with `lt_*` prefixes. Run against a test database when possible.
