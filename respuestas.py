"""Preguntas por correo: el informe semanal trae preguntas numeradas; el usuario responde el correo y este módulo
lee la respuesta, aplica lo que dijo (categorías, notas, saldos), recalcula y le confirma por correo.
Lo llama actualizar.py cada 15 minutos (modo --semanal)."""
import base64, datetime, json, os, re, subprocess
from email.mime.text import MIMEText

LISTAS = "data/listas_preguntas.json"      # {tag: [items numerados]} de cada informe enviado
PROCESADOS = "data/respuestas_procesadas.json"
SALDOS = "data/saldos_manual.json"
CUENTAS = {"bancolombia": "Bancolombia (cuenta de ahorros)", "nequi": "Nequi", "daviplata": "Daviplata",
           "efectivo": "Efectivo en la billetera", "tarjeta bancolombia": "Tarjeta Bancolombia (deuda)"}
MAX_PREGUNTAS = 10
f = lambda v: "$" + f"{round(v):,}".replace(",", ".")


def cargar(p, d):
    return json.load(open(p)) if os.path.exists(p) else d


def guardar(p, x):
    json.dump(x, open(p, "w"), ensure_ascii=False, indent=1)


def monto(texto):
    """'850 mil' / '1,2 M' / '$1.234.567' / '2 millones' / '300k' -> número (o None)."""
    t = texto.lower().replace("$", "").strip()
    if re.search(r"no tengo|nada|cero|^0$", t): return 0.0
    m = re.search(r"(\d+(?:[.,]\d+)*)\s*(m|mill|millones|mil|k)?\b", t)
    if not m: return None
    n, suf = m.group(1), m.group(2) or ""
    if suf in ("m", "mill", "millones"): return float(n.replace(",", ".")) * 1e6
    n = float(n.replace(".", "").replace(",", "")) if re.search(r"[.,]\d{3}\b", n) else float(n.replace(",", "."))
    return n * 1000 if suf in ("mil", "k") else n


def armar_lista(tag):
    """Preguntas pendientes (las más recientes primero, máx. 10) numeradas para el correo de esta semana."""
    pq = cargar("data/preguntas.json", [])
    resp = cargar("data/overrides.json", {}).get("respuestas", {})
    from agente import CATS_DUDOSAS
    cat = {m["ID"]: m["Categoría"] for m in cargar("data/movimientos.json", [])}
    # fuera las ya respondidas y las de movimientos que el sistema ya sabe clasificar
    pend = [p for p in pq if not resp.get(p["q"]) and (not p.get("id") or cat.get(p["id"]) in CATS_DUDOSAS)]
    pend = sorted([p for p in pend if p.get("nuevo")], key=lambda p: p.get("fechas", ""), reverse=True) + [p for p in pend if not p.get("nuevo")]
    items = [{"n": i + 1, "q": p["q"], "monto": p.get("monto", ""), "fechas": p.get("fechas", "")} for i, p in enumerate(pend[:MAX_PREGUNTAS])]
    listas = cargar(LISTAS, {}); listas[tag] = items; guardar(LISTAS, listas)
    return items, len(pend)


def texto_pregunta(q):
    q = re.sub(r"^\[[^\]]+\]\s*", "", q)
    return q.replace(" Escribe una categoría (p. ej. Comida, Préstamo a un amigo, Viajes) o una nota.", "")


