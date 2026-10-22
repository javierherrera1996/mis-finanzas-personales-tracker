"""Crea (o actualiza) el Google Sheet 'Finanzas Personales 2025-2026' a partir de data/movimientos.json."""
import json, os, collections, datetime
from googleapiclient.discovery import build
from auth import get_creds
from fetch_util import call
from config import C, DAVI, SUELDO

TITULO = "Finanzas Personales"
ID_FILE = "data/sheet_id.txt"
movs = json.load(open("data/movimientos.json"))
preguntas = json.load(open("data/preguntas.json"))
deudas = json.load(open("data/deudas.json"))
OV = json.load(open("data/overrides.json")) if os.path.exists("data/overrides.json") else {"movimientos": {}, "respuestas": {}}
CFG = json.load(open("data/deudas_config.json"))
svc = build("sheets", "v4", credentials=get_creds())

meses = sorted({m["Mes"] for m in movs})
nm = len(meses)
TABS = ["Tablero", "Calendario de pagos", "Suscripciones", "Proyección deudas", "Proyección caja", "Línea de tiempo", "Resumen mensual", "Evolución ingresos", "Gastos por categoría", "Top comercios", "Deudas", "Historial saldos", "Preguntas", "Movimientos"]

# ---------- crear o limpiar ----------
if os.path.exists(ID_FILE):
    sid = open(ID_FILE).read().strip()
    meta = call(svc.spreadsheets().get(spreadsheetId=sid))
    reqs = [{"addSheet": {"properties": {"title": "tmp"}}}] + [{"deleteSheet": {"sheetId": s["properties"]["sheetId"]}} for s in meta["sheets"]]
    call(svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": reqs}))
    call(svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [{"addSheet": {"properties": {"title": t}}} for t in TABS]}))
    meta = call(svc.spreadsheets().get(spreadsheetId=sid))
    tmp = [s for s in meta["sheets"] if s["properties"]["title"] == "tmp"][0]["properties"]["sheetId"]
    call(svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [{"deleteSheet": {"sheetId": tmp}}]}))
else:
    body = {"properties": {"title": TITULO, "timeZone": "America/Bogota"}, "sheets": [{"properties": {"title": t}} for t in TABS]}
    sid = call(svc.spreadsheets().create(body=body))["spreadsheetId"]
    open(ID_FILE, "w").write(sid)
call(svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [{"updateSpreadsheetProperties": {"properties": {"locale": "es_CO"}, "fields": "locale"}}]}))
meta = call(svc.spreadsheets().get(spreadsheetId=sid))
SID = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}


def loc(v):  # separador de argumentos para configuración regional en español: "," -> ";" fuera de comillas
    if not (isinstance(v, str) and v.startswith("=")): return v
    out, q = [], False
    for ch in v:
        if ch == '"': q = not q
        out.append(";" if ch == "," and not q else ch)
    return "".join(out)


def put(rango, values, raw=False):
    if not raw: values = [[loc(c) for c in row] for row in values]
    call(svc.spreadsheets().values().update(spreadsheetId=sid, range=rango, body={"values": values},
                                            valueInputOption="RAW" if raw else "USER_ENTERED"))


def col(n):  # 1 -> A
    s = ""
    while n: n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


M = "Movimientos"
# ---------- Movimientos ----------
cab = ["Fecha", "Mes", "Fuente", "Descripción", "Comercio", "Valor", "Tipo", "Categoría", "Subcategoría", "Cuotas", "Categoría manual", "Tu nota", "ID"]
rows = [cab] + [[m["Fecha"], m["Mes"], m["Fuente"], m["Descripción"], m["Comercio"], m["Valor"], m["Tipo"], m["Categoría"], m["Subcategoría"], m["Cuotas"],
                 m.get("Categoría manual", ""), m.get("Tu nota", ""), m["ID"]] for m in movs]
put(f"'{M}'!A1", rows, raw=True)
N = len(rows)
rng = lambda c: f"'{M}'!${c}$2:${c}${N}"
F, B, G, H, I = rng("F"), rng("B"), rng("G"), rng("H"), rng("I")

# ---------- Resumen mensual ----------
R = "Resumen mensual"
cab = ["Mes", "Salario", "Otros ingresos", "TOTAL INGRESOS", "Gastos del día a día", "Cuotas de deudas", "Inversión (apartamento)", "TOTAL SALIDAS",
       "Ahorro / (Déficit)", "Créditos nuevos recibidos", "…de eso, usado para pagar créditos viejos", "Deuda nueva neta", "% del ingreso que se va en cuotas"]
res = [["Resumen mensual — ingresos vs. salidas (sin contar movimientos entre tus propias cuentas)"], [], cab]
PRE = '"Prepago / refinanciación"'
for i, mes in enumerate(meses):
    r = i + 4
    res.append([f"'{mes}",
                f'=SUMIFS({F},{B},$A{r},{G},"Ingreso",{H},"Salario")',
                f'=SUMIFS({F},{B},$A{r},{G},"Ingreso")-B{r}',
                f"=B{r}+C{r}",
                f'=-SUMIFS({F},{B},$A{r},{G},"Gasto")',
                f'=-SUMIFS({F},{B},$A{r},{G},"Deuda",{I},"<>Prepago / refinanciación")',
                f'=-SUMIFS({F},{B},$A{r},{G},"Inversión")',
                f"=E{r}+F{r}+G{r}",
                f"=D{r}-H{r}",
                f'=SUMIFS({F},{B},$A{r},{G},"Financiamiento")',
                f'=-SUMIFS({F},{B},$A{r},{G},"Deuda",{I},{PRE})',
                f"=J{r}-K{r}",
                f'=IFERROR(F{r}/D{r},"")'])
