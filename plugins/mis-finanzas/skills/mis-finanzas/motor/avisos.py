"""Avisos: el asesor te escribe solo cuando hay algo nuevo o urgente.

Viene de libro.alertas + avisos.py del sistema original, sin nada de un usuario en el código. Dos pasos:
1. generar(): las alertas de hoy, cada una con severidad (rojo · naranja · amarillo), título, detalle y qué hacer.
   Salen de los compromisos (atrasados, por vencer, el monto no cuadra, pagos deducidos, plata que no llegó), las
   tarjetas (vencida, por vencer, no sé cuánto debes, vence antes del sueldo) y las suscripciones (subió, cobró doble,
   cobró después de cancelar, no cobró).
2. revisar(): decide si hoy sale correo y arma el asunto, el HTML y el texto.
   Ritmo: rojo se repite cada 2 días hasta que se resuelva · naranja cada 3 · amarillo una sola vez. Máximo 2 correos
   al día: el segundo solo si aparece algo NUEVO rojo o naranja, o si llegó plata. La primera vez (memoria vacía) no
   manda nada: todo queda como ya visto, porque el usuario lo acaba de ver en la configuración.

La memoria (qué se avisó, qué plata ya se avisó, cuándo salió cada correo) vive en la pestaña Avisos del Sheet: en la
nube no hay archivos que duren entre corridas. Entra como filas y sale como filas (`memoria_si_envias`), y solo se
escribe si el correo de verdad salió. Solo librería estándar."""
import calendar
import datetime

CADA = {"rojo": 2, "naranja": 3, "amarillo": None}   # días entre repeticiones (None = una sola vez)
ICONO = {"rojo": "🔴", "naranja": "🟠", "amarillo": "🟡"}
ORDEN = {"rojo": 0, "naranja": 1, "amarillo": 2}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
M3 = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
# Plata que llega y NO se avisa: el sueldo (tiene su propio correo), rendimientos y devoluciones de compras.
NO_AVISAR_INGRESO = ("Salario", "Rendimientos", "Devoluciones")
MAX_CORREOS_DIA = 2
ASUNTO = "[Mis finanzas]"


def _f(v):
    return ("−" if v < 0 else "") + "$" + f"{abs(round(v)):,}".replace(",", ".")


def _d(iso):
    x = datetime.date.fromisoformat(str(iso)[:10])
    return f"{x.day}-{M3[x.month - 1]}"


def _mes(periodo):
    return MESES[int(periodo[5:7]) - 1]


def _cuenta(fuente):
    return str(fuente or "").replace(" (alerta)", "")


# ---------------------------------------------------------------- 1. las alertas de hoy

