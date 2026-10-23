"""Cerebro del agente: calcula el estado de tus finanzas a hoy y detecta lo que hay que preguntarte.
Lo usan informe_semanal.py, calendario.py y make_sheet.py."""
import calendar, datetime, json, os, re, collections
import holidays
from config import C, DAVI, SUELDO

HOY = datetime.date.today()
FEST = holidays.Colombia(years=range(2025, 2031))
TECHO_MES = C.get("techo_gasto_mes", 6000000)   # techo de gasto del día a día
FIJOS_MES = C.get("fijos_mes", 0)                # fijos que se pagan aparte, en el calendario (ej. arriendo)
TECHO_VARIABLE_MES = TECHO_MES - FIJOS_MES
EXCLUIR_VARIABLE = C.get("excluir_del_variable", r"Vivienda|Impuestos")
UMBRAL_PREGUNTA = 100000      # transacciones sin clasificar desde este monto se te preguntan
CATS_DUDOSAS = {"Otros", "Transferencias a terceros", "Gastos vía Daviplata (sin detalle)", "Efectivo", "Por aclarar"}


def penultimo_habil(y, m):
    dias = [datetime.date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]
    habiles = [d for d in dias if d.weekday() < 5 and d not in FEST]
    return habiles[-2]


def dia_sueldo(y, m):
    """Día en que llega el sueldo (config.json -> sueldo.dia_pago: "penultimo_habil" o un número de día)."""
    d = SUELDO.get("dia_pago", "penultimo_habil")
    if d == "penultimo_habil": return penultimo_habil(y, m)
    return datetime.date(y, m, min(int(d), calendar.monthrange(y, m)[1]))


def proximo_pago(desde=HOY):
    p = dia_sueldo(desde.year, desde.month)
    if p >= desde: return p
    y, m = (desde.year + 1, 1) if desde.month == 12 else (desde.year, desde.month + 1)
    return dia_sueldo(y, m)


def ultimo_pago(desde=HOY):
    p = dia_sueldo(desde.year, desde.month)
    if p <= desde: return p
    y, m = (desde.year - 1, 12) if desde.month == 1 else (desde.year, desde.month - 1)
    return dia_sueldo(y, m)


def fecha_pago(p, y, m):
    """Fecha concreta de un pago recurrente en el mes y/m."""
    if p["dia"] == "penultimo_habil": return penultimo_habil(y, m)
    return datetime.date(y, m, min(int(p["dia"]), calendar.monthrange(y, m)[1]))


def caja(movs):
    """Caja de hoy en Davivienda = saldo del último extracto (la cuenta principal YA incluye el bolsillo) + movimientos posteriores.
    Los traslados bolsillo<->cuenta son internos: no cambian la caja, solo cuánto hay en el bolsillo.
    Si el usuario no tiene extractos de Davivienda, la caja sale en 0 (adaptar a su banco con la skill finanzas-nueva-fuente)."""
    from parse_creditos import saldos_cuentas
    sc = saldos_cuentas()
    if not sc:
        return {"total": 0, "bolsillo": 0, "disponible": 0, "extracto": "sin extractos", "hasta": max([m["Fecha"] for m in movs] or [""]), "reservado_inversion": 0, "emergencia": 0}
    ult = max(x[0] for x in sc)
    principal, bolsillo = DAVI.get("cuenta_principal", ""), "*" + (DAVI.get("bolsillo") or "sin-bolsillo")
    total0 = sum(x[2] for x in sc if x[0] == ult)
    bol0 = sum(x[3] for x in sc if x[0] == ult and x[1] == principal)
    fin = f"{ult}-31"
    post = [m for m in movs if m["Fecha"] > fin and m["Fuente"].startswith("Davivienda Ahorros")]
    total = total0 + sum(m["Valor"] for m in post if bolsillo not in m["Fuente"])
    bol = bol0 + sum(m["Valor"] for m in post if bolsillo in m["Fuente"])
    hasta = max([m["Fecha"] for m in post] or [fin])
    res = json.load(open("data/reservas.json")) if os.path.exists("data/reservas.json") else {}
    inv = min(res.get("inversion", 0), max(bol, 0))
    return {"total": round(total), "bolsillo": round(bol), "disponible": round(total - bol), "extracto": ult, "hasta": hasta,
            "reservado_inversion": round(inv), "emergencia": round(bol - inv)}


