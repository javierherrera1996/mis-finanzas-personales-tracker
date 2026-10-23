"""Día de pago: cuando detecta que te llegó el sueldo, te avisa (correo + notificación del Mac):
"Hoy te pagaron $X. Paga esto antes del próximo sueldo, aparta esto, y te queda $Y libre ($Z por día)."
Lo llama actualizar.py en cada corrida; solo avisa una vez por sueldo (marca en data/ultimo_aviso_pago.txt).
Uso: .venv/bin/python dia_de_pago.py [--forzar] [--no-enviar]"""
import datetime, json, os, re, subprocess, sys
import agente, deudas

MARCA = "data/ultimo_aviso_pago.txt"
MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()
f = lambda v: "$" + f"{round(v):,}".replace(",", ".")
d = lambda x: f"{x.day} {MESES[x.month - 1]}"


def sueldo_esperado():
    cfg = json.load(open("data/pagos_config.json"))
    return next((p.get("monto") or 0 for p in cfg["pagos"] if p.get("tipo") == "ingreso"), 0)


def sueldo_reciente(movs, dias=3):
    """El abono de sueldo de los últimos días (o None). Ignora las filas estimadas de libranzas de nómina."""
    desde = (agente.HOY - datetime.timedelta(days=dias)).isoformat()
    minimo = 0.5 * sueldo_esperado() if sueldo_esperado() else 1_000_000
    cands = [m for m in movs if m["Tipo"] == "Ingreso" and m["Categoría"] == "Salario" and m["Fecha"] >= desde
             and m["Valor"] >= minimo and not m["Fuente"].startswith("Descuento de nómina")]
    return max(cands, key=lambda m: m["Valor"]) if cands else None


def plan(movs, sueldo):
    """Qué pagar y apartar desde hoy hasta el próximo sueldo, y cuánto queda libre."""
    hoy = agente.HOY
    sig = agente.proximo_pago(hoy + datetime.timedelta(days=1))
    dias = max(1, (sig - hoy).days)
    prox = agente.proximos_pagos(movs, dias=dias)
    pend = [p for p in prox if hoy - datetime.timedelta(days=3) <= p["fecha"] < sig and not p["pagado"] and not p.get("automatico")
            and p["tipo"] not in ("ingreso",)]
    pagar = [p for p in pend if p["tipo"] != "ahorro"]
    apartar = [p for p in pend if p["tipo"] == "ahorro"]
    auto = [p for p in prox if hoy <= p["fecha"] < sig and p.get("automatico") and p["tipo"] not in ("ingreso",)]
    # tarjetas sin monto en la configuración: usa el pago total del último extracto
    try:
        from parse_creditos import tarjetas
        tj = tarjetas()
        for p in pagar:
            if not p.get("monto") and "Nu" in p["nombre"] and tj.get("Tarjeta Nu", {}).get("pago_total"):
                p["monto"] = round(tj["Tarjeta Nu"]["pago_total"]); p["como"] += " (pago total del último extracto)"
    except Exception:
        pass
    e = agente.estado()
    disponible = e["caja"]["disponible"] + e["liquido_otros"] - e["deuda_tc_otros"]
    total_pagar = sum(p.get("monto") or 0 for p in pagar)
    total_apartar = sum(p.get("monto") or 0 for p in apartar)
    libre = disponible - total_pagar - total_apartar
    return {"sueldo": sueldo, "siguiente": sig, "dias": dias, "pagar": pagar, "apartar": apartar, "automaticos": auto,
            "disponible": disponible, "total_pagar": total_pagar, "total_apartar": total_apartar, "libre": libre,
            "por_dia": libre / dias, "sin_monto": [p for p in pagar if not p.get("monto")], "deudas": deudas.resumen()}


def html(pl):
    fila = lambda p: (f"<tr><td style='padding:4px 8px'>{d(p['fecha'])}</td><td style='padding:4px 8px'>{p['nombre']}</td>"
                      f"<td style='padding:4px 8px;text-align:right'>{f(p['monto']) if p.get('monto') else 'ver extracto'}</td>"
                      f"<td style='padding:4px 8px;color:#555'>{p['como']}</td></tr>")
    tabla = lambda ps: "<table style='border-collapse:collapse;font-size:14px;width:100%'>" + "".join(fila(p) for p in sorted(ps, key=lambda p: p["fecha"])) + "</table>"
    color = "#1a7f37" if pl["por_dia"] > 150000 else "#b35900" if pl["por_dia"] > 60000 else "#c62828"
    s = pl["sueldo"]
    return f"""<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:720px;color:#222">
<h2 style="margin-bottom:4px">💰 ¡Hoy te pagaron!</h2>
<p style="color:#555;margin-top:0">Llegaron <b>{f(s['Valor'])}</b> ({s['Fecha']}). Próximo sueldo: <b>{d(pl['siguiente'])}</b> ({pl['dias']} días).</p>
<h3>1. Paga esto antes del próximo sueldo — {f(pl['total_pagar'])}</h3>
{tabla(pl['pagar']) if pl['pagar'] else '<p>Nada pendiente 🎉</p>'}
{('<p style="color:#b35900">⚠️ Sin monto (revisa el extracto): ' + ', '.join(p['nombre'] for p in pl['sin_monto']) + '</p>') if pl['sin_monto'] else ''}
{('<h3>2. Aparta esto — ' + f(pl['total_apartar']) + '</h3>' + tabla(pl['apartar'])) if pl['apartar'] else ''}
{('<p style="font-size:13px;color:#555">Se descuentan solos: ' + ', '.join(p['nombre'] + ' ' + (f(p['monto']) if p.get('monto') else '') for p in pl['automaticos']) + '.</p>') if pl['automaticos'] else ''}
<div style="background:#f6f8fa;border-radius:10px;padding:16px;margin:16px 0">
  <div style="font-size:15px;color:#555">Después de pagar y apartar te queda libre</div>
  <div style="font-size:34px;font-weight:700;color:{color}">{f(pl['libre'])} → {f(pl['por_dia'])} por día</div>
  <div style="font-size:13px;color:#555">{f(pl['disponible'])} disponibles − {f(pl['total_pagar'])} de pagos − {f(pl['total_apartar'])} para apartar. No cuenta lo reservado para inversión.</div>
</div>
<h3>Tus deudas</h3>
{deudas.tabla_html(pl['deudas']['deudas'])}
</div>"""


