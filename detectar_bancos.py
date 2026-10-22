"""Mira el Gmail del usuario y dice qué bancos, billeteras y tarjetas le escriben (último año), si mandan extractos en PDF,
qué terminaciones de cuenta/tarjeta aparecen y cuáles ya lee el sistema. Lo usa la skill instalar-finanzas.
Uso: .venv/bin/python detectar_bancos.py"""
import collections, re
from email.utils import parseaddr
from googleapiclient.discovery import build
from auth import get_creds
from fetch_util import call

CLAVES = ["bancolombia", "notificacionesbancolombia.com", "an.notificacionesbancolombia.com", "davivienda", "nu.com.co", "nequi", "daviplata", "bbva", "scotiabank", "colpatria", "itau", "bancodebogota",
          "bancodeoccidente", "avvillas", "bancopopular", "bancofalabella", "lulobank", "rappipay", "rappi", "addi", "sistecredito",
          "movii", "dale", "bancocajasocial", "achcolombia", "pse", "global66", "nubank", "lulo", "rappicuenta", "nequi.com.co", "daviplata.com", "dale.com.co", "movii.com.co", "mibanco", "bancoagrario", "serfinanza",
          "coltefinanciera", "bold.co", "wompi", "payu", "mercadopago", "cesantias", "porvenir", "proteccion", "colfondos", "icetex"]
LEE_YA = {"davivienda": "extractos + alertas", "nu.com.co": "extractos de tarjeta", "bancolombia": "alertas", "addi": "extractos"}
# ojo: dominios de publicidad del mismo banco (promociones.*, ofertas.*) salen como "ya lo lee" pero no traen movimientos
Q = "newer_than:365d (" + " OR ".join(f"from:{c}" for c in CLAVES) + ")"

svc = build("gmail", "v1", credentials=get_creds())
ids, tok = [], None
while len(ids) < 1500:
    r = call(svc.users().messages().list(userId="me", q=Q, pageToken=tok, maxResults=500))
    ids += [m["id"] for m in r.get("messages", [])]
    tok = r.get("nextPageToken")
    if not tok: break

por = collections.defaultdict(lambda: {"n": 0, "asuntos": collections.Counter(), "terminaciones": collections.Counter()})
for i in ids[:600]:   # muestra suficiente para ver remitentes y terminaciones
    m = call(svc.users().messages().get(userId="me", id=i, format="metadata", metadataHeaders=["From", "Subject"]))
    h = {x["name"]: x["value"] for x in m["payload"].get("headers", [])}
    dom = parseaddr(h.get("From", ""))[1].split("@")[-1].lower()
    d = por[dom]; d["n"] += 1
    d["asuntos"][re.sub(r"\d", "#", h.get("Subject", ""))[:60]] += 1
    for t in re.findall(r"\*+(\d{4})\b", m.get("snippet", "")): d["terminaciones"][t] += 1

print(f"Correos financieros del último año: {len(ids)} (analizados {min(len(ids), 600)})\n")
for dom, d in sorted(por.items(), key=lambda x: -x[1]["n"]):
    pdf = call(svc.users().messages().list(userId="me", q=f"newer_than:365d from:{dom} has:attachment filename:pdf", maxResults=50)).get("resultSizeEstimate", 0)
    ya = next((v for k, v in LEE_YA.items() if k in dom), None)
    print(f"• {dom}: {d['n']} correos · PDFs: {pdf} · {'YA LO LEE (' + ya + ')' if ya else 'NO lo lee todavía'}")
    print(f"    asuntos típicos: {', '.join(a for a, _ in d['asuntos'].most_common(3))}")
    if d["terminaciones"]: print(f"    terminaciones vistas: {', '.join('*' + t for t, _ in d['terminaciones'].most_common(5))}")