t = len(res) + 1
res.append(["TOTAL"] + [f"=SUM({col(c)}4:{col(c)}{t-1})" for c in range(2, 13)] + [f"=IFERROR(F{t}/D{t},\"\")"])
res.append(["PROMEDIO MENSUAL"] + [f"=AVERAGE({col(c)}4:{col(c)}{t-2})" for c in range(2, 13)] + [""])
res += [[], ["Cómo leerlo"],
        ["• Gastos del día a día = compras, arriendo, comida, transporte, viajes, etc. (débito + tarjetas de crédito Davivienda, Nu y Bancolombia)."],
        ["• Cuotas de deudas = cuotas de créditos (hipoteca, libranzas, consumo, ICETEX; incluye libranzas descontadas de nómina). Las compras con tarjeta ya cuentan como gasto el día de la compra; por eso el pago de la tarjeta NO se suma otra vez."],
        ["• Inversión = pagos que construyen patrimonio (ej. compra de vivienda). No es gasto de consumo, pero sí plata que salió."],
        ["• Créditos nuevos recibidos = desembolsos de préstamos. No es ingreso: es plata prestada, por eso va aparte. Parte se usó para pagar de golpe créditos anteriores (refinanciación); el resto es deuda nueva que financió el déficit."],
        ["• Ahorro / (Déficit) negativo = ese mes salió más de lo que entró; la diferencia se cubrió con créditos o con saldo anterior."],
        ["• El mes en curso está incompleto (solo hasta hoy). Bancolombia viene solo de alertas por correo (no extractos), puede faltar algo."]]
put(f"'{R}'!A1", res)

# ---------- Tablero (gasto real vs. meta) ----------
TB = "Tablero"
TECHO = C.get("techo_gasto_mes", 6000000)
METAS = list(C.get("metas_categoria", {}).items())
mt = meses[-9:]
fut = []
y, mm = int(mt[-1][:4]), int(mt[-1][5:])
for _ in range(6):
    mm += 1
    if mm == 13: y, mm = y + 1, 1
    fut.append(f"{y}-{mm:02d}")
mt += fut
tb = [[f"Tablero — gasto del día a día contra el techo de ${TECHO:,.0f}/mes".replace(",", ".")], [],
      ["Mes", "Gasto del día a día", "Techo", "Diferencia (+ = dentro del techo)", "Estado"]]
for i, x in enumerate(mt):
    r = i + 4
    tb.append([f"'{x}", f'=-SUMIFS({F},{B},$A{r},{G},"Gasto")', TECHO, f'=IF(B{r}=0,"",C{r}-B{r})',
               f'=IF(B{r}=0,"",IF(B{r}<=C{r},"✅ Dentro","❌ Por encima"))'])
r0 = len(tb) + 2
tb += [[], ["Meta por categoría ($/mes)", "Meta"] + [f"'{x}" for x in mt]]
for j, (cat, meta) in enumerate(METAS):
    r = r0 + 1 + j
    tb.append([cat, meta] + [f'=-SUMIFS({F},{B},{col(k+3)}${r0},{H},$A{r},{G},"Gasto")' for k in range(len(mt))])
r1 = r0 + 1 + len(METAS)
tb.append(["Total", f"=SUM(B{r0+1}:B{r1-1})"] + [f"=SUM({col(k+3)}{r0+1}:{col(k+3)}{r1-1})" for k in range(len(mt))])
put(f"'{TB}'!A1", tb)

# ---------- Evolución ingresos ----------
E = "Evolución ingresos"
subs = collections.defaultdict(float)
for m in movs:
    if m["Tipo"] == "Ingreso": subs[(m["Categoría"], m["Subcategoría"])] += m["Valor"]
fuentes = sorted(subs, key=lambda k: (k[0] != "Salario", -subs[k]))
ev = [["Fuente de ingreso", "Categoría"] + [f"'{x}" for x in meses] + ["TOTAL", "Promedio mensual"]]
for j, (cat, sub) in enumerate(fuentes):
    r = j + 2
    ev.append([sub or cat, cat] + [f'=SUMIFS({F},{B},{col(k+3)}$1,{H},$B{r},{I},"{sub}",{G},"Ingreso")' for k in range(nm)]
              + [f"=SUM(C{r}:{col(nm+2)}{r})", f"=AVERAGE(C{r}:{col(nm+2)}{r})"])
r = len(fuentes) + 2
ev.append(["TOTAL INGRESOS", ""] + [f"=SUM({col(k)}2:{col(k)}{r-1})" for k in range(3, nm + 5)])
ev.append(["Solo salario", ""] + [f'=SUMIF($B$2:$B${r-1},"Salario",{col(k)}2:{col(k)}{r-1})' for k in range(3, nm + 5)])
ev += [[], ["Notas"],
       ["• Si te descuentan libranzas de la nómina, configúralas en config.json (libranzas_nomina): se suman aquí como salario y aparecen como pago de deuda."]]
put(f"'{E}'!A1", ev)

# ---------- Gastos por categoría ----------
C = "Gastos por categoría"
tot = collections.defaultdict(float)
for m in movs:
    if m["Tipo"] in ("Gasto", "Deuda", "Inversión"): tot[(m["Tipo"], m["Categoría"])] += -m["Valor"]
cats = sorted(tot, key=lambda k: ({"Gasto": 0, "Deuda": 1}.get(k[0], 2), -tot[k]))
cab = ["Categoría", "Tipo"] + [f"'{x}" for x in meses] + ["TOTAL", "Promedio mensual", "% del total"]
cg = [cab]
for j, (tipo, cat) in enumerate(cats):
    r = j + 2
    fila = [cat, tipo] + [f'=-SUMIFS({F},{B},{col(k+3)}$1,{H},$A{r},{G},$B{r})' for k in range(nm)]
    fila += [f"=SUM(C{r}:{col(nm+2)}{r})", f"=AVERAGE(C{r}:{col(nm+2)}{r})", f"={col(nm+3)}{r}/{col(nm+3)}${len(cats)+2}"]
    cg.append(fila)
r = len(cats) + 2
cg.append(["TOTAL", ""] + [f"=SUM({col(k)}2:{col(k)}{r-1})" for k in range(3, nm + 5)] + [""])
put(f"'{C}'!A1", cg)

