#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  load-tests/run-k6.sh <likes|blogs|rag|analytics|mixed> [key=value...]

Examples:
  load-tests/run-k6.sh likes VUS=40 USERS=40 BLOGS=40 HOLD=2m THINK_SECONDS=0.2
  load-tests/run-k6.sh mixed VUS=10 USERS=10 BLOGS=10 HOLD=2m THINK_SECONDS=1 LABEL=realistic

Supported keys:
  JAVA_BASE, AGENT_BASE, VUS, USERS, BLOGS, RAMP_UP, HOLD, RAMP_DOWN, THINK_SECONDS, LABEL
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

SCRIPT="$1"
shift

case "$SCRIPT" in
  likes|blogs|rag|analytics|mixed) ;;
  *)
    echo "Unknown script: $SCRIPT" >&2
    usage
    exit 2
    ;;
esac

JAVA_BASE="${JAVA_BASE:-http://host.docker.internal:9199/api}"
AGENT_BASE="${AGENT_BASE:-http://host.docker.internal:8081}"
VUS="${VUS:-10}"
USERS="${USERS:-}"
BLOGS="${BLOGS:-}"
RAMP_UP="${RAMP_UP:-}"
HOLD="${HOLD:-1m}"
RAMP_DOWN="${RAMP_DOWN:-}"
THINK_SECONDS="${THINK_SECONDS:-0.2}"
LABEL="${LABEL:-}"

for pair in "$@"; do
  case "$pair" in
    JAVA_BASE=*) JAVA_BASE="${pair#*=}" ;;
    AGENT_BASE=*) AGENT_BASE="${pair#*=}" ;;
    VUS=*) VUS="${pair#*=}" ;;
    USERS=*) USERS="${pair#*=}" ;;
    BLOGS=*) BLOGS="${pair#*=}" ;;
    RAMP_UP=*) RAMP_UP="${pair#*=}" ;;
    HOLD=*) HOLD="${pair#*=}" ;;
    RAMP_DOWN=*) RAMP_DOWN="${pair#*=}" ;;
    THINK_SECONDS=*) THINK_SECONDS="${pair#*=}" ;;
    LABEL=*) LABEL="${pair#*=}" ;;
    *)
      echo "Unknown argument: $pair" >&2
      usage
      exit 2
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
if [[ -n "$LABEL" ]]; then
  RUN_NAME="$TIMESTAMP-$SCRIPT-$LABEL"
else
  RUN_NAME="$TIMESTAMP-$SCRIPT"
fi

REPORT_DIR="$ROOT/reports/k6/$RUN_NAME"
SUMMARY_PATH="reports/k6/$RUN_NAME/summary.json"
CONSOLE_PATH="$REPORT_DIR/console.txt"
META_PATH="$REPORT_DIR/meta.json"
mkdir -p "$REPORT_DIR"

cat > "$META_PATH" <<META
{
  "runName": "$RUN_NAME",
  "startedAt": "$(date -Is)",
  "script": "$SCRIPT.js",
  "javaBase": "$JAVA_BASE",
  "agentBase": "$AGENT_BASE",
  "vus": "$VUS",
  "users": "$USERS",
  "blogs": "$BLOGS",
  "rampUp": "$RAMP_UP",
  "hold": "$HOLD",
  "rampDown": "$RAMP_DOWN",
  "thinkSeconds": "$THINK_SECONDS",
  "summary": "$SUMMARY_PATH",
  "console": "reports/k6/$RUN_NAME/console.txt"
}
META

ENV_ARGS=(
  -e "JAVA_BASE=$JAVA_BASE"
  -e "AGENT_BASE=$AGENT_BASE"
  -e "VUS=$VUS"
  -e "HOLD=$HOLD"
  -e "THINK_SECONDS=$THINK_SECONDS"
)

if [[ -n "$USERS" ]]; then
  ENV_ARGS+=(-e "USERS=$USERS")
fi
if [[ -n "$BLOGS" ]]; then
  ENV_ARGS+=(-e "BLOGS=$BLOGS" -e "SEED_BLOGS=$BLOGS")
fi
if [[ -n "$RAMP_UP" ]]; then
  ENV_ARGS+=(-e "RAMP_UP=$RAMP_UP")
fi
if [[ -n "$RAMP_DOWN" ]]; then
  ENV_ARGS+=(-e "RAMP_DOWN=$RAMP_DOWN")
fi

echo "Writing k6 reports to $REPORT_DIR"

docker run --rm \
  "${ENV_ARGS[@]}" \
  -v "$ROOT:/work" \
  -w /work \
  grafana/k6 run \
  --summary-export "$SUMMARY_PATH" \
  "load-tests/k6/$SCRIPT.js" 2>&1 | tee "$CONSOLE_PATH"
