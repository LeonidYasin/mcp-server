#!/usr/bin/env bash
# Production rollout mcp-server -> a0dc328 (PR #119, squash в main).
# Запуск оператором от root ТОЛЬКО как файл: bash prod_rollout_pr119.sh
# Не вставлять построчно в консоль. Секреты не выводятся.
set -Eeuo pipefail
TARGET=a0dc3286a05f774bdf321de05f695b7d4c755f61
SVC=mcp-server.service
DIR=/home/mcp/mcp-server
U=mcp
PORT=3001
BK=/root/mcp-rollout-$(date +%Y%m%d-%H%M%S)

g(){ sudo -u "$U" -H git -C "$DIR" "$@"; }
stop(){ echo "STOP: $*"; echo "RESULT=STOP (ничего не изменено)"; exit 1; }

[ "$(id -u)" = 0 ] || stop "нужен root"

echo "== preflight"
systemctl is-active --quiet "$SVC" || stop "$SVC не active"
OLD=$(g rev-parse HEAD)
OLDPID=$(systemctl show -p MainPID --value "$SVC")
echo "old=$OLD pid=$OLDPID"
[ "$OLD" = "$TARGET" ] && { echo "RESULT=ALREADY_AT_TARGET $TARGET"; exit 0; }
[ -z "$(g status --porcelain --untracked-files=no)" ] || stop "изменённые tracked-файлы в $DIR"
echo "untracked (не трогаем):"; g status --porcelain || true
FLAGS=$(tr '\0' '\n' < "/proc/$OLDPID/environ" | grep -E '^ENABLE_(AGENT_ROOMS|LOCAL_SHELL|LOCAL_TOOLS|SYNAPSE)=' || true)
echo "flags: ${FLAGS:-<не заданы>}"
if echo "$FLAGS" | grep -qiE '=(1|true|yes|on)$'; then stop "опасный флаг включён в production"; fi
df -h "$DIR" | tail -1

echo "== backup -> $BK"
install -d -m 700 "$BK"
echo "$OLD" > "$BK/old_sha"
systemctl cat "$SVC" > "$BK/unit.txt"
tar -C "$(dirname "$DIR")" -czf "$BK/checkout.tgz" --exclude=.venv "$(basename "$DIR")"

echo "== fetch/verify"
g fetch --quiet origin main
g cat-file -e "$TARGET^{commit}" || stop "target не найден после fetch"
g merge-base --is-ancestor "$OLD" "$TARGET" || stop "текущий SHA не предок target"
g diff --name-only "$OLD" "$TARGET" -- pyproject.toml 'requirements*.txt' setup.py setup.cfg > "$BK/dep_changes"
[ ! -s "$BK/dep_changes" ] || { cat "$BK/dep_changes"; stop "изменились зависимости"; }

rollback(){
  trap - ERR
  echo "!! ОШИБКА -> ROLLBACK на $OLD"
  g checkout --quiet --detach "$OLD" || true
  systemctl restart "$SVC" || true
  sleep 5
  echo "service после отката: $(systemctl is-active "$SVC" || true)"
  echo "RESULT=ROLLED_BACK old=$OLD backup=$BK"
  exit 1
}
trap rollback ERR

echo "== switch"
g checkout --quiet --detach "$TARGET"
sudo -u "$U" -H bash -c "cd '$DIR' && .venv/bin/python -c 'import mcp_server.tools.github.repository_analogs, mcp_server.tools.github.repository_evidence; print(\"import ok\")'"
systemctl restart "$SVC"
sleep 5
systemctl is-active --quiet "$SVC"
NEWPID=$(systemctl show -p MainPID --value "$SVC")
[ "$NEWPID" != "$OLDPID" ]
CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" || true)
echo "health=$CODE"
case "$CODE" in 2??|401|403) ;; *) false ;; esac
trap - ERR
echo "RESULT=ROLLOUT_PASS old=$OLD new=$(g rev-parse HEAD) pid=$NEWPID backup=$BK"