# ---------- Top comercios ----------
T = "Top comercios"
agg = collections.defaultdict(lambda: [0.0, 0, set()])
for m in movs:
    if m["Tipo"] == "Gasto":
        k = (m["Comercio"].upper()[:40], m["Categoría"])
        agg[k][0] += -m["Valor"]; agg[k][1] += 1; agg[k][2].add(m["Mes"])
top = sorted(agg.items(), key=lambda i: -i[1][0])[:150]
tc = [["Comercio / destino", "Categoría", "Total gastado", "N° de pagos", "Meses con pagos", "Promedio por mes activo"]]
tc += [[k[0], k[1], round(v[0]), v[1], len(v[2]), round(v[0] / len(v[2]))] for k, v in top]
put(f"'{T}'!A1", tc, raw=True)

# ---------- Deudas ----------
D = "Deudas"
put(f"'{D}'!A1", deudas, raw=True)

# ---------- Preguntas ----------
P = "Preguntas"
pq = [["#", "Lo que no me cuadra", "Monto", "Fecha(s)", "Tu respuesta"]] + [[i + 1, p["q"], p["monto"], p["fechas"], OV["respuestas"].get(p["q"], "")] for i, p in enumerate(preguntas)]
put(f"'{P}'!A1", pq, raw=True)

# ---------- Calendario de pagos ----------
import agente
CP = "Calendario de pagos"
pcfg = json.load(open("data/pagos_config.json"))
cp = [["Calendario de pagos — qué pagar y cuándo (también en tu Google Calendar)"], [],
      ["Día del mes", "Pago", "Monto aprox.", "Cómo se paga", "Automático", "Próxima fecha", "Estado este mes"]]
estado_mes = {(p["nombre"], p["fecha"]): p["pagado"] for p in agente.proximos_pagos(movs, dias=40)}
for p in pcfg["pagos"]:
    prox = agente.fecha_pago(p, agente.HOY.year, agente.HOY.month)
    if prox < agente.HOY - datetime.timedelta(days=10):
        y2, m2 = (agente.HOY.year + 1, 1) if agente.HOY.month == 12 else (agente.HOY.year, agente.HOY.month + 1)
        prox = agente.fecha_pago(p, y2, m2)
    pag = estado_mes.get((p["nombre"], prox))
    est = "Automático" if p.get("automatico") else ("✅ Pagado" if pag else ("⚠️ Vencido" if prox < agente.HOY else "⏳ Pendiente"))
    cp.append(["penúltimo día hábil" if p["dia"] == "penultimo_habil" else p["dia"], p["nombre"], p["monto"] if p.get("monto") else "ver extracto",
               p["como"], "Sí" if p.get("automatico") else "No", prox.isoformat(), est])
for a_ in pcfg.get("anuales", []):
    cp.append([f"{a_['dia']}/{a_['mes']} (anual)", a_["nombre"], "", a_["como"], "No", "", ""])
cp += [[], ["Para cambiar un pago (monto, día) edita data/pagos_config.json; el calendario se actualiza en la próxima actualización."]]
put(f"'{CP}'!A1", cp)

# ---------- Suscripciones ----------
SU = "Suscripciones"
subs_ = agente.suscripciones(movs)
su = [["Servicio", "Costo mensual (prom. 6 meses)", "Último cobro", "Monto último cobro", "Sugerencia", "¿Qué hago? (Mantener / Cancelar / Revisar)"]]
for x in subs_:
    su.append([x["nombre"], x["mensual"], x["ultimo"], x["ultimo_monto"], x["sugerencia"], OV.get("suscripciones", {}).get(x["nombre"], "")])
su.append(["TOTAL", f"=SUM(B2:B{len(su)})"])
su.append(["Lo que ahorras si cancelas lo marcado", f'=SUMIF(F2:F{len(su)-1},"Cancelar",B2:B{len(su)-1})'])
put(f"'{SU}'!A1", su)

# ---------- Proyección deudas (simulador con fórmulas) ----------
PD = "Proyección deudas"
cr = sorted([c for c in CFG["creditos"] if c.get("en_simulador", True)], key=lambda c: -c["tasa_ea"])  # orden de abono: mayor tasa primero
nL = len(cr)
# el simulador está armado para 3 créditos: con menos se rellena con créditos en cero; con más, toma los 3 de mayor tasa
cr = (cr + [{"nombre": "(sin crédito)", "saldo": 0, "tasa_ea": 0, "cuota_capital_interes": 0, "fecha_saldo": ""}] * 3)[:3]
nL = 3
pdv = [["Simulador: ¿cuándo sales de deudas? — cambia las celdas amarillas"], [],
       ["Parámetros"], ["Crédito", "Saldo inicial", "Tasa E.A.", "Tasa mensual", "Cuota (capital + interés)", "Saldo a la fecha"]]
for k, c in enumerate(cr):
    r = 5 + k
    pdv.append([c["nombre"], c["saldo"], c["tasa_ea"], f"=(1+C{r})^(1/12)-1", c["cuota_capital_interes"], c["fecha_saldo"]])
pdv += [[],
        ["Abono extra cada mes", 0, "", "Lo que pongas aquí se abona cada mes al crédito de mayor tasa"],
        ["Abono único al inicio", 0, "", "Va al crédito de mayor tasa"],
        ["Bola de nieve (SI / NO)", "NO", "", "SI = cuando termines un crédito, su cuota pasa a abonar el siguiente"],
        ["Mes de inicio", f"=DATE({datetime.date.today().year},{datetime.date.today().month},1)"],
        [], ["Resultados"], ["Crédito", "Termina en", "Meses", "Intereses que pagarás", "Solo cuotas: termina en", "Solo cuotas: intereses"]]