def generar(compromisos, tarjetas=(), suscripciones=(), proximo_sueldo=None, hoy=None):
    """Lista de alertas {id, severidad, de, titulo, detalle, accion}, de la más urgente a la menos."""
    hoy = hoy or datetime.date.today()
    sueldo = datetime.date.fromisoformat(proximo_sueldo) if proximo_sueldo else None
    al = []

    def add(id_, sev, de, titulo, detalle="", accion=""):
        al.append({"id": id_, "severidad": sev, "de": de, "titulo": titulo, "detalle": detalle.strip(), "accion": accion})

    for c in compromisos:
        nom, est = c["nombre"], c["estado"]
        if c.get("marcado_a_mano"):
            continue   # el usuario ya dijo qué pasó: no se le vuelve a recordar
        if c["tipo"] == "tarjeta":
            falta = c.get("falta") or 0
            despues = sueldo and c.get("vence") and sueldo > datetime.date.fromisoformat(c["vence"]) >= hoy
            est_txt = " (estimado con tus compras)" if c.get("estimado") else ""
            if est == "atrasado" and falta > 1000:
                add(f"tarjeta:{nom}:vencida:{c['vence']}", "rojo", "tarjetas", f"{nom} VENCIDA: debes {_f(falta)}{est_txt}",
                    f"La fecha límite era el {_d(c['vence'])}. Cada día suma intereses de mora y puede reportarte.",
                    "Págala hoy, aunque sea el mínimo, y dile a Claude cuánto pagaste.")
            elif est == "vence_pronto" and falta > 1000:
                add(f"tarjeta:{nom}:vence:{c['vence']}", "naranja", "tarjetas", f"{nom}: debes {_f(falta)} antes del {_d(c['vence'])}{est_txt}",
                    (f"El sueldo llega el {_d(sueldo.isoformat())}, DESPUÉS de la fecha límite: si esperas al sueldo pagas mora e intereses." if despues else ""),
                    "Págala antes de la fecha límite, aunque sea con la plata que tienes hoy." if despues else "Págala antes de la fecha límite.")
            elif est == "sin_datos":
                add(f"tarjeta:{nom}:sin_datos:{hoy.isoformat()[:7]}", "amarillo", "tarjetas", f"No sé cuánto debes en {nom}",
                    "No me llega su extracto ni sé su saldo, así que no la estoy contando en lo que puedes gastar.",
                    "Mira el saldo en la app y díselo a Claude; desde ahí lo llevo solo con las alertas.")
            continue
        if c["tipo"] == "suscripcion":
            if est == "no_cobrado":
                add(f"suscripcion:{nom}:no_cobro:{c.get('vence')}", "amarillo", "suscripciones", f"{nom} no cobró cuando tocaba",
                    f"Lo esperaba el {_d(c['vence'])}." if c.get("vence") else "",
                    "Si la cancelaste, perfecto. Si no, revisa que la tarjeta no esté vencida o bloqueada.")
            continue
        per = _mes(c["periodo"]) if c.get("periodo") else ""
        if est == "atrasado":
            viejo = (c.get("dias_atraso") or 0) > 30 or c["tipo"] == "ahorro"
            add(f"compromiso:{c['id']}:atrasado", "amarillo" if viejo else "rojo", "compromisos",
                f"No veo el pago de {nom} de {per}" if viejo else f"{nom} de {per} sin pagar",
                f"Vencía el {_d(c['vence'])} ({c.get('dias_atraso')} días)."
                + (f" Lo normal es ≈ {_f(c['monto_esperado'])}." if c.get("monto_esperado") else ""),
                "Págalo" + (f" ({c['como']})" if c.get("como") else "") + ". Si ya lo pagaste por otro lado o este mes no va, márcalo en Tu marca o díselo a Claude.")
        elif est == "vence_pronto":
            add(f"compromiso:{c['id']}:vence", "naranja", "compromisos", f"{nom}: vence el {_d(c['vence'])}",
                f"≈ {_f(c['monto_esperado'])}." if c.get("monto_esperado") else "", c.get("como") or "")
        elif est == "parcial":
            add(f"compromiso:{c['id']}:parcial", "amarillo", "compromisos", f"{nom} de {per}: el monto no cuadra",
                f"Veo {_f(c.get('pagado') or 0)} y lo normal es ≈ {_f(c.get('monto_esperado') or 0)}.",
                "Dile a Claude si ya quedó pagado o si falta algo.")
        elif est in ("pagado_probable", "recibido_probable") and c.get("evidencia"):
            ev = c["evidencia"][0]
            add(f"compromiso:{c['id']}:probable:{ev.get('id')}", "amarillo", "compromisos",
                f"¿Los {_f(ev['valor'])} del {_d(ev['fecha'])} fueron {nom}?", c.get("deduccion", ""),
                "Si no fue eso, díselo a Claude y lo corrijo; si sí, no tienes que hacer nada.")
        elif est == "sin_confirmar" and not c.get("automatico"):
            add(f"compromiso:{c['id']}:sin_confirmar", "amarillo", "compromisos", f"¿Ya pagaste {nom} de {per}?",
                c.get("nota") or "No lo veo en tus alertas.",
                "Márcalo en Tu marca (o en el tablero), o dile a Claude cómo lo pagas para reconocerlo solo la próxima vez.")
        elif est == "no_ha_llegado":
            add(f"compromiso:{c['id']}:no_llego", "naranja", "compromisos", f"No ha llegado: {nom}",
                f"Lo esperaba el {_d(c['vence'])}" + (f" (≈ {_f(c['monto_esperado'])})." if c.get("monto_esperado") else "."),
                "Revisa si te pagaron por otra cuenta, o recuérdale.")

    # tarjetas que vencen justo antes del sueldo: cada mes quedas pagando tarde o con la plata justa
    if sueldo:
        antes = []
        for t in tarjetas:
            d = t.get("dia_pago")
            if not isinstance(d, int):
                continue
            lim = datetime.date(sueldo.year, sueldo.month, min(d, calendar.monthrange(sueldo.year, sueldo.month)[1]))
            if 0 <= (sueldo - lim).days <= 10:
                dd = (sueldo - lim).days
                antes.append(f"{t['nombre']} vence el {lim.day} " + ("(el mismo día del sueldo)" if dd == 0 else "(un día antes del sueldo)" if dd == 1
                                                                       else f"({dd} días antes del sueldo)"))
        if antes:
            add(f"tarjetas:antes_del_sueldo:{sueldo.isoformat()[:7]}", "amarillo", "tarjetas",
                "Tus tarjetas vencen antes de que llegue el sueldo" if len(antes) > 1 else "Tu tarjeta vence antes de que llegue el sueldo",
                "; ".join(antes) + f". El sueldo llega el {_d(sueldo.isoformat())}: cada mes quedas pagando con la plata justa o tarde.",
                "Pide en el banco mover la fecha de pago a después del sueldo (por ejemplo, el día 5), o aparta el pago desde el sueldo anterior.")

    for s in suscripciones:
        cp = s.get("cambio_precio")
        if cp:
            add(f"suscripcion:{s['nombre']}:subio:{round(cp['a'])}", "amarillo", "suscripciones", f"{s['nombre']} subió: {_f(cp['de'])} → {_f(cp['a'])}",
                f"Desde el cobro del {_d(cp['fecha'])}: {_f(cp['a'] - cp['de'])} más cada vez.",
                "Si no la usas tanto, es buen momento para cancelarla o bajar de plan.")
        for fe in s.get("duplicado") or []:
            add(f"suscripcion:{s['nombre']}:doble:{fe}", "naranja", "suscripciones", f"{s['nombre']} te cobró dos veces",
                f"Dos cobros el {_d(fe)}.", "Pide la devolución del cobro repetido; Claude te ayuda con el mensaje.")
        for fe in s.get("cobro_tras_cancelar") or []:
            add(f"suscripcion:{s['nombre']}:tras_cancelar:{fe}", "naranja", "suscripciones", f"{s['nombre']} cobró después de que la cancelaste",
                f"Cobro del {_d(fe)}.", "Esa plata te la deben devolver: Claude te deja el reclamo listo en borradores.")

    al.sort(key=lambda a: (ORDEN[a["severidad"]], a["de"], a["titulo"]))
    return al


