"""Estado general en un solo lugar: cuentas, tarjetas (en vivo), créditos activos (con lo que de verdad cobran: intereses,
capital y seguros), créditos cerrados y en qué se te va la plata. Lo usa contexto_doc.py (Claude web) y se puede correr solo.
Uso: .venv/bin/python estado_general.py"""
import collections, datetime, json, re
import agente, deudas, tarjetas
from parse_creditos import creditos, saldos_cuentas
from config import C, DAVI

f = lambda v: "$" + f"{round(v):,}".replace(",", ".")
SIN_IDENTIFICAR = ("Transferencias a terceros", "Otros", "Gastos vía Daviplata (sin detalle)", "Efectivo", "Por aclarar")


def _mas_meses(fecha, n):
    d = datetime.date.fromisoformat(fecha)
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return f"{['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][m-1]}-{y}"


def construir():
    movs = json.load(open("data/movimientos.json"))
    e = agente.estado()
    c = e["caja"]
    out = {}

    # ---------- cuentas ----------
    sc = saldos_cuentas()
    ult = max([x[0] for x in sc] or [""])
    pri = DAVI.get("cuenta_principal", "")
    afc = next((x[2] for x in sc if x[0] == ult and x[1] != pri), None)
    cuentas = [[f"Davivienda *{pri} (incluye bolsillo)", f(c["total"] - (afc or 0)), f"extracto {c['extracto']} + movimientos hasta {c['hasta']}"],
               ["   · bolsillo: reservado", f(c["reservado_inversion"]), "no se gasta (data/reservas.json)"],
               ["   · bolsillo: colchón", f(c["emergencia"]), "emergencias"],
               ["   · disponible en la cuenta", f(c["disponible"]), ""]]
    if afc is not None: cuentas.append([f"AFC *{DAVI.get('cuenta_afc', '')}", f(afc), f"extracto {ult}"])
    banc = next((v for k, v in e["otros_saldos"].items() if k.lower().startswith("bancolombia")), None)
    cuentas.append([f"Bancolombia *{C.get('bancolombia', {}).get('ahorros', '')}", f(banc["valor"]) if banc else "sin confirmar",
                    f"saldo confirmado {banc.get('base_fecha')} + alertas" if banc and banc.get("base_fecha") else "dime el saldo de la app y lo llevo solo"])
    try:
        from parse_otros import cuenta_nu
        cn = cuenta_nu()
        if cn: cuentas.append(["Cuenta Nu + cajitas", f(cn["cuenta"] + cn["cajitas"]), f"extracto {cn['fecha']}"])
    except Exception:
        pass
    cuentas.append(["Nequi / Daviplata", "sin datos", "no mandan extractos al correo"])
    out["cuentas"] = cuentas

    # ---------- tarjetas ----------
    out["tarjetas"] = [[t["nombre"], "¿?" if t["debes_hoy"] is None else f(t["debes_hoy"]), f(t["vencido"]) if t.get("vencido") else "—",
                        (f"{f(t['proximo_pago'])} el {t['proximo_fecha']:%d-%b}" if t.get("proximo_pago") and t.get("proximo_fecha") else "—"), t["nota"]]
                       for t in tarjetas.en_vivo(movs)]

    # ---------- créditos activos (config + último extracto) ----------
    cfg = json.load(open("data/deudas_config.json"))["creditos"]
    ext = creditos()
    activos, usados = [], set()
    for d in deudas.analisis():
        if d["tipo"] != "crédito": continue
        cc = next((x for x in cfg if x["nombre"] == d["nombre"]), {})
        num = next((k for k in ext if cc.get("sufijo") and k.endswith(cc["sufijo"])), None)
        x = ext.get(num, {}) if num else {}
        if num: usados.add(num)
        seguros = (x.get("seguro_vida") or 0) + (x.get("otros_cargos") or 0)
        cobro = cc.get("cuota_total") or d["cuota"]
        if cc.get("descuento_nomina") and x.get("total_abonado") and not x.get("anticipado"): cobro = x["total_abonado"]   # incluye seguros
        pend = x.get("cuotas_pendientes") or d["meses"]
        activos.append([("👉 " if d.get("abonar_aqui") else "") + d["nombre"], f(d["saldo"]), deudas.pct(d["tasa_ea"]), f(cobro),
                        f(x["intereses_mes"]) if x.get("intereses_mes") else f(d["interes_mes"]),
                        f(seguros) if seguros else "—", f"{pend} cuotas → {_mas_meses(cc.get('fecha_saldo', agente.HOY.isoformat()), pend)}" if pend else "—",
                        "nómina" if cc.get("descuento_nomina") else "tú (PSE)"])
    out["creditos"] = activos
    r = deudas.resumen()
    out["creditos_resumen"] = f"Deuda en créditos {f(r['total'])} · intereses ≈ {f(r['interes_mes'])} al mes. {r['consejo']}"
    cerrados = [[k, v["fecha"], f(v["saldo"]), deudas.pct(v["tasa_ea"]) if v.get("tasa_ea") else "—"]
                for k, v in sorted(ext.items(), key=lambda i: i[1]["fecha"]) if k not in usados and v["fecha"] < (agente.HOY - datetime.timedelta(days=25)).isoformat()]
    out["cerrados"] = cerrados

    # ---------- en qué se te va la plata ----------
    meses = sorted({m["Mes"] for m in movs})[-4:]
    cat = collections.defaultdict(collections.Counter)
    for m in movs:
        if m["Tipo"] == "Gasto" and m["Mes"] in meses: cat[m["Categoría"]][m["Mes"]] -= m["Valor"]
    filas = sorted(cat.items(), key=lambda i: -sum(i[1].values()))
    out["gasto_meses"] = meses
    out["gasto"] = [[k] + [f(v[mm]) for mm in meses] + [f(sum(v.values()) / len(meses))] for k, v in filas]
    tot = sum(sum(v.values()) for v in cat.values()) / len(meses)
    sin_id = sum(sum(v.values()) for k, v in cat.items() if k in SIN_IDENTIFICAR) / len(meses)
    # "día a día" = sin impuestos ni pagos grandes de una sola vez (≥ $1 M: matrículas, bicicleta, tiquetes, cursos)
    gm = [m for m in movs if m["Tipo"] == "Gasto" and m["Mes"] in meses]
    grandes = [m for m in gm if m["Valor"] <= -1_000_000 or m["Categoría"] == "Impuestos"]
    dia = -sum(m["Valor"] for m in gm if m not in grandes and m["Categoría"] != "Vivienda") / len(meses)
    out["gasto_grandes"] = [[m["Fecha"], f(-m["Valor"]), m["Categoría"], (m["Subcategoría"] or m["Comercio"] or m["Descripción"])[:50]]
                            for m in sorted(grandes, key=lambda m: m["Valor"])[:15]]
    out["gasto_resumen"] = (f"Últimos {len(meses)} meses: gastaste {f(tot)} al mes en total, pero ese número incluye la renta y pagos grandes de una vez "
                            f"({f(-sum(m['Valor'] for m in grandes) / len(meses))}/mes en promedio). Tu DÍA A DÍA (sin arriendo, sin impuestos y sin compras ≥ $1 M) "
                            f"es ≈ {f(dia)} al mes. De eso, {f(sin_id)} al mes son transferencias, pagos QR, Daviplata o efectivo SIN identificar.")
    out["recurrentes_nuevos"] = e.get("recurrentes_nuevos", [])
    return out


