"""Simulaciones: lo que el usuario le pregunta a CHARLIE con "¿y si…?". Las cifras salen de aquí, no de Claude.

Entran en `simulaciones` de entrada.json, cada una con su `tipo`, y salen en `simulaciones` con `resultado` (cifras) y
`texto` (una línea lista para decir). Usan lo que el motor ya calculó: deudas, lo libre hasta el sueldo, el flujo por
mes y el gasto por categoría de los últimos 3 meses completos.

Tipos:
  me_alcanza         {"monto", "fecha"?}                  ¿me alcanza para gastar X (hoy o en una fecha)?
  ahorrar_para       {"monto", "fecha", "meta"?}         ¿cuánto aparto al mes para tener X en esa fecha?
  abono_extra        {"credito", "monto_mes"? | "monto_unico"?}   ¿cuánto ahorro y cuándo termino si abono a un crédito?
  salir_de_deudas    {"extra_mes"?}                       ¿cuándo salgo de deudas (lo extra a la de mayor tasa)?
  recortar           {"categoria", "porcentaje"}          ¿cuánto ahorro si gasto X % menos en una categoría?
  cancelar           {"suscripcion"}                      ¿cuánto ahorro si cancelo una suscripción?
No da consejos de inversión: solo cuentas con los datos del usuario (FIN-51). Solo librería estándar."""
import datetime

M3 = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _f(v):
    return ("−" if v < 0 else "") + "$" + f"{abs(round(v)):,}".replace(",", ".")


def _tasa(x):
    if x in (None, ""): return None
    x = float(str(x).replace(",", "."))
    return x / 100 if x > 1 else x


def _dia(iso):
    d = datetime.date.fromisoformat(str(iso)[:10])
    return f"{d.day}-{M3[d.month - 1]}"


def _mes_txt(d):
    return f"{M3[d.month - 1]}-{d.year}"


