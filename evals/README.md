# Agent Quality Evaluation

This directory evaluates answer quality for the RAG Agent and the analytics/operations Agent. It complements k6 load tests:

- k6 answers: how fast and stable is it?
- these evals answer: is the answer correct, grounded, safe, and permission-aware?

## Files

- `rag_cases.json`: fixed RAG quality cases.
- `analytics_cases.json`: fixed operations Agent quality cases.
- `agent_quality_eval.py`: runner that calls the live Python Agent and writes reports.
- `reports/`: generated JSON and CSV reports.

The case set is business-specific. It borrows coverage ideas from public RAG and text-to-SQL benchmarks, but the cases
are tailored to BlogsLike schemas, permissions, Redis/RabbitMQ/RAG behavior, and Agent routes.

Current coverage:

- RAG: fact, summary, citation, no-answer, permission, memory, security, cache.
- Analytics: overview, hot content, low interaction, comment quality, growth, tags, chart, SQL safety, permission,
  custom SQL, ambiguous questions, recent content.

## Authentication

The runner needs an Agent token. You can provide it directly:

```powershell
$env:AGENT_TOKEN='replace_with_agent_token'
python evals\agent_quality_eval.py --target rag
```

Or let it login through Java and request `/agent/token`:

```powershell
$env:EVAL_USERNAME='admin'
$env:EVAL_PASSWORD='your_password'
python evals\agent_quality_eval.py --target all
```

Analytics cases require an ADMIN token. USER tokens are expected to be denied for analytics.

Some cases define `requiredAuthRole`. If your current token role does not match, the runner marks the case as `SKIPPED`
instead of failed. Run once with an ADMIN token and once with a USER token to cover both positive and permission-denied
analytics behavior.

## Default Endpoints

- Java API: `http://127.0.0.1:9199/api`
- Python Agent: `http://127.0.0.1:8081`

Override them if needed:

```powershell
python evals\agent_quality_eval.py --java-base http://127.0.0.1:9199/api --agent-base http://127.0.0.1:8081
```

## Run

RAG only:

```powershell
python evals\agent_quality_eval.py --target rag
```

Analytics only:

```powershell
python evals\agent_quality_eval.py --target analytics
```

Both:

```powershell
python evals\agent_quality_eval.py --target all
```

## Scoring

RAG checks:

- business response code
- answer presence
- expected keyword coverage
- forbidden keyword absence
- citation presence when required
- confidence threshold
- cache metadata visibility

Analytics checks:

- business response code
- expected status such as `DENIED` or `FAILED`
- expected keyword coverage
- execution plan presence
- SQL safety results
- destructive SQL keyword absence

The generated report includes pass rate, average score, average latency, and per-case details.
Skipped cases are excluded from pass rate.

## Recommended Workflow

1. Run k6 low-concurrency performance test.
2. Run these quality evals immediately after.
3. Increase k6 concurrency gradually.
4. Run quality evals again and compare pass rate, score, and latency.

If QPS improves but quality drops, treat that as a failed Agent performance result.