T0, T1 = 32, 32 + 180  # filas de la tabla mes a mes
mr_ = lambda ea: (1 + ea) ** (1 / 12) - 1
def sim_py(extra=0, unico=0, roll=False):
    b = [c["saldo"] for c in cr]; b[0] = max(0, b[0] - unico); it = [0.0] * nL; fin = [None] * nL
    for mth in range(1, 181):
        pool = extra + (sum(c["cuota_capital_interes"] for k, c in enumerate(cr) if b[k] <= 1) if roll else 0)
        for k, c in enumerate(cr):
            if b[k] <= 1: continue
            i = b[k] * mr_(c["tasa_ea"]); it[k] += i; b[k] += i - min(c["cuota_capital_interes"], b[k] + i)
            if b[k] <= 1 and fin[k] is None: fin[k] = mth
        for k in range(nL):
            if b[k] > 1 and pool > 0:
                p = min(pool, b[k]); b[k] -= p; pool -= p
                if b[k] <= 1 and fin[k] is None: fin[k] = mth
    return fin, it
fin0, it0 = sim_py()
def mes_txt(n):
    b0 = datetime.date.today().month - 1
    y, m = datetime.date.today().year + (b0 + n) // 12, (b0 + n) % 12 + 1
    return f"{['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][m-1]}-{y}"
col_s = ["B", "C", "D"]; col_i = ["H", "I", "J"]
for k, c in enumerate(cr):
    sc = f"{col_s[k]}{T0}:{col_s[k]}{T1}"
    pdv.append([c["nombre"], f'=IFERROR(TEXT(INDEX($A${T0}:$A${T1},MATCH(1,INDEX(--({sc}<=1),0),0)),"mmm-yyyy"),"más de 15 años")',
                f'=IFERROR(MATCH(1,INDEX(--({sc}<=1),0),0)-1,">180")', f"=SUM({col_i[k]}{T0+1}:{col_i[k]}{T1})",
                mes_txt(fin0[k]) if fin0[k] else "más de 15 años", round(it0[k])])
rr = len(pdv) + 1
pdv.append(["LIBRE DE DEUDAS", f'=IFERROR(TEXT(INDEX($A${T0}:$A${T1},MATCH(1,INDEX(--(E{T0}:E{T1}<=3),0),0)),"mmm-yyyy"),"más de 15 años")',
            f'=IFERROR(MATCH(1,INDEX(--(E{T0}:E{T1}<=3),0),0)-1,">180")', f"=SUM(D{rr-nL}:D{rr-1})",
            mes_txt(max(f for f in fin0 if f)) if all(fin0) else "más de 15 años", round(sum(it0))])
pdv.append(["Intereses que te ahorras frente a solo pagar cuotas", f"=F{rr}-D{rr}"])
# Escenario "a este ritmo": el hueco mensual se sigue cubriendo con créditos nuevos (al 18,99% E.A.)
HUECO = max(0, C.get("gasto_ritmo_actual", 0) - SUELDO.get("neto_que_llega", 0) - SUELDO.get("otros_ingresos_mes", 0))   # lo que falta cada mes
def sim_ritmo(meses):
    b = [c["saldo"] for c in cr]; nueva = 0.0
    for _ in range(meses):
        for k, c in enumerate(cr):
            if b[k] <= 1: continue
            i = b[k] * mr_(c["tasa_ea"]); b[k] += i - min(c["cuota_capital_interes"], b[k] + i)
        nueva = nueva * (1 + mr_(0.1899)) + HUECO
    return sum(b) + nueva
pdv += [[], [f"A ESTE RITMO: si sigues gastando como ahora y cubres el hueco (≈ ${HUECO/1e6:.1f} M/mes) con créditos, nunca sales de deudas"],
        ["Deuda total en 12 meses", round(sim_ritmo(12))], ["Deuda total en 24 meses", round(sim_ritmo(24))], ["Deuda total en 36 meses", round(sim_ritmo(36))]]
RIT = len(pdv)
while len(pdv) < T0 - 2: pdv.append([])
pdv.append(["Mes", "Saldo " + cr[0]["nombre"], "Saldo " + cr[1]["nombre"], "Saldo " + cr[2]["nombre"], "Deuda total", "Intereses del mes", "Abono extra aplicado",
            "int1", "int2", "int3", "s1 tras cuota", "s2 tras cuota", "s3 tras cuota", "bolsa extra"])
pdv.append(["=B12", "=MAX(0,B5-B10)", "=B6", "=B7", f"=SUM(B{T0}:D{T0})", 0, 0])
for r in range(T0 + 1, T1 + 1):
    p = r - 1
    pdv.append([f"=EDATE(A{p},1)",
                f"=K{r}-MIN(N{r},K{r})",
                f"=L{r}-MIN(MAX(0,N{r}-MIN(N{r},K{r})),L{r})",
                f"=M{r}-MIN(MAX(0,N{r}-MIN(N{r},K{r})-MIN(MAX(0,N{r}-MIN(N{r},K{r})),L{r})),M{r})",
                f"=B{r}+C{r}+D{r}", f"=H{r}+I{r}+J{r}", f"=(K{r}-B{r})+(L{r}-C{r})+(M{r}-D{r})",
                f"=B{p}*$D$5", f"=C{p}*$D$6", f"=D{p}*$D$7",
                f"=MAX(0,B{p}+H{r}-MIN($E$5,B{p}+H{r}))", f"=MAX(0,C{p}+I{r}-MIN($E$6,C{p}+I{r}))", f"=MAX(0,D{p}+J{r}-MIN($E$7,D{p}+J{r}))",
                f'=$B$9+IF($B$11="SI",IF(B{p}<=1,$E$5,0)+IF(C{p}<=1,$E$6,0)+IF(D{p}<=1,$E$7,0),0)'])
put(f"'{PD}'!A1", pdv)