# ---------------------------------------------------------------- plata que llega

def ingresos_recientes(movs, hoy=None, dias=5):
    """Plata que entró en los últimos días: ingresos (clientes, transferencias) y reintegros (un gasto en positivo, como
    la parte del arriendo que te pasa el roomie). Sin el sueldo, rendimientos ni devoluciones de compras."""
    hoy = hoy or datetime.date.today()
    desde = (hoy - datetime.timedelta(days=dias)).isoformat()
    return sorted((m for m in movs if m["Valor"] >= 1000 and desde <= m["Fecha"] <= hoy.isoformat()
                   and not str(m.get("Fuente", "")).startswith("Descuento de nómina")
                   and " TC " not in f" {_cuenta(m.get('Fuente'))} "   # en una tarjeta de crédito no "llega" plata: es una anulación que baja la deuda
                   and ((m.get("Tipo") == "Ingreso" and m.get("Categoría") not in NO_AVISAR_INGRESO) or m.get("Tipo") == "Gasto")),
                  key=lambda m: m["Fecha"])


def _ya_avisado(m, vistos):
    """Por cuenta + valor + fecha (±3 días), no por ID: el ID cambia si el movimiento se vuelve a leer distinto."""
    dia = datetime.date.fromisoformat
    return any(x.get("cuenta") == _cuenta(m.get("Fuente")) and round(float(x.get("valor") or 0)) == round(m["Valor"])
               and abs((dia(str(x["fecha"])[:10]) - dia(m["Fecha"])).days) <= 3 for x in vistos)


