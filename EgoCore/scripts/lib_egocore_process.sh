#!/bin/bash

egocore_is_windows_shell() {
    case "$(uname -s)" in
        MINGW*|MSYS*|CYGWIN*) return 0 ;;
        *) return 1 ;;
    esac
}

egocore_read_pid_file() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        tr -d '\r\n' < "$pid_file" 2>/dev/null || true
    fi
}

egocore_read_lock_pid() {
    local lock_file="$1"
    if [ ! -f "$lock_file" ]; then
        return 0
    fi
    grep -oE 'pid=[0-9]+' "$lock_file" 2>/dev/null | head -n1 | cut -d= -f2
}

egocore_list_telegram_pids() {
    if egocore_is_windows_shell && command -v powershell.exe >/dev/null 2>&1; then
        local ps_script
        ps_script=$(cat <<'EOF'
$ErrorActionPreference = "SilentlyContinue"
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and
    $_.CommandLine -match '(^|\\)(python|py)(\.exe)?' -and
    $_.CommandLine -match '(^|\s)-m\s+app\.main(\s|$)' -and
    $_.CommandLine -match '(^|\s)--telegram(\s|$)'
  } |
  Select-Object -ExpandProperty ProcessId
EOF
)
        powershell.exe -NoProfile -NonInteractive -Command "$ps_script" 2>/dev/null | tr -d '\r'
        return 0
    fi

    ps -eo pid=,args= 2>/dev/null | awk '/python/ && /-m app\.main/ && /--telegram/ {print $1}'
}

egocore_pid_is_running() {
    local pid="$1"
    if [ -z "$pid" ]; then
        return 1
    fi

    if egocore_is_windows_shell && command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -NonInteractive -Command "if (Get-Process -Id $pid -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >/dev/null 2>&1
        return $?
    fi

    ps -p "$pid" >/dev/null 2>&1
}

egocore_kill_pid() {
    local pid="$1"
    local mode="${2:-graceful}"
    if [ -z "$pid" ]; then
        return 0
    fi

    if egocore_is_windows_shell && command -v cmd.exe >/dev/null 2>&1; then
        if [ "$mode" = "force" ]; then
            cmd.exe /c "taskkill /PID $pid /T /F >NUL 2>&1" >/dev/null 2>&1 || true
        elif command -v powershell.exe >/dev/null 2>&1; then
            powershell.exe -NoProfile -NonInteractive -Command "Stop-Process -Id $pid -ErrorAction SilentlyContinue" >/dev/null 2>&1 || true
        else
            cmd.exe /c "taskkill /PID $pid /T >NUL 2>&1" >/dev/null 2>&1 || true
        fi
        return 0
    fi

    if [ "$mode" = "force" ]; then
        kill -9 "$pid" 2>/dev/null || true
    else
        kill "$pid" 2>/dev/null || true
    fi
}

egocore_pid_list_contains() {
    local pid_list="$1"
    local target="$2"
    local pid
    for pid in $pid_list; do
        if [ "$pid" = "$target" ]; then
            return 0
        fi
    done
    return 1
}

egocore_collect_target_pids() {
    local tracked_pid="$1"
    local lock_pid="$2"
    local live_pids="$3"
    local pid

    {
        [ -n "$tracked_pid" ] && printf '%s\n' "$tracked_pid"
        [ -n "$lock_pid" ] && printf '%s\n' "$lock_pid"
        for pid in $live_pids; do
            [ -n "$pid" ] && printf '%s\n' "$pid"
        done
    } | awk 'NF && !seen[$0]++'
}

egocore_find_new_pid() {
    local baseline_pids="$1"
    local current_pids="$2"
    local pid
    for pid in $current_pids; do
        if ! egocore_pid_list_contains "$baseline_pids" "$pid"; then
            printf '%s\n' "$pid"
            return 0
        fi
    done
    return 1
}
