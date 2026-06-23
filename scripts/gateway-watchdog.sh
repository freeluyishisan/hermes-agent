#!/bin/bash
# Gateway watchdog — checks if hermes-gateway is running, restarts if down.
# Silent when healthy. Outputs only when it had to restart.

if systemctl --user is-active --quiet hermes-gateway; then
    exit 0
fi

echo "[watchdog] Gateway was DOWN, restarting at $(date '+%Y-%m-%d %H:%M:%S')"
systemctl --user reset-failed hermes-gateway 2>/dev/null
systemctl --user restart hermes-gateway

sleep 3
if systemctl --user is-active --quiet hermes-gateway; then
    echo "[watchdog] Gateway restarted successfully"
else
    echo "[watchdog] FAILED to restart gateway — manual intervention needed"
fi
