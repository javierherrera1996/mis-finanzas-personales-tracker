"""Descarga correos completos de una búsqueda a data/<nombre>.jsonl (texto plano + adjuntos listados)."""
import base64, json, sys, time, html, re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from auth import get_creds
svc = build("gmail", "v1", credentials=get_creds())

def call(req):
    for attempt in range(20):
        try:
            return req.execute()
        except HttpError as e:
            if e.resp.status not in (403, 429, 500, 503): raise
            time.sleep(min(60, 2 ** attempt))
        except (OSError, ConnectionError) as e:
            time.sleep(min(60, 2 ** attempt))
    raise RuntimeError("demasiados reintentos")
name, q = sys.argv[1], sys.argv[2]
ids, tok = [], None
while True:
    r = call(svc.users().messages().list(userId="me", q=q, pageToken=tok, maxResults=500))
    ids += [m["id"] for m in r.get("messages", [])]
    tok = r.get("nextPageToken")
    if not tok: break

def text_of(part, out, atts):
    mt = part.get("mimeType", ""); body = part.get("body", {})
    if part.get("filename"):
        atts.append({"filename": part["filename"], "attachmentId": body.get("attachmentId"), "mime": mt})
    elif mt in ("text/plain", "text/html") and body.get("data"):
        t = base64.urlsafe_b64decode(body["data"]).decode("utf-8", "ignore")
        if mt == "text/html":
            t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
            t = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|td|li|h\d)>", "\n", t)
            t = html.unescape(re.sub(r"<[^>]+>", " ", t))
        out.append((mt, t))
    for p in part.get("parts", []) or []:
        text_of(p, out, atts)

import os
path = f"data/{name}.jsonl"
done = {json.loads(l)["id"] for l in open(path)} if os.path.exists(path) else set()
with open(path, "a") as f:
    for mid in ids:
        if mid in done: continue
        m = call(svc.users().messages().get(userId="me", id=mid, format="full"))
        time.sleep(0.05)
        h = {x["name"]: x["value"] for x in m["payload"]["headers"]}
        out, atts = [], []
        text_of(m["payload"], out, atts)
        plain = [t for mt, t in out if mt == "text/plain"]
        body = plain[0] if plain else (out[0][1] if out else "")
        body = re.sub(r"[ \t\xa0]+", " ", body); body = re.sub(r"\n\s*\n+", "\n", body).strip()
        f.write(json.dumps({"id": mid, "date": int(m["internalDate"]) // 1000, "from": h.get("From"),
                            "subject": h.get("Subject"), "body": body, "atts": atts}, ensure_ascii=False) + "\n")
print(name, len(ids))
