"""Arma el informe semanal en HTML y te lo envía por correo (o lo guarda en data/informes/ si aún no hay permiso de envío).
Uso: .venv/bin/python informe_semanal.py [--no-enviar]"""
import base64, datetime, json, os, sys
from email.mime.text import MIMEText
from agente import estado, HOY

from config import C
DEST = C["correo"]
SHEET = "https://docs.google.com/spreadsheets/d/" + open("data/sheet_id.txt").read().strip()
MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()
f = lambda v: "$" + f"{round(v):,}".replace(",", ".")
d = lambda x: f"{x.day} {MESES[x.month - 1]}"


SECCION_PREGUNTAS = ""


def html(e):
    c = e["caja"]
    color = "#1a7f37" if e["por_dia"] > 150000 else "#b35900" if e["por_dia"] > 60000 else "#c62828"
    sem_ok = e["gasto_semana"] <= e["techo_semana"]
    filas = lambda rows: "".join(f"<tr>{''.join(f'<td style=\"padding:4px 10px;border-bottom:1px solid #eee\">{x}</td>' for x in r)}</tr>" for r in rows)
    tabla = lambda cab, rows: (f"<table style='border-collapse:collapse;font-size:14px;width:100%'><tr>{''.join(f'<th style=\"text-align:left;padding:4px 10px;border-bottom:2px solid #ccc\">{h}</th>' for h in cab)}</tr>{filas(rows)}</table>")
    por_pagar = [[d(p["fecha"]) + (" ⚠️ vencido" if p["fecha"] < HOY else ""), p["nombre"], f(p["monto"]), p["como"]] for p in e["por_pagar_antes_del_sueldo"]]
    proximos = [[d(p["fecha"]), ("✅" if p["pagado"] else "🔁" if p.get("automatico") else "⏳") + " " + p["nombre"], f(p["monto"]) if p.get("monto") else "ver extracto"]
                for p in e["proximos"] if p["fecha"] >= HOY - datetime.timedelta(days=3)]
    top = [[m["Fecha"][5:], m["Comercio"][:40] or m["Descripción"][:40], m["Categoría"], f(-m["Valor"])] for m in e["top_semana"]]
    ing = [[m["Fecha"][5:], m["Subcategoría"] or m["Categoría"], f(m["Valor"])] for m in e["ingresos_semana"]]
    subs = [s for s in e["suscripciones"] if s["activa"]]
    sub_rows = [[s["nombre"], f(s["mensual"]) + "/mes", s["sugerencia"]] for s in subs[:8]]
    cats = [[k, f(v)] for k, v in e["categorias_ciclo"][:6]]
    pq = [p for p in e["preguntas"] if p.get("nuevo")][:8]
    pq_rows = [[p["fechas"], p["monto"], p["q"].replace("[Nuevo] ", "")[:120]] for p in pq]
    cred = " · ".join(f"{c['nombre']} {f(c['saldo'])}" for c in e["creditos"])
    return f"""<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:720px;color:#222">
<h2 style="margin-bottom:0">Tu semana financiera — {d(HOY)} {HOY.year}</h2>
<p style="color:#666;margin-top:4px">Datos hasta el {c['hasta']} · sueldo el {d(e['proximo_pago'])} (en {e['dias_al_pago']} días)</p>

<div style="background:#f6f8fa;border-radius:10px;padding:16px;margin:12px 0">
  <div style="font-size:15px;color:#555">Puedes gastar hasta el sueldo</div>
  <div style="font-size:34px;font-weight:700;color:{color}">{f(e['por_dia'])} por día</div>
  <div style="font-size:14px;color:#555">{f(e['libre'])} libres = {f(c['disponible'])} disponibles en Davivienda{(' + ' + f(e['liquido_otros']) + ' en otras cuentas (confirmados por WhatsApp)') if e['liquido_otros'] else ''}{(' − ' + f(e['deuda_tc_otros']) + ' de tarjeta Bancolombia') if e['deuda_tc_otros'] else ''} − {f(e['comprometido'])} de pagos pendientes antes del sueldo.<br>
  Caja total Davivienda {f(c['total'])}. En el bolsillo: {f(c['reservado_inversion'])} reservados para inversión{(' + ' + f(c['emergencia']) + ' de colchón') if c['emergencia'] > 0 else ''} (no se cuentan para gastar).</div>
</div>

<h3>Antes del sueldo tienes que pagar</h3>
{tabla(["Fecha", "Pago", "Monto", "Cómo"], por_pagar) if por_pagar else "<p>Nada pendiente 🎉</p>"}

<h3>Esta semana</h3>
<p>Gasto variable (sin arriendo, impuestos ni inglés): <b>{f(e['gasto_semana'])}</b> — techo semanal {f(e['techo_semana'])} {"✅" if sem_ok else "❌ te pasaste por " + f(e['gasto_semana'] - e['techo_semana'])}
{f"<br>Pagos fijos de la semana: {f(e['fijos_semana'])}" if e['fijos_semana'] else ""}</p>
{tabla(["Fecha", "En qué", "Categoría", "Valor"], top) if top else ""}
{("<p><b>Ingresos de la semana</b></p>" + tabla(["Fecha", "Fuente", "Valor"], ing)) if ing else "<p>Sin ingresos esta semana.</p>"}

<h3>Desde el último sueldo ({d(e['ultimo_pago'])})</h3>
<p>Gasto variable: <b>{f(e['gasto_ciclo'])}</b> de un techo mensual de {f(e['techo_ciclo'])}.</p>
{tabla(["Categoría", "Gastado"], cats) if cats else ""}

<h3>Próximos pagos</h3>
{tabla(["Fecha", "Pago", "Monto"], proximos)}
<p style="font-size:12px;color:#777">✅ pagado · ⏳ pendiente · 🔁 automático. Los recordatorios también están en tu Google Calendar.</p>

<h3>Deudas</h3>
<p>Total conocido <b>{f(e['deuda'])}</b> ({cred}). Mira la pestaña <b>Proyección deudas</b> del Sheet para ver cuándo sales y cuánto ahorras abonando extra.</p>

{"".join(f"<p style='background:#fdecea;padding:10px;border-radius:8px'>⚠️ <b>{s['nombre']}</b> te siguió cobrando después de cancelarla: " + ", ".join(f"{fe} {f(v)}" for fe, v in s['cobro_tras_cancelar']) + ". Revísalo.</p>" for s in e['suscripciones'] if s.get('cobro_tras_cancelar'))}
<h3>Suscripciones activas: {f(sum(s['mensual'] for s in subs))}/mes</h3>
{tabla(["Servicio", "Costo", "Sugerencia"], sub_rows)}

{SECCION_PREGUNTAS}
<p><a href="{SHEET}" style="background:#1f6feb;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none">Responder en el Sheet (pestaña Preguntas)</a></p>
<p style="font-size:12px;color:#777">Notas: las compras con la tarjeta Nu aparecen cuando llega su extracto (día 7). Bancolombia se lee de las alertas (no muestra saldo). Los traslados entre tus cuentas no cuentan como gasto.</p>
</div>"""


