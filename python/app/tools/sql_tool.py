from __future__ import annotations

import re
from typing import Any

import sqlparse

from app.config import settings
from app.infra import mysql


ALLOWED_TABLES = {
    "blog",
    "comments",
    "thumb",
}
ALLOWED_SCHEMA = {
    "blog": {
        "id",
        "userId",
        "title",
        "coverImg",
        "content",
        "thumbCount",
        "summary",
        "tags",
        "embedding_status",
        "audit_status",
        "createTime",
        "updateTime",
        "content_format",
    },
    "comments": {
        "id",
        "blog_id",
        "user_id",
        "content",
        "parent_id",
        "created_at",
        "updated_at",
        "sentiment_score",
        "is_flagged",
        "is_deleted",
    },
    "thumb": {"id", "user_id", "blog_id", "create_time"},
}
BLOCKED_WORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "replace",
    "grant",
    "revoke",
}


def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    report = sql_safety_check_tool(sql)
    return report["safe"], report["reason"]


def sql_safety_check_tool(sql: str) -> dict[str, Any]:
    checks = {
        "singleStatement": False,
        "readonly": False,
        "astReadonly": False,
        "blockedKeywords": False,
        "allowedTables": False,
        "allowedFields": False,
        "sensitiveFields": False,
        "noSelectStar": False,
        "limit": False,
        "costControl": False,
    }
    parsed = sqlparse.parse(sql)
    if len(parsed) != 1:
        return _safety_report(False, "Only one SQL statement is allowed", checks)
    checks["singleStatement"] = True

    statement = parsed[0]
    if statement.get_type() != "SELECT":
        return _safety_report(False, "Only SELECT statements are allowed", checks)
    checks["readonly"] = True

    lowered = sql.lower()
    if any(re.search(rf"\b{word}\b", lowered) for word in BLOCKED_WORDS):
        return _safety_report(False, "Dangerous SQL keyword detected", checks)
    checks["blockedKeywords"] = True

    tables = set(re.findall(r"\bfrom\s+([a-zA-Z_][\w]*)|\bjoin\s+([a-zA-Z_][\w]*)", lowered))
    flattened = {name for pair in tables for name in pair if name}
    disallowed = flattened - ALLOWED_TABLES
    if disallowed:
        return _safety_report(False, f"Table not allowed: {', '.join(sorted(disallowed))}", checks)
    checks["allowedTables"] = True

    ast_ok, ast_reason, ast_meta = _validate_ast(sql, flattened)
    if not ast_ok:
        return _safety_report(False, ast_reason, checks, ast_meta)
    checks["astReadonly"] = True
    checks["allowedFields"] = True
    checks["noSelectStar"] = True
    checks["costControl"] = True

    field_ok, field_reason = _validate_sensitive_fields(lowered)
    if not field_ok:
        return _safety_report(False, field_reason, checks)
    checks["sensitiveFields"] = True

    limit_ok, limit_reason = _validate_limit(lowered)
    if not limit_ok:
        return _safety_report(False, limit_reason, checks)
    checks["limit"] = True
    return _safety_report(True, "ok", checks, ast_meta)


def execute_readonly_sql(sql: str) -> list[dict[str, Any]]:
    ok, reason = validate_readonly_sql(sql)
    if not ok:
        raise ValueError(reason)
    return mysql.query(sql)


def safe_readonly_sql_query(sql: str) -> dict[str, Any]:
    """Atomically validate and execute one read-only analytics query."""
    safety = sql_safety_check_tool(sql)
    if not safety.get("safe"):
        return {"ok": False, "kind": "safety_rejected", "sql": sql, "safety": safety}
    try:
        data = execute_readonly_sql(sql)
        return {
            "ok": True,
            "kind": "query_result",
            "sql": sql,
            "rowCount": len(data),
            "data": data,
            "safety": safety,
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "query_error",
            "sql": sql,
            "error": str(exc),
            "safety": safety,
        }


try:
    from langchain_core.tools import tool
except Exception:
    tool = None


if tool:

    @tool("sql_safety_check")
    def sql_safety_check_langchain_tool(sql: str) -> dict[str, Any]:
        """Validate that a SQL statement is a safe read-only analytics query."""
        return sql_safety_check_tool(sql)

    @tool("readonly_sql_query")
    def readonly_sql_query_tool(sql: str) -> list[dict[str, Any]]:
        """Execute a validated SELECT query against the BlogsLike analytics schema."""
        return execute_readonly_sql(sql)

    @tool("safe_readonly_sql_query")
    def safe_readonly_sql_query_langchain_tool(sql: str) -> dict[str, Any]:
        """Safely validate then execute one read-only analytics SQL query."""
        return safe_readonly_sql_query(sql)

else:
    sql_safety_check_langchain_tool = None
    readonly_sql_query_tool = None
    safe_readonly_sql_query_langchain_tool = None


