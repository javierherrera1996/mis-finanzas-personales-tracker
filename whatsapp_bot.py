"""Bot de WhatsApp de finanzas (Meta WhatsApp Cloud API) que corre en el Mac.
- Te hace, una por una, las preguntas pendientes (de dónde viene una plata, qué fue un pago) y te pide confirmar saldos.
- Guarda tus respuestas en data/overrides.json (preguntas) y data/saldos_manual.json (saldos) y recalcula el Sheet.
- También responde: "cuánto puedo gastar", "pagos", "saldo", "preguntas", "ayuda".
Configuración en data/whatsapp.env (ver whatsapp.env.ejemplo). Uso: .venv/bin/python whatsapp_bot.py  (o vía launchd)."""
import datetime, hashlib, hmac, json, os, re, subprocess, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import requests

HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
ENV = dict(l.strip().split("=", 1) for l in open("data/whatsapp.env") if "=" in l and not l.startswith("#"))
TOKEN, PHONE_ID, VERIFY, SECRET = ENV["WA_TOKEN"], ENV["WA_PHONE_NUMBER_ID"], ENV["WA_VERIFY_TOKEN"], ENV.get("WA_APP_SECRET", "")
MI_NUMERO = re.sub(r"\D", "", ENV["WA_MI_NUMERO"])          # solo se atiende a este número
PORT = int(ENV.get("WA_PORT", "8787"))
ESTADO = "data/wa_estado.json"
SALDOS = "data/saldos_manual.json"
LOG = "data/whatsapp.log"
CUENTAS_A_CONFIRMAR = ["Bancolombia (cuenta de ahorros)", "Daviplata", "Nequi", "Tarjeta Bancolombia (deuda)", "Efectivo en la billetera"]
f = lambda v: "$" + f"{round(v):,}".replace(",", ".")


def log(x):
    open(LOG, "a").write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {x}\n")


def enviar(texto, a=MI_NUMERO):
    r = requests.post(f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages", timeout=20,
                      headers={"Authorization": f"Bearer {TOKEN}"},
                      json={"messaging_product": "whatsapp", "to": a, "type": "text", "text": {"body": texto[:4000]}})
    log(f"→ {r.status_code} {texto[:80]!r}")
    return r


def enviar_plantilla(nombre, idioma="es"):
    """Mensaje que inicia la conversación (fuera de la ventana de 24 h solo se permiten plantillas aprobadas)."""
    r = requests.post(f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages", timeout=20,
                      headers={"Authorization": f"Bearer {TOKEN}"},
                      json={"messaging_product": "whatsapp", "to": MI_NUMERO, "type": "template",
                            "template": {"name": nombre, "language": {"code": idioma}}})
    log(f"→ plantilla {nombre}: {r.status_code} {r.text[:200]}")
    return r.ok


def cargar(p, defecto):
    return json.load(open(p)) if os.path.exists(p) else defecto


def guardar(p, x):
    json.dump(x, open(p, "w"), ensure_ascii=False, indent=1)


def monto(texto):
    """'850 mil' / '1,2 M' / '$1.234.567' / '2 millones' -> número (o None)."""
    t = texto.lower().replace("$", "").strip()
    m = re.search(r"(\d+(?:[.,]\d+)*)\s*(m|mill|millones|mil|k)?\b", t)
    if not m: return None
    n, suf = m.group(1), m.group(2) or ""
    if suf in ("m", "mill", "millones"):
        return float(n.replace(".", "").replace(",", ".") if n.count(",") == 1 and n.count(".") == 0 else n.replace(",", ".")) * 1e6
    n = float(n.replace(".", "").replace(",", "")) if re.search(r"[.,]\d{3}\b", n) else float(n.replace(",", "."))
    return n * 1000 if suf in ("mil", "k") else n


