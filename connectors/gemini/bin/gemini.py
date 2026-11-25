#!/usr/bin/env python3
"""Google Gemini API CLI — text generation + media generation.

Auth: the per-user `custom.gemini` credential (Google AI Studio API key),
loaded as a surrogate via the bundled dynamic_credentials helper. The real
key never touches this script: the runtime swaps the surrogate on approved
egress, only to generativelanguage.googleapis.com.

COST WARNING: all media generation (image, imagen, video, tts) requires a
BILLING-ENABLED project — free-tier media quota is 0 — and spends real money.
Those commands refuse to run without --confirm-cost "<model> <estimate>"
naming the model that will be billed; the confirmation is enforced here in
code, not just documented. Text `generate` calls follow normal API billing
for the key's project/tier.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

BASE = "https://generativelanguage.googleapis.com"
ALLOWED = ["generativelanguage.googleapis.com"]
CRED = "custom.gemini"

TEXT_MODEL = "gemini-flash-lite-latest"
IMAGE_MODEL = "gemini-2.5-flash-image"        # Nano Banana, text-to-image/edit, sync
IMAGEN_MODEL = "imagen-4.0-generate-001"      # Imagen 4, sync
VEO_MODEL = "veo-3.1-generate-preview"       # Veo 3.1, async long-running op
TTS_MODEL = "gemini-2.5-flash-preview-tts"   # TTS, sync

COST_HINTS = {
    IMAGE_MODEL: "about $0.02-0.04 per image",
    IMAGEN_MODEL: "about $0.02-0.06 per image",
    VEO_MODEL: "about $0.40/second (Veo 3.1); Fast ~$0.10/s, Lite ~$0.05/s",
    TTS_MODEL: "billed per input character/token; short lines are cents",
}


def _request(method, path, body=None, raw=False, timeout=120):
    url = BASE + path if path.startswith("/") else path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(req, CRED, entry_name="access_token",
                             allowed_hosts=ALLOWED)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if raw:
                return resp.status, resp.read()
            return resp.status, read_json_response(resp)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {"error": f"HTTP {e.code}"}
        return e.code, payload


def _die(status, payload):
    print(json.dumps({"status": status, "payload": payload}, indent=2)[:4000])
    sys.exit(1)


def require_cost_confirm(args, model):
    """Media generation spends real money: refuse without a --confirm-cost
    that names the exact model being billed and an estimated cost, e.g.
    --confirm-cost "imagen-4.0-generate-001 ~$0.04 for 1 image". The user
    confirms the cost in conversation first; never pre-fill it."""
    cc = getattr(args, "confirm_cost", None)
    if not cc or model not in cc:
        hint = COST_HINTS.get(model, "see provider pricing")
        raise SystemExit(
            f"refused: {model} generation is billed ({hint}) and needs cost "
            f"confirmation. Re-run with --confirm-cost \"{model} <estimated "
            f"cost>\" after the user confirms the spend in conversation.")
    print(f"notice: cost confirmed for {model}: {cc}", file=sys.stderr)


def _merge_json(extra, base):
    if not extra:
        return base
    try:
        obj = json.loads(extra)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: --json is not valid JSON: {exc}")
    if not isinstance(obj, dict):
        raise SystemExit("error: --json must be a JSON object")
    base.update(obj)
    return base


def _file_part(path):
    """Inline an input image with its real MIME type: extension first, then
    magic bytes. (Labelling every input image/png, as the earlier draft did,
    makes non-PNG edits fail or silently degrade.)"""
    with open(path, "rb") as fh:
        blob = fh.read()
    mime = mimetypes.guess_type(path)[0]
    if not mime or not mime.startswith("image/"):
        if blob.startswith(b"\x89PNG"):
            mime = "image/png"
        elif blob.startswith(b"\xff\xd8"):
            mime = "image/jpeg"
        elif blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
            mime = "image/webp"
        elif blob.startswith(b"GIF8"):
            mime = "image/gif"
        else:
            mime = "image/png"
    return {"inlineData": {"mimeType": mime,
                           "data": base64.b64encode(blob).decode("ascii")}}


_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp",
        "audio/wav": "wav", "audio/x-wav": "wav", "audio/mpeg": "mp3",
        "video/mp4": "mp4"}


def _save_inline(result, out_prefix):
    saved = []
    idx = 0
    for cand in result.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime = inline.get("mimeType", "image/png")
                path = f"{out_prefix}-{idx}.{_EXT.get(mime, 'bin')}"
                with open(path, "wb") as fh:
                    fh.write(base64.b64decode(inline["data"]))
                saved.append(path)
                idx += 1
    return saved


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth(_args):
    status, payload = _request("GET", "/v1beta/models?pageSize=1")
    ok = status == 200
    print(json.dumps({"ok": ok, "status": status}))
    return 0 if ok else 1


def cmd_models(args):
    status, payload = _request("GET", "/v1beta/models")
    if status != 200:
        _die(status, payload)
    models = payload.get("models", [])
    out = [{"name": m.get("name"), "displayName": m.get("displayName")}
           for m in models[: args.limit]]
    print(json.dumps({"status": status, "count": len(models), "models": out},
                     indent=2))


def cmd_generate(args):
    body = {"contents": [{"parts": [{"text": args.prompt}]}]}
    if args.tools:
        body["tools"] = json.loads(args.tools)
    if args.system:
        body["systemInstruction"] = {"parts": [{"text": args.system}]}
    status, payload = _request(
        "POST", f"/v1beta/models/{args.model}:generateContent", body)
    print(json.dumps({"status": status, "payload": payload}, indent=2)[:8000])
    return 0 if status == 200 else 1


def cmd_image(args):
    require_cost_confirm(args, args.model)
    parts = [{"text": args.prompt}]
    if args.image:
        parts.append(_file_part(args.image))
    payload = _merge_json(args.json, {"contents": [{"parts": parts}]})
    status, result = _request(
        "POST", f"/v1beta/models/{args.model}:generateContent", payload)
    if status != 200:
        _die(status, result)
    saved = _save_inline(result, args.out)
    print(json.dumps({"ok": True, "model": args.model, "saved": saved}, indent=2))


def cmd_imagen(args):
    require_cost_confirm(args, args.model)
    payload = _merge_json(args.json, {
        "instances": [{"prompt": args.prompt}],
        "parameters": {"sampleCount": args.count}})
    status, result = _request(
        "POST", f"/v1beta/models/{args.model}:predict", payload)
    if status != 200:
        _die(status, result)
    saved = []
    for i, pred in enumerate(result.get("predictions", [])):
        b64 = pred.get("bytesBase64Encoded")
        if b64:
            path = f"{args.out}-{i}.png"
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(b64))
            saved.append(path)
    print(json.dumps({"ok": True, "model": args.model, "saved": saved}, indent=2))


def cmd_video(args):
    require_cost_confirm(args, args.model)
    payload = _merge_json(args.json, {"instances": [{"prompt": args.prompt}]})
    status, result = _request(
        "POST", f"/v1beta/models/{args.model}:predictLongRunning", payload,
        timeout=300)
    if status != 200:
        _die(status, result)
    name = result.get("name", "")
    print(json.dumps({"ok": True, "model": args.model, "operation": name,
                      "next": f"poll op-status --op {name}, then "
                              f"download --op {name} --out <prefix>"}, indent=2))
    print("note: Veo renders take minutes; poll with backoff, do not hammer.",
          file=sys.stderr)


def _get_op(args):
    name = args.op.lstrip("/")
    status, result = _request("GET", f"/{name}")
    if status != 200:
        _die(status, result)
    return result


def cmd_op_status(args):
    result = _get_op(args)
    done = result.get("done", False)
    out = {"done": done}
    if done:
        out["response"] = result.get("response")
        out["error"] = result.get("error")
    else:
        out["metadata"] = result.get("metadata")
    print(json.dumps(out, indent=2))


def _find_video_uri(node):
    """Walk an operation response for a generated video download URI."""
    if isinstance(node, dict):
        uri = node.get("uri")
        if isinstance(uri, str) and ("files" in uri or ":download" in uri
                                     or uri.endswith(".mp4")):
            return uri
        for v in node.values():
            found = _find_video_uri(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _find_video_uri(v)
            if found:
                return found
    return None


def _find_video_b64(node):
    if isinstance(node, dict):
        b64 = node.get("bytesBase64Encoded")
        if isinstance(b64, str) and len(b64) > 1000:
            return b64
        for v in node.values():
            found = _find_video_b64(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _find_video_b64(v)
            if found:
                return found
    return None


def cmd_download(args):
    """Real download step for a finished Veo operation: fetch the generated
    video (URI form or inline base64 form) and save it to <out>.mp4."""
    result = _get_op(args)
    if not result.get("done"):
        print(json.dumps({"done": False, "metadata": result.get("metadata")},
                         indent=2))
        return
    response = result.get("response") or {}
    path = f"{args.out}.mp4"
    b64 = _find_video_b64(response)
    if b64:
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(b64))
        print(json.dumps({"ok": True, "saved": path, "form": "inline"}))
        return
    uri = _find_video_uri(response)
    if not uri:
        _die(0, {"error": "operation done but no video uri/bytes found",
                 "response": response})
    status, blob = _request("GET", uri, raw=True, timeout=300)
    if status != 200:
        _die(status, {"error": f"video download HTTP {status}"})
    with open(path, "wb") as fh:
        fh.write(blob)
    print(json.dumps({"ok": True, "saved": path, "bytes": len(blob)}))


def cmd_tts(args):
    require_cost_confirm(args, args.model)
    payload = _merge_json(args.json, {
        "contents": [{"parts": [{"text": args.text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {
                "prebuiltVoiceConfig": {"voiceName": args.voice}}}},
    })
    status, result = _request(
        "POST", f"/v1beta/models/{args.model}:generateContent", payload)
    if status != 200:
        _die(status, result)
    saved = _save_inline(result, args.out)
    print(json.dumps({"ok": True, "model": args.model, "saved": saved}, indent=2))


def main():
    p = argparse.ArgumentParser(description="Gemini API CLI (text + media)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth", help="verify the stored credential answers")

    m = sub.add_parser("models", help="list available models")
    m.add_argument("--limit", type=int, default=50)

    g = sub.add_parser("generate", help="text generation (system instruction, tools)")
    g.add_argument("--model", default=TEXT_MODEL)
    g.add_argument("--prompt", required=True)
    g.add_argument("--tools", default=None,
                   help="JSON array of tools, e.g. '[{\"google_maps\": {}}]' for Maps grounding")
    g.add_argument("--system", default=None)

    cc = ('REQUIRED for billed generation: "<model> <estimated cost>", '
          'confirmed by the user in conversation')

    im = sub.add_parser("image", help="Nano Banana text-to-image / edit (billed)")
    im.add_argument("--prompt", required=True)
    im.add_argument("--image", default=None, help="input image for editing")
    im.add_argument("--out", required=True, help="output path prefix")
    im.add_argument("--model", default=IMAGE_MODEL)
    im.add_argument("--json", default=None, help="extra JSON fields merged into the request")
    im.add_argument("--confirm-cost", default=None, help=cc)

    ig = sub.add_parser("imagen", help="Imagen 4 text-to-image (billed)")
    ig.add_argument("--prompt", required=True)
    ig.add_argument("--count", type=int, default=1)
    ig.add_argument("--out", required=True, help="output path prefix")
    ig.add_argument("--model", default=IMAGEN_MODEL)
    ig.add_argument("--json", default=None)
    ig.add_argument("--confirm-cost", default=None, help=cc)

    v = sub.add_parser("video", help="Veo text-to-video, async (billed per second)")
    v.add_argument("--prompt", required=True)
    v.add_argument("--model", default=VEO_MODEL)
    v.add_argument("--json", default=None)
    v.add_argument("--confirm-cost", default=None, help=cc)

    o = sub.add_parser("op-status", help="poll a long-running operation")
    o.add_argument("--op", required=True, help="operation id, e.g. operations/abc123")

    d = sub.add_parser("download", help="download a finished Veo operation's video")
    d.add_argument("--op", required=True)
    d.add_argument("--out", required=True, help="output path prefix (saves <out>.mp4)")

    t = sub.add_parser("tts", help="text-to-speech (billed)")
    t.add_argument("--text", required=True)
    t.add_argument("--voice", default="Kore", help="prebuilt voice name")
    t.add_argument("--out", required=True, help="output path prefix")
    t.add_argument("--model", default=TTS_MODEL)
    t.add_argument("--json", default=None)
    t.add_argument("--confirm-cost", default=None, help=cc)

    args = p.parse_args()
    try:
        if args.cmd == "auth":
            return cmd_auth(args)
        if args.cmd == "models":
            cmd_models(args)
        elif args.cmd == "generate":
            return cmd_generate(args)
        elif args.cmd == "image":
            cmd_image(args)
        elif args.cmd == "imagen":
            cmd_imagen(args)
        elif args.cmd == "video":
            cmd_video(args)
        elif args.cmd == "op-status":
            cmd_op_status(args)
        elif args.cmd == "download":
            cmd_download(args)
        elif args.cmd == "tts":
            cmd_tts(args)
    except DynamicCredentialError as e:
        print(json.dumps({"error": f"credential: {e}"}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
