"""Crea (o actualiza) el Google Sheet 'Plan y estrategia': foto financiera de hoy, objetivos del año,
hoja de ruta, estrategias, escenarios, mercado, perfil, SECOP e ideas de ingreso. Pensado para leerlo desde
Claude en el celular (conector de Google Drive).
Fuente: data/plan.json + data/ideas_ingreso.json + agente.estado(). Antes de reescribir, guarda en plan.json lo que
el usuario haya cambiado en las columnas Estado y Nota del Sheet.
Uso: .venv/bin/python plan_sheet.py"""
import collections, datetime, json, os
from googleapiclient.discovery import build
from auth import get_creds
from fetch_util import call
from config import C

TITULO = f"Plan y estrategia — {C['nombre']}"
ID_FILE = "data/plan_sheet_id.txt"
PLAN = "data/plan.json"
FIN_ID = open("data/sheet_id.txt").read().strip()
TABS = ["LEEME", "Hoy", "Objetivos 2027", "Hoja de ruta", "Estrategias", "Escenarios", "Mercado salarial", "Perfil", "SECOP", "Ideas de ingreso"]
EDITABLES = {"Objetivos 2027": ("objetivos", "id"), "Hoja de ruta": ("hoja_de_ruta", "id"), "Perfil": ("perfil_checklist", "item")}
f = lambda v: "$" + f"{round(v):,}".replace(",", ".")

svc = build("sheets", "v4", credentials=get_creds())
plan = json.load(open(PLAN))


def col(n):
    s = ""
    while n: n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


# ---------- crear, o guardar ediciones y limpiar ----------
if os.path.exists(ID_FILE):
    sid = open(ID_FILE).read().strip()
    meta = call(svc.spreadsheets().get(spreadsheetId=sid))
    existentes = {s["properties"]["title"] for s in meta["sheets"]}
    for tab, (clave, llave) in EDITABLES.items():   # Estado / Nota que el usuario cambió en el Sheet -> plan.json
        if tab not in existentes: continue
        filas = call(svc.spreadsheets().values().get(spreadsheetId=sid, range=f"'{tab}'!A1:Z")).get("values", [])
        if len(filas) < 2: continue
        cab = filas[0]
        for fila in filas[1:]:
            d = dict(zip(cab, fila + [""] * (len(cab) - len(fila))))
            for it in plan[clave]:
                if d.get(llave.upper() if llave == "id" else "Ítem") == it[llave]:
                    for campo in ("estado", "nota"):
                        v = d.get(campo.capitalize())
                        if v is not None and campo in it: it[campo] = v
    json.dump(plan, open(PLAN, "w"), ensure_ascii=False, indent=1)
    faltan = [t for t in TABS if t not in existentes]
    if faltan: call(svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [{"addSheet": {"properties": {"title": t}}} for t in faltan]}))
    call(svc.spreadsheets().values().batchClear(spreadsheetId=sid, body={"ranges": [f"'{t}'!A1:Z2000" for t in TABS]}))
else:
    body = {"properties": {"title": TITULO, "timeZone": "America/Bogota", "locale": "es_CO"}, "sheets": [{"properties": {"title": t}} for t in TABS]}
    sid = call(svc.spreadsheets().create(body=body))["spreadsheetId"]
    open(ID_FILE, "w").write(sid)
meta = call(svc.spreadsheets().get(spreadsheetId=sid))
SID = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
datos = {}


def put(tab, filas):
    datos[tab] = filas
    call(svc.spreadsheets().values().update(spreadsheetId=sid, range=f"'{tab}'!A1", body={"values": filas}, valueInputOption="RAW"))


ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

# ---------- LEEME ----------
put("LEEME", [
    [f"Plan y estrategia de {C['nombre']} — cómo leer este archivo"],
    [f"Última actualización: {ahora} (se actualiza solo cuando el usuario prende su Mac; los datos vienen de sus correos bancarios)."],
    [""],
    ["Pestaña", "Qué tiene"],
    ["Hoy", "Foto financiera: caja, cuánto puede gastar por día hasta el sueldo, pagos pendientes, deudas, gasto del mes y de los últimos meses."],
    ["Objetivos 2027", "Objetivos del año con meta, fecha y estado (se pueden editar Estado y Nota)."],
    ["Hoja de ruta", "Tareas por fase con fecha, horas, costo, beneficio y estado (Estado y Nota editables)."],
    ["Estrategias", "Estrategias de ingreso ordenadas por costo-beneficio de su tiempo."],
    ["Escenarios", "Probabilidad de cada escenario para pagar tus deudas."],
    ["Mercado salarial", "Dónde está su salario frente al mercado."],
    ["Perfil", "Checklist de CV, LinkedIn, GitHub y página web."],
    ["SECOP", "Hallazgos de contratación pública y qué hacer con ellos."],
    ["Ideas de ingreso", "Ideas de ingreso extra con neto mensual, probabilidad, horas y riesgo con tu empleador."],
    [""],
    ["Detalle de movimientos, presupuesto y proyecciones", f"https://docs.google.com/spreadsheets/d/{FIN_ID}"],
    [""],
    ["Reglas para interpretar (no romperlas)"],
    *[[p] for p in plan["principios"]],
    ["La caja de la cuenta principal YA incluye el bolsillo; lo reservado para inversión (data/reservas.json) no se cuenta para gastar."],
    ["Las compras con tarjeta cuentan el día de la compra; pagos de tarjeta, traslados entre cuentas propias y avances son internos."],
    ["Cifras en pesos colombianos con puntos de miles ($1.234.567)."],
])

