"""Deudas, recordatorios de Calendar e informe semanal de la skill: lo mismo que deudas.py, calendario.py e informe_semanal.py
de la versión instalada, pero sin Google. El motor arma los eventos y el texto; Claude los crea y lo manda con sus conectores."""
import datetime, re, unicodedata
import deudas as D

ANTES = [3 * 1440 - 540, 1440 - 540]   # como calendario.py: 3 días y 1 día antes, a las 9:00 a. m. (eventos de todo el día)
TASA_TARJETA = 0.285                    # como deudas.py: tasa típica de tarjeta si el usuario no sabe la suya
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def f(v):
    return ("-" if v < 0 else "") + "$" + f"{abs(round(v)):,}".replace(",", ".")


def d(x):
    x = x if isinstance(x, datetime.date) else datetime.date.fromisoformat(str(x)[:10])
    return f"{x.day}-{MESES[x.month - 1]}"


def tasa(x):
    """18,99 o 0,1899 -> 0.1899."""
    x = float(str(x or 0).replace("%", "").replace(",", "."))
    return x / 100 if x > 1 else x


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def credito(c):
    """Fila de la pestaña Créditos -> crédito con tasa y cuota en números."""
    return {"nombre": c["nombre"], "entidad": c.get("entidad", ""), "saldo": float(c.get("saldo") or 0), "fecha_saldo": c.get("fecha_saldo"),
            "tasa_ea": tasa(c.get("tasa_ea")), "cuota": float(c.get("cuota") or 0), "dia_pago": c.get("dia_pago"),
            "descuento_nomina": bool(c.get("descuento_nomina")), "buscar": c.get("buscar", "")}


def lista_deudas(creditos, tarjetas):
    """Todas las deudas de mayor a menor tasa, intereses al mes, cuándo terminan y dónde abonar (el crédito más caro)."""
    out = []
    for c in creditos:
        if c["saldo"] <= 0: continue
        n = D._meses(c["saldo"], c["tasa_ea"], c["cuota"])
        out.append({"nombre": c["nombre"], "tipo": "crédito", "saldo": round(c["saldo"]), "fecha_saldo": c["fecha_saldo"], "tasa_ea": c["tasa_ea"],
                    "interes_mes": round(c["saldo"] * D.mv(c["tasa_ea"])), "cuota": round(c["cuota"]), "meses": n, "nomina": c["descuento_nomina"]})
    for t in tarjetas:
        if t.get("deuda") is None: continue
        out.append({"nombre": t["nombre"], "tipo": "tarjeta", "saldo": t["deuda"], "tasa_ea": t.get("tasa_ea") or TASA_TARJETA,
                    "tasa_supuesta": not t.get("tasa_ea"), "interes_mes": None, "cuota": None, "meses": None, "vence": t.get("vence")})
    out.sort(key=lambda x: -x["tasa_ea"])
    cr = [x for x in out if x["tipo"] == "crédito"]
    if cr: cr[0]["abonar_aqui"] = True   # las tarjetas se pagan completas, no se "abonan"
    r = D.resumen(out)
    return {"deudas": out, "total_creditos": round(r["total"]), "intereses_mes": round(r["interes_mes"]), "consejo": r["consejo"]}


def _siguiente(dia, hoy, agente):
    for k in range(3):
        y, m = hoy.year + (hoy.month - 1 + k) // 12, (hoy.month - 1 + k) % 12 + 1
        fe = agente.fecha_pago({"dia": dia}, y, m)
        if fe >= hoy: return fe


def _evento(id_, titulo, dia, hoy, agente, descripcion, avisos=True):
    rrule = ("RRULE:FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-2" if dia == "penultimo_habil"
             else f"RRULE:FREQ=MONTHLY;BYMONTHDAY={int(dia)}")
    return {"id": "mis-finanzas:" + id_, "titulo": titulo, "primera_fecha": _siguiente(dia, hoy, agente).isoformat(), "todo_el_dia": True,
            "recurrencia": rrule, "avisos_minutos_antes": ANTES if avisos else [],
            "avisos": "3 días y 1 día antes, a las 9:00 a. m., por notificación y correo" if avisos else "sin aviso",
            "descripcion": (descripcion + "\n\n" if descripcion else "") + "Creado por Mis finanzas · mis-finanzas:" + id_}