def html_seccion(items, total):
    filas = "".join(f"<tr><td style='padding:4px 8px;font-weight:700'>{it['n']}</td><td style='padding:4px 8px'>{texto_pregunta(it['q'])[:170]}</td>"
                    f"<td style='padding:4px 8px;white-space:nowrap'>{it['monto']}</td></tr>" for it in items)
    ejemplo = "<br>".join([f"{items[0]['n']}: mercado"] + ([f"{items[1]['n']}: préstamo a un amigo"] if len(items) > 1 else []) + ["Bancolombia: 850 mil", "Nequi: 120 mil"])
    return f"""<h3>✍️ Responde este correo ({total} pendientes{', aquí van las ' + str(len(items)) + ' más recientes' if total > len(items) else ''})</h3>
<table style='border-collapse:collapse;font-size:14px;width:100%'>{filas}</table>
<p style='font-size:14px'>Y cuéntame tus saldos de hoy en: <b>Bancolombia, Nequi, Daviplata, efectivo</b> y lo que debes en la <b>tarjeta Bancolombia</b>.</p>
<p style='font-size:14px;background:#f6f8fa;padding:10px;border-radius:8px'>Dale <b>Responder</b> y escribe, una por línea:<br><code>{ejemplo}</code><br>
<span style='color:#666'>Número: una categoría corta (Comida, Arriendo, Préstamo a un amigo…) o una explicación. "saltar" para dejarla. Te confirmo por correo lo que entendí.</span></p>"""


# ---------- leer respuestas ----------
def _cuerpo(payload):
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "ignore")
    for p in payload.get("parts", []) or []:
        t = _cuerpo(p)
        if t: return t
    if payload.get("body", {}).get("data"):
        t = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "ignore")
        return re.sub(r"<[^>]+>", "\n", t)
    return ""


def _sin_citas(t):
    out = []
    for l in t.splitlines():
        if re.match(r"^\s*>", l) or re.match(r"^\s*(El|On)\s.+(escribi[oó]|wrote):?\s*$", l) or re.match(r"^-{2,}\s*(Original|Mensaje)", l, re.I):
            break
        out.append(l)
    return out


def interpretar(lineas, items):
    por_n = {it["n"]: it for it in items}
    respuestas, saldos, no_entendi = [], [], []
    for l in lineas:
        l = l.strip()
        if not l: continue
        m = re.match(r"^(\d{1,2})\s*[:.)\-–=]\s*(.+)$", l)
        if m and int(m.group(1)) in por_n:
            if m.group(2).strip().lower() not in ("saltar", "skip", "no se", "no sé"):
                respuestas.append((por_n[int(m.group(1))], m.group(2).strip()))
            continue
        m = re.match(r"^(tarjeta bancolombia|bancolombia|nequi|daviplata|efectivo)\b\s*[:=\-]?\s*(.+)$", l, re.I)
        if m:
            v = monto(m.group(2))
            if v is not None:
                saldos.append((CUENTAS[m.group(1).lower()], v)); continue
        # texto libre: si menciona un monto igual al de una pregunta (±1%), es la respuesta a esa pregunta
        cifras = [monto(x) for x in re.findall(r"\$?\d[\d.,]*\s*(?:mil|millones|m|k)?", l, re.I)]
        cifras = [c for c in cifras if c and c >= 10000]
        hecho = False
        for it in items:
            mi = monto(it.get("monto", "") or "")
            if mi and any(abs(c - mi) <= mi * 0.01 for c in cifras) and it not in [r[0] for r in respuestas]:
                respuestas.append((it, l)); hecho = True; break
        if not hecho and len(l) < 400 and not re.match(r"^(hola|gracias|saludos|enviado desde)", l, re.I):
            no_entendi.append(l)
    return respuestas, saldos, no_entendi


