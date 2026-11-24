"""Los datos del tablero (artifact) de cada usuario, a partir de lo que devuelve el motor.

Las mismas secciones del tablero original de Javier (Inicio, Cuentas, Movimientos, Flujo, Reportes, Pagos y Metas), con
lo que el motor general sabe. Claude guarda cada documento en la colección `tablero` del almacén del artifact:
  resumen      Inicio: cuánto puede gastar por día, indicadores, avisos, gasto diario de este mes vs el anterior
  cuentas      saldos, balance (lo que tienes − lo que debes), tarjetas con lo comprado desde el corte, créditos
  reportes     flujo por mes, grupos de gasto, categorías, comercios, ingresos por fuente, la semana, gastos grandes
  compromisos  cada pago del mes con su estado y cómo se sabe
  movimientos  los de los últimos 60 días (máximo 1.200, en filas compactas)
  metas        cada meta de la pestaña Metas con su avance medido
Todos quedan muy por debajo del límite de 256 KiB por documento. Los botones de la página escriben marcas/<clave>; la
siguiente actualización los pasa a Tu marca del Sheet. Solo librería estándar."""
import calendar
import datetime
import re

DIAS_MOVS = 60
MAX_MOVS = 1200
DUDOSAS = {"Otros", "Transferencias a terceros", "Gastos vía billetera (sin detalle)", "Efectivo", "Por aclarar"}
# Grupos de gasto (los del resumen financiero original): (grupo, condición sobre categoría y subcategoría)
GRUPOS = [
    ("Sin destino identificado", lambda c, s: c in DUDOSAS),
    ("Esencial", lambda c, s: c in ("Vivienda", "Transporte", "Salud", "Educación", "Servicios") or (c == "Comida" and s == "Mercado y tiendas")),
    ("Intereses, comisiones e impuestos", lambda c, s: c in ("Intereses y comisiones", "Impuestos")),
    ("Estilo de vida", lambda c, s: True),
]
UNICO = "Pagos únicos y grandes"
LIQUIDOS = ("ahorros", "corriente", "billetera", "bolsillo")
M3 = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def clave(id_):
    """El ID de un compromiso ("2026-11|Arriendo") como nombre de documento válido del almacén."""
    c = re.sub(r"[^A-Za-z0-9_.~:@+-]+", "-", str(id_)).strip("-")
    return (c or "x")[:180]


def _cat(m):
    return m.get("Categoría manual") or m.get("Categoría") or ""


def _tipo(m):
    return m.get("Tipo manual") or m.get("Tipo") or ""


def _nombre(m):
    n = m.get("Comercio") or m.get("Descripción") or ""
    return re.sub(r"\s+", " ", str(n)).strip()[:60]


