"""Mira el Gmail del usuario y dice qué bancos, billeteras, tarjetas, inversiones y CDTs le escriben (último año), si mandan
extractos en PDF, qué productos se ven de cada uno (un mismo banco puede tener cuenta Y tarjeta: RappiCuenta y RappiCard),
qué terminaciones aparecen y cuáles ya lee el sistema. Lo usa la skill instalar-finanzas para armar config.json -> cuentas.
Uso: .venv/bin/python detectar_bancos.py"""
import collections, re
from email.utils import parseaddr
from googleapiclient.discovery import build
from auth import get_creds
from fetch_util import call

CLAVES = ["bancolombia", "notificacionesbancolombia.com", "an.notificacionesbancolombia.com", "davivienda", "nu.com.co", "nequi", "daviplata", "bbva", "scotiabank", "colpatria", "itau", "bancodebogota",
          "bancodeoccidente", "avvillas", "bancopopular", "bancofalabella", "lulobank", "rappipay", "rappi", "rappicard", "addi", "sistecredito",
          "movii", "dale", "bancocajasocial", "achcolombia", "pse", "global66", "nubank", "lulo", "rappicuenta", "nequi.com.co", "daviplata.com", "dale.com.co", "movii.com.co", "mibanco", "bancoagrario", "serfinanza",
          "coltefinanciera", "bold.co", "wompi", "payu", "mercadopago", "cesantias", "porvenir", "proteccion", "colfondos", "icetex",
          # inversiones, CDTs y bancos más nuevos
          "trii", "littio", "tyba", "hapi", "koa", "santander", "uala", "finandina", "pichincha", "bancow"]
LEE_YA = {"davivienda": "extractos + alertas", "nu.com.co": "extractos de tarjeta", "bancolombia": "alertas", "addi": "extractos"}
# ojo: dominios de publicidad del mismo banco (promociones.*, ofertas.*) salen como "ya lo lee" pero no traen movimientos
# qué producto sugiere cada correo (asunto + primeras líneas); el usuario confirma
PISTAS = {"tarjeta de crédito": r"tarjeta de cr[eé]dito|\bT\.? ?CRED|\bTC\b|RappiCard|\bCMR\b|cupo|pago m[ií]nimo",
          "cuenta / billetera": r"cuenta|ahorros|bolsillo|cajita|recibiste|transferiste|consignaci|recarga",
          "inversión": r"inversi[oó]n|acciones|portafolio|rentabilidad|dividendo|\bETF\b|d[oó]lares digitales",
          "CDT": r"\bCDT\b|dep[oó]sito a t[eé]rmino",
          "crédito": r"pr[eé]stamo|desembolso|cuota de tu cr[eé]dito|libranza|compra de cartera"}
Q = "newer_than:365d (" + " OR ".join(f"from:{c}" for c in CLAVES) + ")"

svc = build("gmail", "v1", credentials=get_creds())
ids, tok = [], None
while len(ids) < 1500:
    r = call(svc.users().messages().list(userId="me", q=Q, pageToken=tok, maxResults=500))
    ids += [m["id"] for m in r.get("messages", [])]
    tok = r.get("nextPageToken")
    if not tok: break

por = collections.defaultdict(lambda: {"n": 0, "asuntos": collections.Counter(), "terminaciones": collections.Counter(), "productos": collections.Counter()})
def leer(i):
    m = call(svc.users().messages().get(userId="me", id=i, format="metadata", metadataHeaders=["From", "Subject"]))
    h = {x["name"]: x["value"] for x in m["payload"].get("headers", [])}
    dom = parseaddr(h.get("From", ""))[1].split("@")[-1].lower()
    d = por[dom]; d["n"] += 1
    d["asuntos"][re.sub(r"\d", "#", h.get("Subject", ""))[:60]] += 1
    for t in re.findall(r"\*+(\d{4})\b", m.get("snippet", "")): d["terminaciones"][t] += 1
    for k, pat in PISTAS.items():
        if re.search(pat, h.get("Subject", "") + " " + m.get("snippet", ""), re.I): d["productos"][k] += 1

for i in ids[:600]:   # muestra suficiente para ver remitentes y terminaciones
    leer(i)
# los que escriben poco (un banco nuevo, un CDT) no alcanzan a salir en la muestra: se buscan uno por uno
for c in CLAVES:
    if any(c.split(".")[0] in dom for dom in list(por)): continue
    for x in call(svc.users().messages().list(userId="me", q=f"newer_than:365d from:{c}", maxResults=5)).get("messages", []):
        leer(x["id"])

print(f"Correos financieros del último año: {len(ids)} (analizados {min(len(ids), 600)} + los remitentes poco frecuentes)\n")
for dom, d in sorted(por.items(), key=lambda x: -x[1]["n"]):
    pdf = call(svc.users().messages().list(userId="me", q=f"newer_than:365d from:{dom} has:attachment filename:pdf", maxResults=50)).get("resultSizeEstimate", 0)
    ya = next((v for k, v in LEE_YA.items() if k in dom), None)
    print(f"• {dom}: {d['n']} correos · PDFs: {pdf} · {'YA LO LEE (' + ya + ')' if ya else 'NO lo lee todavía'}")
    print(f"    asuntos típicos: {', '.join(a for a, _ in d['asuntos'].most_common(3))}")
    if d["productos"]: print(f"    productos que se ven: {', '.join(f'{k} ({n})' for k, n in d['productos'].most_common())}")
    if d["terminaciones"]: print(f"    terminaciones vistas: {', '.join('*' + t for t, _ in d['terminaciones'].most_common(5))}")
print("\nConfirma con el usuario cada producto (y los que no escriben al correo) y escríbelos en config.json -> cuentas.")
