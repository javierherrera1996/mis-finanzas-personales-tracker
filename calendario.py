"""Crea/actualiza en tu Google Calendar los recordatorios de pagos de data/pagos_config.json (sin duplicar)."""
import datetime, json
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from auth import get_creds, SCOPES

CAL = "primary"


def evento(p, inicio):
    monto = f" — ${p['monto']:,.0f}".replace(",", ".") if p.get("monto") else ""
    if p["dia"] == "penultimo_habil":
        rrule = "RRULE:FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-2"
    else:
        rrule = f"RRULE:FREQ=MONTHLY;BYMONTHDAY={int(p['dia'])}"
    return {
        "summary": f"💳 {p['nombre']}{monto}" if p["tipo"] not in ("ingreso",) else f"{p['nombre']}{monto}",
        "description": f"{p['como']}\n\nCreado por tu agente de finanzas (data/pagos_config.json). Para cambiarlo, edita ese archivo.",
        "start": {"date": inicio.isoformat()}, "end": {"date": (inicio + datetime.timedelta(days=1)).isoformat()},
        "recurrence": [rrule],
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 15 * 60}]} if not p.get("automatico") else {"useDefault": False},
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
        body = evento(p, hoy.replace(day=min(dia, 28)))
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