def eventos_calendario(pagos, tarjetas, hoy, agente):
    """Un evento mensual por pago fijo, cuota, tarjeta y sueldo (el del sueldo trae la lista de lo que hay que pagar)."""
    activos = [p for p in pagos if not p.get("solo_mes")]
    pagar = [p for p in activos if not p.get("automatico") and p["tipo"] not in ("ingreso", "cobro")]
    lin = [f"• {'El día del sueldo' if p['dia'] == 'penultimo_habil' else 'Día ' + str(p['dia'])}: {p['nombre']}"
           + (f" — {f(p['monto'])}" if p.get("monto") else "") for p in pagar]
    lin += [f"• Día {t['dia_pago']}: {t['nombre']} — lo que diga el extracto" for t in tarjetas if t.get("dia_pago")]
    lista = ("Hoy te pagaron. Este mes tienes que pagar:\n" + "\n".join(lin) + f"\n\nTotal ≈ {f(sum(p.get('monto') or 0 for p in pagar))} + tarjetas."
             if lin else "Hoy te pagaron.")
    ev = []
    for p in activos:
        nombre = p["nombre"].lstrip("💰🏦💳🔁 ")
        monto = f" — {f(p['monto'])}" if p.get("monto") else ""
        if p["tipo"] == "ingreso":
            ev.append(_evento("sueldo", f"💰 {nombre}{monto}", p["dia"], hoy, agente, lista, avisos=False))
        elif p["tipo"] == "cobro":
            ev.append(_evento("cobro-" + slug(nombre), f"💵 {nombre}{monto}", p["dia"], hoy, agente, p.get("como", ""), avisos=False))
        elif p.get("automatico"):
            ev.append(_evento("pago-" + slug(nombre), f"🔁 {nombre}{monto} (sale solo)", p["dia"], hoy, agente, p.get("como", ""), avisos=False))
        else:
            ev.append(_evento("pago-" + slug(nombre), f"💳 Vence: {nombre}{monto}", p["dia"], hoy, agente, p.get("como", "")))
    for t in tarjetas:
        if t.get("dia_pago"):
            ev.append(_evento("tarjeta-" + slug(t.get("terminacion") or t["nombre"]), f"💳 Vence: {t['nombre']}", int(t["dia_pago"]), hoy, agente,
                              "Paga el total que diga el extracto o la app: si difieres a cuotas pagas intereses."))
    return ev


SIN_DETALLE = ("Transferencias a terceros", "Gastos vía billetera (sin detalle)", "Otros", "Efectivo")


def destino(desc):
    """A quién se mandó una transferencia según la alerta: llave, cuenta o nombre (None si la alerta no lo dice)."""
    for pat in (r"\ba (?:la )?llave\s+(@?[\w.@-]{4,})", r"\ba (?:la )?(?:cuenta|cta\.?)\s*\*?(\d{4,})", r"\bllave\s+(@?[\w.@-]{4,})",
                r"\ba ([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ.]+(?: [A-ZÁÉÍÓÚÑ.]+){1,4})\b"):
        m = re.search(pat, desc)
        if m: return m.group(1).strip()
    return None


