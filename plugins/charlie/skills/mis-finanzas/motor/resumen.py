"""Resumen financiero: el cierre de la configuración (y del mes), con las preguntas numeradas.

Lo que CHARLIE le entrega a alguien la primera vez, en un solo lugar: cómo está hoy (lo que tiene, lo que debe, cuánto
puede gastar por día), cómo le va cada mes (entra, sale, le queda), en qué se le va la plata, sus deudas, lo que falta
pagar, sus suscripciones, lo que pide atención y las preguntas que hacen falta para que las cifras queden exactas.
Usa las mismas cifras del tablero (tablero._cuentas y tablero._reportes): una sola definición por número.
Devuelve `secciones` (datos), `preguntas` (numeradas), `texto` (Markdown para el chat), `html` y `asunto` (correo).
Solo librería estándar."""
import datetime
import html as _h

import tablero

M3 = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
OBJ = {"saber": "saber en qué se te va la plata", "gastar_menos": "gastar menos", "deudas": "salir de deudas", "ahorrar": "ahorrar para algo"}


def _f(v):
    if v is None: return "—"
    return ("−" if v < 0 else "") + "$" + f"{abs(round(v)):,}".replace(",", ".")


def _d(iso):
    x = datetime.date.fromisoformat(str(iso)[:10])
    return f"{x.day}-{M3[x.month - 1]}"


def _mes(ym):
    return f"{M3[int(ym[5:7]) - 1]}-{ym[:4]}"


def _preguntas(res, hoy):
    """Lo que falta para que las cifras queden exactas, numerado: movimientos grandes sin aclarar, datos que faltan
    (prioridad 1) y pagos que no se ven en las alertas. Máximo 7."""
    movs = {m.get("ID"): m for m in res.get("movimientos") or []}
    dudosos = sorted((movs[i] for i in res.get("por_confirmar") or [] if i in movs), key=lambda m: -abs(m["Valor"]))[:4]
    out = []
    for m in dudosos:
        verbo = "entraron" if m["Valor"] > 0 else "salieron"
        out.append({"tipo": "movimiento", "id": m.get("ID"),
                    "texto": f"El {_d(m['Fecha'])} {verbo} {_f(abs(m['Valor']))} ({str(m.get('Comercio') or m.get('Descripción', ''))[:50]}, {str(m.get('Fuente', '')).replace(' (alerta)', '')}). ¿Qué fue?"})
    for x in [f for f in res.get("faltantes") or [] if f.get("prioridad") == 1][:3]:
        out.append({"tipo": "dato", "id": x.get("id"), "texto": x["que_falta"] + "?" if not x["que_falta"].endswith("?") else x["que_falta"]})
    for c in [c for c in res.get("compromisos") or [] if c.get("estado") == "sin_confirmar"][:2]:
        out.append({"tipo": "compromiso", "id": c["id"], "texto": f"¿Ya pagaste {c['nombre']} ({_d(c['vence'])})? No lo veo en tus alertas."})
    out = out[:7]
    for n, p in enumerate(out, 1):
        p["n"] = n
        if p["tipo"] == "dato" and not p["texto"].startswith("¿"):
            p["texto"] = "¿" + p["texto"]
    return out