def _mes_ant(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def _meses_completos(hoy, n):
    out, (y, m) = [], (hoy.year, hoy.month)
    for _ in range(n):
        y, m = _mes_ant(y, m)
        out.append(f"{y}-{m:02d}")
    return out[::-1]


def _grupo(c, s):
    return next(g for g, f in GRUPOS if f(c, s))


def _tasa(x):
    if x in (None, ""): return None
    x = float(str(x).replace(",", "."))
    return x / 100 if x > 1 else x


def _resumen(res, hoy, sheet_url, movs, ahora):
    r = res.get("resumen", {})
    an = res.get("analisis", {}) or {}
    mes = hoy.isoformat()[:7]
    y0, m0 = _mes_ant(hoy.year, hoy.month)
    mes_ant = f"{y0}-{m0:02d}"
    dia = hoy.day
    gasto = lambda ms, hasta_dia=None: round(sum(-m["Valor"] for m in movs if _tipo(m) == "Gasto" and m["Fecha"][:7] == ms
                                                 and (hasta_dia is None or int(m["Fecha"][8:10]) <= hasta_dia)))
    entro = round(sum(m["Valor"] for m in movs if _tipo(m) == "Ingreso" and m["Fecha"][:7] == mes))
    salio = round(sum(-m["Valor"] for m in movs if _tipo(m) in ("Gasto", "Deuda") and m["Fecha"][:7] == mes))
    deu = res.get("deudas") or {}
    pasivo = sum(d.get("saldo") or 0 for d in deu.get("deudas") or [])
    st = an.get("suscripciones_total") or {}
    por_revisar = len(res.get("por_confirmar") or [])
    kpis = [
        {"clave": "falta_pagar", "etiqueta": "Falta pagar este mes", "valor": (res.get("compromisos_resumen") or {}).get("falta_pagar_este_mes")},
        {"clave": "libre", "etiqueta": "Libre hasta el sueldo", "valor": r.get("libre")},
        {"clave": "plata", "etiqueta": "Plata en tus cuentas", "valor": r.get("plata_en_cuentas")},
        {"clave": "gasto_mes", "etiqueta": f"Gasto de {M3[hoy.month - 1]} (al {dia})", "valor": gasto(mes),
         "nota": f"{M3[m0 - 1]} al {dia}: ${gasto(mes_ant, dia):,}".replace(",", ".")},
        {"clave": "entro", "etiqueta": "Entró este mes", "valor": entro},
        {"clave": "salio", "etiqueta": "Salió este mes", "valor": salio, "nota": "gastos y cuotas de deudas"},
        {"clave": "deudas", "etiqueta": "Lo que debes", "valor": round(pasivo),
         "nota": f"intereses ≈ ${deu.get('intereses_mes') or 0:,} al mes".replace(",", ".") if deu.get("intereses_mes") else None},
        {"clave": "suscripciones", "etiqueta": "Suscripciones al mes", "valor": st.get("mensual"), "nota": f"{st.get('activas') or 0} activas"},
        {"clave": "por_revisar", "etiqueta": "Movimientos por revisar", "valor": por_revisar, "unidad": "n"},
        {"clave": "sin_detalle", "etiqueta": "Gasto sin detalle", "valor": (an.get("sin_detalle") or {}).get("porcentaje"), "unidad": "%"},
    ]
    # gasto acumulado día a día: este mes contra el anterior
    ult_ant = calendar.monthrange(y0, m0)[1]
    ult = calendar.monthrange(hoy.year, hoy.month)[1]
    def acum(ms, ndias):
        por_dia = {}
        for m in movs:
            if _tipo(m) == "Gasto" and m["Fecha"][:7] == ms:
                d = int(m["Fecha"][8:10])
                por_dia[d] = por_dia.get(d, 0) - m["Valor"]
        out, s = [], 0
        for d in range(1, ndias + 1):
            s += por_dia.get(d, 0)
            out.append(round(s))
        return out
    este, ant = acum(mes, ult), acum(mes_ant, ult_ant)
    diario = [{"dia": d, "este_mes": este[d - 1] if d <= dia else None, "mes_anterior": ant[d - 1] if d <= ult_ant else None}
              for d in range(1, max(ult, ult_ant) + 1)]
    avisos = (res.get("avisos") or {}).get("alertas", [])
    return {
        "actualizado": ahora, "hoy": hoy.isoformat(), "alertas_hasta": r.get("alertas_hasta"), "sheet_url": sheet_url,
        "kpis": {"plata_en_cuentas": r.get("plata_en_cuentas"), "disponible": r.get("disponible"), "libre": r.get("libre"),
                 "por_dia": r.get("por_dia"), "proximo_sueldo": r.get("proximo_sueldo"), "dias_al_sueldo": r.get("dias_al_sueldo"),
                 "aproximado": bool(r.get("aproximado")), "cuentas_sin_saldo": r.get("cuentas_sin_saldo") or [],
                 "falta_pagar_este_mes": (res.get("compromisos_resumen") or {}).get("falta_pagar_este_mes")},
        "indicadores": kpis,
        "compromisos_resumen": res.get("compromisos_resumen") or {},
        "avisos": [{k: a.get(k) for k in ("id", "severidad", "titulo", "detalle", "accion")} for a in avisos[:15]],
        "gasto_diario": diario,
        "gasto_mes": [{"categoria": k, "total": v} for k, v in (r.get("gasto_mes_por_categoria") or {}).items()][:12],
        "gasto_mes_anterior": sum((r.get("gasto_mes_anterior_por_categoria") or {}).values()),
        "suscripciones": [{"nombre": s.get("nombre"), "mensual": s.get("mensual"), "proximo": s.get("proximo_cobro"),
                           "tarjeta": s.get("tarjeta"), "subio": bool(s.get("cambio_precio"))}
                          for s in an.get("suscripciones") or [] if s.get("activa")][:20],
        "suscripciones_total": st,
        "tarjetas": [{"nombre": t.get("nombre"), "deuda": t.get("deuda"), "vence": t.get("vence"), "corte": t.get("corte"),
                      "estimada": bool(t.get("estimada"))} for t in res.get("tarjetas") or []],
        "datos": {"alertas_hasta": r.get("alertas_hasta"), "por_banco": (res.get("lectura") or {}).get("por_banco"),
                  "movimientos": len(res.get("movimientos") or []), "por_revisar": por_revisar},
    }


def _cuentas(res, hoy, movs):
    saldos, activo, no_sumado = [], 0, []
    grupo = lambda t: "Inversiones" if t in ("inversion", "cdt") else "Bolsillos" if t == "bolsillo" else "Cuentas y billeteras"
    for c in res.get("cuentas") or []:
        saldos.append({"nombre": c.get("nombre"), "tipo": c.get("tipo"), "grupo": grupo(c.get("tipo")), "saldo": c.get("saldo"),
                       "desde": c.get("desde"), "hasta": c.get("hasta")})
        if c.get("saldo") is None:
            no_sumado.append(c.get("nombre"))
        elif c.get("tipo") != "bolsillo":   # el bolsillo vive dentro del saldo de su cuenta: no se suma dos veces
            activo += c["saldo"]
    tarjetas = []
    for t in res.get("tarjetas") or []:
        term = str(t.get("terminacion") or "")
        compras, desde = [], None
        if t.get("corte"):   # lo comprado desde el último corte (se paga en el extracto siguiente)
            prox = datetime.date.fromisoformat(t["corte"])
            y, m = _mes_ant(prox.year, prox.month)
            desde = datetime.date(y, m, min(prox.day, calendar.monthrange(y, m)[1])).isoformat()
        if term:
            compras = [{"fecha": m["Fecha"], "nombre": _nombre(m), "valor": round(-m["Valor"]), "categoria": _cat(m)}
                       for m in sorted(movs, key=lambda m: m["Fecha"], reverse=True)
                       if f"*{term}" in str(m.get("Fuente", "")) and " TC " in f" {m.get('Fuente', '')} " and m["Valor"] < 0
                       and (not desde or m["Fecha"] > desde)][:30]
        tarjetas.append({"nombre": t.get("nombre"), "deuda": t.get("deuda"), "estimada": bool(t.get("estimada")), "vence": t.get("vence"),
                         "dia_pago": t.get("dia_pago"), "corte": t.get("corte"), "desde_corte": desde,
                         "compras_desde_corte": compras, "total_compras": sum(c["valor"] for c in compras),
                         "tasa_ea": _tasa(t.get("tasa_ea"))})
    deu = res.get("deudas") or {}
    creditos = [{"nombre": d.get("nombre"), "saldo": d.get("saldo"), "tasa_ea": _tasa(d.get("tasa_ea")), "cuota": d.get("cuota"),
                 "meses": d.get("meses"), "interes_mes": d.get("interes_mes"), "abonar_aqui": bool(d.get("abonar_aqui")),
                 "nomina": bool(d.get("nomina"))} for d in deu.get("deudas") or [] if d.get("tipo") != "tarjeta"]
    pasivo = sum(t["deuda"] or 0 for t in tarjetas) + sum(c["saldo"] or 0 for c in creditos)
    return {"saldos": saldos, "tarjetas": tarjetas, "creditos": creditos, "consejo": deu.get("consejo"),
            "balance": {"activo": round(activo), "pasivo": round(pasivo), "patrimonio": round(activo - pasivo),
                        "no_incluye": no_sumado + [t["nombre"] for t in tarjetas if t["deuda"] is None],
                        "nota": "Lo que tienes en cuentas e inversiones menos lo que debes. No incluye vivienda, carro, cesantías ni lo que no me has contado."}}


def _reportes(res, hoy, movs, historia_desde=None):
    an = res.get("analisis", {}) or {}
    mes = hoy.isoformat()[:7]
    previos = _meses_completos(hoy, 3)
    por_mes = an.get("por_mes") or {}
    # un mes es parcial si está en curso o si la historia leída empieza después de su día 1 (configuración por etapas)
    incompleto = lambda k: bool(historia_desde) and k + "-01" < historia_desde
    flujo = [{"mes": k, "ingresos": v.get("ingresos", 0), "gastos": v.get("gastos", 0), "cuotas_deuda": v.get("cuotas_deuda", 0),
              "te_quedo": v.get("te_quedo", 0), "parcial": k == mes or incompleto(k), "incompleto": incompleto(k)}
             for k, v in sorted(por_mes.items())][-12:]
    meses_con_datos = [m for m in previos if m in por_mes and not incompleto(m)]
    ing_prom = sum(por_mes[m]["ingresos"] for m in meses_con_datos) / len(meses_con_datos) if meses_con_datos else 0
    umbral_unico = max(1_000_000, 0.25 * ing_prom)
    grupos, cats, com = {}, {}, {}
    for m in movs:
        if _tipo(m) != "Gasto" or m["Fecha"][:7] not in previos + [mes]:
            continue
        v = -m["Valor"]
        g = UNICO if v >= umbral_unico else _grupo(_cat(m), m.get("Subcategoría") or "")
        x = grupos.setdefault(g, {"grupo": g, "previos": 0, "mes_actual": 0})
        x["mes_actual" if m["Fecha"][:7] == mes else "previos"] += v
        if m["Fecha"][:7] == mes and _cat(m) not in DUDOSAS:
            k = _nombre(m).upper()
            c = com.setdefault(k, {"nombre": _nombre(m), "total": 0, "veces": 0, "categoria": _cat(m)})
            c["total"] += v
            c["veces"] += 1
    n = len(meses_con_datos) or 1
    orden = [g for g, _ in GRUPOS] + [UNICO]
    grupos = [{"grupo": g["grupo"], "promedio": round(g["previos"] / n), "mes_actual": round(g["mes_actual"])}
              for g in sorted(grupos.values(), key=lambda g: orden.index(g["grupo"]))]
    for c, ms in (an.get("gasto_por_categoria_y_mes") or {}).items():
        cats[c] = {"categoria": c, "mes_actual": ms.get(mes, 0), "promedio": round(sum(ms.get(m, 0) for m in meses_con_datos) / n)}
    categorias = sorted(cats.values(), key=lambda c: -(c["mes_actual"] + c["promedio"]))[:15]
    ing = {}
    for m in movs:
        if _tipo(m) == "Ingreso" and m["Fecha"][:7] in meses_con_datos:
            k = m.get("Subcategoría") or _cat(m)
            ing[k] = ing.get(k, 0) + m["Valor"]
    ingresos = [{"fuente": k, "promedio_mes": round(v / n)} for k, v in sorted(ing.items(), key=lambda i: -i[1])][:10]
    # la semana pasada (lunes a domingo) contra la anterior
    lun = hoy - datetime.timedelta(days=hoy.weekday() + 7)
    dom = lun + datetime.timedelta(days=6)
    lun0, dom0 = lun - datetime.timedelta(days=7), lun - datetime.timedelta(days=1)
    g_sem = lambda a, b: round(sum(-m["Valor"] for m in movs if _tipo(m) == "Gasto" and a.isoformat() <= m["Fecha"] <= b.isoformat()))
    semana = {"desde": lun.isoformat(), "hasta": dom.isoformat(), "gasto": g_sem(lun, dom), "gasto_anterior": g_sem(lun0, dom0),
              "entro": round(sum(m["Valor"] for m in movs if _tipo(m) == "Ingreso" and lun.isoformat() <= m["Fecha"] <= dom.isoformat()))}
    return {"flujo": flujo, "grupos": grupos, "meses_base": meses_con_datos, "categorias": categorias,
            "comercios_mes": sorted(({**c, "total": round(c["total"])} for c in com.values()), key=lambda c: -c["total"])[:12],
            "ingresos_fuente": ingresos, "semana": semana, "gastos_grandes": (an.get("gastos_mas_grandes") or [])[:8],
            "sin_detalle": an.get("sin_detalle"), "umbral_unico": round(umbral_unico)}


def _metas(metas, cuentas, hoy):
    """Avance de cada meta: ahorro = saldo de la cuenta que la mide / monto; deuda = cuánto ha bajado el crédito desde
    el saldo inicial hasta el objetivo; otro = lo que el usuario escribe en Estado."""
    por_nombre = {str(c.get("nombre", "")).lower(): c for c in cuentas["saldos"] + cuentas["creditos"]}
    out = []
    for x in metas or []:
        monto = float(x.get("monto") or 0)
        tipo = (x.get("tipo") or "otro").lower()
        medir = por_nombre.get(str(x.get("medir") or "").lower())
        actual = (medir or {}).get("saldo")
        fecha = str(x.get("fecha") or "")[:10]
        meses = None
        if fecha:
            f = datetime.date.fromisoformat(fecha)
            meses = max(0, (f.year - hoy.year) * 12 + f.month - hoy.month)
        it = {"meta": x.get("meta"), "tipo": tipo, "monto": monto, "fecha": fecha or None, "medir": x.get("medir"), "actual": actual,
              "progreso": None, "falta": None, "al_mes": None, "estado": x.get("estado")}
        if tipo == "ahorro" and actual is not None and monto:
            it["progreso"] = max(0.0, min(1.0, actual / monto))
            it["falta"] = max(0, round(monto - actual))
        elif tipo == "deuda" and actual is not None:
            ini = float(x.get("inicial") or 0) or None
            if ini and ini > monto:
                it["progreso"] = max(0.0, min(1.0, (ini - actual) / (ini - monto)))
            it["falta"] = max(0, round(actual - monto))
        if it["falta"] and meses:
            it["al_mes"] = round(it["falta"] / meses)
        if medir is None and tipo in ("ahorro", "deuda"):
            it["nota"] = f"No encuentro \"{x.get('medir')}\" en tus cuentas ni créditos: escribe el nombre tal como está en el Sheet."
        out.append(it)
    return {"items": out}


def armar(res, hoy=None, sheet_url=None, metas=None, historia_desde=None):
    hoy = hoy or datetime.date.today()
    ahora = datetime.datetime.now().isoformat(timespec="minutes")
    movs = [m for m in res.get("movimientos") or [] if m.get("Fecha")]
    cuentas = _cuentas(res, hoy, movs)
    compromisos = {"actualizado": ahora, "items": [
        {"clave": clave(c["id"]), "id": c["id"], "nombre": c["nombre"], "tipo": c["tipo"], "vence": c.get("vence"),
         "esperado": c.get("monto_esperado"), "pagado": c.get("pagado"), "falta": c.get("falta"), "estado": c["estado"],
         "grupo": c.get("grupo"), "prueba": c.get("prueba"), "nota": c.get("nota") or c.get("deduccion"),
         "marcado": bool(c.get("marcado_a_mano"))} for c in res.get("compromisos") or []]}
    desde = (hoy - datetime.timedelta(days=DIAS_MOVS)).isoformat()
    revisar = set(res.get("por_confirmar") or [])
    recientes = sorted((m for m in movs if m["Fecha"] >= desde), key=lambda m: (m["Fecha"], m.get("ID", "")), reverse=True)
    movimientos = {"actualizado": ahora, "desde": desde,
                   "columnas": ["fecha", "valor", "descripcion", "categoria", "tipo", "cuenta", "id", "revisar"],
                   "filas": [[m["Fecha"], m["Valor"], str(m.get("Descripción", ""))[:90], _cat(m), _tipo(m),
                              str(m.get("Fuente", "")).replace(" (alerta)", ""), m.get("ID"),
                              1 if (m.get("ID") in revisar or "❓" in str(m.get("Tu nota") or "")) else 0] for m in recientes[:MAX_MOVS]]}
    return {"resumen": _resumen(res, hoy, sheet_url, movs, ahora), "cuentas": {"actualizado": ahora, **cuentas},
            "reportes": {"actualizado": ahora, "historia_desde": historia_desde, **_reportes(res, hoy, movs, historia_desde)}, "compromisos": compromisos,
            "movimientos": movimientos, "metas": {"actualizado": ahora, **_metas(metas, cuentas, hoy)}}