def cola():
    """Lo que el bot tiene que preguntarte: preguntas pendientes + saldos a confirmar (máx. 1 vez por semana)."""
    pq = cargar("data/preguntas.json", [])
    resp = cargar("data/overrides.json", {}).get("respuestas", {})
    items = [{"tipo": "pregunta", "q": p["q"], "monto": p.get("monto", ""), "fechas": p.get("fechas", "")}
             for p in pq if not resp.get(p["q"]) and p.get("nuevo")]
    items += [{"tipo": "pregunta", "q": p["q"], "monto": p.get("monto", ""), "fechas": p.get("fechas", "")}
              for p in pq if not resp.get(p["q"]) and not p.get("nuevo")]
    saldos = cargar(SALDOS, {})
    hace7 = (datetime.date.today() - datetime.timedelta(days=6)).isoformat()
    items += [{"tipo": "saldo", "cuenta": c} for c in CUENTAS_A_CONFIRMAR if saldos.get(c, {}).get("fecha", "") < hace7]
    return items


def texto_item(it, i, n):
    if it["tipo"] == "saldo":
        return f"({i}/{n}) ¿Cuánto tienes hoy en *{it['cuenta']}*? Escribe el valor (ej. 850 mil), 'no tengo' o 'saltar'."
    q = re.sub(r"^\[[^\]]+\]\s*", "", it["q"])
    q = q.replace(" Escribe una categoría (p. ej. Comida, Préstamo a un amigo, Viajes) o una nota.", "")
    return f"({i}/{n}) {q}\nMonto: {it['monto']}\n\nResponde con una categoría corta (ej. 'Mercado', 'Préstamo a un amigo', 'Comida') o una explicación. 'saltar' para dejarla."


def aplicar_en_segundo_plano():
    def run():
        subprocess.run([".venv/bin/python", "build.py"], capture_output=True)
        subprocess.run([".venv/bin/python", "make_sheet.py"], capture_output=True)
        log("Sheet recalculado con tus respuestas")
    threading.Thread(target=run, daemon=True).start()


def resumen_gasto():
    from importlib import reload
    import agente; reload(agente)
    e = agente.estado()
    pend = "\n".join(f"• {p['fecha'].day}/{p['fecha'].month} {p['nombre']}: {f(p['monto'])}" for p in e["por_pagar_antes_del_sueldo"]) or "• Nada pendiente"
    extra = cargar(SALDOS, {})
    otros = "\n".join(f"• {k}: {f(v['valor'])} ({v['fecha']})" for k, v in extra.items() if v.get("valor"))
    return (f"💸 Puedes gastar *{f(e['por_dia'])} por día* hasta el sueldo ({e['proximo_pago'].day}/{e['proximo_pago'].month}, en {e['dias_al_pago']} días).\n"
            f"Libre: {f(e['libre'])} · Davivienda disponible {f(e['caja']['disponible'])} · bolsillo {f(e['caja']['bolsillo'])}\n\n"
            f"Antes del sueldo debes pagar:\n{pend}" + (f"\n\nOtros saldos que me diste:\n{otros}" if otros else ""))


AYUDA = ("Puedo:\n• *empezar* — te hago las preguntas pendientes y te pido saldos\n• *cuánto puedo gastar*\n• *pagos* — lo que falta pagar antes del sueldo\n"
         "• *saldo Bancolombia 850 mil* — registrar un saldo cuando quieras\n• *pausa* — dejar las preguntas para después")


