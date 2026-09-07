from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JAVA_BASE = "http://127.0.0.1:9199/api"
DEFAULT_AGENT_BASE = "http://127.0.0.1:8081"


@dataclass
class EvalAuth:
    java_token: str | None = None
    agent_token: str | None = None
    user_id: int | None = None
    role: str = "USER"


def main() -> int:
    parser = argparse.ArgumentParser(description="Quality evaluation for BlogsLike RAG and analytics agents.")
    parser.add_argument("--target", choices=["rag", "analytics", "all"], default="all")
    parser.add_argument("--java-base", default=os.getenv("JAVA_BASE", DEFAULT_JAVA_BASE))
    parser.add_argument("--agent-base", default=os.getenv("AGENT_BASE", DEFAULT_AGENT_BASE))
    parser.add_argument("--rag-cases", default=str(ROOT / "evals" / "rag_cases.json"))
    parser.add_argument("--analytics-cases", default=str(ROOT / "evals" / "analytics_cases.json"))
    parser.add_argument("--username", default=os.getenv("EVAL_USERNAME"))
    parser.add_argument("--password", default=os.getenv("EVAL_PASSWORD"))
    parser.add_argument("--role", default=os.getenv("EVAL_ROLE", "USER"))
    parser.add_argument("--agent-token", default=os.getenv("AGENT_TOKEN"))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("EVAL_TIMEOUT_SECONDS", "60")))
    parser.add_argument("--out-dir", default=str(ROOT / "evals" / "reports"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    auth = build_auth(args)
    all_results: list[dict[str, Any]] = []
    if args.target in {"rag", "all"}:
        all_results.extend(run_rag_cases(load_cases(args.rag_cases), args.agent_base, auth, args.timeout))
    if args.target in {"analytics", "all"}:
        all_results.extend(run_analytics_cases(load_cases(args.analytics_cases), args.agent_base, auth, args.timeout))

    report = build_report(all_results, args)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"agent-quality-{stamp}.json"
    csv_path = out_dir / f"agent-quality-{stamp}.csv"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, all_results)

    print_summary(report, json_path, csv_path)
    return 0 if report["summary"]["failed"] == 0 else 1


def build_auth(args: argparse.Namespace) -> EvalAuth:
    if args.agent_token:
        return EvalAuth(agent_token=args.agent_token, role=args.role.upper())
    if not args.username or not args.password:
        return EvalAuth(role=args.role.upper())

    login_res = request_json(
        "POST",
        f"{args.java_base}/login",
        {"username": args.username, "password": args.password},
        timeout=args.timeout,
    )
    data = login_res.get("data") or {}
    java_token = data.get("token")
    user = data.get("user") or {}
    if not java_token:
        return EvalAuth(role=args.role.upper())
    token_res = request_json(
        "POST",
        f"{args.java_base}/agent/token",
        None,
        headers={"Authorization": f"Bearer {java_token}"},
        timeout=args.timeout,
    )
    agent_token = ((token_res.get("data") or {}).get("token"))
    return EvalAuth(
        java_token=java_token,
        agent_token=agent_token,
        user_id=to_int(user.get("id")),
        role=str(user.get("role") or args.role).upper(),
    )


def run_rag_cases(cases: list[dict[str, Any]], agent_base: str, auth: EvalAuth, timeout: float) -> list[dict[str, Any]]:
    results = []
    for case in cases:
        started = time.perf_counter()
        result = base_result("rag", case)
        if should_skip_for_role(case, auth):
            result.update(status="SKIPPED", skipped=True, passed=None, errors=[skip_reason(case, auth)])
            results.append(result)
            continue
        if not auth.agent_token:
            result.update(status="AUTH_MISSING", passed=False, score=0.0, errors=["Missing AGENT_TOKEN or login credentials"])
            results.append(result)
            continue
        payload = {
            "question": case["question"],
            "sessionId": case.get("sessionId") or f"eval-rag-{case['id']}",
            "userId": case.get("userId", auth.user_id),
            "role": case.get("role", auth.role),
            "visibleScopes": case.get("visibleScopes", ["PUBLIC"]),
        }
        try:
            response = request_json(
                "POST",
                f"{agent_base}/api/agent/rag/ask",
                payload,
                headers={"Authorization": f"Bearer {auth.agent_token}"},
                timeout=timeout,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            data = response.get("data") or {}
            score, checks, errors = score_rag(case, response, data)
            result.update(
                status="PASS" if score >= float(case.get("minScore", 0.7)) and not errors else "FAIL",
                passed=score >= float(case.get("minScore", 0.7)) and not errors,
                score=round(score, 4),
                elapsedMs=round(elapsed_ms, 2),
                checks=checks,
                errors=errors,
                response=summarize_rag(data),
            )
        except Exception as exc:
            result.update(status="ERROR", passed=False, score=0.0, errors=[str(exc)])
        results.append(result)
    return results


def run_analytics_cases(cases: list[dict[str, Any]], agent_base: str, auth: EvalAuth, timeout: float) -> list[dict[str, Any]]:
    results = []
    for case in cases:
        started = time.perf_counter()
        result = base_result("analytics", case)
        if should_skip_for_role(case, auth):
            result.update(status="SKIPPED", skipped=True, passed=None, errors=[skip_reason(case, auth)])
            results.append(result)
            continue
        if not auth.agent_token:
            result.update(status="AUTH_MISSING", passed=False, score=0.0, errors=["Missing AGENT_TOKEN or login credentials"])
            results.append(result)
            continue
        payload = {
            "question": case["question"],
            "userId": case.get("userId", auth.user_id),
            "role": case.get("role", auth.role),
        }
        try:
            response = request_json(
                "POST",
                f"{agent_base}/api/agent/analytics/query",
                payload,
                headers={"Authorization": f"Bearer {auth.agent_token}"},
                timeout=timeout,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            data = response.get("data") or {}
            score, checks, errors = score_analytics(case, response, data)
            result.update(
                status="PASS" if score >= float(case.get("minScore", 0.75)) and not errors else "FAIL",
                passed=score >= float(case.get("minScore", 0.75)) and not errors,
                score=round(score, 4),
                elapsedMs=round(elapsed_ms, 2),
                checks=checks,
                errors=errors,
                response=summarize_analytics(data),
            )
        except Exception as exc:
            result.update(status="ERROR", passed=False, score=0.0, errors=[str(exc)])
        results.append(result)
    return results


def score_rag(case: dict[str, Any], envelope: dict[str, Any], data: dict[str, Any]) -> tuple[float, dict[str, Any], list[str]]:
    checks: dict[str, Any] = {}
    errors: list[str] = []
    points = 0.0
    total = 0.0

    answer = str(data.get("answer") or "")
    citations = data.get("citations") or []
    confidence = safe_float(data.get("confidence"), 0.0)
    evaluation = data.get("evaluation") or {}

    total += 1
    checks["businessCodeOk"] = envelope.get("code") == 0
    points += 1 if checks["businessCodeOk"] else 0

    total += 1
    checks["answerPresent"] = len(answer.strip()) >= int(case.get("minAnswerChars", 20))
    points += 1 if checks["answerPresent"] else 0

    expected_keywords = case.get("expectedKeywords") or []
    total += max(len(expected_keywords), 1)
    keyword_hits = keyword_matches(answer, expected_keywords)
    checks["expectedKeywordHits"] = keyword_hits
    points += len(keyword_hits) if expected_keywords else 1

    forbidden_hits = keyword_matches(answer, case.get("forbiddenKeywords") or [])
    checks["forbiddenKeywordHits"] = forbidden_hits
    if forbidden_hits:
        errors.append(f"Forbidden keywords found: {forbidden_hits}")

    if case.get("citationRequired", False):
        total += 1
        checks["hasCitations"] = bool(citations) or bool(evaluation.get("hasCitations"))
        points += 1 if checks["hasCitations"] else 0
        if not checks["hasCitations"]:
            errors.append("Expected citations but none were returned")

    total += 1
    min_confidence = float(case.get("minConfidence", 0.0))
    checks["confidenceOk"] = confidence >= min_confidence
    points += 1 if checks["confidenceOk"] else 0

    cache = data.get("cache") or {}
    checks["cacheBackend"] = cache.get("backend")
    checks["cacheHit"] = cache.get("hit")
    checks["citationCount"] = len(citations)
    return points / max(total, 1), checks, errors


def score_analytics(case: dict[str, Any], envelope: dict[str, Any], data: dict[str, Any]) -> tuple[float, dict[str, Any], list[str]]:
    checks: dict[str, Any] = {}
    errors: list[str] = []
    points = 0.0
    total = 0.0

    text = json.dumps(data, ensure_ascii=False)
    status = str(data.get("status") or "")
    execution_plan = data.get("executionPlan") or data.get("execution_plan") or {}
    sql_list = collect_sql(data)
    safety_items = collect_safety(data)

    total += 1
    checks["businessCodeOk"] = envelope.get("code") == 0 or envelope.get("code") == 403
    points += 1 if checks["businessCodeOk"] else 0

    expected_status = case.get("expectedStatus") or []
    if expected_status:
        total += 1
        checks["expectedStatusOk"] = status.upper() in {item.upper() for item in expected_status} or any(
            item.upper() in text.upper() for item in expected_status
        )
        points += 1 if checks["expectedStatusOk"] else 0

    expected_keywords = case.get("expectedKeywords") or []
    total += max(len(expected_keywords), 1)
    keyword_hits = keyword_matches(text, expected_keywords)
    checks["expectedKeywordHits"] = keyword_hits
    points += len(keyword_hits) if expected_keywords else 1

    total += 1
    checks["hasExecutionPlan"] = bool(execution_plan)
    points += 1 if checks["hasExecutionPlan"] else 0

    forbidden_sql_hits = []
    sql_text = "\n".join(sql_list)
    if sql_text:
        for keyword in case.get("forbiddenSqlKeywords") or []:
            if re.search(rf"\b{re.escape(keyword)}\b", sql_text, re.IGNORECASE):
                forbidden_sql_hits.append(keyword)
    checks["forbiddenSqlHits"] = forbidden_sql_hits
    if forbidden_sql_hits:
        errors.append(f"Forbidden SQL keywords found: {forbidden_sql_hits}")

    if case.get("requireSqlSafe", False):
        total += 1
        checks["sqlSafetyOk"] = bool(safety_items) and all(item.get("safe") is True for item in safety_items)
        points += 1 if checks["sqlSafetyOk"] else 0
        if not checks["sqlSafetyOk"]:
            errors.append("Expected all SQL safety checks to pass")

    checks["sqlList"] = sql_list[:5]
    checks["safety"] = safety_items[:5]
    return points / max(total, 1), checks, errors


def request_json(method: str, url: str, payload: dict[str, Any] | None, headers: dict[str, str] | None = None, timeout: float = 60) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"raw": raw}
        data["_httpStatus"] = exc.code
        return data


def load_cases(path: str) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def base_result(kind: str, case: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": case.get("id"),
        "category": case.get("category", "uncategorized"),
        "question": case.get("question"),
        "minScore": case.get("minScore"),
        "passed": False,
        "skipped": False,
        "status": "NOT_RUN",
        "score": 0.0,
        "elapsedMs": None,
        "checks": {},
        "errors": [],
    }


def keyword_matches(text: str, keywords: list[str]) -> list[str]:
    lower = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lower]


def collect_sql(data: Any) -> list[str]:
    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in {"sql", "query"} and isinstance(value, str):
                found.append(value)
            else:
                found.extend(collect_sql(value))
    elif isinstance(data, list):
        for item in data:
            found.extend(collect_sql(item))
    return found


def collect_safety(data: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(data, dict):
        if "safe" in data and ("reason" in data or "toolCall" in data or "sql" in data):
            found.append(data)
        for value in data.values():
            found.extend(collect_safety(value))
    elif isinstance(data, list):
        for item in data:
            found.extend(collect_safety(item))
    return found


def summarize_rag(data: dict[str, Any]) -> dict[str, Any]:
    answer = str(data.get("answer") or "")
    return {
        "answerPreview": answer[:500],
        "confidence": data.get("confidence"),
        "citationCount": len(data.get("citations") or []),
        "cache": data.get("cache"),
        "evaluation": data.get("evaluation"),
    }


def summarize_analytics(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": data.get("status"),
        "error": data.get("error"),
        "intent": data.get("intent"),
        "sqlList": collect_sql(data)[:5],
        "chart": data.get("chart"),
        "report": data.get("report"),
        "executionPlan": data.get("executionPlan") or data.get("execution_plan"),
    }


def build_report(results: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    runnable = [item for item in results if not item.get("skipped")]
    skipped = len(results) - len(runnable)
    passed = sum(1 for item in runnable if item.get("passed"))
    failed = len(runnable) - passed
    by_kind: dict[str, dict[str, Any]] = {}
    by_category: dict[str, dict[str, Any]] = {}
    for item in runnable:
        kind = item["kind"]
        group = by_kind.setdefault(kind, {"total": 0, "passed": 0, "failed": 0, "avgScore": 0.0, "avgLatencyMs": 0.0})
        group["total"] += 1
        group["passed"] += 1 if item.get("passed") else 0
        group["failed"] += 0 if item.get("passed") else 1
        category_key = f"{kind}:{item.get('category', 'uncategorized')}"
        category = by_category.setdefault(category_key, {"total": 0, "passed": 0, "failed": 0, "avgScore": 0.0})
        category["total"] += 1
        category["passed"] += 1 if item.get("passed") else 0
        category["failed"] += 0 if item.get("passed") else 1
    for kind, group in by_kind.items():
        kind_results = [item for item in runnable if item["kind"] == kind]
        group["avgScore"] = round(sum(float(item.get("score") or 0.0) for item in kind_results) / max(len(kind_results), 1), 4)
        latencies = [float(item["elapsedMs"]) for item in kind_results if item.get("elapsedMs") is not None]
        group["avgLatencyMs"] = round(sum(latencies) / max(len(latencies), 1), 2) if latencies else None
    for category_key, group in by_category.items():
        category_results = [
            item for item in runnable if f"{item['kind']}:{item.get('category', 'uncategorized')}" == category_key
        ]
        group["avgScore"] = round(
            sum(float(item.get("score") or 0.0) for item in category_results) / max(len(category_results), 1),
            4,
        )
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "target": args.target,
            "javaBase": args.java_base,
            "agentBase": args.agent_base,
        },
        "summary": {
            "total": len(results),
            "runnable": len(runnable),
            "skipped": skipped,
            "passed": passed,
            "failed": failed,
            "passRate": round(passed / max(len(runnable), 1), 4),
            "byKind": by_kind,
            "byCategory": by_category,
        },
        "results": results,
    }


def write_csv(path: Path, results: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["kind", "category", "id", "status", "passed", "score", "elapsedMs", "question", "errors"],
        )
        writer.writeheader()
        for item in results:
            writer.writerow({
                "kind": item.get("kind"),
                "category": item.get("category"),
                "id": item.get("id"),
                "status": item.get("status"),
                "passed": item.get("passed"),
                "score": item.get("score"),
                "elapsedMs": item.get("elapsedMs"),
                "question": item.get("question"),
                "errors": "; ".join(item.get("errors") or []),
            })


def print_summary(report: dict[str, Any], json_path: Path, csv_path: Path) -> None:
    summary = report["summary"]
    print(
        f"Agent quality eval: {summary['passed']}/{summary['runnable']} runnable passed, "
        f"skipped={summary['skipped']}, passRate={summary['passRate']}"
    )
    for kind, group in summary["byKind"].items():
        print(
            f"- {kind}: {group['passed']}/{group['total']} passed, "
            f"avgScore={group['avgScore']}, avgLatencyMs={group['avgLatencyMs']}"
        )
    print(f"JSON report: {json_path}")
    print(f"CSV report:  {csv_path}")


def safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def should_skip_for_role(case: dict[str, Any], auth: EvalAuth) -> bool:
    required = str(case.get("requiredAuthRole") or "").upper().strip()
    return bool(required and auth.role.upper() != required)


def skip_reason(case: dict[str, Any], auth: EvalAuth) -> str:
    return f"Case requires {case.get('requiredAuthRole')} token, current auth role is {auth.role}"


if __name__ == "__main__":
    sys.exit(main())