def procesar(svc_leer, svc_enviar=None, dest=None):
    """Busca respuestas nuevas a los informes, aplica y confirma. Devuelve cuántas procesó."""
    from config import C
    dest = dest or C["correo"]
    listas = cargar(LISTAS, {}); hechos = set(cargar(PROCESADOS, []))
    if not listas: return 0
    r = svc_leer.users().messages().list(userId="me", q='from:me subject:"[Fin-" newer_than:30d', maxResults=30).execute()
    n = 0
    for x in r.get("messages", []):
        if x["id"] in hechos: continue
        msg = svc_leer.users().messages().get(userId="me", id=x["id"], format="full").execute()
        h = {k["name"].lower(): k["value"] for k in msg["payload"]["headers"]}
        asunto = h.get("subject", "")
        tag = re.search(r"\[(Fin-[\d-]+)\]", asunto)
        if not re.match(r"^\s*(re|rv|fw|fwd)\s*:", asunto, re.I) or not tag or tag.group(1) not in listas:
            hechos.add(x["id"]); continue   # el informe original u otro correo: no es una respuesta
        cuerpo_txt = _cuerpo(msg["payload"])
        if "Recibí tu respuesta" in cuerpo_txt.split("escribió")[0]:
            hechos.add(x["id"]); continue   # es una confirmación que envió el sistema
        respuestas, saldos, no_entendi = interpretar(_sin_citas(cuerpo_txt), listas[tag.group(1)])
        ov = cargar("data/overrides.json", {"movimientos": {}, "respuestas": {}})
        for it, txt in respuestas: ov.setdefault("respuestas", {})[it["q"]] = txt
        guardar("data/overrides.json", ov)
        sal = cargar(SALDOS, {}); hoy = datetime.date.today().isoformat()
        for cuenta, v in saldos: sal[cuenta] = {"valor": v, "fecha": hoy}
        guardar(SALDOS, sal)
        if no_entendi:  # queda para que Claude lo revise con el usuario (skill finanzas-clasificar)
            libres = cargar("data/respuestas_libres.json", [])
            libres.append({"fecha": datetime.date.today().isoformat(), "tag": tag.group(1), "lineas": no_entendi, "revisado": False})
            guardar("data/respuestas_libres.json", libres)
        hechos.add(x["id"]); guardar(PROCESADOS, sorted(hechos)); n += 1
        # recalcular con lo nuevo y confirmar
        subprocess.run([".venv/bin/python", "build.py"], capture_output=True)
        subprocess.run([".venv/bin/python", "make_sheet.py"], capture_output=True)
        if svc_enviar:
            from importlib import reload
            import agente; reload(agente); e = agente.estado()
            lineas = [f"• {it['n']}. {texto_pregunta(it['q'])[:90]} → <b>{txt}</b>" for it, txt in respuestas]
            lineas += [f"• {c} → <b>{f(v)}</b>" for c, v in saldos]
            cuerpo = (f"<p>Recibí tu respuesta ✅. Esto es lo que entendí y ya quedó en tu Sheet:</p><p>{'<br>'.join(lineas) or '(no encontré respuestas con número ni saldos)'}</p>"
                      + (f"<p>Estas líneas no las pude asignar solo; quedaron guardadas y las reviso contigo la próxima vez que abras Claude (o reescríbelas como <code>3: comida</code> / <code>Nequi: 120 mil</code>):<br><i>{'<br>'.join(no_entendi[:8])}</i></p>" if no_entendi else "")
                      + f"<p>💸 Ahora puedes gastar <b>{f(e['por_dia'])} por día</b> hasta el sueldo ({e['proximo_pago']:%d/%m}). Quedan {len(e['preguntas'])} preguntas pendientes.</p>")
            m = MIMEText(cuerpo, "html", "utf-8"); m["to"] = dest; m["from"] = dest
            m["subject"] = "Re: " + re.sub(r"^\s*(re|rv)\s*:\s*", "", asunto, flags=re.I)
            if h.get("message-id"): m["In-Reply-To"] = h["message-id"]; m["References"] = h["message-id"]
            svc_enviar.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(m.as_bytes()).decode(),
                                                                   "threadId": msg["threadId"]}).execute()
            guardar(PROCESADOS, sorted(hechos))
    return n


if __name__ == "__main__":
    from googleapiclient.discovery import build
    from auth import get_creds, SCOPES
    c = get_creds(SCOPES)
    print("Respuestas procesadas:", procesar(build("gmail", "v1", credentials=c), build("gmail", "v1", credentials=c)))
