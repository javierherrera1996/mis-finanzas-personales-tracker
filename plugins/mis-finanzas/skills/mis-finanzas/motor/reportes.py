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
                    "tasa_supuesta": not t.get("tasa_ea"), "interes_mes": None, "cuota": None, "meses": None, "vence": t.get("vence"),
                    "corte": t.get("corte")})
    out.sort(key=lambda x: -x["tasa_ea"])
    cr = [x for x in out if x["tipo"] == "crédito"]
    if cr: cr[0]["abonar_aqui"] = True   # las tarjetas se pagan completas, no se "abonan"
    r = D.resumen(out)
    return {"deudas": out, "total_creditos": round(r["total"]), "intereses_mes": round(r["interes_mes"]), "consejo": r["consejo"]}


def _cuota(saldo, ea, n):
    """Cuota fija que paga `saldo` en `n` meses a la tasa `ea`."""
    i = D.mv(ea)
    return saldo / n if i == 0 else saldo * i / (1 - (1 + i) ** -n)


def comparar_ofertas(creditos, tarjetas, ofertas, tasa_usura=None):
    """Cuánto ahorraría con cada oferta que Claude encontró en internet (compra de cartera, libranza, libre inversión):
    con la misma cuota (termina antes) y con el mismo plazo (paga menos cada mes), menos los costos que diga la oferta.
    También marca las deudas por encima de la tasa de usura. Claude busca; el motor hace las cuentas."""
    deudas = {c["nombre"].lower(): c for c in creditos}
    deudas.update({t["nombre"].lower(): {"nombre": t["nombre"], "saldo": t.get("deuda") or 0, "tasa_ea": t.get("tasa_ea") or TASA_TARJETA,
                                         "cuota": 0} for t in tarjetas})
    out = []
    for o in ofertas:
        c = deudas.get(str(o.get("credito", "")).lower())
        if not c or not c["saldo"]: continue
        nueva, costos = tasa(o.get("tasa_ea")), float(o.get("costos") or 0)
        x = {"credito": c["nombre"], "entidad": o.get("entidad", ""), "tasa_actual": c["tasa_ea"], "tasa_oferta": nueva,
             "condiciones": o.get("condiciones", ""), "fuente": o.get("fuente", ""), "fecha": o.get("fecha", ""),
             "ahorro_intereses_mes": round(c["saldo"] * (D.mv(c["tasa_ea"]) - D.mv(nueva)))}
        n = D._meses(c["saldo"], c["tasa_ea"], c["cuota"]) if c["cuota"] else None
        n2 = D._meses(c["saldo"], nueva, c["cuota"]) if n else None
        if n and not n2:   # con esa tasa la cuota ni alcanza para los intereses: es más cara
            x["ahorro_total_misma_cuota"] = None
        elif n:
            x.update(meses_que_faltan=n, meses_con_la_oferta=n2,
                     ahorro_total_misma_cuota=round(c["cuota"] * (n - n2) - costos),
                     cuota_mismo_plazo=round(_cuota(c["saldo"], nueva, n)),
                     ahorro_cuota_mismo_plazo=round(c["cuota"] - _cuota(c["saldo"], nueva, n)))
        else:   # tarjeta o crédito sin cuota: lo que dejaría de pagar en intereses en un año
            x["ahorro_total_un_ano"] = round(x["ahorro_intereses_mes"] * 12 - costos)
        x["vale_la_pena"] = nueva <= c["tasa_ea"] - 0.01 and (x.get("ahorro_total_misma_cuota") or x.get("ahorro_total_un_ano") or 0) > 0
        out.append(x)
    usura = tasa(tasa_usura) if tasa_usura else None
    sobre_usura = [{"credito": c["nombre"], "tasa": c["tasa_ea"], "usura": usura} for c in deudas.values()
                   if usura and c["tasa_ea"] > usura and c["saldo"]]
    return {"ofertas": sorted(out, key=lambda x: -x["ahorro_intereses_mes"]), "sobre_usura": sobre_usura}


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
        if t.get("dia_corte"):
            ev.append(_evento("corte-" + slug(t.get("terminacion") or t["nombre"]), f"✂️ Corte: {t['nombre']}", t["dia_corte"], hoy, agente,
                              "Lo que compres desde mañana se paga en el extracto siguiente: si vas a hacer una compra grande, mejor después del corte.",
                              avisos=False))
        if t.get("dia_pago"):
            ev.append(_evento("tarjeta-" + slug(t.get("terminacion") or t["nombre"]), f"💳 Vence: {t['nombre']}", t["dia_pago"], hoy, agente,
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


PASARELAS = {"BOLD", "SA", "MERPAGO", "MERCADOPAGO", "MERCADO", "PAGO", "PAYU", "WOMPI", "EPAYCO", "DLO", "PSE", "P", "A", "COMPRA", "EN",
             "ESTABLECIMIENTO", "DESCUENTO", "INTERNET", "DE", "LA", "EL", "POR", "CON", "CORRECCION"}


def _palabras(texto, n):
    t = [w for w in re.sub(r"[^A-Z0-9ÁÉÍÓÚÑ]+", " ", texto.upper()).split() if w not in PASARELAS and w not in ("DEL", "LOS", "LAS")]
    return " ".join(t[:n]) or None


def _clave(r, palabras=2):
    """Con quién es un movimiento, para ver si se repite: la cuenta o llave de destino, o las primeras palabras del comercio o
    del nombre sin la pasarela (BOLD SA*KONA TRA -> KONA TRA). Así el mismo arriendo pagado desde dos bancos queda junto.
    None si la alerta no dice con quién ("Transferencia a una llave")."""
    d = r["Descripción"]
    k = destino(d)
    if k: return k.upper() if re.match(r"@?\d", k) else _palabras(k, palabras)
    m = re.search(r"(?:Compraste|Pagaste)\s+(?:COP|\$)\s?[\d.,]+\s+(?:en|a)\s+(.+?)(?:,|\s+el\s+\d|\s+desde|\s+con\s)", d, re.I)
    if m: return _palabras(m.group(1), palabras)   # alertas de Bancolombia: el comercio va después de "en"
    m = re.search(r"Recibiste .*?\bde ([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ .]{3,40}?)(?:\s+en\s|\s+a\s+tu|\.|,|$)", d)
    if m: return _palabras(m.group(1), palabras)   # plata que entra: quién la manda
    k = _palabras(r.get("Comercio") or d, palabras)
    # sin destino, "Transferencia a una llave" o un retiro no dicen con quién; un PSE a un comercio sí, aunque esté en "Otros"
    if r["Categoría"] in SIN_DETALLE and (not k or re.search(r"TRANSFERENCIA|LLAVE|RETIRO|CAJERO|\bAPP\b|\bQR\b|AVANCE|^\d", k)): return None
    return k


def patrones(todos, pagos):
    """Lo que se repite, con al menos 2 meses de movimientos: pagos de cada mes (con su día típico, para Fijos), hábitos
    (comercios de muchas veces al mes: Uber, Rappi…) e ingresos de cada mes. Dice si ya está en Fijos o Créditos."""
    pats = [p["buscar"] for p in pagos if p.get("buscar")]
    gr, hab = {}, {}
    for r in todos:
        if r["Tipo"] not in ("Gasto", "Deuda", "Ingreso"): continue
        k = _clave(r)
        if k: gr.setdefault((r["Tipo"] == "Ingreso", k), []).append(r)
        if r["Tipo"] == "Gasto":
            h = _clave(r, palabras=1)
            if h: hab.setdefault(h, []).append(r)

    def resumen(k, rs):
        meses = sorted({r["Mes"] for r in rs})
        vals = sorted(abs(r["Valor"]) for r in rs)
        dias = sorted(int(r["Fecha"][8:10]) for r in rs)
        return {"con": k, "meses": len(meses), "veces": len(rs), "monto_tipico": round(vals[len(vals) // 2]), "dia_tipico": dias[len(dias) // 2],
                "al_mes": round(sum(vals) / len(meses)), "categoria": rs[-1].get("Subcategoría") or rs[-1]["Categoría"],
                "ya_registrado": any(re.search(p, " ".join(r["Descripción"] for r in rs), re.I) for p in pats)}

    fijos, ingresos, habitos = [], [], []
    for (entra, k), rs in gr.items():
        vals = sorted(abs(r["Valor"]) for r in rs)
        med = vals[len(vals) // 2]
        rs = [r for r in rs if 0.75 * med <= abs(r["Valor"]) <= 1.33 * med]   # el monto típico; un abono extra o un pago raro no cuenta
        meses = {r["Mes"] for r in rs}
        if len(meses) < 2 or len(rs) > 2 * len(meses): continue
        # en comida, transporte y compras lo que se repite suele ser un hábito; solo es "fijo" si cae siempre por el mismo día
        dias = [int(r["Fecha"][8:10]) for r in rs]
        mismo_dia = max(dias) - min(dias) <= 7 or min(dias) + 31 - max(dias) <= 7   # el 30 y el 2 también son "cerca"
        if rs[-1]["Categoría"] in ("Comida", "Transporte", "Compras", "Entretenimiento", "Ocio") and not mismo_dia: continue
        (ingresos if entra else fijos).append(resumen(k, rs))
    for k, rs in hab.items():
        meses = {r["Mes"] for r in rs}
        if len(meses) >= 2 and len(rs) >= 4 * len(meses):
            habitos.append(resumen(k, rs))
    orden = lambda xs: sorted(xs, key=lambda x: -x["al_mes"])
    return {"pagos_que_se_repiten": orden(fijos), "ingresos_que_se_repiten": orden(ingresos), "habitos": orden(habitos)[:8]}


SERVICIOS = [   # suscripciones y membresías que se cobran solas (nombre, cómo aparece en la alerta)
    ("Netflix", r"NETFLIX"), ("Spotify", r"SPOTIFY"), ("Disney+", r"DISNEY"), ("HBO Max", r"HBO|HBOMAX"),
    ("Amazon Prime", r"PRIME ?VIDEO|AMAZON ?PRIME|PRIMEVIDEO"), ("Apple", r"APPLE\W*COM|ITUNES|ICLOUD"), ("YouTube Premium", r"YOUTUBE"),
    ("Google", r"GOOGLE\W*(ONE|PLAY|STORAGE|GOOGLE)"), ("ChatGPT", r"OPENAI|CHATGPT"), ("Claude", r"ANTHROPIC|CLAUDE\W*AI"),
    ("Microsoft", r"MICROSOFT|MSFT|XBOX"), ("PlayStation", r"PLAYSTATION"), ("Canva", r"CANVA"), ("Adobe", r"ADOBE"), ("Dropbox", r"DROPBOX"),
    ("Notion", r"NOTION"), ("Duolingo", r"DUOLINGO"), ("Uber One", r"UBER\W*ONE"), ("Rappi Prime", r"RAPPI\W*(PRIME|PRO)"),
    ("Crunchyroll", r"CRUNCHYROLL"), ("Paramount+", r"PARAMOUNT"), ("Deezer", r"DEEZER"), ("Platzi", r"PLATZI"), ("Coursera", r"COURSERA"),
    ("LinkedIn", r"LINKEDIN"), ("Tinder", r"TINDER"), ("Smart Fit", r"SMART\W*FIT"), ("Bodytech", r"BODYTECH"), ("GitHub", r"GITHUB"),
    ("Fly.io", r"FLY\W*IO"), ("Paddle", r"PADDLE"),
]


def suscripciones(todos, pa, hoy, canceladas=None):
    """Cada suscripción con lo que hace falta para decidir: cuánto al mes y al año, cada cuánto y qué día cobra, el próximo cobro,
    con qué tarjeta, si subió de precio, si cobró dos veces y si siguió cobrando después de cancelarla. Las conocidas salen por
    su nombre; un cobro pequeño que se repite cada mes y no es conocido sale como "posible suscripción"."""
    canceladas = {k.lower(): v for k, v in (canceladas or {}).items()}
    grupos = {}
    for r in todos:
        if r["Tipo"] != "Gasto" or r["Valor"] >= 0: continue
        txt = (r["Descripción"] + " " + (r.get("Comercio") or "")).upper()
        nombre = next((n for n, p in SERVICIOS if re.search(p, txt)), None)
        if nombre: grupos.setdefault(nombre, []).append(r)
    conocidos = set(grupos)
    for x in pa["pagos_que_se_repiten"]:   # cobros chicos de cada mes que no están en la lista
        if 5000 <= x["monto_tipico"] <= 300000 and not any(re.search(p, x["con"]) for _, p in SERVICIOS) \
                and not re.search(r"Vivienda|Arriendo|Celular|Internet|Servicios|Luz|Agua|Gas|Deuda|ICETEX|libranza|Educación|Salud", x["categoria"], re.I):
            grupos[x["con"].title()] = [r for r in todos if r["Tipo"] == "Gasto" and _clave(r) == x["con"]]
    out = []
    for nombre, rs in grupos.items():
        # varios planes del mismo servicio (p. ej. dos cobros de Apple) son suscripciones distintas: se separan por monto
        for rs in _por_monto(sorted(rs, key=lambda r: r["Fecha"])):
            meses = {r["Mes"] for r in rs}
            # una que no conocemos solo cuenta si cobra una vez al mes, en dos meses o más, y no es comida, viajes, compras ni transporte
            if nombre not in conocidos and (len(meses) < 2 or len(rs) > len(meses) + 1 or abs(rs[-1]["Valor"]) < 5000
                                            or any(r["Categoría"] in ("Comida", "Viajes", "Compras", "Transporte", "Mercado") for r in rs)):
                continue
            montos = [round(-r["Valor"]) for r in rs]
            fechas = [datetime.date.fromisoformat(r["Fecha"]) for r in rs]
            gaps = sorted((b - a).days for a, b in zip(fechas, fechas[1:]) if (b - a).days > 3)
            gap = gaps[len(gaps) // 2] if gaps else None
            frec = ("mensual" if gap is None or gap <= 45 else "trimestral" if 75 <= gap <= 105 else "anual" if 330 <= gap <= 400 else "irregular")
            mensual = montos[-1] / {"mensual": 1, "trimestral": 3, "anual": 12}.get(frec, 1)
            prox = fechas[-1] + datetime.timedelta(days=gap or 30)
            ultimo = rs[-1]
            dup = [r["Fecha"] for a, r in zip(rs, rs[1:]) if (datetime.date.fromisoformat(r["Fecha"]) - datetime.date.fromisoformat(a["Fecha"])).days <= 3
                   and abs(r["Valor"] - a["Valor"]) <= 0.03 * abs(a["Valor"])]
            cancelada = canceladas.get(nombre.lower())
            out.append({
                "nombre": nombre + (f" ({f(montos[-1])})" if sum(1 for o in out if o["nombre"].startswith(nombre)) else ""),
                "conocida": nombre in conocidos, "mensual": round(mensual), "al_ano": round(mensual * 12), "frecuencia": frec,
                "dia_de_cobro": fechas[-1].day, "ultimo_cobro": ultimo["Fecha"], "ultimo_monto": montos[-1],
                "proximo_cobro": prox.isoformat(), "tarjeta": ultimo["Fuente"].replace(" (alerta)", ""), "veces": len(rs), "desde": rs[0]["Fecha"],
                "activa": (hoy - fechas[-1]).days <= (gap or 30) + 15,
                "cambio_precio": {"de": montos[-2], "a": montos[-1], "fecha": ultimo["Fecha"]} if len(montos) > 1 and montos[-1] > montos[-2] * 1.03 else None,
                "duplicado": dup,
                "cobro_tras_cancelar": [r["Fecha"] for r in rs if cancelada and r["Fecha"] > cancelada],
            })
    activas = [s for s in out if s["activa"]]
    return sorted(out, key=lambda s: (not s["activa"], -s["mensual"])), {"activas": len(activas), "mensual": sum(s["mensual"] for s in activas),
                                                                         "al_ano": sum(s["al_ano"] for s in activas)}


def _por_monto(rs):
    """Agrupa cobros del mismo servicio por monto (±15%): cada grupo es un plan. Un cobro hasta 40% más caro que llega
    20 días o más después del último de un plan es ese mismo plan con precio nuevo (Netflix de $38.900 a $44.900)."""
    grupos = []
    for r in rs:
        v, fe = abs(r["Valor"]), datetime.date.fromisoformat(r["Fecha"])
        g = next((g for g in grupos if abs(v - abs(g[-1]["Valor"])) <= 0.15 * abs(g[-1]["Valor"])), None)
        if g is None:
            g = next((g for g in grupos if abs(g[-1]["Valor"]) < v <= 1.4 * abs(g[-1]["Valor"])
                      and (fe - datetime.date.fromisoformat(g[-1]["Fecha"])).days >= 20), None)
        (g.append(r) if g is not None else grupos.append([r]))
    return grupos


def analisis(todos, agente, hoy=None, canceladas=None):
    """En qué se va la plata en las filas que le pasen: por mes, por categoría y mes, comercios, ingresos por fuente,
    gastos más grandes, cuánto queda sin detalle, suscripciones activas y cobros que se repiten."""
    por_mes, cat, com, ing = {}, {}, {}, {}
    for r in todos:
        x = por_mes.setdefault(r["Mes"], {"ingresos": 0, "gastos": 0, "cuotas_deuda": 0, "abonos_extra": 0, "movimientos": 0})
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
        elif r["Tipo"] == "Deuda":   # un abono extra o un prepago es una decisión con plata ahorrada, no lo que se va cada mes
            x["abonos_extra" if "Prepago" in (r.get("Subcategoría") or "") else "cuotas_deuda"] -= r["Valor"]
    for x in por_mes.values():
        x.update({k: round(x[k]) for k in ("ingresos", "gastos", "cuotas_deuda", "abonos_extra")})
        x["te_quedo"] = x["ingresos"] - x["gastos"] - x["cuotas_deuda"]
    gasto = sum(-r["Valor"] for r in todos if r["Tipo"] == "Gasto")
    sin = sum(-r["Valor"] for r in todos if r["Tipo"] == "Gasto" and r["Categoría"] in SIN_DETALLE)
    res = {
        "por_mes": dict(sorted(por_mes.items())),
        "gasto_por_categoria_y_mes": {k: {m: round(v) for m, v in sorted(ms.items())}
                                      for k, ms in sorted(cat.items(), key=lambda i: -sum(i[1].values()))},
        "comercios": [dict(c, total=round(c["total"])) for c in sorted(com.values(), key=lambda c: -c["total"])[:15]],
        "ingresos_por_fuente": {k: round(v) for k, v in sorted(ing.items(), key=lambda i: -i[1])},
        "gastos_mas_grandes": [{"fecha": r["Fecha"], "descripcion": r["Descripción"][:60], "categoria": r["Categoría"], "valor": round(-r["Valor"])}
                               for r in sorted((r for r in todos if r["Tipo"] == "Gasto"), key=lambda r: r["Valor"])[:10]],
        "sin_detalle": {"valor": round(sin), "porcentaje": round(100 * sin / gasto) if gasto else 0},
        "recurrentes": agente.recurrentes_nuevos(todos),
        "patrones": patrones(todos, agente.pagos_config()["pagos"]),
    }
    res["suscripciones"], res["suscripciones_total"] = suscripciones(todos, res["patrones"], hoy or agente.HOY, canceladas)
    return res


def sueldo_probable(todos, agente):
    """El sueldo que se ve en los correos, para confirmarlo en el primer uso: el ingreso más grande de cada mes, si se parece
    de un mes a otro (±15%) y llega por los mismos días. Dice si cae el penúltimo día hábil."""
    por_mes = {}
    for r in todos:
        if r["Tipo"] == "Ingreso" and r["Valor"] >= 1000000 and r["Valor"] > por_mes.get(r["Mes"], {"Valor": 0})["Valor"]:
            por_mes[r["Mes"]] = r
    rs = [por_mes[m] for m in sorted(por_mes)]
    if len(rs) < 2: return None
    ult = rs[-1]
    rs = [r for r in rs if abs(r["Valor"] - ult["Valor"]) <= 0.15 * ult["Valor"]]
    dias = [int(r["Fecha"][8:10]) for r in rs]
    if len(rs) < 2 or not (max(dias) - min(dias) <= 5 or min(dias) + 31 - max(dias) <= 5): return None
    penultimo = all(datetime.date.fromisoformat(r["Fecha"]) == agente.penultimo_habil(int(r["Fecha"][:4]), int(r["Fecha"][5:7])) for r in rs)
    return {"monto": round(ult["Valor"]), "dia": "penultimo_habil" if penultimo else sorted(dias)[len(dias) // 2],
            "fechas": [r["Fecha"] for r in rs], "descripcion": ult["Descripción"][:80]}


def cobertura(productos, todos, filas, cuentas_mod):
    """Cómo están los datos de cada cuenta: cuántos movimientos se vieron, el último, desde cuándo hay saldo y qué no se ve."""
    saldo = {f["id"]: f for f in filas}
    out = []
    for p in productos:
        ms = [r for r in todos if cuentas_mod.de_fuente(r["Fuente"], productos) is p]
        s = saldo.get(p["id"], {})
        if p["tipo"] in ("inversion", "cdt"): nota = "no manda alertas: su saldo es el que me des"
        elif not ms and p["tipo"] == "bolsillo": nota = "está dentro de su cuenta: sus movimientos salen allá"
        elif not ms: nota = "no vi alertas de esta cuenta: actívalas en la app del banco o dame su saldo de vez en cuando"
        else: nota = ""
        out.append({"nombre": p["nombre"], "tipo": p["tipo"], "movimientos": len(ms), "ultimo_movimiento": max([r["Fecha"] for r in ms] or [None]),
                    "saldo_desde": s.get("desde"), "nota": nota})
    return out


def acciones(objetivo, an, deu, hoy):
    """Una a tres cosas concretas para hacer, empezando por lo que el usuario quiere lograr (saber, gastar_menos, deudas, ahorrar)."""
    pa = an["patrones"]
    hab = pa["habitos"][0] if pa["habitos"] else None
    mes = hoy.strftime("%Y-%m")
    cerrados = sorted(v["te_quedo"] for k, v in an["por_mes"].items() if k != mes)
    prom = cerrados[len(cerrados) // 2] if cerrados else 0   # la mediana: un mes con un gasto raro no manda
    claro = an["sin_detalle"]["porcentaje"] < 25           # con mucho gasto sin detalle, "te quedó" no es confiable
    n_meses = max(1, len(an["por_mes"]))
    cats = [(k, sum(v.values()), len(v)) for k, v in an["gasto_por_categoria_y_mes"].items() if k not in SIN_DETALLE]
    seguido = max((c for c in cats if c[2] >= 2), key=lambda c: c[1], default=None)
    unico = max((c for c in cats if c[2] == 1 and c[1] > (seguido[1] / n_meses if seguido else 0)), key=lambda c: c[1], default=None)
    porque = {
        "gastar_menos": [f"Gastas ≈ {f(hab['al_mes'])} al mes en {hab['con'].title()} ({round(hab['veces'] / hab['meses'])} veces al mes). "
                         f"Si lo bajas a la mitad, te quedan ≈ {f(hab['al_mes'] * 6)} más al año." if hab else None,
                         (lambda t: f"Pagas {t['activas']} suscripciones por ≈ {f(t['mensual'])} al mes ({f(t['al_ano'])} al año): revisa cuáles usas de verdad."
                          if t["activas"] else None)(an["suscripciones_total"])],
        "deudas": [next((f"Paga completo {x['nombre']} ({f(x['saldo'])}): diferirla a cuotas cuesta ≈ {D.pct(x['tasa_ea'])} E.A."
                         for x in deu["deudas"] if x["tipo"] == "tarjeta" and x["saldo"] > 0), None),
                   deu["consejo"] or None],
        "ahorrar": [((f"En los últimos meses te quedaron ≈ {f(prom)} al mes. Si apartas {f(prom / 2)} el día del sueldo, en un año juntas ≈ {f(prom * 6)}."
                      if prom > 0 else f"En los últimos meses gastaste ≈ {f(-prom)} al mes más de lo que entró: antes de ahorrar, toca cerrar esa brecha.")
                     if claro else f"Para decirte cuánto puedes ahorrar, primero aclaremos el {an['sin_detalle']['porcentaje']}% de tu gasto que no dice en qué fue.")
                    if cerrados else None],
        "saber": [(f"El {an['sin_detalle']['porcentaje']}% de tu gasto ({f(an['sin_detalle']['valor'])}) no dice en qué fue (transferencias, retiros). "
                   f"Cuéntame qué fueron las más grandes y lo afinamos.") if an["sin_detalle"]["porcentaje"] >= 20 else None,
                  f"Donde más se te va mes a mes: {seguido[0]} (≈ {f(seguido[1] / n_meses)} al mes)." if seguido else None,
                  f"Además hubo un gasto grande que no se repite: {unico[0]} ({f(unico[1])})." if unico else None],
    }
    orden = [objetivo] + [k for k in ("gastar_menos", "deudas", "ahorrar", "saber") if k != objetivo] if objetivo in porque else ["saber", "gastar_menos", "deudas", "ahorrar"]
    return [t for k in orden for t in porque[k] if t][:3]


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
    pa = an["patrones"]
    for x in pa["pagos_que_se_repiten"][:15]:
        if not x["ya_registrado"] and x["monto_tipico"] >= 10000:   # lo de $3.500 es ruido para anotar
            add(f"patron:{slug(x['con'])}", f"Cada mes, cerca del día {x['dia_tipico']}, pagas ≈ {f(x['monto_tipico'])} a {x['con']} ({x['meses']} meses, {x['categoria']}).",
                "¿Lo agrego a tus pagos fijos?")
    for x in pa["ingresos_que_se_repiten"]:
        if not x["ya_registrado"] and x["categoria"] not in ("Salario", "Nómina"):
            add(f"ingreso:{slug(x['con'])}", f"Cada mes, cerca del día {x['dia_tipico']}, te entran ≈ {f(x['monto_tipico'])} de {x['con']} ({x['meses']} meses).",
                "¿Qué es? (roomie, arriendo que cobras, un cliente…)")
    for x in pa["habitos"]:
        add(f"habito:{slug(x['con'])}", f"Gastas ≈ {f(x['al_mes'])} al mes en {x['con']} ({round(x['veces'] / x['meses'])} veces al mes).")
    for s in an["suscripciones"]:
        k = slug(s["nombre"])
        if s["activa"]:
            add(f"suscripcion:{k}", f"Suscripción: {s['nombre']} ≈ {f(s['mensual'])} al mes ({f(s['al_ano'])} al año), cobra el {s['dia_de_cobro']} en {s['tarjeta']}.",
                "" if s["conocida"] else "¿Es una suscripción? ¿La sigues usando?")
        if s["cambio_precio"]:
            c = s["cambio_precio"]
            add(f"precio:{k}:{c['fecha']}", f"{s['nombre']} subió de {f(c['de'])} a {f(c['a'])} el {d(c['fecha'])}.", "¿La sigues usando a ese precio?")
        for fe in s["duplicado"]:
            add(f"duplicado:{k}:{fe}", f"{s['nombre']} te cobró dos veces casi seguidas (el {d(fe)}).", "Revísalo con el banco o el servicio.")
        for fe in s["cobro_tras_cancelar"]:
            add(f"tras-cancelar:{k}:{fe}", f"{s['nombre']} te cobró el {d(fe)} aunque la cancelaste.", "Reclama el reembolso.")
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
        if x["tipo"] == "bolsillo":   # sin su saldo no se sabe cuánto del bolsillo es colchón y cuánto está apartado
            if not x["desde"]: add("saldo:" + slug(x["nombre"]), f"Cuánto tienes hoy en {x['nombre']}", 2)
            continue
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
                L.append(f"• 💳 {x['nombre']}  debes {f(x['saldo'])}" + (f", vence el {d(x['vence'])}" if x.get("vence") else "")
                         + (f", corta el {d(x['corte'])}" if x.get("corte") else "") + f"  ({t} E.A. si difieres)")
        if deu["intereses_mes"]: L.append(f"Tus créditos te cuestan ≈ {f(deu['intereses_mes'])} al mes en intereses. {deu['consejo']}")
    if dudosos:
        L += ["", "¿QUÉ FUE ESTO? (respóndeme y lo clasifico)"]
        L += [f"• {d(m['Fecha'])}  {m['Descripción'][:50]}  {f(m['Valor'])}" for m in dudosos[:8]]
    subs = [s for s in res.get("analisis", {}).get("suscripciones", []) if s["activa"]]
    if subs:
        tot = res["analisis"]["suscripciones_total"]
        L += ["", f"SUSCRIPCIONES: {f(tot['mensual'])} al mes ({f(tot['al_ano'])} al año)"]
        for s in subs[:8]:
            marcas = (" ⬆️ subió" if s["cambio_precio"] else "") + (" ⚠️ cobro doble" if s["duplicado"] else "") + (" ❌ cobró tras cancelar" if s["cobro_tras_cancelar"] else "")
            L.append(f"• {s['nombre']}  {f(s['mensual'])}/mes, cobra el {s['dia_de_cobro']}{marcas}")
    nuevos_d = [x for x in res.get("descubrimientos", []) if x.get("nuevo")]
    if nuevos_d:
        L += ["", "LO QUE DESCUBRÍ"]
        L += [f"• {x['texto']}" + (f" {x['pregunta']}" if x["pregunta"] else "") for x in nuevos_d[:6]]
    falt = [x for x in res.get("faltantes", []) if x["prioridad"] <= 2]
    if falt:
        L += ["", "ME FALTA SABER (respóndeme y lo anoto)"]
        L += [f"• {x['que_falta']}" for x in falt[:5]]
    mejores = [o for o in (res.get("comparacion_ofertas") or {}).get("ofertas", []) if o["vale_la_pena"]][:2]
    if mejores:
        L += ["", "PARA MEJORAR TUS DEUDAS (tasas publicadas: la tuya depende de tu perfil)"]
        L += [f"• {o['credito']} ({D.pct(o['tasa_actual'])}): {o['entidad']} publica {D.pct(o['tasa_oferta'])} → ≈ {f(o['ahorro_intereses_mes'])} menos de intereses al mes"
              + (f", terminarías {o['meses_que_faltan'] - o['meses_con_la_oferta']} meses antes" if o.get("meses_con_la_oferta") else "") + f". {o['fuente']}" for o in mejores]
    if res.get("acciones"):
        L += ["", "UNA COSA PARA ESTA SEMANA", res["acciones"][0]]
    asunto = f"💸 Puedes gastar {f(r['por_dia'])}/día hasta el {d(pp)} · informe semanal"
    return {"asunto": asunto, "texto": "\n".join(L)}