# ---------- Hoy ----------
import agente
e = agente.estado()
c = e["caja"]
movs = json.load(open("data/movimientos.json"))
cfg = {x["nombre"]: x for x in json.load(open("data/deudas_config.json"))["creditos"]}
filas = [
    ["Foto financiera", "Valor", "Detalle"],
    ["Actualizado", ahora, f"Movimientos hasta el {c['hasta']}"],
    ["Puede gastar por día hasta el sueldo", f(e["por_dia"]), f"{f(e['libre'])} libres ÷ {e['dias_al_pago']} días"],
    ["Próximo sueldo", e["proximo_pago"].isoformat(), f"en {e['dias_al_pago']} días (penúltimo día hábil)"],
    ["Caja total Davivienda (incluye bolsillo)", f(c["total"]), f"extracto {c['extracto']} + movimientos posteriores"],
    ["Reservado para inversión (no gastar)", f(c["reservado_inversion"]), "en el bolsillo"],
    ["Colchón", f(c["emergencia"]), "resto del bolsillo"],
    ["Disponible en cuenta", f(c["disponible"]), ""],
    ["Pagos pendientes antes del sueldo", f(e["comprometido"]), "; ".join(f"{p['fecha']:%d-%b} {p['nombre']} {f(p['monto'])}" for p in e["por_pagar_antes_del_sueldo"])],
    ["Gasto variable desde el último sueldo", f(e["gasto_ciclo"]), f"techo del mes {f(e['techo_ciclo'])}"],
    ["Gasto variable últimos 7 días", f(e["gasto_semana"]), f"techo semanal {f(e['techo_semana'])}"],
    ["Deuda total conocida", f(e["deuda"]), "; ".join(f"{x['nombre']} {f(x['saldo'])}" for x in e["creditos"])],
    ["Suscripciones activas", f(sum(s["mensual"] for s in e["suscripciones"] if s["activa"])) + "/mes", ", ".join(s["nombre"] for s in e["suscripciones"] if s["activa"])],
    ["Preguntas pendientes", str(len(e["preguntas"])), "movimientos que el sistema no supo clasificar"],
    [""],
    ["Deudas (de mayor a menor tasa)", "Saldo", "Tasa E.A.", "Intereses al mes", "Termina en"],
]
import deudas as _dd
_r = _dd.resumen()
for d_ in _r["deudas"]:
    filas.append([("👉 " if d_.get("abonar_aqui") else "") + d_["nombre"], f(d_["saldo"]), _dd.pct(d_["tasa_ea"]),
                  f(d_["interes_mes"]) if d_["interes_mes"] is not None else "paga el total", (str(d_["meses"]) + " meses") if d_["meses"] else d_["nota"][:80]])
filas += [["Consejo", _r["consejo"]], [""], ["Últimos meses", "Ingresos", "Gastos", "Neto (ingresos − gastos)", "Pago de deudas"]]
por_mes = collections.defaultdict(lambda: collections.Counter())
for m in movs: por_mes[m["Mes"]][m["Tipo"]] += m["Valor"]
for mes in sorted(por_mes)[-6:]:
    t = por_mes[mes]
    filas.append([mes + (" (parcial)" if mes == datetime.date.today().strftime("%Y-%m") else ""), f(t["Ingreso"]), f(-t["Gasto"]), f(t["Ingreso"] + t["Gasto"]), f(-t["Deuda"])])
put("Hoy", filas)

# ---------- tablas del plan ----------
put("Objetivos 2027", [["ID", "Objetivo", "Métrica", "Meta", "Fecha", "Estado", "Nota"]] +
    [[o["id"], o["objetivo"], o["metrica"], o["meta"], o["fecha"], o["estado"], o["nota"]] for o in plan["objetivos"]])
put("Hoja de ruta", [["ID", "Fase", "Tarea", "Fecha", "Horas", "Costo", "Beneficio", "Estado", "Nota"]] +
    [[r["id"], r["fase"], r["tarea"], r["fecha"], r["horas"], f(r["costo"]) if r["costo"] else "$0", r["beneficio"], r["estado"], r["nota"]] for r in plan["hoja_de_ruta"]])