def enviar(cuerpo, asunto):
    from informe_semanal import enviar as _enviar
    return _enviar(cuerpo, asunto)


def revisar(forzar=False, enviar_correo=True):
    """Avisa si llegó el sueldo y todavía no se avisó. Devuelve el plan (o None)."""
    movs = json.load(open("data/movimientos.json"))
    s = sueldo_reciente(movs)
    if not s: return None
    ya = open(MARCA).read().strip() if os.path.exists(MARCA) else ""
    if ya == s["ID"] and not forzar: return None
    pl = plan(movs, s)
    cuerpo = html(pl)
    os.makedirs("data/informes", exist_ok=True)
    open(f"data/informes/dia-de-pago-{agente.HOY}.html", "w").write(cuerpo)
    asunto = f"💰 Te pagaron: paga {f(pl['total_pagar'])} y te quedan {f(pl['por_dia'])}/día hasta el {d(pl['siguiente'])}"
    if enviar_correo and enviar(cuerpo, asunto):
        open(MARCA, "w").write(s["ID"])
        subprocess.run(["osascript", "-e", f'display notification "Paga {f(pl["total_pagar"])} · libres {f(pl["por_dia"])}/día" with title "💰 Hoy te pagaron"'], capture_output=True)
    return pl


if __name__ == "__main__":
    movs = json.load(open("data/movimientos.json"))
    sim = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--simular=")), None)
    if "--forzar" in sys.argv or sim:   # vista previa: con el último sueldo, o simulando el próximo día de pago
        minimo = 0.5 * sueldo_esperado()
        cands = [m for m in movs if m["Categoría"] == "Salario" and m["Tipo"] == "Ingreso" and m["Valor"] >= minimo and not m["Fuente"].startswith("Descuento de nómina")]
        if not cands and not sim: sys.exit("Todavía no hay un sueldo identificado (categoría Salario). Usa --simular=AAAA-MM-DD.")
        s = max(cands, key=lambda m: m["Fecha"]) if cands else {"Fecha": "", "Valor": 0, "ID": ""}
        extra = 0
        if sim:   # "como si hoy fuera el día de pago": suma el sueldo esperado a la caja de hoy
            agente.HOY = datetime.date.fromisoformat(sim)
            s = {**s, "Fecha": sim, "Valor": sueldo_esperado(), "ID": "simulado"}; extra = sueldo_esperado()
        pl = plan(movs, s)
        pl["disponible"] += extra; pl["libre"] += extra; pl["por_dia"] = pl["libre"] / pl["dias"]
        os.makedirs("data/informes", exist_ok=True)
        open("data/informes/dia-de-pago-vista-previa.html", "w").write(html(pl))
        print(f"Sueldo {s['Fecha']} {f(s['Valor'])} · próximo {pl['siguiente']} ({pl['dias']} días)")
        for p in pl["pagar"]: print("  pagar  ", p["fecha"], p["nombre"], f(p["monto"]) if p.get("monto") else "ver extracto")
        for p in pl["apartar"]: print("  apartar", p["fecha"], p["nombre"], f(p["monto"]))
        for p in pl["automaticos"]: print("  solo   ", p["fecha"], p["nombre"], f(p["monto"]) if p.get("monto") else "")
        print(f"  disponible {f(pl['disponible'])} − pagar {f(pl['total_pagar'])} − apartar {f(pl['total_apartar'])} = libre {f(pl['libre'])} ({f(pl['por_dia'])}/día)")
        print("Vista previa: data/informes/dia-de-pago-vista-previa.html")
    else:
        pl = revisar(enviar_correo="--no-enviar" not in sys.argv)
        print("Sin sueldo nuevo" if not pl else f"Aviso de día de pago: libre {f(pl['libre'])}")