def texto(o=None):
    o = o or construir()
    lin = ["== CUENTAS =="] + [f"  {a:<40} {b:>14}  {c}" for a, b, c in o["cuentas"]]
    lin += ["", "== TARJETAS (en vivo) =="] + [f"  {a:<20} debes {b:>12}  vencido {c:>10}  próximo {d}" for a, b, c, d, _ in o["tarjetas"]]
    lin += ["", "== CRÉDITOS ACTIVOS ==", f"  {'Crédito':<16}{'Saldo':>14}{'Tasa':>8}{'Te cobran':>13}{'Intereses':>12}{'Seguros':>10}  Termina · Cómo"]
    lin += [f"  {a[:16]:<16}{b:>14}{c:>8}{d:>13}{e:>12}{g:>10}  {h} · {i}" for a, b, c, d, e, g, h, i in o["creditos"]]
    lin += ["  " + o["creditos_resumen"], "", "== CRÉDITOS CERRADOS / PREPAGADOS =="] + [f"  {a} último extracto {b} (saldo {c}, tasa {d})" for a, b, c, d in o["cerrados"]]
    lin += ["", "== EN QUÉ SE TE VA LA PLATA ==", "  " + o["gasto_resumen"]]
    lin += [f"  {r[0][:34]:<34}" + "".join(f"{x:>13}" for x in r[1:]) for r in o["gasto"][:14]]
    if o["recurrentes_nuevos"]:
        lin += ["", "== COBROS QUE SE REPITEN Y NO TENGO REGISTRADOS =="] + [f"  {r['comercio']} ≈ {f(r['mensual'])}/mes ({r['meses']} meses)" for r in o["recurrentes_nuevos"]]
    return "\n".join(lin)


if __name__ == "__main__":
    print(texto())
