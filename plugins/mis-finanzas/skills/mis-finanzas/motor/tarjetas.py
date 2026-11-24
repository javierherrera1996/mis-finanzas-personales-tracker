"""Deuda de cada tarjeta de crédito EN VIVO: último extracto + compras nuevas (alertas) − pagos hechos después del corte.
Dice cuánto debes hoy, qué está vencido y cuánto te van a cobrar en el próximo pago, sin esperar el extracto.
Uso: .venv/bin/python tarjetas.py"""
import calendar, datetime, json, re
import agente

f = lambda v: "$" + f"{round(v):,}".replace(",", ".")


def _mas_un_mes(d, dia=None):
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return datetime.date(y, m, min(dia or d.day, calendar.monthrange(y, m)[1]))


def _davivienda(movs, hoy):
    tc = agente.tarjeta_davivienda(movs)
    if not tc: return None
    corte = datetime.date.fromisoformat(tc["corte"])
    compras_l = [m for m in movs if m["Fuente"].startswith("Davivienda TC") and m["Fecha"] > tc["corte"] and m["Valor"] < 0]
    compras = -sum(m["Valor"] for m in compras_l)
    facturado = tc["pago_total"] - tc["creditos_despues"]            # lo del último extracto, ya con devoluciones
    exceso = max(0, tc["pagado_despues"] - facturado)                 # si pagaste más que el extracto, abona a lo nuevo
    pendiente = tc["a_pagar"]
    vencido = pendiente if tc["limite"] and hoy > tc["limite"] and pendiente > 1000 else 0
    corte_sig = _mas_un_mes(corte)
    limite_sig = _mas_un_mes(tc["limite"]) if tc["limite"] else None
    proximo = max(0, pendiente + compras - exceso)
    return {"nombre": "Tarjeta Davivienda", "debes_hoy": proximo, "vencido": vencido, "vence": tc["limite"],
            "pendiente_extracto": pendiente, "compras_ciclo": compras, "n_compras": len(compras_l), "pagado_despues": tc["pagado_despues"],
            "corte": corte, "corte_sig": corte_sig, "proximo_pago": proximo, "proximo_fecha": limite_sig,
            "solo_nuevo": max(0, compras - exceso),   # lo del próximo extracto sin contar lo vencido (que va aparte)
            "nota": (f"⚠️ VENCIDO {f(vencido)} desde el {tc['limite']:%d-%b}: págalo ya (genera mora). " if vencido else "")
                    + f"Compras desde el corte del {corte:%d-%b}: {f(compras)} ({len(compras_l)} compras). "
                    + (f"Próximo pago ≈ {f(proximo)} el {limite_sig:%d-%b} (corte {corte_sig:%d-%b}; lo que compres hasta ese día suma)." if limite_sig else "")}


def _nu(movs, hoy):
    try:
        from parse_creditos import tarjetas
        t = tarjetas().get("Tarjeta Nu")
    except Exception:
        t = None
    if not t: return None
    txt = open(t["archivo"]).read()
    M3 = {m: i + 1 for i, m in enumerate("ENE FEB MAR ABR MAY JUN JUL AGO SEP OCT NOV DIC".split())}
    c = re.search(r"Fecha de corte\n(\d{2}) ([A-Z]{3}) (\d{4})", txt)
    corte = datetime.date(int(c.group(3)), M3[c.group(2)], int(c.group(1))) if c else None
    pagos = -sum(m["Valor"] for m in movs if m["Categoría"] == "Pago tarjeta Nu" and corte and m["Fecha"] > corte.isoformat())
    a_pagar = max(0, (t.get("pago_total") or 0) - pagos)
    lim = datetime.date.fromisoformat(t["fecha_limite"]) if t.get("fecha_limite") else None
    vencido = a_pagar if lim and hoy > lim and a_pagar > 1000 else 0
    corte_sig = _mas_un_mes(corte) if corte else None
    return {"nombre": "Tarjeta Nu", "debes_hoy": a_pagar, "vencido": vencido, "vence": lim, "pendiente_extracto": a_pagar,
            "compras_ciclo": None, "pagado_despues": pagos, "corte": corte, "corte_sig": corte_sig,
            "proximo_pago": None, "proximo_fecha": _mas_un_mes(lim) if lim else None,
            "nota": (f"⚠️ VENCIDO {f(vencido)}. " if vencido else ("Extracto pagado ✅. " if a_pagar <= 1000 else f"Debes {f(a_pagar)} del extracto (vence {lim:%d-%b}). "))
                    + "Nu no manda correo por cada compra: lo nuevo se ve con el extracto" + (f" del {corte_sig:%d-%b}." if corte_sig else ".")}


