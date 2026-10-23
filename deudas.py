"""Tus deudas de un vistazo: saldo, tasa (leída de los extractos cuando se puede), cuánto te cuestan en intereses cada mes,
cuándo terminan y dónde conviene abonar primero (la de mayor tasa). Lo usan dia_de_pago.py, informe_semanal.py y Claude.
Uso: .venv/bin/python deudas.py"""
import json, math

f = lambda v: "$" + f"{round(v):,}".replace(",", ".")
mv = lambda ea: (1 + ea) ** (1 / 12) - 1
pct = lambda x: f"{x:.2%}".replace(".", ",")


def _meses(saldo, ea, cuota):
    """Cuotas que faltan con cuota fija (None si la cuota no alcanza ni para los intereses)."""
    i = mv(ea)
    if not cuota or saldo <= 0: return None
    if i == 0: return math.ceil(saldo / cuota)
    if cuota <= saldo * i: return None
    return math.ceil(-math.log(1 - saldo * i / cuota) / math.log(1 + i))


def analisis():
    cfg = json.load(open("data/deudas_config.json"))["creditos"]
    out = []
    for c in cfg:
        if c.get("saldo", 0) <= 0: continue
        ea, cuota = c.get("tasa_ea", 0), c.get("cuota_capital_interes") or c.get("cuota_total")
        n = _meses(c["saldo"], ea, cuota)
        out.append({"nombre": c["nombre"], "tipo": "crédito", "saldo": c["saldo"], "tasa_ea": ea, "tasa_mv": mv(ea),
                    "interes_mes": c["saldo"] * mv(ea), "cuota": c.get("cuota_total") or cuota, "meses": n,
                    "intereses_restantes": (cuota * n - c["saldo"]) if n else None, "nomina": c.get("descuento_nomina", False),
                    "nota": c.get("nota", "")})
    try:   # tarjetas: si pagas el total cada mes no pagas intereses; si difieres a cuotas, sí
        from parse_creditos import tarjetas
        for nombre, t in tarjetas().items():
            if not t.get("tasa_ea"): continue
            saldo = t.get("deuda_total") or t.get("pago_total") or 0
            out.append({"nombre": nombre, "tipo": "tarjeta", "saldo": saldo, "tasa_ea": t["tasa_ea"], "tasa_mv": mv(t["tasa_ea"]),
                        "interes_mes": None, "cuota": t.get("pago_total"), "meses": None, "intereses_restantes": None, "nomina": False,
                        "nota": ("⚠️ Te cobraron intereses de mora: pagaste tarde. " if t.get("intereses_mora") else "")
                                + "Paga siempre el TOTAL: las compras a cuotas pagan esta tasa." + (f" Vence el {t['fecha_limite']}." if t.get("fecha_limite") else "")})
    except Exception:
        pass
    out.sort(key=lambda d: -d["tasa_ea"])
    creditos = [d for d in out if d["tipo"] == "crédito"]
    # dónde abonar: el crédito de mayor tasa (las tarjetas se pagan completas, no se "abonan")
    if creditos:
        top = creditos[0]
        top["abonar_aqui"] = True
    return out


def resumen(ds=None):
    ds = ds if ds is not None else analisis()
    cr = [d for d in ds if d["tipo"] == "crédito"]
    total = sum(d["saldo"] for d in cr)
    interes = sum(d["interes_mes"] for d in cr)
    top = next((d for d in cr if d.get("abonar_aqui")), None)
    barata = min(cr, key=lambda d: d["tasa_ea"]) if cr else None
    consejo = (f"Si te sobra plata, abónala a {top['nombre']} ({pct(top['tasa_ea'])} E.A.): cada $1.000.000 abonado te ahorra ≈ {f(1e6 * top['tasa_ea'])} de intereses al año."
               + (f" No abones extra a {barata['nombre']} ({pct(barata['tasa_ea'])}): es tu deuda más barata." if barata and barata is not top else "")) if top else ""
    return {"total": total, "interes_mes": interes, "consejo": consejo, "deudas": ds}


def tabla_html(ds=None):
    r = resumen(ds)
    fila = lambda d: (f"<tr><td style='padding:4px 8px'>{'👉 ' if d.get('abonar_aqui') else ''}{d['nombre']}</td>"
                      f"<td style='padding:4px 8px;text-align:right'>{f(d['saldo'])}</td>"
                      f"<td style='padding:4px 8px;text-align:right'>{pct(d['tasa_ea'])}</td>"
                      f"<td style='padding:4px 8px;text-align:right'>{f(d['interes_mes']) if d['interes_mes'] is not None else '—'}</td>"
                      f"<td style='padding:4px 8px'>{(str(d['meses']) + ' meses') if d['meses'] else ''}</td></tr>")
    return (f"<table style='border-collapse:collapse;font-size:14px;width:100%'><tr style='text-align:left'><th>Deuda</th><th>Saldo</th><th>Tasa E.A.</th><th>Intereses/mes</th><th>Termina en</th></tr>"
            + "".join(fila(d) for d in r["deudas"]) + "</table>"
            + f"<p style='font-size:14px'>Te cuestan ≈ <b>{f(r['interes_mes'])} al mes en intereses</b>. {r['consejo']}</p>")


if __name__ == "__main__":
    r = resumen()
    print(f"{'Deuda':<22}{'Saldo':>14}{'Tasa E.A.':>11}{'Interés/mes':>14}{'Cuota':>13}  Termina")
    for d in r["deudas"]:
        print(f"{('👉 ' if d.get('abonar_aqui') else '') + d['nombre']:<22}{f(d['saldo']):>14}{d['tasa_ea']:>10.2%}{(f(d['interes_mes']) if d['interes_mes'] is not None else '—'):>14}"
              f"{(f(d['cuota']) if d['cuota'] else '—'):>13}  {(str(d['meses']) + ' meses') if d['meses'] else ''}  {d['nota'][:90]}")
    print(f"\nDeuda en créditos {f(r['total'])} · intereses ≈ {f(r['interes_mes'])}/mes\n{r['consejo']}")