# ---------- Proyección caja ----------
PC = "Proyección caja"
MES_RENTA = C.get("renta_anual", {}).get("mes", 10)
from parse_creditos import saldos_cuentas
sc_ = saldos_cuentas()
ult = max([x[0] for x in sc_] or ["0000-00"])
caja0 = sum(x[2] for x in sc_ if x[0] == ult)  # OJO: el saldo de la cuenta principal YA incluye el bolsillo
fin_mes = f"{ult}-31"
# salidas/entradas posteriores al extracto; los traslados bolsillo<->cuenta son internos y no cambian la caja
_bol = "*" + (DAVI.get("bolsillo") or "sin-bolsillo")
flujo = sum(m["Valor"] for m in movs if m["Fecha"] > fin_mes and m["Fuente"].startswith("Davivienda Ahorros") and _bol not in m["Fuente"])
caja_hoy = round(caja0 + flujo)
ult_fecha = max([m["Fecha"] for m in movs if m["Fuente"].startswith("Davivienda Ahorros")] or [datetime.date.today().isoformat()])
pc = [["Proyección de caja — ¿hasta cuándo alcanza la plata?"], [],
      ["Parámetros (cámbialos)", "Valor", "Nota"],
      ["Caja de hoy (Davivienda, incluye bolsillo)", caja_hoy, f"Extracto de {ult} menos salidas hasta {ult_fecha}. Sin Bancolombia/Nu/Daviplata."],
      ["Gasto que falta hasta el próximo pago", 2500000, "Lo que vas a gastar antes del penúltimo día hábil de este mes"],
      ["Sueldo que llega a la cuenta cada mes", SUELDO.get("neto_que_llega", 0), "Ya descontado lo que te quitan de nómina"],
      ["Otros ingresos (promedio mensual)", SUELDO.get("otros_ingresos_mes", 0), "Pon 0 si no quieres contarlos"],
      ["Cuotas que pagas aparte cada mes", 0, "Créditos que no se descuentan de nómina"],
      ["Gasto del día a día — ritmo actual", C.get("gasto_ritmo_actual", 0), "Promedio sin pagos únicos"],
      ["Gasto del día a día — meta", C.get("techo_gasto_mes", 0), "Techo del informe"],
      [f"Renta anual (se paga en el mes {C.get('renta_anual', {}).get('mes', 10)})", C.get("renta_anual", {}).get("monto", 0), ""],
      [], ["Resultado", "Ritmo actual", "Con la meta"],
      ["La caja se acaba en", '=IFERROR(TEXT(INDEX(A18:A41,MATCH(1,INDEX(--(B18:B41<0),0),0)),"mmm-yyyy"),"no se acaba en 2 años")',
       '=IFERROR(TEXT(INDEX(A18:A41,MATCH(1,INDEX(--(C18:C41<0),0),0)),"mmm-yyyy"),"no se acaba en 2 años")'],
      ["Caja dentro de 12 meses", "=B29", "=C29"], [],
      ["Fin del ciclo (antes del siguiente pago)", "Caja — ritmo actual", "Caja — con la meta"]]
y, mm_ = int(ult_fecha[:4]), int(ult_fecha[5:7])
mm_ += 1
if mm_ == 13: y, mm_ = y + 1, 1
for i in range(24):
    r = 18 + i
    if i == 0:
        pc.append([f"=DATE({y},{mm_},1)", f"=B4-B5+B6+B7-B8-B9-IF(MONTH(A{r})={MES_RENTA},B11,0)", f"=B4-B5+B6+B7-B8-B10-IF(MONTH(A{r})={MES_RENTA},B11,0)"])
    else:
        pc.append([f"=EDATE(A{r-1},1)", f"=B{r-1}+$B$6+$B$7-$B$8-$B$9-IF(MONTH(A{r})={MES_RENTA},$B$11,0)", f"=C{r-1}+$B$6+$B$7-$B$8-$B$10-IF(MONTH(A{r})={MES_RENTA},$B$11,0)"])
put(f"'{PC}'!A1", pc)

# ---------- Historial saldos ----------
HS = "Historial saldos"
hm = collections.defaultdict(dict)
for mes, cta, saldo, bol in sc_:
    hm[mes][cta] = saldo
    if cta == DAVI.get("cuenta_principal"): hm[mes]["bol"] = bol
_p, _a = DAVI.get("cuenta_principal", ""), DAVI.get("cuenta_afc", "")
hs = [["Mes (fin)", f"Cuenta *{_p} (incluye bolsillo)", "…de eso en el bolsillo", f"AFC *{_a}", "Total Davivienda"]]
for k, mes in enumerate(sorted(hm)):
    r = k + 2
    hs.append([f"'{mes}", hm[mes].get(_p, 0), hm[mes].get("bol", 0), hm[mes].get(_a, 0), f"=B{r}+D{r}"])
put(f"'{HS}'!A1", hs)

# ---------- Línea de tiempo (viajes y proyectos) ----------
LT = "Línea de tiempo"
import viajes as _vj
_filas, _asig = _vj.resumen(movs)
_grp = ["Vuelos y transporte largo", "Alojamiento", "Comida y pagos locales", "Transporte local", "Buceo y surf", "Equipo (bici, reloj, ropa)",
        "Inscripción y fotos de carrera", "Tours, compras y otros", "Transferencias y efectivo", "Regalo"]
lt = [["Desde", "Hasta", "Viaje / proyecto", "TOTAL"] + _grp + ["Nota"]]
for f_ in _filas:
    lt.append([f_["desde"], f_["hasta"], f_["nombre"], f_["total"]] + [round(f_["grupos"].get(g_, 0)) for g_ in _grp] + [f_["nota"]])
lt.append(["", "", "TOTAL", f"=SUM(D2:D{len(lt)})"] + [f"=SUM({col(5+k)}2:{col(5+k)}{len(lt)})" for k in range(len(_grp))] + [""])
lt += [[], ["Detalle de cada viaje (edita fechas y compras asignadas en data/viajes.json)"], ["Viaje", "Fecha", "Valor", "Grupo", "Descripción"]]
for nombre_, rows_ in _asig.items():
    for r_ in sorted(rows_, key=lambda r: r["Fecha"]):
        lt.append([nombre_, r_["Fecha"], -r_["Valor"], _vj.grupo(r_), r_["Descripción"][:90]])