def _bancolombia(movs, hoy):
    """Sin extractos: parte del último saldo que confirmaste (data/saldos_manual.json) o del último pago visto, y suma las compras después."""
    compras_all = [m for m in movs if m["Fuente"].startswith("Bancolombia TC") and m["Valor"] < 0]
    if not compras_all: return None
    manual = json.load(open("data/saldos_manual.json")) if __import__("os").path.exists("data/saldos_manual.json") else {}
    base = next((v for k, v in manual.items() if re.search(r"tarjeta bancolombia", k, re.I)), None)
    pagos = [m for m in movs if m["Categoría"] == "Pago tarjeta Bancolombia"]
    ult_pago = max((m["Fecha"] for m in pagos), default=None)
    ciclo = -sum(m["Valor"] for m in compras_all if m["Fecha"] >= (hoy - datetime.timedelta(days=31)).isoformat())
    if base and (not ult_pago or base["fecha"] >= ult_pago):
        desde, saldo0, origen = base["fecha"], base["valor"], f"saldo que confirmaste el {base['fecha']}"
    elif ult_pago:
        desde, saldo0, origen = ult_pago, 0, f"tu último pago ({ult_pago})"
    else:
        return {"nombre": "Tarjeta Bancolombia", "debes_hoy": None, "vencido": 0, "vence": None, "pendiente_extracto": None,
                "compras_ciclo": ciclo, "pagado_despues": None, "corte": None, "corte_sig": None, "proximo_pago": ciclo, "proximo_fecha": None,
                "sin_saldo": True,
                "nota": f"No sé cuánto debes: Bancolombia no manda extractos al correo y no veo pagos. Este mes le cargaste {f(ciclo)} (Uber One, Netflix, HBO). "
                        "Dime el saldo que ves en la app (responde el correo con 'tarjeta bancolombia: X') y desde ahí lo llevo solo."}
    compras = -sum(m["Valor"] for m in compras_all if m["Fecha"] > desde)
    pagado = -sum(m["Valor"] for m in pagos if m["Fecha"] > desde)
    total = max(0, saldo0 + compras - pagado)
    return {"nombre": "Tarjeta Bancolombia", "debes_hoy": total, "vencido": 0, "vence": None, "pendiente_extracto": None,
            "compras_ciclo": ciclo, "pagado_despues": pagado, "corte": None, "corte_sig": None, "proximo_pago": total, "proximo_fecha": None,
            "nota": f"Desde {origen}: + {f(compras)} en compras − {f(pagado)} en pagos. Este mes: {f(ciclo)}."}


def en_vivo(movs=None, hoy=None):
    movs = movs if movs is not None else json.load(open("data/movimientos.json"))
    hoy = hoy or agente.HOY
    return [t for t in (_davivienda(movs, hoy), _nu(movs, hoy), _bancolombia(movs, hoy)) if t]


if __name__ == "__main__":
    for t in en_vivo():
        print(f"{t['nombre']:<20} debes hoy {(f(t['debes_hoy']) if t['debes_hoy'] is not None else '¿?'):>12}" + (f" · VENCIDO {f(t['vencido'])}" if t["vencido"] else "")
              + (f" · próximo pago ≈ {f(t['proximo_pago'])} el {t['proximo_fecha']}" if t.get("proximo_pago") and t.get("proximo_fecha") else ""))
        print("   ", t["nota"])