def analisis(todos, agente):
    """En qué se va la plata en las filas que le pasen: por mes, por categoría y mes, comercios, ingresos por fuente,
    gastos más grandes, cuánto queda sin detalle, suscripciones activas y cobros que se repiten."""
    por_mes, cat, com, ing = {}, {}, {}, {}
    for r in todos:
        x = por_mes.setdefault(r["Mes"], {"ingresos": 0, "gastos": 0, "cuotas_deuda": 0, "movimientos": 0})
        x["movimientos"] += 1
        if r["Tipo"] == "Ingreso":
            x["ingresos"] += r["Valor"]
            k = r.get("Subcategoría") or r["Categoría"]
            ing[k] = ing.get(k, 0) + r["Valor"]
        elif r["Tipo"] == "Gasto":
            x["gastos"] -= r["Valor"]
            cat.setdefault(r["Categoría"], {})
            cat[r["Categoría"]][r["Mes"]] = cat[r["Categoría"]].get(r["Mes"], 0) - r["Valor"]
            if r["Categoría"] not in SIN_DETALLE:
                k = re.sub(r"[^A-Z0-9ÁÉÍÓÚÑ]+", " ", (r.get("Comercio") or r["Descripción"]).upper())[:40].strip()   # UBER*RIDES = UBER RIDES
                c = com.setdefault(k, {"comercio": k, "total": 0, "veces": 0, "categoria": r["Categoría"]})
                c["total"] -= r["Valor"]
                c["veces"] += 1
        elif r["Tipo"] == "Deuda":
            x["cuotas_deuda"] -= r["Valor"]
    for x in por_mes.values():
        x.update({k: round(x[k]) for k in ("ingresos", "gastos", "cuotas_deuda")})
        x["te_quedo"] = x["ingresos"] - x["gastos"] - x["cuotas_deuda"]
    gasto = sum(-r["Valor"] for r in todos if r["Tipo"] == "Gasto")
    sin = sum(-r["Valor"] for r in todos if r["Tipo"] == "Gasto" and r["Categoría"] in SIN_DETALLE)
    return {
        "por_mes": dict(sorted(por_mes.items())),
        "gasto_por_categoria_y_mes": {k: {m: round(v) for m, v in sorted(ms.items())}
                                      for k, ms in sorted(cat.items(), key=lambda i: -sum(i[1].values()))},
        "comercios": [dict(c, total=round(c["total"])) for c in sorted(com.values(), key=lambda c: -c["total"])[:15]],
        "ingresos_por_fuente": {k: round(v) for k, v in sorted(ing.items(), key=lambda i: -i[1])},
        "gastos_mas_grandes": [{"fecha": r["Fecha"], "descripcion": r["Descripción"][:60], "categoria": r["Categoría"], "valor": round(-r["Valor"])}
                               for r in sorted((r for r in todos if r["Tipo"] == "Gasto"), key=lambda r: r["Valor"])[:10]],
        "sin_detalle": {"valor": round(sin), "porcentaje": round(100 * sin / gasto) if gasto else 0},
        # el último cobro, no el promedio de 6 meses de agente.suscripciones: aquí puede haber solo uno o dos meses de filas
        "suscripciones": [{"nombre": s["nombre"], "mensual": s["ultimo_monto"], "ultimo": s["ultimo"]} for s in agente.suscripciones(todos) if s["activa"]],
        "recurrentes": agente.recurrentes_nuevos(todos),
    }


def descubrimientos(todos, nuevos, cfg, vistos, an, hoy):
    """Lo que el motor descubrió y vale la pena anotar en la pestaña Notas (cada uno con un id para no repetirlo)."""
    out = []

    def add(id_, texto, pregunta=""):
        out.append({"id": id_, "texto": texto, "pregunta": pregunta})

    conocidos = {(str(c.get("institucion", "")).lower(), str(t)) for c in cfg.get("cuentas", [])
                 for t in (c.get("terminacion"), c.get("tarjeta_debito"), c.get("celular")) if t}
    for p in vistos:
        if (p["institucion"].lower(), p["terminacion"]) not in conocidos:
            add(f"producto:{slug(p['institucion'])}-{p['terminacion']}",
                f"En tus alertas aparece {p['institucion']} *{p['terminacion']} ({p['pista']}, {p['movimientos']} movimientos) y no está en tus cuentas.",
                "¿Es tuya? ¿Qué producto es?")
    neto = (cfg.get("sueldo") or {}).get("neto_que_llega") or 0
    for r in nuevos:
        if r["Tipo"] == "Ingreso" and r["Categoría"] == "Salario" and neto and abs(r["Valor"] - neto) > 0.02 * neto:
            add(f"sueldo:{r['Fecha']}", f"El sueldo del {d(r['Fecha'])} llegó por {f(r['Valor'])}, distinto de los {f(neto)} que tengo anotados ({f(r['Valor'] - neto)}).",
                "¿Lo actualizo? ¿Sabes por qué cambió?")
    for x in an["recurrentes"]:
        add(f"recurrente:{slug(x['comercio'])}", f"Cobro que se repite: {x['comercio']} ≈ {f(x['monto'])} en {x['meses']} meses distintos ({x['categoria']}).",
            "¿Es un pago fijo o una suscripción? ¿La sigues usando?")
    for s in an["suscripciones"]:
        add(f"suscripcion:{slug(s['nombre'])}", f"Suscripción activa: {s['nombre']} ≈ {f(s['mensual'])}/mes (último cobro el {d(s['ultimo'])}).")
    desde = (hoy - datetime.timedelta(days=90)).isoformat()
    grupos = {}
    for r in todos:
        if r["Fecha"] >= desde and r["Tipo"] == "Gasto" and r["Categoría"] in SIN_DETALLE[:3]:
            k = destino(r["Descripción"])
            if k: grupos.setdefault(k, []).append(r)
    for k, rs in sorted(grupos.items(), key=lambda i: sum(r["Valor"] for r in i[1])):
        if len(rs) >= 2:
            add(f"destino:{slug(k)}", f"Le has mandado plata {len(rs)} veces a {k} desde el {d(min(r['Fecha'] for r in rs))}: {f(-sum(r['Valor'] for r in rs))} en total.",
                "¿Quién es y qué le pagas?")
    return out