def pagado(p, movs, desde, hasta):
    if not p.get("buscar"): return p.get("automatico", False)
    return any(re.search(p["buscar"], m["Descripción"] + " " + m.get("Subcategoría", "") + " " + m.get("Tu nota", ""), re.I) and desde <= m["Fecha"] <= hasta for m in movs)


def tarjeta_davivienda(movs):
    """Pago total y fecha límite del último extracto de la tarjeta de crédito Davivienda, menos abonos/anulaciones posteriores al corte."""
    import glob
    MES3 = {m: i + 1 for i, m in enumerate("Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split())}
    for fn in sorted(glob.glob("pdfs/davivienda/*portafolio*.txt"), reverse=True):
        t = open(fn).read()
        if "Detalle de movimientos del mes" not in t: continue
        pt = re.search(r"Pago total \$([\d,]+)", t)
        per = re.search(r"Mis gastos desde\n(\d{2})/(\w{3})/(\d{4}) - (\d{2})/(\w{3})/(\d{4})", t)
        lim = re.search(r"\n(\d{2})/(\w{3})/(\d{4})\n\$[\d,]+\n\$[\d,]+\n", t)
        if not (pt and per): continue
        corte = f"{per.group(6)}-{MES3[per.group(5)]:02d}-{per.group(4)}"
        c0 = datetime.date.fromisoformat(corte); limite = None
        for d, mo, y in re.findall(r"(\d{2})/([A-Z][a-z]{2})/(\d{4})", t):
            if mo in MES3:
                f_ = datetime.date(int(y), MES3[mo], int(d))
                if c0 < f_ <= c0 + datetime.timedelta(days=30): limite = f_; break
        total = float(pt.group(1).replace(",", ""))
        creditos = sum(m["Valor"] for m in movs if m["Fuente"].startswith("Davivienda TC") and m["Fecha"] > corte and m["Valor"] > 0)
        pagado = sum(-m["Valor"] for m in movs if re.search(r"Pago Tarj|Pago Tarjeta de Credito", m["Descripción"]) and m["Fecha"] > corte)
        return {"corte": corte, "limite": limite, "pago_total": total, "creditos_despues": creditos,
                "a_pagar": max(0, total - creditos - pagado), "pagado_despues": pagado}
    return None


def proximos_pagos(movs, dias=21):
    cfg = json.load(open("data/pagos_config.json"))
    tc = tarjeta_davivienda(movs)
    out = []
    for k in range(0, 2):
        y, m = HOY.year + (HOY.month - 1 + k) // 12, (HOY.month - 1 + k) % 12 + 1
        for p in cfg["pagos"]:
            if p.get("solo_mes") and p["solo_mes"] != f"{y}-{m:02d}": continue  # pagos de una sola vez
            f = fecha_pago(p, y, m)
            if HOY - datetime.timedelta(days=10) <= f <= HOY + datetime.timedelta(days=dias):
                ini = (f - datetime.timedelta(days=20)).isoformat()
                item = {**p, "fecha": f, "pagado": pagado(p, movs, ini, (f + datetime.timedelta(days=15)).isoformat()) if f <= HOY + datetime.timedelta(days=3) else False}
                if p["nombre"].startswith("Tarjeta Davivienda") and tc and tc["limite"] and abs((tc["limite"] - f).days) <= 10:
                    item.update({"fecha": tc["limite"], "monto": round(tc["a_pagar"]), "pagado": tc["a_pagar"] <= 1000,
                                 "como": f"Extracto corte {tc['corte']}: pago total ${tc['pago_total']:,.0f}".replace(",", ".") + (f" − devoluciones ${tc['creditos_despues']:,.0f}".replace(",", ".") if tc["creditos_despues"] else "") + ". Verifica el valor en la app."})
                out.append(item)
    return sorted(out, key=lambda x: x["fecha"])


def suscripciones(movs):
    cfg = json.load(open("data/suscripciones.json"))
    ini = (HOY - datetime.timedelta(days=183)).isoformat()
    out = []
    for s in cfg["items"]:
        rs = [m for m in movs if m["Valor"] < 0 and m["Tipo"] == "Gasto" and re.search(s["buscar"], m["Descripción"])]
        rec = [m for m in rs if m["Fecha"] >= ini]
        if not rs: continue
        # suscripción cancelada que sigue cobrando (después del último cobro esperado)
        tarde = [m for m in rs if s.get("ultimo_cobro_esperado_hasta") and m["Fecha"] > s["ultimo_cobro_esperado_hasta"]]
        out.append({**s, "mensual": round(-sum(m["Valor"] for m in rec) / 6), "ultimo": rs[-1]["Fecha"], "ultimo_monto": round(-rs[-1]["Valor"]),
                    "activa": rs[-1]["Fecha"] >= (HOY - datetime.timedelta(days=45)).isoformat() and not (s.get("cancelada") and not tarde),
                    "cobro_tras_cancelar": [(m["Fecha"], round(-m["Valor"])) for m in tarde]})
    return sorted(out, key=lambda x: -x["mensual"])


def gasto(movs, desde, hasta, solo_variable=False):
    return round(-sum(m["Valor"] for m in movs if m["Tipo"] == "Gasto" and desde <= m["Fecha"] <= hasta
                      and not (solo_variable and re.search(EXCLUIR_VARIABLE, m["Categoría"] + " " + m["Subcategoría"]))))


def ingresos(movs, desde, hasta):
    return [m for m in movs if m["Tipo"] == "Ingreso" and desde <= m["Fecha"] <= hasta and m["Valor"] > 20000
            and "Libranza descontada" not in m["Subcategoría"] and m["Categoría"] != "Devoluciones"]


def nuevas_preguntas(movs):
    """Agrega a data/preguntas.json las transacciones recientes que el agente no sabe clasificar."""
    pq = json.load(open("data/preguntas.json"))
    ya = {p.get("id") for p in pq}
    ini = (HOY - datetime.timedelta(days=45)).isoformat()
    n = 0
    for m in movs:
        if m["Fecha"] < ini or m["ID"] in ya or m.get("Categoría manual"): continue
        if m["Categoría"] in CATS_DUDOSAS and abs(m["Valor"]) >= UMBRAL_PREGUNTA:
            pq.append({"id": m["ID"], "q": f"[Nuevo] {m['Fecha']} · {m['Fuente']} · {m['Descripción'][:90]}. ¿Qué fue? Escribe una categoría (p. ej. Comida, Préstamo a un amigo, Viajes) o una nota.",
                       "monto": f"${abs(m['Valor']):,.0f}".replace(",", "."), "fechas": m["Fecha"], "nuevo": True})
            n += 1
    json.dump(pq, open("data/preguntas.json", "w"), ensure_ascii=False, indent=1)
    return n


def pendientes(pq=None):
    pq = pq if pq is not None else json.load(open("data/preguntas.json"))
    ov = json.load(open("data/overrides.json")) if os.path.exists("data/overrides.json") else {"respuestas": {}}
    return [p for p in pq if not ov.get("respuestas", {}).get(p["q"])]


def _por_cat(movs, desde):
    c = collections.defaultdict(float)
    for m in movs:
        if m["Tipo"] == "Gasto" and m["Fecha"] >= desde and not re.search(EXCLUIR_VARIABLE, m["Categoría"] + " " + m["Subcategoría"]):
            c[m["Categoría"]] -= m["Valor"]
    return {k: round(v) for k, v in c.items()}


def deuda():
    cfg = json.load(open("data/deudas_config.json"))["creditos"]
    return round(sum(c["saldo"] for c in cfg)), cfg


def estado():
    movs = json.load(open("data/movimientos.json"))
    c = caja(movs)
    pp, up = proximo_pago(), ultimo_pago()
    dias = max(1, (pp - HOY).days)
    prox = proximos_pagos(movs)
    por_pagar = [p for p in prox if not p["pagado"] and not p.get("automatico") and p["fecha"] < pp and p["tipo"] not in ("ingreso", "ahorro") and p.get("monto")]
    comprometido = sum(p["monto"] for p in por_pagar)
    # saldos que el usuario confirma por correo/WhatsApp (Bancolombia, Nequi, Daviplata, efectivo) de los últimos 7 días
    manual = json.load(open("data/saldos_manual.json")) if os.path.exists("data/saldos_manual.json") else {}
    hace7 = (HOY - datetime.timedelta(days=7)).isoformat()
    otros = {k: v for k, v in manual.items() if v.get("fecha", "") >= hace7 and v.get("valor") is not None}
    try:   # Cuenta Nu (ahorros + cajitas) del último extracto, si tiene plata y el extracto es reciente
        from parse_otros import cuenta_nu
        cn = cuenta_nu()
        if cn and cn["cuenta"] + cn["cajitas"] > 0 and cn["fecha"] >= (HOY - datetime.timedelta(days=40)).isoformat() and "Cuenta Nu" not in otros:
            otros["Cuenta Nu (extracto)"] = {"valor": cn["cuenta"] + cn["cajitas"], "fecha": cn["fecha"]}
    except Exception:
        pass
    liquido_otros = sum(v["valor"] for k, v in otros.items() if not re.search(r"tarjeta|deuda", k, re.I))
    deuda_tc_otros = sum(v["valor"] for k, v in otros.items() if re.search(r"tarjeta|deuda", k, re.I))
    libre = c["disponible"] + liquido_otros - deuda_tc_otros - comprometido
    semana_ini = (HOY - datetime.timedelta(days=7)).isoformat()
    ciclo_ini = up.isoformat()
    total_deuda, creditos = deuda()
    return {
        "hoy": HOY, "caja": c, "otros_saldos": otros, "liquido_otros": liquido_otros, "deuda_tc_otros": deuda_tc_otros, "proximo_pago": pp, "ultimo_pago": up, "dias_al_pago": dias,
        "por_pagar_antes_del_sueldo": por_pagar, "comprometido": comprometido, "libre": libre, "por_dia": round(libre / dias),
        "gasto_semana": gasto(movs, semana_ini, HOY.isoformat(), True), "techo_semana": round(TECHO_VARIABLE_MES * 7 / 30),
        "gasto_ciclo": gasto(movs, ciclo_ini, HOY.isoformat(), True), "techo_ciclo": TECHO_VARIABLE_MES,
        "fijos_semana": gasto(movs, semana_ini, HOY.isoformat()) - gasto(movs, semana_ini, HOY.isoformat(), True),
        "ingresos_semana": ingresos(movs, semana_ini, HOY.isoformat()),
        "top_semana": sorted([m for m in movs if m["Tipo"] == "Gasto" and m["Fecha"] >= semana_ini and not re.search(EXCLUIR_VARIABLE, m["Categoría"] + " " + m["Subcategoría"])], key=lambda m: m["Valor"])[:8],
        "categorias_ciclo": sorted(collections.Counter({k: v for k, v in _por_cat(movs, ciclo_ini).items()}).items(), key=lambda i: -i[1]),
        "proximos": prox, "suscripciones": suscripciones(movs), "deuda": total_deuda, "creditos": creditos,
        "preguntas": pendientes(),
    }


if __name__ == "__main__":
    e = estado()
    print(f"Caja {e['caja']} | próximo pago {e['proximo_pago']} ({e['dias_al_pago']} días)")
    print(f"Por pagar antes del sueldo: {[(p['nombre'], p['monto']) for p in e['por_pagar_antes_del_sueldo']]}")
    print(f"Libre {e['libre']:,} → {e['por_dia']:,}/día | gasto semana {e['gasto_semana']:,} (techo {e['techo_semana']:,})")
    for p in e["proximos"]: print("  ", p["fecha"], "✅" if p["pagado"] else "⏳", p["nombre"], p.get("monto"))
    for s in e["suscripciones"]: print("  sub", s["nombre"], s["mensual"], s["ultimo"], "activa" if s["activa"] else "inactiva")
    print("preguntas pendientes", len(e["preguntas"]))
