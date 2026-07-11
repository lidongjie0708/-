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

## 4. Increase load gradually

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

## Notes

- Likes should use multiple users and multiple blogs. One user repeatedly liking one blog mostly tests duplicate-like handling.
- RAG and analytics may call external LLM/embedding services. Start with low concurrency to avoid cost and provider throttling.
- These scripts create test users and blogs with `lt_*` prefixes. Run against a test database when possible.