def armar(res, hoy=None, objetivo=None):
    hoy = hoy or datetime.date.today()
    r = res.get("resumen") or {}
    movs = [m for m in res.get("movimientos") or [] if m.get("Fecha")]
    cu = tablero._cuentas(res, hoy, movs)
    rp = tablero._reportes(res, hoy, movs)
    an = res.get("analisis") or {}
    deu = res.get("deudas") or {}
    cr = res.get("compromisos_resumen") or {}
    flujo = [f for f in rp["flujo"] if not f["parcial"]]
    prom = lambda k: round(sum(f[k] for f in flujo[-3:]) / len(flujo[-3:])) if flujo else None
    st = an.get("suscripciones_total") or {}
    urg = [a for a in (res.get("avisos") or {}).get("alertas", []) if a.get("severidad") in ("rojo", "naranja")][:5]
    abonar = next((d for d in deu.get("deudas") or [] if d.get("abonar_aqui")), None)
    sec = {
        "hoy": {"plata_en_cuentas": r.get("plata_en_cuentas"), "lo_que_tienes": cu["balance"]["activo"], "lo_que_debes": cu["balance"]["pasivo"],
                "diferencia": cu["balance"]["patrimonio"], "por_dia": r.get("por_dia"), "libre": r.get("libre"), "proximo_sueldo": r.get("proximo_sueldo"),
                "aproximado": bool(r.get("aproximado")), "no_incluye": cu["balance"]["no_incluye"]},
        "cada_mes": {"meses": [f["mes"] for f in flujo[-3:]], "entra": prom("ingresos"), "gastos": prom("gastos"), "cuotas": prom("cuotas_deuda"), "te_queda": prom("te_quedo")},
        "en_que_se_va": {"grupos": rp["grupos"], "categorias": rp["categorias"][:6], "sin_detalle": an.get("sin_detalle")},
        "deudas": {"total": cu["balance"]["pasivo"], "intereses_mes": deu.get("intereses_mes"), "abonar_aqui": abonar.get("nombre") if abonar else None,
                   "lista": [{"nombre": c["nombre"], "saldo": c["saldo"], "tasa_ea": c["tasa_ea"], "interes_mes": c["interes_mes"]} for c in cu["creditos"]]
                            + [{"nombre": t["nombre"], "saldo": t["deuda"], "tasa_ea": t["tasa_ea"], "interes_mes": None} for t in cu["tarjetas"]]},
        "este_mes": {"falta_pagar": cr.get("falta_pagar_este_mes"), "listos": cr.get("listo"), "atencion": cr.get("atencion"), "atrasados": cr.get("atrasados") or []},
        "suscripciones": {"activas": st.get("activas"), "al_mes": st.get("mensual"), "al_ano": st.get("al_ano")},
        "atencion": [{k: a.get(k) for k in ("severidad", "titulo", "accion")} for a in urg],
        "objetivo": objetivo,
    }
    preguntas = _preguntas(res, hoy)

    # Markdown para el chat
    h, m, e, d = sec["hoy"], sec["cada_mes"], sec["en_que_se_va"], sec["deudas"]
    L = ["## Tu resumen financiero", ""]
    L.append(f"**Hoy:** tienes {_f(h['lo_que_tienes'])} y debes {_f(h['lo_que_debes'])}"
             f" (diferencia: {_f(h['diferencia'])}). Puedes gastar **{'≈ ' if h['aproximado'] else ''}{_f(h['por_dia'])} por día**"
             + (f" hasta el sueldo del {_d(h['proximo_sueldo'])}." if h.get("proximo_sueldo") else "."))
    if h["no_incluye"]:
        L.append(f"_No sumé {', '.join(h['no_incluye'])}: no sé su saldo._")
    if m["entra"] is not None:
        L.append(f"**Cada mes** (promedio de {', '.join(_mes(x) for x in m['meses'])}): entran {_f(m['entra'])}, se van {_f(m['gastos'])} en gastos"
                 + (f" y {_f(m['cuotas'])} en cuotas" if m["cuotas"] else "") + f"; te quedan **{_f(m['te_queda'])}**.")
    else:
        L.append("**Cada mes:** aún no tengo un mes completo; lo completo con los días.")
    if e["grupos"]:
        L.append("**En qué se va** (promedio al mes): " + " · ".join(f"{g['grupo']} {_f(g['promedio'] or g['mes_actual'])}" for g in e["grupos"]) + ".")
    if e.get("sin_detalle") and e["sin_detalle"].get("porcentaje", 0) >= 20:
        L.append(f"El {e['sin_detalle']['porcentaje']} % de lo que gastas no tiene detalle (transferencias, efectivo, billeteras): con las preguntas de abajo baja.")
    if d["lista"]:
        L.append(f"**Deudas:** debes {_f(d['total'])}" + (f"; pagas ≈ {_f(d['intereses_mes'])} de intereses al mes" if d.get("intereses_mes") else "")
                 + (f". Si te sobra algo, abónalo a {d['abonar_aqui']} (la de mayor tasa)." if d.get("abonar_aqui") else "."))
    em = sec["este_mes"]
    L.append(f"**Este mes:** {em['listos'] or 0} pagos listos, {em['atencion'] or 0} para mirar; falta pagar {_f(em['falta_pagar'])}.")
    if sec["suscripciones"]["activas"]:
        s_ = sec["suscripciones"]
        L.append(f"**Suscripciones:** {s_['activas']} activas, {_f(s_['al_mes'])} al mes ({_f(s_['al_ano'])} al año).")
    if sec["atencion"]:
        L += ["", "**Para mirar ya:**"] + [f"- {a['titulo']}" for a in sec["atencion"]]
    if preguntas:
        L += ["", "**Preguntas para que tus cifras queden exactas** (respóndeme con el número, por ejemplo «1 fue el arriendo»):"]
        L += [f"{p['n']}. {p['texto']}" for p in preguntas]
    L += ["", "Pregúntame lo que quieras: «¿me alcanza para un viaje de $3 M en marzo?», «¿y si abono $500.000 al mes a la tarjeta?», «¿cuánto ahorro si recorto restaurantes?»."]
    texto = "\n".join(L)

    # HTML para el correo (mismo contenido)
    esc = lambda x: _h.escape(str(x))
    filas = "".join(f"<li>{esc(p['n'])}. {esc(p['texto'])}</li>" for p in preguntas)
    cuerpo = "".join(f"<p style='margin:0 0 10px'>{esc(l).replace('**', '')}</p>" for l in L[2:] if l and not l.startswith(("- ", "**Para mirar", "**Preguntas")) and not l[:2].isdigit() and not l[:1].isdigit())
    html = ("<div style='font-family:-apple-system,Segoe UI,Arial,sans-serif;font-size:15px;line-height:1.5;max-width:640px'>"
            "<h2 style='font-family:Georgia,serif;font-weight:400;margin:0 0 12px'>Tu resumen financiero</h2>" + cuerpo
            + ("<h3 style='margin:14px 0 6px'>Para mirar ya</h3><ul>" + "".join(f"<li>{esc(a['titulo'])}</li>" for a in sec["atencion"]) + "</ul>" if sec["atencion"] else "")
            + ("<h3 style='margin:14px 0 6px'>Preguntas para que tus cifras queden exactas</h3><p style='color:#555'>Responde este correo con el número: «1 fue el arriendo».</p><ul style='list-style:none;padding-left:0'>" + filas + "</ul>" if preguntas else "")
            + "<p style='color:#777;font-size:12px'>CHARLIE · hace cuentas con tus datos; no es asesoría financiera.</p></div>")
    return {"secciones": sec, "preguntas": preguntas, "texto": texto, "html": html, "asunto": f"Tu resumen financiero · CHARLIE · {_d(hoy.isoformat())}"}
