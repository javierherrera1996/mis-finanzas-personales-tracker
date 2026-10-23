"""Genera el Google Doc "Mi economía — contexto para Claude": TODO el contexto financiero en un solo documento de texto,
para consultarlo desde Claude web / celular con el conector de Google Drive (los Sheets solo se leen en muestras; un Doc se lee completo).
Se regenera en cada actualización. Uso: .venv/bin/python contexto_doc.py"""
import collections, datetime, io, json, os, re
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from auth import get_creds
from fetch_util import call
import agente, deudas

ID_FILE = "data/contexto_doc_id.txt"
TITULO = "Mi economía — contexto para Claude"
f = lambda v: "$" + f"{round(v):,}".replace(",", ".")
esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
MESES = "ene feb mar abr may jun jul ago sep oct nov dic".split()


def tabla(cab, filas):
    th = "".join(f"<th>{esc(c)}</th>" for c in cab)
    tr = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in fila) + "</tr>" for fila in filas)
    return f"<table border='1'><tr>{th}</tr>{tr}</table>"


def construir():
    movs = json.load(open("data/movimientos.json"))
    e = agente.estado()
    c = e["caja"]
    hoy = agente.HOY
    h = []
    add = h.append
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    add(f"<h1>{TITULO}</h1>")
    add(f"<p><b>Actualizado:</b> {ahora} · movimientos hasta el {c['hasta']}. Se regenera solo cuando el usuario prende su Mac (cada día) y el informe sale los lunes. "
        "Fuente: sus correos de bancos. Detalle completo en sus Sheets 'Finanzas Personales' y 'Plan y estrategia'.</p>")
    add("<h2>Cómo usar este documento (instrucciones para Claude)</h2><ul>"
        "<li>Responde en español, breve, con cifras en pesos ($1.234.567) y una recomendación concreta.</li>"
        "<li>Usa SOLO estas cifras; si algo no está aquí, dilo. Si la fecha de actualización tiene más de 3 días, avísalo.</li>"
        "<li>La caja de la cuenta principal YA incluye el bolsillo: nunca lo sumes aparte. Lo reservado (data/reservas.json) NO es gastable.</li>"
        "<li>Compras con tarjeta cuentan el día de la compra; pagos de tarjeta, avances y traslados entre cuentas propias son internos (no gasto).</li>"
        "<li>Lo extra a deudas va a la de MAYOR tasa; las tarjetas se pagan completas.</li>"
        "<li>No compares promedios largos con un mes puntual; el mes en curso es parcial.</li></ul>")

    # 1. Foto de hoy
    add("<h2>1. Foto de hoy</h2>")
    add(tabla(["Concepto", "Valor", "Detalle"], [
        ["Puede gastar por día hasta el sueldo", f(e["por_dia"]), f"{f(e['libre'])} libres ÷ {e['dias_al_pago']} días"],
        ["Próximo sueldo", e["proximo_pago"].isoformat(), f"último: {e['ultimo_pago'].isoformat()}"],
        ["Caja total (incluye bolsillo)", f(c["total"]), f"extracto {c['extracto']} + movimientos posteriores"],
        ["Bolsillo", f(c["bolsillo"]), f"{f(c['reservado_inversion'])} reservados + {f(c['emergencia'])} colchón"],
        ["Disponible en cuenta", f(c["disponible"]), ""],
        ["Otros saldos confirmados", f(e["liquido_otros"]), ", ".join(f"{k}: {f(v['valor'])}" for k, v in e["otros_saldos"].items()) or "—"],
        ["Pagos pendientes antes del sueldo", f(e["comprometido"]), "; ".join(f"{p['fecha']} {p['nombre']} {f(p['monto'])}" for p in e["por_pagar_antes_del_sueldo"]) or "—"],
        ["Gasto variable desde el último sueldo", f(e["gasto_ciclo"]), f"techo del mes {f(e['techo_ciclo'])}"],
        ["Gasto variable últimos 7 días", f(e["gasto_semana"]), f"techo semanal {f(e['techo_semana'])}"],
    ]))

    # 2. Pagos
    add("<h2>2. Pagos: qué vence y cuándo</h2><h3>Próximos 30 días</h3>")
    prox = agente.proximos_pagos(movs, dias=30)
    add(tabla(["Fecha", "Pago", "Monto", "Estado", "Cómo"], [[p["fecha"].isoformat(), p["nombre"], f(p["monto"]) if p.get("monto") else "ver extracto",
         "pagado" if p["pagado"] else ("automático" if p.get("automatico") else "pendiente"), p["como"]] for p in prox]))
    cfg = json.load(open("data/pagos_config.json"))
    add("<h3>Calendario mensual completo</h3>")
    add(tabla(["Día", "Pago", "Monto", "Tipo", "Automático", "Cómo"], [["penúltimo día hábil" if p["dia"] == "penultimo_habil" else p["dia"], p["nombre"],
         f(p["monto"]) if p.get("monto") else "según extracto", p["tipo"], "sí" if p.get("automatico") else "no", p["como"]]
         for p in cfg["pagos"] if not p.get("solo_mes") or p["solo_mes"] >= hoy.strftime("%Y-%m")]))
    if cfg.get("anuales"):
        add("<p><b>Anuales:</b> " + "; ".join(f"{a['dia']}/{a['mes']} {a['nombre']}" for a in cfg["anuales"]) + "</p>")

    # 3. Deudas
    r = deudas.resumen()
    add("<h2>3. Deudas y tasas (de mayor a menor tasa)</h2>")
    add(tabla(["Deuda", "Saldo", "Tasa E.A.", "Intereses al mes", "Cuota", "Termina en", "Nota"], [[
        ("👉 " if d.get("abonar_aqui") else "") + d["nombre"], f(d["saldo"]), deudas.pct(d["tasa_ea"]),
        f(d["interes_mes"]) if d["interes_mes"] is not None else "paga el total", f(d["cuota"]) if d["cuota"] else "—",
        f"{d['meses']} meses" if d["meses"] else "—", re.sub(r"Deudora solidaria:[^.]*\.", "", d["nota"])] for d in r["deudas"]]))
    add(f"<p>Deuda en créditos {f(r['total'])} · intereses ≈ {f(r['interes_mes'])} al mes. {esc(r['consejo'])}</p>")

    # 4. Flujo mensual
    add("<h2>4. Flujo por mes (últimos 12 meses)</h2>")
    pm = collections.defaultdict(collections.Counter)
    for m in movs: pm[m["Mes"]][m["Tipo"]] += m["Valor"]
    filas = []
    for mes in sorted(pm)[-12:]:
        t = pm[mes]
        filas.append([mes + (" (parcial)" if mes == hoy.strftime("%Y-%m") else ""), f(t["Ingreso"]), f(-t["Gasto"]), f(-t["Deuda"]),
                      f(t["Financiamiento"]) if t["Financiamiento"] else "—", f(t["Ingreso"] + t["Gasto"] + t["Deuda"])])
    add(tabla(["Mes", "Ingresos", "Gastos", "Pagos de deudas", "Créditos recibidos", "Neto (ingresos − gastos − deudas)"], filas))

    # 5. Gasto por categoría
    meses = sorted(pm)[-4:]
    cat = collections.defaultdict(collections.Counter)
    for m in movs:
        if m["Tipo"] == "Gasto" and m["Mes"] in meses: cat[m["Categoría"]][m["Mes"]] -= m["Valor"]
    add("<h2>5. Gasto por categoría (últimos 4 meses)</h2>")
    add(tabla(["Categoría"] + meses, [[k] + [f(v[mm]) for mm in meses] for k, v in sorted(cat.items(), key=lambda i: -sum(i[1].values()))]))

    # 6. Ingresos por fuente
    add("<h2>6. Ingresos por fuente (últimos 12 meses)</h2>")
    ing = collections.Counter()
    desde12 = sorted(pm)[-12:][0]
    for m in movs:
        if m["Tipo"] == "Ingreso" and m["Mes"] >= desde12 and m["Categoría"] != "Devoluciones": ing[(m["Categoría"], m["Subcategoría"])] += m["Valor"]
    add(tabla(["Categoría", "Fuente", "Total 12 meses"], [[k[0], k[1] or "—", f(v)] for k, v in ing.most_common(25)]))

    # 7. Suscripciones
    add("<h2>7. Suscripciones</h2>")
    add(tabla(["Servicio", "Costo mensual", "Último cobro", "Activa", "Sugerencia"], [[s["nombre"], f(s["mensual"]), s["ultimo"], "sí" if s["activa"] else "no", s.get("sugerencia", "")]
         for s in e["suscripciones"]]))

    # 8. Top comercios
    add("<h2>8. Dónde más gasta (últimos 6 meses)</h2>")
    desde6 = sorted(pm)[-6:][0]
    com = collections.Counter()
    for m in movs:
        if m["Tipo"] == "Gasto" and m["Mes"] >= desde6: com[(m["Comercio"] or m["Descripción"])[:40]] -= m["Valor"]
    add(tabla(["Comercio", "Total 6 meses"], [[k, f(v)] for k, v in com.most_common(30)]))

    # 9. Viajes
    try:
        import viajes
        fl, _ = viajes.resumen(movs)
        add("<h2>9. Viajes y proyectos</h2>")
        add(tabla(["Desde", "Hasta", "Viaje / proyecto", "Total", "Nota"], [[x["desde"], x["hasta"], x["nombre"], f(x["total"]), x.get("nota", "")] for x in fl]))
    except Exception:
        pass

    # 10. Plan
    if os.path.exists("data/plan.json"):
        pl = json.load(open("data/plan.json"))
        add("<h2>10. Plan, objetivos y hoja de ruta</h2><h3>Principios</h3><ul>" + "".join(f"<li>{esc(p)}</li>" for p in pl.get("principios", [])) + "</ul>")
        add("<h3>Objetivos</h3>" + tabla(["ID", "Objetivo", "Meta", "Fecha", "Estado", "Nota"], [[o["id"], o["objetivo"], o["meta"], o["fecha"], o["estado"], o.get("nota", "")] for o in pl.get("objetivos", [])]))
        add("<h3>Hoja de ruta</h3>" + tabla(["ID", "Fase", "Tarea", "Fecha", "Horas", "Estado"], [[x["id"], x["fase"], x["tarea"], x["fecha"], x["horas"], x["estado"]] for x in pl.get("hoja_de_ruta", [])]))
        if pl.get("estrategias"):
            add("<h3>Estrategias de ingreso</h3>" + tabla(["Orden", "Estrategia", "Neto/mes", "Probabilidad", "Horas/sem", "Costo-beneficio"], [[s["orden"], s["estrategia"], s["neto_mes"], s["prob"], s["horas_sem"], s["costo_beneficio"]] for s in pl["estrategias"]]))
        if pl.get("escenarios"):
            add("<h3>Escenarios</h3>" + tabla(["Escenario", "Día a día/mes", "Extra neto/mes", "Probabilidad"], [[s["escenario"], s["dia_a_dia_mes"], s["extra_neto_mes"], s["probabilidad"]] for s in pl["escenarios"]]))

    # 11. Hechos confirmados (de CLAUDE.md, sin números de documento)
    if os.path.exists("CLAUDE.md"):
        t = open("CLAUDE.md").read()
        m = re.search(r"## Hechos confirmados[^\n]*\n(.*?)\n## ", t, re.S)
        if m:
            hechos = re.sub(r"\(?CC ?\d{6,}\)?|cédula \d+|\b\d{9,}\b", "[oculto]", m.group(1))
            add("<h2>11. Hechos confirmados por el usuario</h2><p>" + esc(hechos).replace("\n\n", "</p><p>") + "</p>")

    # 12. Preguntas pendientes
    pq = e["preguntas"][:15]
    if pq:
        add("<h2>12. Movimientos que el sistema no entendió (pendientes)</h2>")
        add(tabla(["Fecha", "Monto", "Pregunta"], [[p.get("fechas", ""), p.get("monto", ""), re.sub(r"^\[[^\]]+\]\s*", "", p["q"])[:160]] for p in pq]))

    # 13. Movimientos recientes
    desde = (hoy - datetime.timedelta(days=60)).isoformat()
    rec = sorted([m for m in movs if m["Fecha"] >= desde], key=lambda m: m["Fecha"], reverse=True)
    add(f"<h2>13. Todos los movimientos desde el {desde} ({len(rec)})</h2>")
    add(tabla(["Fecha", "Valor", "Tipo", "Categoría", "Subcategoría", "Comercio / descripción", "Fuente"],
              [[m["Fecha"], f(m["Valor"]), m["Tipo"], m["Categoría"], m["Subcategoría"], (m["Comercio"] or m["Descripción"])[:50], m["Fuente"].replace(" (alerta)", "")] for m in rec]))
    return "<html><head><meta charset='utf-8'></head><body>" + "\n".join(h) + "</body></html>"


def publicar(html):
    svc = build("drive", "v3", credentials=get_creds())
    media = MediaIoBaseUpload(io.BytesIO(html.encode("utf-8")), mimetype="text/html", resumable=False)
    if os.path.exists(ID_FILE):
        fid = open(ID_FILE).read().strip()
        try:
            call(svc.files().update(fileId=fid, media_body=media, body={"name": TITULO}))
            return fid
        except Exception:
            pass   # lo borraron: se crea de nuevo
    fid = call(svc.files().create(body={"name": TITULO, "mimeType": "application/vnd.google-apps.document"}, media_body=media, fields="id"))["id"]
    open(ID_FILE, "w").write(fid)
    return fid


if __name__ == "__main__":
    html = construir()
    open("data/contexto.html", "w").write(html)
    fid = publicar(html)
    txt = call(build("drive", "v3", credentials=get_creds()).files().export(fileId=fid, mimeType="text/plain"))
    print(f"{len(html) // 1024} KB html · {len(txt) // 1024} KB de texto · https://docs.google.com/document/d/{fid}")
