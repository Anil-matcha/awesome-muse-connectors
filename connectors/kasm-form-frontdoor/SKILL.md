---
name: "kasm-form-frontdoor"
description: "Form-login front door for KasmVNC: a standard HTML sign-in form and signed session-cookie gate in front of a KasmVNC server, with HTTP/WebSocket proxying, so password managers and browser saved-login flows (including AI browser agents) can sign in — KasmVNC's native basic-auth prompt cannot be filled by any of them. KasmVNC's own authentication stays fully enabled behind the door. Trigger phrases: kasm, kasmvnc, vnc login, remote desktop login, form front door, basic auth prompt."
metadata: { "includeInPrompt": true }
tagline: "Give KasmVNC a real login form: signed session cookies and an HTTP/WebSocket proxy in front of KasmVNC, without disabling its authentication."
catalog_auth: "Username/password form login checked against the same credential as the KasmVNC user (password read from a mode-0600 file on the host); on success the door issues a stateless HMAC session cookie (HttpOnly, Secure, SameSite=Lax, 30-day expiry; secret in a second mode-0600 file, auto-created). The door presents KasmVNC's credential to the server server-side; KasmVNC basic auth remains enabled and is never disabled."
catalog_hosts: ["127.0.0.1"]
---

# Kasm Form Front Door

## Purpose

[KasmVNC](https://kasmweb.com/kasmvnc) gates its web client with the browser's **native HTTP basic-auth prompt**. That prompt cannot be filled by password managers' form fillers, browser saved-login flows, or browser automation (including AI browser agents) — the page exposes no form, and in automated sessions the prompt may not render at all, leaving a blank page. The common workaround, disabling KasmVNC basic auth, weakens the deployment. This connector is the alternative: a small proxy that puts a standard form login in front of KasmVNC while KasmVNC's authentication stays on.

How it works:

1. The door serves a normal HTML login form (`username` / `password` fields) at `/__login`.
2. It verifies the **same credential** the KasmVNC user has (constant-time comparison), and only then sets a signed, expiring session cookie.
3. Authenticated requests are proxied — HTTP and WebSocket — to the KasmVNC server, presenting Kasm's credential server-side.

Unauthenticated requests redirect to the form; wrong credentials return 401; nothing reaches KasmVNC without passing the door.

## Auth

Username/password form login, checked against the same credential as the KasmVNC user (constant-time comparison). The password is read from a mode-0600 file on the host; a second mode-0600 file holds the HMAC secret for the stateless session cookie (HttpOnly, Secure, SameSite=Lax, 30-day expiry; auto-created on first run — rotating it logs everyone out). The door presents KasmVNC's credential to the server server-side. KasmVNC's own basic auth remains enabled and is never disabled; there is no API key, OAuth flow, or third-party host involved.

## Tooling

`frontdoor.py` — one file, pure Python standard library (asyncio), no dependencies. Source: [github.com/jonathancruzate/kasm-form-frontdoor](https://github.com/jonathancruzate/kasm-form-frontdoor) (MIT). A systemd unit template ships in the same repo.

Key behavior:

- Stateless HMAC session cookies; rotating the secret file logs everyone out.
- Login path is `/__login` (GET serves the form, POST verifies); every other path requires the session cookie.
- Upstream may be plain HTTP (e.g. KasmVNC bound to a private/tailnet address) or HTTPS with a self-signed cert (`FD_UPSTREAM_HTTPS=1`); the browser-facing side is expected to sit behind real TLS (Tailscale Funnel, a Cloudflare tunnel, or a reverse proxy).

## Setup

1. Install KasmVNC and create its user as usual (`kasmvncpasswd`); keep its authentication enabled. Bind KasmVNC to a private interface (localhost or tailnet), never the public internet.
2. Store the shared password in a file only the service user can read:

   ```bash
   mkdir -p ~/.kasm-frontdoor
   printf '%s' 'your-kasm-password' > ~/.kasm-frontdoor/password.txt
   chmod 600 ~/.kasm-frontdoor/password.txt
   ```

3. Run the door (env-configured):

   ```bash
   FD_USERNAME=your-kasm-user \
   FD_UPSTREAM_HOST=127.0.0.1 \
   FD_UPSTREAM_PORT=8443 \
   FD_UPSTREAM_HTTPS=1 \
   python3 frontdoor.py    # listens on 127.0.0.1:8952
   ```

4. Publish the door — not KasmVNC — through your TLS front, e.g. Tailscale Funnel:

   ```bash
   sudo tailscale funnel --bg --https=443 http://127.0.0.1:8952
   ```

5. Save the login in your password manager / Muse Secure Vault for the door's origin, and saved-login flows will sign in by default from then on.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `FD_USERNAME` | `user` | Login username (the KasmVNC user) |
| `FD_PASSWORD_FILE` | `~/.kasm-frontdoor/password.txt` | File containing the shared password |
| `FD_SECRET_FILE` | `~/.kasm-frontdoor/secret.txt` | Cookie HMAC secret (auto-created, 0600) |
| `FD_UPSTREAM_HOST` | `127.0.0.1` | KasmVNC host |
| `FD_UPSTREAM_PORT` | `8443` | KasmVNC web port |
| `FD_UPSTREAM_HTTPS` | `0` | `1` when Kasm serves HTTPS with a self-signed cert |
| `FD_LISTEN_HOST` | `127.0.0.1` | Listen address |
| `FD_LISTEN_PORT` | `8952` | Listen port |

## Files

From the source repo [github.com/jonathancruzate/kasm-form-frontdoor](https://github.com/jonathancruzate/kasm-form-frontdoor) (MIT):

- `frontdoor.py` — the whole service: form login, cookie gate, HTTP/WebSocket proxy (pure Python stdlib).
- `kasm-frontdoor.service` — systemd unit template.
- `README.md` — setup, configuration table, and security notes.
- `LICENSE` — MIT.

On the host, state lives outside the repo: the password file and cookie-secret file (both mode 0600, paths configurable via `FD_PASSWORD_FILE` / `FD_SECRET_FILE`).

## Operating rules

- **Never disable KasmVNC's basic auth** to make sign-in easier; the door exists precisely so you don't have to.
- The door and KasmVNC share one credential by design (single-user/small-team scope). For multi-user SSO, use Kasm Workspaces or an OAuth proxy instead.
- Add rate limiting at the TLS front if the door is exposed beyond your own devices.
- Verify before trusting a deployment: unauthenticated root redirects to the form, wrong credentials return 401, correct credentials set the cookie, and the Kasm client connects over the proxied WebSocket.

## Maturity

Working and verified end-to-end in production use (2026-11-08): a KasmVNC session mirroring a live Chrome window, published via Tailscale Funnel, signed into by an AI browser agent using only a saved login, with a human taking over the same session from a phone.