put("Estrategias", [["Orden", "Estrategia", "Neto extra al mes", "Probabilidad", "Horas por semana", "Costo-beneficio"]] +
    [[s["orden"] if s["orden"] < 99 else "Evitar", s["estrategia"], s["neto_mes"], s["prob"], s["horas_sem"], s["costo_beneficio"]] for s in plan["estrategias"]])
put("Escenarios", [["Escenario", "Gasto día a día al mes", "Ingreso extra neto necesario al mes", "Probabilidad (estimación)"]] +
    [[s["escenario"], s["dia_a_dia_mes"], s["extra_neto_mes"], s["probabilidad"]] for s in plan["escenarios"]])
put("Mercado salarial", [["Mercado", "Rango", "Lectura"]] + [[m["mercado"], m["rango"], m["lectura"]] for m in plan["mercado"]])
put("Perfil", [["Ítem", "Estado"]] + [[p["item"], p["estado"]] for p in plan["perfil_checklist"]])
put("SECOP", [["Hallazgo", "Ejemplos", "Qué hacer"]] + [[s["hallazgo"], s["ejemplos"], s["accion"]] for s in plan["secop"]])
ideas = json.load(open("data/ideas_ingreso.json")) if os.path.exists("data/ideas_ingreso.json") else []
for i in ideas:
    i["ev"] = i["neto_mes_M"] * i["prob"] / 100
    i["por_hora"] = round(i["neto_mes_M"] * 1e6 / (i["horas_sem"] * 4.3)) if i["horas_sem"] else None
put("Ideas de ingreso", [["#", "Familia", "Idea", "Detalle", "Neto/mes (millones)", "Probabilidad 2027", "Valor esperado (millones)", "Neto por hora", "Meses al 1er ingreso", "Horas/sem", "Riesgo con empleador", "Apalancamiento", "Encaja con perfil"]] +
    [[i["n"], i["familia"], i["idea"], i["detalle"], i["neto_mes_M"], f"{i['prob']}%", round(i["ev"], 2), f(i["por_hora"]) if i["por_hora"] else "sin horas extra",
      i["meses_primer_ingreso"], i["horas_sem"], i.get("riesgo_empleador", ""), i["apalancamiento"], "Sí" if i["encaja_perfil"] else ""]
     for i in sorted(ideas, key=lambda x: -x["ev"])])

# ---------- formato ----------
ANCHOS = {"LEEME": [420, 700], "Hoy": [300, 160, 520, 200, 160], "Objetivos 2027": [50, 300, 260, 260, 100, 110, 260],
          "Hoja de ruta": [50, 200, 420, 95, 60, 100, 300, 110, 260], "Estrategias": [60, 420, 160, 160, 130, 320],
          "Escenarios": [300, 180, 240, 300], "Mercado salarial": [320, 260, 420], "Perfil": [600, 110], "SECOP": [320, 520, 380],
          "Ideas de ingreso": [40, 160, 300, 420, 90, 90, 110, 110, 90, 70, 90, 100, 80]}
reqs = []
for tab, ws in ANCHOS.items():
    t = SID[tab]
    reqs += [{"updateDimensionProperties": {"range": {"sheetId": t, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1}, "properties": {"pixelSize": w}, "fields": "pixelSize"}} for i, w in enumerate(ws)]
    reqs.append({"repeatCell": {"range": {"sheetId": t, "startRowIndex": 0, "endRowIndex": 2000, "startColumnIndex": 0, "endColumnIndex": len(ws)},
                                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}}, "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}})
    cab = 3 if tab == "LEEME" else 0
    reqs.append({"repeatCell": {"range": {"sheetId": t, "startRowIndex": cab, "endRowIndex": cab + 1}, "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.88, "green": 0.93, "blue": 0.91}}},
                                "fields": "userEnteredFormat(textFormat,backgroundColor)"}})
    if tab != "LEEME":
        reqs.append({"updateSheetProperties": {"properties": {"sheetId": t, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}})
reqs.append({"repeatCell": {"range": {"sheetId": SID["LEEME"], "startRowIndex": 0, "endRowIndex": 1}, "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 14}}}, "fields": "userEnteredFormat.textFormat"}})
fila_meses = [r[0] if r else '' for r in datos["Hoy"]].index("Últimos meses")
fila_deu = [r[0] if r else '' for r in datos["Hoy"]].index("Deudas (de mayor a menor tasa)")
reqs.append({"repeatCell": {"range": {"sheetId": SID["Hoy"], "startRowIndex": fila_deu, "endRowIndex": fila_deu + 1}, "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.88, "green": 0.93, "blue": 0.91}}}, "fields": "userEnteredFormat(textFormat,backgroundColor)"}})
reqs.append({"repeatCell": {"range": {"sheetId": SID["Hoy"], "startRowIndex": fila_meses, "endRowIndex": fila_meses + 1}, "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.88, "green": 0.93, "blue": 0.91}}},
                            "fields": "userEnteredFormat(textFormat,backgroundColor)"}})
call(svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": reqs}))
print(f"https://docs.google.com/spreadsheets/d/{sid}")