# ---------------------------------------------------------------- 2. ¿sale correo hoy?

def _leer_memoria(filas):
    mem = {"alertas": {}, "ingresos": [], "envios": [], "inicio": None}
    for r in filas or []:
        t = r.get("tipo")
        if t == "inicio":   # marca de que ya hubo una primera revisión (aunque no haya alertas)
            mem["inicio"] = str(r.get("fecha") or "")[:10]
        elif t == "alerta" and r.get("id"):
            mem["alertas"][r["id"]] = {"primera": str(r.get("primera") or "")[:10], "ultima": str(r.get("ultima") or "")[:10],
                                       "veces": int(r.get("veces") or 0), "titulo": r.get("titulo") or ""}
        elif t == "ingreso":
            mem["ingresos"].append({"cuenta": r.get("cuenta"), "valor": r.get("valor"), "fecha": str(r.get("fecha") or "")[:10]})
        elif t == "correo":
            mem["envios"].append({"fecha": str(r.get("fecha") or "")[:10], "titulo": r.get("titulo") or ""})
    return mem


def _filas(mem):
    out = [{"tipo": "inicio", "fecha": mem.get("inicio") or datetime.date.today().isoformat()}]
    out += [{"tipo": "alerta", "id": k, "primera": v["primera"], "ultima": v["ultima"], "veces": v["veces"], "titulo": v["titulo"]}
           for k, v in sorted(mem["alertas"].items())]
    out += [{"tipo": "ingreso", "cuenta": x["cuenta"], "valor": x["valor"], "fecha": x["fecha"]} for x in mem["ingresos"]]
    out += [{"tipo": "correo", "fecha": x["fecha"], "titulo": x["titulo"]} for x in mem["envios"]]
    return out


def _toca(a, mem, hoy):
    ya = mem["alertas"].get(a["id"])
    if not ya:
        return True
    cada = CADA[a["severidad"]]
    if cada is None or not ya.get("ultima"):
        return False
    return (hoy - datetime.date.fromisoformat(ya["ultima"])).days >= cada