def enviar(cuerpo, asunto):
    from googleapiclient.discovery import build
    from auth import get_creds, SCOPES
    from google.oauth2.credentials import Credentials
    granted = set(Credentials.from_authorized_user_file("token.json").scopes or [])
    if "https://www.googleapis.com/auth/gmail.send" not in granted:
        return False
    msg = MIMEText(cuerpo, "html", "utf-8"); msg["to"] = DEST; msg["from"] = DEST; msg["subject"] = asunto
    svc = build("gmail", "v1", credentials=get_creds(SCOPES))
    svc.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}).execute()
    return True


if __name__ == "__main__":
    e = estado()
    import respuestas
    tag = f"Fin-{HOY}"
    items, total = respuestas.armar_lista(tag)
    SECCION_PREGUNTAS = respuestas.html_seccion(items, total) if items else "<p>✅ No hay preguntas pendientes. Si quieres, responde este correo con tus saldos (ej. <code>Bancolombia: 850 mil</code>).</p>"
    cuerpo = html(e)
    os.makedirs("data/informes", exist_ok=True)
    ruta = f"data/informes/{HOY}.html"; open(ruta, "w").write(cuerpo)
    asunto = f"💸 Puedes gastar {f(e['por_dia'])}/día hasta el {d(e['proximo_pago'])} · informe semanal [{tag}]"
    if "--no-enviar" in sys.argv:
        print("Guardado en", ruta)
    elif enviar(cuerpo, asunto):
        print("Informe enviado a", DEST)
    else:
        print("Aún no hay permiso para enviar correo; informe guardado en", ruta)
