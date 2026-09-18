---
name: remote-control-keepalive-setup
description: How Remote Control runs in the background on this PC — a hidden self-restarting scheduled task; includes the rename gotcha (bridge-pointer.json).
metadata: 
  node_type: memory
  type: project
  originSessionId: b4eac168-aaa6-49ee-a707-95589bf30484
  modified: 2026-09-09T14:41:58.473Z
---

The user is a **contractor (외주)** who works on this office PC (on the institutional network, required to reach **KOLIS**) remotely from a MacBook via Remote Control. Set up 2026-09-09.

**Background runner** — a scheduled task `ClaudeRemoteControl` (registered under the user, LogonType Interactive, AtLogOn trigger only, RestartCount 10 / RestartInterval 1m) runs a hidden keep-alive wrapper `C:\Users\User\.claude\rc-keepalive.ps1`. The wrapper loops: `& 'C:\Users\User\.local\bin\claude.exe' remote-control --name "<name>" --debug-file $dbg` inside `while ($true)`, restarting 5s after any exit. **Must invoke claude with the call operator `&`, NOT `Start-Process -ArgumentList`** — the Start-Process form failed to parse and caused a 5-second crash loop (22:09–22:12 on setup day); `&` also makes claude a true child so exits are detected reliably. So: no visible window (nothing to accidentally close), survives terminal close, self-heals on crash/clean-exit, and comes back after reboot **only if the user logs on** (AutoAdminLogon is off). Server debug log: `~/.claude/rc-server-debug.log`; wrapper log: `~/.claude/rc-keepalive.log`.

**Logoff settings checked:** screensaver locks at 10 min (lock ≠ logoff, session survives), no idle auto-logoff policy, AC never sleeps (desktop). Rule for the user: leave PC on, don't log off (screen-lock is fine).

**Rename gotcha (cost a lot of time):** `--name` only titles a NEWLY created session. The server auto-resumes the session recorded in `C:\Users\User\.claude\projects\C--Users-User-dataclip\bridge-pointer.json` (a stale one keeps the old name, and if that session was deleted in the browser the server 404-loops "Adopted session … re-queued / registerWorker failed 404" and never makes a new one). **To rename or force a fresh session: stop task+wrapper+server, delete bridge-pointer.json, then start the task.** Confirm via debug log line `server title for session_…: <name>`.

**Reading `rc-keepalive.log`:** occasional, spread-out `exited → restarting in 5s` pairs = healthy self-heal (network blip). Dense 5-second-interval repetition = a real failure loop (claude never starts), investigate. The user's standing worry is transient network drops; those are fully covered (claude reconnects internally, and the unbounded wrapper loop retries forever until the link returns).

**Ops:** start/stop `Start-ScheduledTask`/`Stop-ScheduledTask -TaskName 'ClaudeRemoteControl'`; remove `Unregister-ScheduledTask`. When listing processes, filtering on a CommandLine substring also matches your own PowerShell tool call — identify the real wrapper by parent = `svchost.exe`. Killing processes needs `dangerouslyDisableSandbox`. Depends on [[somansa-dlp-tls-interception]] (NODE_EXTRA_CA_CERTS) for eligibility. Current session name as of last edit: **powershell** (was kolis-remote → dataclip → powershell during testing).