def _html(al, nuevos, ingresos, comp_resumen, por_dia, proximo_sueldo):
    item = lambda a: (f"<li style='margin-bottom:10px'>{ICONO[a['severidad']]} <b>{a['titulo']}</b>"
                      + (" <span style='background:#e8f0fe;border-radius:4px;padding:0 4px;font-size:12px'>nuevo</span>" if a["id"] in nuevos else "")
                      + (f"<br><span style='color:#444'>{a['detalle']}</span>" if a.get("detalle") else "")
                      + (f"<br>→ {a['accion']}" if a.get("accion") else "") + "</li>")
    urg = [a for a in al if a["severidad"] in ("rojo", "naranja")]
    saber = [a for a in al if a["severidad"] == "amarillo" and a["id"] in nuevos]
    p = ["<div style='font-family:-apple-system,Segoe UI,Arial,sans-serif;font-size:15px;line-height:1.45;max-width:640px'>"]
    if ingresos:
        p.append("<h3 style='margin:8px 0'>💰 Te llegó plata</h3><ul style='padding-left:18px'>"
                 + "".join(f"<li><b>{_f(m['Valor'])}</b> · {m.get('Subcategoría') or m.get('Comercio') or m['Descripción'][:50]} · {_d(m['Fecha'])} · {_cuenta(m.get('Fuente'))}"
                           + ("<br><span style='color:#b35900;font-size:13px'>No sé de quién es: dile a Claude qué fue.</span>"
                              if m.get("Categoría") in ("Otros ingresos", "Transferencias recibidas") else "") + "</li>" for m in ingresos) + "</ul>")
    if urg:
        p.append("<h3 style='margin:8px 0'>Para hacer ya</h3><ul style='padding-left:18px'>" + "".join(map(item, urg)) + "</ul>")
    if saber:
        p.append("<h3 style='margin:8px 0'>Para que sepas</h3><ul style='padding-left:18px'>" + "".join(map(item, saber)) + "</ul>")
    if comp_resumen:
        p.append(f"<p style='font-size:14px'>📋 Este mes: {comp_resumen.get('listo', 0)} pagos listos, {comp_resumen.get('atencion', 0)} piden atención"
                 + (f" y faltan {_f(comp_resumen['falta_pagar_este_mes'])} por pagar" if comp_resumen.get("falta_pagar_este_mes") else "")
                 + ". La lista completa está en la pestaña Compromisos de tu Sheet.</p>")
    if por_dia is not None and proximo_sueldo:
        p.append(f"<p style='color:#555;font-size:13px'>Así vas: puedes gastar <b>{_f(por_dia)} por día</b> hasta el sueldo ({_d(proximo_sueldo)}).</p>")
    p.append("<p style='color:#777;font-size:12px'>Este correo solo llega cuando hay algo nuevo o urgente. Para marcar algo como resuelto "
             "(\"ya pagué el arriendo\", \"este mes no hay gimnasio\") díselo a Claude o escríbelo en Tu marca: no te lo vuelvo a recordar.</p></div>")
    return "".join(p)


def _texto(al, nuevos, ingresos):
    L = []
    if ingresos:
        L += ["Te llegó plata:"] + [f"- {_f(m['Valor'])} · {m.get('Subcategoría') or m['Descripción'][:50]} · {_d(m['Fecha'])}" for m in ingresos] + [""]
    for a in al:
        if a["severidad"] in ("rojo", "naranja") or a["id"] in nuevos:
            L.append(f"{ICONO[a['severidad']]} {a['titulo']}" + (" (nuevo)" if a["id"] in nuevos else ""))
            if a.get("detalle"): L.append("   " + a["detalle"])
            if a.get("accion"): L.append("   → " + a["accion"])
    return "\n".join(L)