def faltantes(filas, tarjetas, creditos, cfg, hoy):
    """Lo que el motor necesita saber y no sabe, de lo más importante (1) a lo opcional (3)."""
    import cuentas
    out = []

    def add(id_, que, prioridad):
        out.append({"id": id_, "que_falta": que, "prioridad": prioridad})

    def dias(fe):
        return (hoy - datetime.date.fromisoformat(str(fe)[:10])).days

    for x in filas:
        if x["tipo"] == "bolsillo": continue
        liquida = x["tipo"] in cuentas.LIQUIDOS
        if not x["desde"]:
            add("saldo:" + slug(x["nombre"]), f"Cuánto tienes hoy en {x['nombre']}", 1 if liquida else 2)
        elif x["saldo"] is None:
            add("saldo:" + slug(x["nombre"]), f"El saldo de hoy de {x['nombre']} (no manda alertas; el último es del {d(x['desde'])})", 1)
        elif dias(x["desde"]) > 35:
            add("saldo:" + slug(x["nombre"]), f"El saldo de hoy de {x['nombre']} (el último que me diste es del {d(x['desde'])})", 2)
    for t in tarjetas:
        if t["deuda"] is None: add("deuda:" + slug(t["nombre"]), f"Cuánto debes hoy en {t['nombre']}", 1)
        if not t.get("dia_pago"): add("dia:" + slug(t["nombre"]), f"El día límite de pago de {t['nombre']}", 1)
        if not t.get("tasa_ea"): add("tasa:" + slug(t["nombre"]), f"La tasa E.A. de {t['nombre']} (estoy suponiendo 28,5%)", 3)
    for c in creditos:
        if not c["tasa_ea"]: add("tasa:" + slug(c["nombre"]), f"La tasa E.A. de {c['nombre']}", 2)
        if not c["cuota"] or not c["dia_pago"]: add("cuota:" + slug(c["nombre"]), f"La cuota y el día de pago de {c['nombre']}", 1)
        if not c["fecha_saldo"] or dias(c["fecha_saldo"]) > 90:
            add("saldo:" + slug(c["nombre"]), f"El saldo de hoy de {c['nombre']}" + (f" (el último es del {d(c['fecha_saldo'])})" if c["fecha_saldo"] else ""), 2)
    s = cfg.get("sueldo") or {}
    if not s.get("dia_pago") or not s.get("neto_que_llega"): add("sueldo", "Qué día te llega el sueldo y cuánto te llega a la cuenta", 1)
    if not [n for n in cfg.get("nombre_en_bancos", []) if n]: add("nombre", "Cómo aparece tu nombre cuando te transfieres entre tus cuentas", 2)
    if not cfg.get("techo_gasto_mes"): add("techo", "Cuánto quieres gastar al mes en el día a día (opcional, para avisarte si te pasas)", 3)
    return sorted(out, key=lambda x: x["prioridad"])


