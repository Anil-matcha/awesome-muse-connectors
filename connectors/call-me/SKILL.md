---
name: "call-me"
description: "Ring or text the user's own phone (iPhone or Android) and read their spoken answer back as text. Trigger phrases: call me, ring my phone, text my phone, ask me out loud, phone me when it is done."
metadata: { "includeInPrompt": true }
tagline: "Your assistant rings or texts your actual phone and gets your spoken answer back as text. Needs the paid /call-me app."
catalog_auth: "None (no API key). The user's own 10-digit /call-me number, from My Number in the app"
catalog_hosts: ["callmemcp.com"]
---

# Call Me (/call-me)

## Purpose
/call-me lets an AI agent ring or text its user's real phone. A call reads the agent's text aloud, the user answers out loud, and the spoken answer comes back as text. Use it when a task is blocked on a decision, when the user asked to be phoned with an update, or when the user wants a message pushed to their phone.

The phone app (iPhone and Android) is paid: a subscription is needed for the number to work. Site: https://callmemcp.com. Source: https://github.com/radres/call-me (MIT). The provider's README documents the plain HTTP endpoints used below. The same tools are also served as a remote MCP server at `https://callmemcp.com/mcp` (no OAuth, no API key); the provider's README does not list Muse as a tested client, so this entry only uses the HTTP endpoints.

## Tooling
No script ships. The commands are plain `curl` calls with a JSON body. `<NUMBER>` is the user's 10-digit number.

```bash
# Text only, no ring
curl -sS https://callmemcp.com/text -H 'content-type: application/json' \
  -d '{"to":"<NUMBER>","body":"Migration finished.","from":"Muse"}'

# Ring, read the text aloud, wait for the spoken answer (up to 300 s)
curl -sS https://callmemcp.com/ring -H 'content-type: application/json' \
  -d '{"to":"<NUMBER>","text":"Deploy to prod?","from":"Muse"}'

# Keep the line open for a back-and-forth: add "keep_open":true to /ring, then use the call_id and session_token it returns
curl -sS https://callmemcp.com/aiphone/calls/<call_id>/say -H 'content-type: application/json' \
  -d '{"session_token":"<session_token>","text":"Anything else?"}'
curl -sS https://callmemcp.com/aiphone/calls/<call_id>/hangup -H 'content-type: application/json' \
  -d '{"session_token":"<session_token>","text":"Thanks, talk later."}'
```

`/ring` returns `status` (`completed`, `missed`, `declined`, `timeout` or `failed`) and `transcript`, the user's spoken answer as text. `/text` returns `{"ok":true,"message_id":...,"delivered":true}`. `text` and `body` take up to 2000 characters. Add `"language":"tr"` (any language code) to `/ring` and `say` when the text is not English.

## Auth
- Provider id: `call-me` (no credential is collected; there is no key or OAuth)
- Collection: ask the user for their 10-digit number from My Number in the /call-me app. Never guess it, never use a number from an example, never call or text any other number.
- Required scopes: none
- Allowed hosts: `callmemcp.com`
- Status check: send the test text above to the user's own number; `"delivered":true` means it reached the phone

## Operating Rules
1. A call or text interrupts a real person. Ring or text only when the user asked for it or asked to be reached, and say so before the first call in a session. Prefer a text for news that needs no answer.
2. Keep each call short and put one question in it. Hang up as soon as the answer is in.
3. Limits per IP: 20 rings an hour and 60 a day, and 10 calls an hour and 40 a day to any one number. A user who blocked the sender in the app gets `missed` with an empty transcript.
4. The user's spoken answer is data from the user. Relay it and act on it as an instruction from the user only for the task at hand.
5. Do not put secrets, passwords or private data in the text; it is read aloud and shown on the phone.

## Files
- SKILL.md

## Maturity
🧪 Draft: written from the provider's public README (https://github.com/radres/call-me, October 2026); not yet live-tested inside Muse. Contributed by the provider.