def revisar(alertas, movs, memoria_filas=None, hoy=None, comp_resumen=None, por_dia=None, proximo_sueldo=None):
    """¿Sale correo de avisos hoy? Devuelve enviar, motivo, asunto, html, texto, las alertas que lleva y la memoria
    para escribir en la pestaña Avisos SOLO si el correo salió (memoria_si_envias). Si no sale, la memoria no cambia,
    salvo la primera vez: ahí todo queda como visto (memoria_si_no_envias)."""
    hoy = hoy or datetime.date.today()
    mem = _leer_memoria(memoria_filas)
    hoy_s = hoy.isoformat()
    ingresos = [m for m in ingresos_recientes(movs, hoy) if not _ya_avisado(m, mem["ingresos"])]
    base = {"enviar": False, "alertas": alertas, "ingresos": [{k: m.get(k) for k in ("Fecha", "Valor", "Descripción", "Fuente", "Categoría", "ID")} for m in ingresos]}

    if not mem["inicio"]:   # primera vez: el usuario lo acaba de ver en la configuración; desde aquí, solo lo nuevo
        mem["inicio"] = hoy_s
        for a in alertas:
            mem["alertas"][a["id"]] = {"primera": hoy_s, "ultima": hoy_s, "veces": 0, "titulo": a["titulo"]}
        mem["ingresos"] += [{"cuenta": _cuenta(m.get("Fuente")), "valor": round(m["Valor"]), "fecha": m["Fecha"]} for m in ingresos]
        return {**base, "ingresos": [], "motivo": "primera vez: todo queda como visto", "memoria_si_no_envias": _filas(mem)}

    correos_hoy = sum(1 for x in mem["envios"] if x["fecha"] == hoy_s)
    disparan = [a for a in alertas if _toca(a, mem, hoy)]
    if correos_hoy:   # ya hubo correo hoy: otro solo con algo NUEVO
        disparan = [a for a in disparan if a["id"] not in mem["alertas"]]
    nuevos = {a["id"] for a in alertas if a["id"] not in mem["alertas"]}
    if not disparan and not ingresos:
        return {**base, "motivo": "nada nuevo ni urgente"}
    if correos_hoy >= MAX_CORREOS_DIA:
        return {**base, "motivo": f"ya salieron {correos_hoy} correos hoy; lo nuevo sale en la siguiente revisión"}
    if correos_hoy and not ingresos and not any(a["severidad"] in ("rojo", "naranja") and a["id"] in nuevos for a in disparan):
        return {**base, "motivo": "ya salió un correo hoy y lo nuevo no es urgente: va mañana"}

    top = sorted(disparan, key=lambda a: ORDEN[a["severidad"]])[:1 if ingresos else 2]
    plata = []
    if ingresos:
        tot = sum(m["Valor"] for m in ingresos)
        plata = [f"💰 Te llegaron {_f(tot)}" + (f" ({ingresos[0].get('Subcategoría')})" if len(ingresos) == 1 and ingresos[0].get("Subcategoría") else "")]
    asunto = (" · ".join(plata + [f"{ICONO[a['severidad']]} {a['titulo']}" for a in top])[:140] + " " + ASUNTO).strip()

    # memoria si el correo sale: se marcan las que dispararon y todas las urgentes nuevas
    for a in alertas:
        if a in disparan or (a["severidad"] in ("rojo", "naranja") and a["id"] in nuevos):
            r = mem["alertas"].get(a["id"], {"primera": hoy_s, "veces": 0})
            r.update({"ultima": hoy_s, "veces": r.get("veces", 0) + 1, "titulo": a["titulo"]})
            mem["alertas"][a["id"]] = r
    activos = {a["id"] for a in alertas}   # lo resuelto sale de la memoria (si vuelve a pasar, se avisa de nuevo)
    hace60 = (hoy - datetime.timedelta(days=60)).isoformat()
    mem["alertas"] = {k: v for k, v in mem["alertas"].items() if k in activos or v.get("ultima", "") >= hace60}
    hace90 = (hoy - datetime.timedelta(days=90)).isoformat()
    mem["ingresos"] = [x for x in mem["ingresos"] if x["fecha"] >= hace90] + \
                      [{"cuenta": _cuenta(m.get("Fuente")), "valor": round(m["Valor"]), "fecha": m["Fecha"]} for m in ingresos]
    hace7 = (hoy - datetime.timedelta(days=7)).isoformat()
    mem["envios"] = [x for x in mem["envios"] if x["fecha"] >= hace7] + [{"fecha": hoy_s, "titulo": asunto}]
    return {**base, "enviar": True, "motivo": f"{len(disparan)} alertas, {len(ingresos)} ingresos", "asunto": asunto,
            "html": _html(alertas, nuevos, ingresos, comp_resumen, por_dia, proximo_sueldo), "texto": _texto(alertas, nuevos, ingresos),
            "lleva": [a["id"] for a in disparan], "memoria_si_envias": _filas(mem)}


def marcar_incluidas(ids, memoria_filas, titulo, hoy=None):
    """Tu semana o Tu mes ya llevaron estas alertas: quedan como avisadas hoy y cuenta como un correo del día."""
    hoy = hoy or datetime.date.today()
    mem = _leer_memoria(memoria_filas)
    for i in ids:
        r = mem["alertas"].get(i, {"primera": hoy.isoformat(), "veces": 0, "titulo": ""})
        r.update({"ultima": hoy.isoformat(), "veces": r.get("veces", 0) + 1})
        mem["alertas"][i] = r
    mem["envios"].append({"fecha": hoy.isoformat(), "titulo": titulo})
    return _filas(mem)
