#!/bin/zsh
# 맥북 임시 실행(개발용). 도서관 PC 는 bin\app.vbs. 모든 맥 전용 처리는 임시다.
cd "$(dirname "$0")/.."
export KOLIS_AGENT_HOME="${KOLIS_AGENT_HOME:-/private/tmp/kolis_agent}"   # 상위에 CLAUDE.md 가 없는 곳
export KOLIS_AGENT_MODEL="${KOLIS_AGENT_MODEL:-sonnet}"
exec .venv-mac/bin/python -X utf8 -m kolis_tool.app "$@"