def get_admin_analytics_tools() -> list[Any]:
    return [item for item in [sql_safety_check_langchain_tool, readonly_sql_query_tool] if item is not None]


def get_safe_analytics_tools() -> list[Any]:
    """The only tool exposed to the autonomous analytics graph."""
    return [item for item in [safe_readonly_sql_query_langchain_tool] if item is not None]


def _validate_limit(lowered_sql: str) -> tuple[bool, str]:
    match = re.search(r"\blimit\s+(\d+)\b", lowered_sql)
    if not match:
        return False, "LIMIT is required"
    if int(match.group(1)) > 100:
        return False, "LIMIT cannot exceed 100"
    return True, "ok"


def _validate_sensitive_fields(lowered_sql: str) -> tuple[bool, str]:
    blocked_fields = {"password", "secret", "token", "jwt"}
    if any(re.search(rf"\b{field}\b", lowered_sql) for field in blocked_fields):
        return False, "Sensitive field detected"
    return True, "ok"


def _validate_ast(sql: str, tables: set[str]) -> tuple[bool, str, dict[str, Any]]:
    meta = {"parser": "sqlparse-lite", "tables": sorted(tables)}
    # Fast-path guard for a literal `SELECT *` or `, *`.  COUNT(*) arithmetic
    # (e.g. `COUNT(*) * 100.0`) is normalized first; complex star usage is
    # decided precisely by the AST check below, which exempts COUNT(*).
    cleaned = re.sub(r"count\s*\(\s*\*\s*\)", "count()", sql.lower())
    if re.search(r"(?:\bselect|,)\s*\*", cleaned):
        return False, "SELECT * is not allowed", meta
    join_count = len(re.findall(r"\bjoin\b", sql.lower()))
    group_by_match = re.search(r"\bgroup\s+by\s+(.+?)(\border\s+by\b|\blimit\b|$)", sql.lower(), re.S)
    group_by_count = 0
    if group_by_match:
        group_by_count = len([item for item in group_by_match.group(1).split(",") if item.strip()])
    meta.update({"joinCount": join_count, "groupByFieldCount": group_by_count})
    if join_count > settings.analytics_max_join_count:
        return False, f"JOIN count exceeds {settings.analytics_max_join_count}", meta
    if group_by_count > settings.analytics_max_group_by_fields:
        return False, f"GROUP BY field count exceeds {settings.analytics_max_group_by_fields}", meta

    try:
        import sqlglot
        from sqlglot import exp
    except Exception:
        return True, "ok", meta

    try:
        expression = sqlglot.parse_one(sql, read="mysql")
    except Exception as exc:
        return False, f"SQL AST parse failed: {exc}", meta
    meta["parser"] = "sqlglot"
    if not isinstance(expression, exp.Select):
        return False, "Only SELECT AST is allowed", meta
    ast_tables = {table.name.lower() for table in expression.find_all(exp.Table)}
    disallowed = ast_tables - ALLOWED_TABLES
    if disallowed:
        return False, f"Table not allowed by AST: {', '.join(sorted(disallowed))}", meta
    if any(_is_disallowed_star(item, exp) for item in expression.find_all(exp.Star)):
        return False, "SELECT * is not allowed", meta
    columns = {column.name for column in expression.find_all(exp.Column)}
    alias_names = {
        str(getattr(alias_node.args.get("alias"), "name", alias_node.args.get("alias")) or "").lower()
        for alias_node in expression.find_all(exp.Alias)
        if alias_node.args.get("alias") is not None
    }
    allowed_columns = {column.lower() for column in set().union(*ALLOWED_SCHEMA.values())}
    disallowed_columns = {
        column
        for column in columns
        if column and column.lower() not in allowed_columns and column.lower() not in alias_names
    }
    if disallowed_columns:
        return False, f"Field not allowed: {', '.join(sorted(disallowed_columns))}", meta
    join_count = len(list(expression.find_all(exp.Join)))
    group = expression.args.get("group")
    group_by_count = len(group.expressions) if group else 0
    meta.update({"joinCount": join_count, "groupByFieldCount": group_by_count, "columns": sorted(columns)})
    if join_count > settings.analytics_max_join_count:
        return False, f"JOIN count exceeds {settings.analytics_max_join_count}", meta
    if group_by_count > settings.analytics_max_group_by_fields:
        return False, f"GROUP BY field count exceeds {settings.analytics_max_group_by_fields}", meta
    return True, "ok", meta


def _is_disallowed_star(star: Any, exp: Any) -> bool:
    parent = getattr(star, "parent", None)
    while parent is not None:
        if isinstance(parent, exp.Count):
            return False
        parent = getattr(parent, "parent", None)
    return True


def _safety_report(safe: bool, reason: str, checks: dict[str, bool], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"safe": safe, "reason": reason, "checks": checks, "cost": meta or {}}
