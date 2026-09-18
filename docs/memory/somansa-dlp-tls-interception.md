---
name: somansa-dlp-tls-interception
description: This machine sits behind a Somansa NDLP TLS-inspecting proxy; Claude Code needs NODE_EXTRA_CA_CERTS or feature-flag-gated features silently break.
metadata: 
  node_type: memory
  type: project
  originSessionId: b4eac168-aaa6-49ee-a707-95589bf30484
  modified: 2026-09-09T11:53:56.323Z
---

All HTTPS on this Windows machine is intercepted by a **Somansa NDLP** DLP agent — every host (`api.anthropic.com`, `claude.ai`, `cdn.growthbook.io`) presents a cert issued by `CN=Somansa Root CA, OU=NDLP, O=Somansa, C=KR` (thumbprint `945FC59B8AA6583DDE7E851670064409BC9FAB56`). The root is in the Windows store, so PowerShell/Schannel tools work fine, which masks the problem.

Claude Code's native binary does not use the Windows store, so its GrowthBook feature-flag fetch to `cdn.growthbook.io` failed silently: `growthBookFeaturesLoaded=0`, `growthBookLastFetched=never`. That made Remote Control report *"Couldn't verify Remote Control eligibility — the feature-flag service was unreachable"* and kept `/remote-control` out of the slash-command menu, even though version, plan (Max), OAuth scopes, workspace trust, and settings were all correct.

Fixed on 2026-09-09 by exporting the root CA to `C:\Users\User\.claude\somansa-root-ca.pem` and setting the user-scope env var `NODE_EXTRA_CA_CERTS` to that path. Verified: `claude doctor` now reports Remote Control available.

**Why:** the ten-item Remote Control checklist in the docs does not cover TLS interception, so it burns a lot of time before you look at the cert chain.

**How to apply:** when any Claude Code feature that depends on server-side flags or streaming misbehaves on this machine, check the TLS issuer first (`SslStream.AuthenticateAsClient` against the host) rather than working the docs checklist. If `NODE_EXTRA_CA_CERTS` is ever unset or the PEM deleted, the same symptoms return. Related: [[claude-code-remote-control-setup]].