put(f"'{LT}'!A1", lt)
NLT = len(_filas) + 2

# ---------- Formato ----------
money = {"numberFormat": {"type": "CURRENCY", "pattern": "$#,##0;[Red]-$#,##0"}}
hdr = {"textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}, "backgroundColor": {"red": 0.13, "green": 0.27, "blue": 0.45}}
reqs = []
def fmt(tab, r0, r1, c0, c1, f, fields):
    reqs.append({"repeatCell": {"range": {"sheetId": SID[tab], "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1},
                                "cell": {"userEnteredFormat": f}, "fields": f"userEnteredFormat({fields})"}})
def freeze(tab, rows, cols=0):
    reqs.append({"updateSheetProperties": {"properties": {"sheetId": SID[tab], "gridProperties": {"frozenRowCount": rows, "frozenColumnCount": cols}}, "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}})
def widths(tab, ws):
    for i, w in enumerate(ws):
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": SID[tab], "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1}, "properties": {"pixelSize": w}, "fields": "pixelSize"}})

# Resumen
fmt(R, 0, 1, 0, 1, {"textFormat": {"bold": True, "fontSize": 13}}, "textFormat")
fmt(R, 2, 3, 0, 13, {**hdr, "wrapStrategy": "WRAP"}, "textFormat,backgroundColor,wrapStrategy")
fmt(R, 3, t + 1, 1, 12, money, "numberFormat")
fmt(R, 3, t + 1, 12, 13, {"numberFormat": {"type": "PERCENT", "pattern": "0%"}}, "numberFormat")
fmt(R, t - 1, t + 1, 0, 13, {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.92, "green": 0.92, "blue": 0.92}}, "textFormat,backgroundColor")
fmt(R, 3, t + 1, 3, 4, {"textFormat": {"bold": True}}, "textFormat")
fmt(R, 3, t + 1, 7, 9, {"textFormat": {"bold": True}}, "textFormat")
reqs.append({"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": SID[R], "startRowIndex": 3, "endRowIndex": t + 1, "startColumnIndex": 8, "endColumnIndex": 9}],
             "booleanRule": {"condition": {"type": "NUMBER_LESS", "values": [{"userEnteredValue": "0"}]}, "format": {"backgroundColor": {"red": 0.99, "green": 0.85, "blue": 0.85}}}}, "index": 0}})
reqs.append({"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": SID[R], "startRowIndex": 3, "endRowIndex": t + 1, "startColumnIndex": 8, "endColumnIndex": 9}],
             "booleanRule": {"condition": {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "0"}]}, "format": {"backgroundColor": {"red": 0.85, "green": 0.95, "blue": 0.85}}}}, "index": 1}})