def manejar(texto):
    st = cargar(ESTADO, {"activo": False, "items": [], "i": 0})
    t = texto.strip(); tl = t.lower()

    m = re.match(r"saldo\s+(.+?)\s+(\$?[\d.,]+\s*(?:mil|m|millones|k)?)\s*$", tl)
    if m:
        sal = cargar(SALDOS, {}); nombre = m.group(1).strip().title()
        sal[nombre] = {"valor": monto(m.group(2)), "fecha": datetime.date.today().isoformat()}
        guardar(SALDOS, sal); return f"Anotado: {nombre} = {f(sal[nombre]['valor'])} ✅"
    if re.search(r"cu[aá]nto puedo gastar|puedo gastar|cu[aá]nto tengo|caja", tl):
        return resumen_gasto()
    if re.search(r"^pagos|qu[eé] (me )?falta pagar", tl):
        return resumen_gasto().split("\n\n", 1)[1]
    if tl in ("ayuda", "help", "?", "menu", "menú"):
        return AYUDA
    if tl in ("pausa", "después", "despues", "luego", "stop"):
        st["activo"] = False; guardar(ESTADO, st); return "Listo, seguimos después. Escribe *empezar* cuando quieras. 👍"
    if not st["activo"] and re.search(r"^(hola|empezar|empecemos|dale|si|sí|arranquemos|preguntas)", tl):
        items = cola()
        if not items: return "No tengo preguntas pendientes 🎉\n\n" + AYUDA
        st = {"activo": True, "items": items, "i": 0}; guardar(ESTADO, st)
        return f"Tengo {len(items)} cosas por confirmar. Vamos una por una (escribe *pausa* para parar).\n\n" + texto_item(items[0], 1, len(items))

    if st["activo"]:
        it = st["items"][st["i"]]
        if tl not in ("saltar", "skip", "siguiente"):
            if it["tipo"] == "saldo":
                sal = cargar(SALDOS, {})
                val = 0 if re.search(r"no tengo|nada|cero|^0$", tl) else monto(t)
                if val is None: return "No entendí el valor 🤔 Escríbelo así: 850 mil, 1,2 M o 1.250.000 (o 'saltar')."
                sal[it["cuenta"]] = {"valor": val, "fecha": datetime.date.today().isoformat()}; guardar(SALDOS, sal)
            else:
                ov = cargar("data/overrides.json", {"movimientos": {}, "respuestas": {}})
                ov.setdefault("respuestas", {})[it["q"]] = t; guardar("data/overrides.json", ov)
        st["i"] += 1
        if st["i"] >= len(st["items"]):
            st["activo"] = False; guardar(ESTADO, st); aplicar_en_segundo_plano()
            return "¡Listo, gracias! 🙌 Ya actualizo tu Sheet con lo que me dijiste.\n\n" + resumen_gasto()
        guardar(ESTADO, st)
        return "✅\n\n" + texto_item(st["items"][st["i"]], st["i"] + 1, len(st["items"]))
    return "Hola 👋 " + AYUDA


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):  # verificación del webhook que hace Meta
        q = parse_qs(urlparse(self.path).query)
        if q.get("hub.mode") == ["subscribe"] and q.get("hub.verify_token") == [VERIFY]:
            self.send_response(200); self.end_headers(); self.wfile.write(q["hub.challenge"][0].encode()); return
        self.send_response(200 if self.path == "/salud" else 403); self.end_headers(); self.wfile.write(b"ok")

    def do_POST(self):
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200); self.end_headers()
        if SECRET:  # solo aceptar mensajes firmados por Meta
            firma = "sha256=" + hmac.new(SECRET.encode(), cuerpo, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(firma, self.headers.get("X-Hub-Signature-256", "")):
                log("firma inválida: ignorado"); return
        try:
            data = json.loads(cuerpo)
            for e in data.get("entry", []):
                for c in e.get("changes", []):
                    for msg in c.get("value", {}).get("messages", []):
                        if re.sub(r"\D", "", msg.get("from", "")) != MI_NUMERO:
                            log(f"mensaje de otro número ignorado"); continue
                        texto = msg.get("text", {}).get("body", "") if msg.get("type") == "text" else ""
                        log(f"← {texto[:80]!r}")
                        enviar(manejar(texto) if texto else "Por ahora solo entiendo texto ✍️")
        except Exception as ex:
            log(f"ERROR {ex}")


if __name__ == "__main__":
    import sys
    if "--ping" in sys.argv:  # lo llama actualizar.py al terminar: te invita a responder
        n = len(cola())
        if n: enviar_plantilla(ENV.get("WA_PLANTILLA", "hello_world"), ENV.get("WA_PLANTILLA_IDIOMA", "en_US"))
        sys.exit(0)
    log(f"bot escuchando en :{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
