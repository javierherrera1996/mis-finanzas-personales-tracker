"""Descarga los PDF adjuntos de los correos ya bajados (data/*.jsonl) que coincidan con un filtro de remitente."""
import base64, json, os, re, sys, datetime
from googleapiclient.discovery import build
from auth import get_creds
from fetch_util import call
svc = build("gmail", "v1", credentials=get_creds())
src, pat, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(outdir, exist_ok=True)
for l in open(src):
    r = json.loads(l)
    if not re.search(pat, (r["from"] or "") + " " + (r["subject"] or ""), re.I): continue
    for a in r["atts"]:
        if not a["filename"].lower().endswith(".pdf") or not a["attachmentId"]: continue
        d = datetime.date.fromtimestamp(r["date"]).isoformat()
        fn = os.path.join(outdir, f"{d}_{re.sub(r'[^\w.-]', '_', a['filename'])}")
        if os.path.exists(fn): continue
        att = call(svc.users().messages().attachments().get(userId="me", messageId=r["id"], id=a["attachmentId"]))
        open(fn, "wb").write(base64.urlsafe_b64decode(att["data"]))
        print(fn)