freeze(R, 3, 1); widths(R, [140] + [125] * 12)
# Calendario de pagos
fmt(CP, 0, 1, 0, 1, {"textFormat": {"bold": True, "fontSize": 13}}, "textFormat")
fmt(CP, 2, 3, 0, 7, hdr, "textFormat,backgroundColor"); fmt(CP, 3, len(cp), 2, 3, {"numberFormat": {"type": "CURRENCY", "pattern": "$#,##0"}}, "numberFormat")
widths(CP, [150, 330, 130, 380, 100, 120, 130])
# Suscripciones
fmt(SU, 0, 1, 0, 6, {**hdr, "wrapStrategy": "WRAP"}, "textFormat,backgroundColor,wrapStrategy")
fmt(SU, 1, len(su), 1, 2, money, "numberFormat"); fmt(SU, 1, len(su), 3, 4, money, "numberFormat")
fmt(SU, 1, len(su) - 2, 5, 6, {"backgroundColor": {"red": 1, "green": 0.97, "blue": 0.75}}, "backgroundColor")
fmt(SU, len(su) - 2, len(su), 0, 6, {"textFormat": {"bold": True}}, "textFormat")
reqs.append({"setDataValidation": {"range": {"sheetId": SID[SU], "startRowIndex": 1, "endRowIndex": len(su) - 2, "startColumnIndex": 5, "endColumnIndex": 6},
             "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in ("Mantener", "Cancelar", "Revisar")]}, "showCustomUi": True, "strict": True}}})
widths(SU, [260, 150, 110, 130, 460, 200])
# Proyección deudas
yellow = {"backgroundColor": {"red": 1, "green": 0.97, "blue": 0.75}}
fmt(PD, 0, 1, 0, 1, {"textFormat": {"bold": True, "fontSize": 13}}, "textFormat")
fmt(PD, 3, 4, 0, 6, hdr, "textFormat,backgroundColor")
fmt(PD, 4, 7, 1, 2, {**money, **yellow}, "numberFormat,backgroundColor")
fmt(PD, 4, 7, 2, 3, {"numberFormat": {"type": "PERCENT", "pattern": "0.00%"}, **yellow}, "numberFormat,backgroundColor")
fmt(PD, 4, 7, 3, 4, {"numberFormat": {"type": "PERCENT", "pattern": "0.000%"}}, "numberFormat")
fmt(PD, 4, 7, 4, 5, {**money, **yellow}, "numberFormat,backgroundColor")
fmt(PD, 8, 10, 1, 2, {**money, **yellow}, "numberFormat,backgroundColor")
fmt(PD, 10, 11, 1, 2, yellow, "backgroundColor")
fmt(PD, 11, 12, 1, 2, {"numberFormat": {"type": "DATE", "pattern": "mmm yyyy"}}, "numberFormat")
fmt(PD, 14, 15, 0, 6, hdr, "textFormat,backgroundColor")
fmt(PD, 15, rr + 1, 3, 4, money, "numberFormat"); fmt(PD, 15, rr + 1, 5, 6, money, "numberFormat")
fmt(PD, rr - 1, rr + 1, 0, 6, {"textFormat": {"bold": True}}, "textFormat")
fmt(PD, rr, rr + 1, 1, 2, money, "numberFormat")
fmt(PD, RIT - 4, RIT - 3, 0, 1, {"textFormat": {"bold": True, "foregroundColor": {"red": 0.7, "green": 0.1, "blue": 0.1}}}, "textFormat")
fmt(PD, RIT - 3, RIT, 1, 2, money, "numberFormat")
fmt(PD, T0 - 2, T0 - 1, 0, 7, hdr, "textFormat,backgroundColor")
fmt(PD, T0 - 1, T1, 0, 1, {"numberFormat": {"type": "DATE", "pattern": "mmm yyyy"}}, "numberFormat")
fmt(PD, T0 - 1, T1, 1, 14, money, "numberFormat")
reqs.append({"setDataValidation": {"range": {"sheetId": SID[PD], "startRowIndex": 10, "endRowIndex": 11, "startColumnIndex": 1, "endColumnIndex": 2},
             "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "SI"}, {"userEnteredValue": "NO"}]}, "showCustomUi": True, "strict": True}}})
reqs.append({"updateDimensionProperties": {"range": {"sheetId": SID[PD], "dimension": "COLUMNS", "startIndex": 7, "endIndex": 14}, "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
widths(PD, [330, 150, 150, 150, 170, 150, 150])
reqs.append({"addChart": {"chart": {"spec": {"title": "Deuda total proyectada", "basicChart": {"chartType": "LINE", "legendPosition": "NO_LEGEND",
    "domains": [{"domain": {"sourceRange": {"sources": [{"sheetId": SID[PD], "startRowIndex": T0 - 1, "endRowIndex": T1, "startColumnIndex": 0, "endColumnIndex": 1}]}}}],
    "series": [{"series": {"sourceRange": {"sources": [{"sheetId": SID[PD], "startRowIndex": T0 - 1, "endRowIndex": T1, "startColumnIndex": 4, "endColumnIndex": 5}]}}, "targetAxis": "LEFT_AXIS"}]}},
    "position": {"overlayPosition": {"anchorCell": {"sheetId": SID[PD], "rowIndex": 2, "columnIndex": 7}, "widthPixels": 620, "heightPixels": 330}}}}})
# Proyección caja
fmt(PC, 0, 1, 0, 1, {"textFormat": {"bold": True, "fontSize": 13}}, "textFormat")
fmt(PC, 2, 3, 0, 3, hdr, "textFormat,backgroundColor"); fmt(PC, 12, 13, 0, 3, hdr, "textFormat,backgroundColor"); fmt(PC, 16, 17, 0, 3, hdr, "textFormat,backgroundColor")
fmt(PC, 3, 11, 1, 2, {**money, **yellow}, "numberFormat,backgroundColor")
fmt(PC, 14, 15, 1, 3, money, "numberFormat")
fmt(PC, 13, 15, 0, 3, {"textFormat": {"bold": True}}, "textFormat")
fmt(PC, 17, 41, 0, 1, {"numberFormat": {"type": "DATE", "pattern": "mmm yyyy"}}, "numberFormat")
fmt(PC, 17, 41, 1, 3, money, "numberFormat")
reqs.append({"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": SID[PC], "startRowIndex": 17, "endRowIndex": 41, "startColumnIndex": 1, "endColumnIndex": 3}],
             "booleanRule": {"condition": {"type": "NUMBER_LESS", "values": [{"userEnteredValue": "0"}]}, "format": {"backgroundColor": {"red": 0.99, "green": 0.85, "blue": 0.85}}}}, "index": 0}})
widths(PC, [330, 180, 180, 520])
reqs.append({"addChart": {"chart": {"spec": {"title": "Caja proyectada: ritmo actual vs. meta", "basicChart": {"chartType": "LINE", "legendPosition": "BOTTOM_LEGEND", "headerCount": 1,
    "domains": [{"domain": {"sourceRange": {"sources": [{"sheetId": SID[PC], "startRowIndex": 16, "endRowIndex": 41, "startColumnIndex": 0, "endColumnIndex": 1}]}}}],
    "series": [{"series": {"sourceRange": {"sources": [{"sheetId": SID[PC], "startRowIndex": 16, "endRowIndex": 41, "startColumnIndex": c, "endColumnIndex": c + 1}]}}, "targetAxis": "LEFT_AXIS"} for c in (1, 2)]}},
    "position": {"overlayPosition": {"anchorCell": {"sheetId": SID[PC], "rowIndex": 12, "columnIndex": 3}, "widthPixels": 620, "heightPixels": 330}}}}})
# Historial saldos
fmt(HS, 0, 1, 0, 5, hdr, "textFormat,backgroundColor"); fmt(HS, 1, len(hs), 1, 5, money, "numberFormat"); freeze(HS, 1); widths(HS, [100, 220, 180, 140, 160])
# Línea de tiempo
fmt(LT, 0, 1, 0, 15, {**hdr, "wrapStrategy": "WRAP"}, "textFormat,backgroundColor,wrapStrategy")
fmt(LT, 1, NLT, 3, 14, money, "numberFormat"); fmt(LT, 1, NLT, 3, 4, {"textFormat": {"bold": True}}, "textFormat")
fmt(LT, NLT - 1, NLT, 0, 15, {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.92, "green": 0.92, "blue": 0.92}}, "textFormat,backgroundColor")
fmt(LT, NLT + 2, NLT + 3, 0, 5, hdr, "textFormat,backgroundColor"); fmt(LT, NLT + 3, len(lt), 2, 3, money, "numberFormat")
freeze(LT, 1, 3); widths(LT, [95, 95, 300, 120] + [115] * 10 + [300])
# Tablero
fmt(TB, 0, 1, 0, 1, {"textFormat": {"bold": True, "fontSize": 13}}, "textFormat")
fmt(TB, 2, 3, 0, 5, hdr, "textFormat,backgroundColor")
fmt(TB, 3, 3 + len(mt), 1, 4, money, "numberFormat")
fmt(TB, r0 - 1, r0, 0, len(mt) + 2, hdr, "textFormat,backgroundColor")
fmt(TB, r0, r1 + 1, 1, len(mt) + 2, money, "numberFormat")
fmt(TB, r1, r1 + 1, 0, len(mt) + 2, {"textFormat": {"bold": True}}, "textFormat")
reqs.append({"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": SID[TB], "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": 2, "endColumnIndex": len(mt) + 2}],
             "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f"=C{r0+1}>$B{r0+1}"}]}, "format": {"backgroundColor": {"red": 0.99, "green": 0.85, "blue": 0.85}}}}, "index": 0}})
reqs.append({"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": SID[TB], "startRowIndex": 3, "endRowIndex": 3 + len(mt), "startColumnIndex": 3, "endColumnIndex": 4}],
             "booleanRule": {"condition": {"type": "NUMBER_LESS", "values": [{"userEnteredValue": "0"}]}, "format": {"backgroundColor": {"red": 0.99, "green": 0.85, "blue": 0.85}}}}, "index": 1}})
