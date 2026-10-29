"""Crea/actualiza en tu Google Calendar los recordatorios de pagos de data/pagos_config.json (sin duplicar)."""
import datetime, json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from auth import get_creds, SCOPES

CAL = "primary"


# Avisos antes de que venza (eventos de todo el día: los minutos se cuentan desde la medianoche del día del pago)
ANTES = [3 * 1440 - 540, 1440 - 540]   # 3 días antes y 1 día antes, a las 9:00 a. m.


def lista_pagos(cfg):
    """Texto con lo que hay que pagar en el mes (para el evento del día del sueldo)."""
    ps = [p for p in cfg["pagos"] if not p.get("automatico") and p["tipo"] not in ("ingreso", "cobro") and not p.get("solo_mes")]
    lin = [f"• {'El día del sueldo' if p['dia'] == 'penultimo_habil' else 'Día ' + str(p['dia'])}: {'Aparta ' if p['tipo'] == 'ahorro' else ''}{p['nombre']}" + (f" — ${p['monto']:,.0f}".replace(",", ".") if p.get("monto") else " — ver extracto") for p in ps]
    tot = sum(p.get("monto") or 0 for p in ps)
    return "Hoy te pagaron. Este mes tienes que pagar:\n" + "\n".join(lin) + f"\n\nTotal ≈ ${tot:,.0f}".replace(",", ".") + " (+ tarjetas según extracto).\nEl mismo día te llega un correo con lo que te queda libre por día."


def evento(p, inicio, cfg=None):
    monto = f" — ${p['monto']:,.0f}".replace(",", ".") if p.get("monto") else ""
    if p["dia"] == "penultimo_habil":
        rrule = "RRULE:FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-2"
    else:
        rrule = f"RRULE:FREQ=MONTHLY;BYMONTHDAY={int(p['dia'])}"
    ingreso = p["tipo"] == "ingreso"
    nombre = p["nombre"].lstrip("💰🏦💳🔁 ")
    titulo = (f"💰 {nombre}{monto}" if ingreso else f"💵 {nombre}{monto}" if p["tipo"] == "cobro" else f"🔁 {nombre}{monto} (sale solo)" if p.get("automatico")
              else f"🏦 Aparta: {nombre}{monto}" if p["tipo"] == "ahorro" else f"💳 Vence: {nombre}{monto}")
    desc = (lista_pagos(cfg) if ingreso and cfg else p["como"]) + "\n\nCreado por tu agente de finanzas (data/pagos_config.json). Para cambiarlo, edita ese archivo."
    return {
        "summary": titulo,
        "description": desc,
        "start": {"date": inicio.isoformat()}, "end": {"date": (inicio + datetime.timedelta(days=1)).isoformat()},
        "recurrence": [rrule],
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": m} for m in ANTES] + [{"method": "email", "minutes": ANTES[0]}]}
                     if not p.get("automatico") and p["tipo"] != "cobro" else {"useDefault": False},   # lo automático y el sueldo no necesitan aviso (el sueldo llega por correo)
        "colorId": "11" if p["tipo"] in ("fijo", "tarjeta", "deuda") else "10",
        "extendedProperties": {"private": {"finanzas_id": p["nombre"]}},
        "transparency": "transparent",
    }


def sync():
    svc = build("calendar", "v3", credentials=get_creds(SCOPES))
    cfg = json.load(open("data/pagos_config.json"))
    hoy = datetime.date.today().replace(day=1)
    n_new = n_upd = 0
    for p in cfg["pagos"]:
        if p.get("automatico") and p["tipo"] == "deuda": continue  # libranzas/hipoteca salen solas
        if p.get("solo_mes"): continue  # pago de una sola vez: va en el informe, no como evento mensual
        dia = 1 if p["dia"] == "penultimo_habil" else int(p["dia"])
        body = evento(p, hoy.replace(day=min(dia, 28)), cfg)
        found = svc.events().list(calendarId=CAL, privateExtendedProperty=f"finanzas_id={p['nombre']}", maxResults=5).execute().get("items", [])
        if found:
            svc.events().update(calendarId=CAL, eventId=found[0]["id"], body=body).execute(); n_upd += 1
        else:
            svc.events().insert(calendarId=CAL, body=body).execute(); n_new += 1
    for a in cfg.get("anuales", []):
        body = {"summary": f"📋 {a['nombre']}", "description": a["como"],
                "start": {"date": f"{hoy.year}-{a['mes']:02d}-{a['dia']:02d}"}, "end": {"date": f"{hoy.year}-{a['mes']:02d}-{a['dia'] + 1:02d}"},
                "recurrence": ["RRULE:FREQ=YEARLY"], "extendedProperties": {"private": {"finanzas_id": a["nombre"]}},
                "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 15 * 60}]}}
        found = svc.events().list(calendarId=CAL, privateExtendedProperty=f"finanzas_id={a['nombre']}", maxResults=5).execute().get("items", [])
        (svc.events().update(calendarId=CAL, eventId=found[0]["id"], body=body) if found else svc.events().insert(calendarId=CAL, body=body)).execute()
    print(f"Calendario: {n_new} recordatorios nuevos, {n_upd} actualizados")


if __name__ == "__main__":
    try:
        sync()
    except HttpError as e:
        print("No se pudo usar Google Calendar:", str(e)[:300])