def _sumar_meses(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    return datetime.date(d.year + y, m + 1, 1)


def _meses_completos(hoy, n=3):
    out, y, m = [], hoy.year, hoy.month
    for _ in range(n):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        out.append(f"{y}-{m:02d}")
    return out


def _promedios(res, hoy):
    """Lo que te quedó por mes y el gasto por categoría, en promedio de los últimos 3 meses completos con datos."""
    an = res.get("analisis") or {}
    pm = an.get("por_mes") or {}
    meses = [m for m in _meses_completos(hoy) if m in pm]
    n = len(meses) or 1
    queda = sum(pm[m].get("te_quedo", 0) for m in meses) / n if meses else None
    cats = {c: sum(v.get(m, 0) for m in meses) / n for c, v in (an.get("gasto_por_categoria_y_mes") or {}).items()} if meses else {}
    return queda, cats, meses


def _amortizar(saldo, tasa_ea, cuota, extra=0.0, max_meses=600):
    """Meses e intereses hasta pagar el crédito con su cuota + un abono extra al mes (reducción de plazo)."""
    i = (1 + tasa_ea) ** (1 / 12) - 1
    n, intereses = 0, 0.0
    while saldo > 1 and n < max_meses:
        inter = saldo * i
        pago = min(cuota + extra, saldo + inter)
        if pago <= inter:
            return None, None   # con esa cuota la deuda no baja
        saldo = saldo + inter - pago
        intereses += inter
        n += 1
    return n, intereses


def _creditos(res):
    return [d for d in ((res.get("deudas") or {}).get("deudas") or []) if d.get("tipo") != "tarjeta" and d.get("saldo")]


def _buscar(xs, nombre, clave="nombre"):
    n = str(nombre or "").lower().strip()
    return next((x for x in xs if str(x.get(clave, "")).lower() == n), None) or \
        next((x for x in xs if n and n in str(x.get(clave, "")).lower()), None)


def me_alcanza(s, res, hoy):
    r = res.get("resumen") or {}
    monto = float(s.get("monto") or 0)
    libre, por_dia = r.get("libre") or 0, r.get("por_dia")
    sueldo = datetime.date.fromisoformat(r["proximo_sueldo"]) if r.get("proximo_sueldo") else None
    fecha = datetime.date.fromisoformat(str(s["fecha"])[:10]) if s.get("fecha") else hoy
    aprox = " (aproximado: faltan saldos)" if r.get("aproximado") else ""
    if not sueldo or fecha <= sueldo:
        dias = max(1, (sueldo - hoy).days) if sueldo else 30
        queda = libre - monto
        out = {"libre": libre, "despues": queda, "por_dia_antes": por_dia, "por_dia_despues": round(queda / dias), "alcanza": queda >= 0}
        txt = (f"Sí: te quedan {_f(libre)} libres hasta el sueldo; después de {_f(monto)} quedan {_f(queda)}, o sea {_f(queda / dias)} por día (hoy son {_f(por_dia)}){aprox}."
               if queda >= 0 else f"No alcanza con lo libre: tienes {_f(libre)} hasta el sueldo y te faltarían {_f(-queda)}{aprox}.")
        return out, txt
    queda_mes, _, meses = _promedios(res, hoy)
    n = max(0, (fecha.year - hoy.year) * 12 + fecha.month - hoy.month)
    if queda_mes is None:
        return {"alcanza": None}, "Aún no tengo meses completos para proyectar: con más historia te digo."
    proy = libre + queda_mes * n
    out = {"libre_hoy": libre, "te_queda_al_mes": round(queda_mes), "meses": n, "proyectado": round(proy), "alcanza": proy >= monto, "meses_base": meses}
    txt = (f"Al ritmo de los últimos meses (te quedan ≈ {_f(queda_mes)} al mes), para {_mes_txt(fecha)} tendrías ≈ {_f(proy)}: "
           + ("te alcanza" if proy >= monto else f"te faltarían ≈ {_f(monto - proy)}") + f" para {_f(monto)}. Es un estimado, no una promesa{aprox}.")
    return out, txt


def ahorrar_para(s, res, hoy):
    monto = float(s.get("monto") or 0) - float(s.get("ya_tengo") or 0)
    fecha = datetime.date.fromisoformat(str(s["fecha"])[:10])
    n = max(1, (fecha.year - hoy.year) * 12 + fecha.month - hoy.month)
    al_mes = monto / n
    queda_mes, cats, meses = _promedios(res, hoy)
    out = {"meses": n, "al_mes": round(al_mes), "te_queda_al_mes": round(queda_mes) if queda_mes is not None else None}
    meta = s.get("meta") or "eso"
    txt = f"Para {meta} necesitas apartar {_f(al_mes)} al mes durante {n} meses (hasta {_mes_txt(fecha)})."
    if queda_mes is not None:
        if queda_mes >= al_mes:
            txt += f" Te alcanza: en promedio te quedan {_f(queda_mes)} al mes; sería el {round(100 * al_mes / queda_mes) if queda_mes else 0} % de eso."
        else:
            falta = al_mes - max(0, queda_mes)
            disc = sorted(((c, v) for c, v in cats.items() if c not in ("Vivienda", "Salud", "Educación", "Impuestos")), key=lambda x: -x[1])[:3]
            out["recortes_sugeridos"] = [{"categoria": c, "promedio": round(v), "recorte_necesario_pct": round(min(100, 100 * falta / v)) if v else None} for c, v in disc]
            txt += (f" Hoy no alcanza: en promedio te quedan {_f(queda_mes)} al mes y faltan {_f(falta)}."
                    + (" Donde más se va (para recortar): " + ", ".join(f"{c} ({_f(v)} al mes)" for c, v in disc) + "." if disc else ""))
    return out, txt


def abono_extra(s, res, hoy):
    c = _buscar(_creditos(res), s.get("credito"))
    if not c:
        return {"error": "credito"}, f"No encuentro el crédito \"{s.get('credito')}\" en tus deudas. Tus créditos: " + ", ".join(x["nombre"] for x in _creditos(res)) + "."
    tasa, cuota = _tasa(c.get("tasa_ea")), c.get("cuota")
    if not tasa or not cuota:
        return {"error": "datos"}, f"Me falta la tasa o la cuota de {c['nombre']} para simularlo: dámelas y lo calculo."
    saldo = float(c["saldo"])
    n0, i0 = _amortizar(saldo, tasa, cuota)
    unico = float(s.get("monto_unico") or 0)
    n1, i1 = _amortizar(saldo - unico, tasa, cuota, float(s.get("monto_mes") or 0))
    if n0 is None or n1 is None:
        return {"error": "cuota"}, f"Con una cuota de {_f(cuota)} la deuda de {c['nombre']} no baja (los intereses son mayores): revisa la cuota."
    fin0, fin1 = _sumar_meses(hoy, n0), _sumar_meses(hoy, n1)
    abono = f"{_f(s['monto_mes'])} extra al mes" if s.get("monto_mes") else f"{_f(unico)} de una vez"
    out = {"credito": c["nombre"], "meses_sin": n0, "meses_con": n1, "intereses_sin": round(i0), "intereses_con": round(i1),
           "ahorro_intereses": round(i0 - i1), "termina_sin": fin0.isoformat()[:7], "termina_con": fin1.isoformat()[:7]}
    txt = (f"Abonando {abono} a {c['nombre']} (con reducción de plazo) terminas en {_mes_txt(fin1)} en vez de {_mes_txt(fin0)}: "
           f"{n0 - n1} cuotas menos y {_f(i0 - i1)} menos de intereses.")
    return out, txt


def salir_de_deudas(s, res, hoy):
    cr = [dict(c, tasa=_tasa(c.get("tasa_ea")), saldo=float(c["saldo"])) for c in _creditos(res) if _tasa(c.get("tasa_ea")) and c.get("cuota")]
    if not cr:
        return {"error": "datos"}, "Necesito saldo, tasa y cuota de tus créditos para simularlo."
    extra = float(s.get("extra_mes") or 0)

    def correr(extra):
        xs = [dict(c) for c in cr]
        mes, intereses, orden = 0, 0.0, []
        while any(x["saldo"] > 1 for x in xs) and mes < 600:
            mes += 1
            libre = extra
            for x in sorted(xs, key=lambda x: -x["tasa"]):   # lo extra (y lo que libera cada crédito pagado) a la de mayor tasa
                if x["saldo"] <= 1: libre += x["cuota"]; continue
                inter = x["saldo"] * ((1 + x["tasa"]) ** (1 / 12) - 1)
                intereses += inter
                pago = min(x["cuota"], x["saldo"] + inter)
                x["saldo"] += inter - pago
                libre += x["cuota"] - pago
            for x in sorted(xs, key=lambda x: -x["tasa"]):
                if x["saldo"] > 1 and libre > 0:
                    a = min(libre, x["saldo"]); x["saldo"] -= a; libre -= a
                if x["saldo"] <= 1 and x["nombre"] not in [o[0] for o in orden]:
                    orden.append((x["nombre"], mes))
        return mes, intereses, orden
    m0, i0, _ = correr(0)
    m1, i1, orden = correr(extra)
    out = {"meses_sin": m0, "meses_con": m1, "intereses_sin": round(i0), "intereses_con": round(i1), "ahorro_intereses": round(i0 - i1),
           "termina_con": _sumar_meses(hoy, m1).isoformat()[:7], "orden": [{"credito": n, "pagado_en": _sumar_meses(hoy, m).isoformat()[:7]} for n, m in orden]}
    txt = (f"Solo con las cuotas sales de tus créditos en {_mes_txt(_sumar_meses(hoy, m0))}."
           + (f" Con {_f(extra)} extra al mes, siempre a la de mayor tasa (y lo que libera cada una a la siguiente), sales en "
              f"{_mes_txt(_sumar_meses(hoy, m1))} y te ahorras {_f(i0 - i1)} de intereses. Orden: " + ", ".join(f"{n} ({_mes_txt(_sumar_meses(hoy, m))})" for n, m in orden) + "." if extra else ""))
    return out, txt


def recortar(s, res, hoy):
    _, cats, meses = _promedios(res, hoy)
    c = _buscar([{"nombre": k, "v": v} for k, v in cats.items()], s.get("categoria"))
    if not c:
        return {"error": "categoria"}, "No encuentro esa categoría en tus últimos meses. Tus categorías: " + ", ".join(sorted(cats)) + "."
    pct = float(s.get("porcentaje") or 0) / 100
    out = {"categoria": c["nombre"], "promedio_mes": round(c["v"]), "ahorro_mes": round(c["v"] * pct), "ahorro_ano": round(c["v"] * pct * 12), "meses_base": meses}
    txt = (f"En {c['nombre']} gastas en promedio {_f(c['v'])} al mes; con {round(pct * 100)} % menos te quedan {_f(c['v'] * pct)} al mes, "
           f"{_f(c['v'] * pct * 12)} al año.")
    return out, txt


def cancelar(s, res, hoy):
    subs = [x for x in ((res.get("analisis") or {}).get("suscripciones") or []) if x.get("activa")]
    x = _buscar(subs, s.get("suscripcion"))
    if not x:
        return {"error": "suscripcion"}, "No la encuentro entre tus suscripciones activas: " + ", ".join(y["nombre"] for y in subs) + "."
    out = {"suscripcion": x["nombre"], "al_mes": x.get("mensual"), "al_ano": x.get("al_ano") or (x.get("mensual") or 0) * 12, "proximo_cobro": x.get("proximo_cobro")}
    txt = f"Cancelando {x['nombre']} ahorras {_f(out['al_mes'])} al mes, {_f(out['al_ano'])} al año" + (f"; cancélala antes del {_dia(x['proximo_cobro'])} para que no cobre otra vez." if x.get("proximo_cobro") else ".")
    return out, txt


TIPOS = {"me_alcanza": me_alcanza, "ahorrar_para": ahorrar_para, "abono_extra": abono_extra, "salir_de_deudas": salir_de_deudas,
         "recortar": recortar, "cancelar": cancelar}


def correr(sims, res, hoy=None):
    hoy = hoy or datetime.date.today()
    out = []
    for s in sims or []:
        f = TIPOS.get(s.get("tipo"))
        if not f:
            out.append({"tipo": s.get("tipo"), "entrada": s, "error": "tipo", "texto": "Tipos: " + ", ".join(TIPOS) + "."})
            continue
        try:
            resultado, texto = f(s, res, hoy)
            out.append({"tipo": s["tipo"], "entrada": s, "resultado": resultado, "texto": texto})
        except Exception as e:   # una simulación mal armada no tumba la actualización
            out.append({"tipo": s.get("tipo"), "entrada": s, "error": str(e)[:200], "texto": "No pude simularlo: revisa los datos."})
    return out