freeze(TB, 0, 1); widths(TB, [260, 140] + [110] * (len(mt) + 1))
# Evolución ingresos
fmt(E, 0, 1, 0, nm + 4, hdr, "textFormat,backgroundColor")
fmt(E, 1, len(fuentes) + 3, 2, nm + 4, money, "numberFormat")
fmt(E, len(fuentes) + 1, len(fuentes) + 3, 0, nm + 4, {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.92, "green": 0.92, "blue": 0.92}}, "textFormat,backgroundColor")
freeze(E, 1, 2); widths(E, [300, 120] + [95] * nm + [120, 120])
reqs.append({"addChart": {"chart": {"spec": {"title": "Salario mensual (incluye libranza descontada)", "basicChart": {"chartType": "COLUMN", "legendPosition": "NO_LEGEND",
    "domains": [{"domain": {"sourceRange": {"sources": [{"sheetId": SID[E], "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": nm + 2}]}}}],
    "series": [{"series": {"sourceRange": {"sources": [{"sheetId": SID[E], "startRowIndex": len(fuentes) + 2, "endRowIndex": len(fuentes) + 3, "startColumnIndex": 2, "endColumnIndex": nm + 2}]}}, "targetAxis": "LEFT_AXIS"}],
    "headerCount": 0}},
    "position": {"overlayPosition": {"anchorCell": {"sheetId": SID[E], "rowIndex": len(fuentes) + 10, "columnIndex": 0}, "widthPixels": 900, "heightPixels": 320}}}}})
# Categorías
fmt(C, 0, 1, 0, nm + 5, hdr, "textFormat,backgroundColor")
fmt(C, 1, len(cg), 2, nm + 4, money, "numberFormat")
fmt(C, 1, len(cg), nm + 4, nm + 5, {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}}, "numberFormat")
fmt(C, len(cg) - 1, len(cg), 0, nm + 5, {"textFormat": {"bold": True}}, "textFormat")
fmt(C, 1, len(cg), nm + 2, nm + 4, {"textFormat": {"bold": True}}, "textFormat")
reqs.append({"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": SID[C], "startRowIndex": 1, "endRowIndex": len(cg) - 1, "startColumnIndex": 2, "endColumnIndex": nm + 2}],
             "gradientRule": {"minpoint": {"color": {"red": 1, "green": 1, "blue": 1}, "type": "MIN"},
                              "maxpoint": {"color": {"red": 0.96, "green": 0.6, "blue": 0.5}, "type": "PERCENTILE", "value": "95"}}}, "index": 0}})
freeze(C, 1, 2); widths(C, [200, 70] + [95] * nm + [120, 120, 80])
# Top
fmt(T, 0, 1, 0, 6, hdr, "textFormat,backgroundColor"); fmt(T, 1, len(tc), 2, 3, money, "numberFormat"); fmt(T, 1, len(tc), 5, 6, money, "numberFormat")
freeze(T, 1); widths(T, [280, 170, 120, 90, 110, 140])
# Deudas
fmt(D, 0, 1, 0, 1, {"textFormat": {"bold": True, "fontSize": 13}}, "textFormat")
widths(D, [260, 170, 140, 140, 140, 360])
# Preguntas
fmt(P, 0, 1, 0, 5, hdr, "textFormat,backgroundColor"); fmt(P, 1, len(pq), 0, 5, {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}, "wrapStrategy,verticalAlignment")
fmt(P, 1, len(pq), 4, 5, {"backgroundColor": {"red": 1, "green": 0.98, "blue": 0.8}}, "backgroundColor")
freeze(P, 1); widths(P, [30, 520, 120, 150, 360])
# Movimientos
fmt(M, 0, 1, 0, 13, hdr, "textFormat,backgroundColor"); fmt(M, 1, N, 5, 6, money, "numberFormat")
fmt(M, 1, N, 10, 12, {"backgroundColor": {"red": 1, "green": 0.98, "blue": 0.85}}, "backgroundColor")
freeze(M, 1); widths(M, [90, 70, 230, 380, 220, 110, 110, 190, 190, 70, 190, 200, 90])
cats_all = sorted({m["Categoría"] for m in movs if m["Tipo"] in ("Gasto", "Ingreso", "Inversión")} | {"Préstamo a un amigo"})
reqs.append({"setDataValidation": {"range": {"sheetId": SID[M], "startRowIndex": 1, "endRowIndex": N, "startColumnIndex": 10, "endColumnIndex": 11},
             "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": c} for c in cats_all]}, "showCustomUi": True, "strict": False}}})
reqs.append({"setBasicFilter": {"filter": {"range": {"sheetId": SID[M], "startRowIndex": 0, "endRowIndex": N, "startColumnIndex": 0, "endColumnIndex": 13}}}})
call(svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": reqs}))
print(f"https://docs.google.com/spreadsheets/d/{sid}")