def informe(est, res, deu, proximos, dudosos, hoy):
    """Texto del informe del lunes, con las mismas secciones de informe_semanal.py."""
    r, c = res["resumen"], est["caja"]
    pp, up = est["proximo_pago"], est["ultimo_pago"]
    falta = r["falta_pagar_antes_del_sueldo"]
    L = [f"Tu semana financiera — {d(hoy)} {hoy.year}",
         f"Datos hasta el {d(r['alertas_hasta']) if r['alertas_hasta'] else '—'} · sueldo el {d(pp)} "
         f"(en {est['dias_al_pago']} día{'' if est['dias_al_pago'] == 1 else 's'})", "",
         f"PUEDES GASTAR {f(r['por_dia'])} POR DÍA hasta el sueldo",
         f"{f(r['libre'])} libres = {f(r['disponible'])} disponibles en tus cuentas − {f(sum(p['monto'] for p in falta))} de pagos antes del sueldo."]
    if r["apartado"]: L.append(f"Apartado (no se cuenta para gastar): {f(r['apartado'])}.")
    if r["inversiones"]: L.append(f"Inversiones y CDTs: {f(r['inversiones'])} (no se cuentan para gastar).")
    if r["cuentas_sin_saldo"]: L.append(f"No sé cuánto hay en: {', '.join(r['cuentas_sin_saldo'])}. Respóndeme con el saldo de hoy.")
    L += ["", "ANTES DEL SUELDO TIENES QUE PAGAR"]
    L += [f"• {d(p['fecha'])}{' ⚠️ vencido' if p['fecha'] < hoy.isoformat() else ''}  {p['nombre']}  {f(p['monto'])}" for p in falta] or ["Nada pendiente 🎉"]
    techo_s, techo_c = est["techo_semana"], est["techo_ciclo"]
    L += ["", "ESTA SEMANA", f"Gasto del día a día: {f(est['gasto_semana'])}"
          + (f" — techo semanal {f(techo_s)} " + ("✅" if est["gasto_semana"] <= techo_s else f"❌ te pasaste por {f(est['gasto_semana'] - techo_s)}") if techo_s > 0 else "")]
    L += [f"• {d(m['Fecha'])}  {(m.get('Comercio') or m['Descripción'])[:40]} ({m['Categoría']})  {f(-m['Valor'])}" for m in est["top_semana"]]
    ing = est["ingresos_semana"]
    L += (["Ingresos:"] + [f"• {d(m['Fecha'])}  {m.get('Subcategoría') or m['Categoría']}  {f(m['Valor'])}" for m in ing]) if ing else ["Sin ingresos esta semana."]
    L += ["", f"DESDE EL ÚLTIMO SUELDO ({d(up)})", f"Gasto del día a día: {f(est['gasto_ciclo'])}" + (f" de un techo de {f(techo_c)}" if techo_c > 0 else "")]
    L += [f"• {k}: {f(v)}" for k, v in est["categorias_ciclo"][:6]]
    L += ["", "PRÓXIMOS PAGOS"]
    L += [f"• {d(p['fecha'])}  {'💰' if p.get('tipo') == 'ingreso' else '✅' if p['pagado'] else '🔁' if p.get('automatico') else '⏳'} {p['nombre']}"
          f"  {f(p['monto']) if p.get('monto') else 'ver extracto'}"
          for p in proximos] or ["Ninguno en las próximas semanas."]
    if deu["deudas"]:
        L += ["", "DEUDAS (de mayor a menor tasa)"]
        for x in deu["deudas"]:
            t = f"{x['tasa_ea']:.2%}".replace(".", ",") + (" (supuesta)" if x.get("tasa_supuesta") else "")
            if x["tipo"] == "crédito":
                L.append(f"• {'👉 ' if x.get('abonar_aqui') else ''}{x['nombre']}  {f(x['saldo'])}  {t} E.A.  intereses ≈ {f(x['interes_mes'])}/mes"
                         + (f"  termina en {x['meses']} meses" if x["meses"] else ""))
            else:
                L.append(f"• 💳 {x['nombre']}  debes {f(x['saldo'])}" + (f", vence el {d(x['vence'])}" if x.get("vence") else "") + f"  ({t} E.A. si difieres)")
        if deu["intereses_mes"]: L.append(f"Tus créditos te cuestan ≈ {f(deu['intereses_mes'])} al mes en intereses. {deu['consejo']}")
    if dudosos:
        L += ["", "¿QUÉ FUE ESTO? (respóndeme y lo clasifico)"]
        L += [f"• {d(m['Fecha'])}  {m['Descripción'][:50]}  {f(m['Valor'])}" for m in dudosos[:8]]
    nuevos_d = [x for x in res.get("descubrimientos", []) if x.get("nuevo")]
    if nuevos_d:
        L += ["", "LO QUE DESCUBRÍ"]
        L += [f"• {x['texto']}" + (f" {x['pregunta']}" if x["pregunta"] else "") for x in nuevos_d[:6]]
    falt = [x for x in res.get("faltantes", []) if x["prioridad"] <= 2]
    if falt:
        L += ["", "ME FALTA SABER (respóndeme y lo anoto)"]
        L += [f"• {x['que_falta']}" for x in falt[:5]]
    asunto = f"💸 Puedes gastar {f(r['por_dia'])}/día hasta el {d(pp)} · informe semanal"
    return {"asunto": asunto, "texto": "\n".join(L)}
