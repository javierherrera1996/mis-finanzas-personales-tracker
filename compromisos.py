"""Compromisos del mes: cada pago y cobro del usuario (Fijos, cuotas de créditos, tarjetas y suscripciones) con su estado
y CÓMO se sabe (la prueba), para que se dé cuenta solo de qué está y qué no.

Viene del especialista de Compromisos de la versión original (libro.py), sin nada de un usuario en el código: los pagos,
las tarjetas, las suscripciones y las marcas a mano llegan como datos. Solo librería estándar: corre igual en el
computador y dentro de la skill de claude.ai.

Estados: pagado · pagado_probable · parcial · pendiente · vence_pronto · atrasado (y para lo que entra: recibido ·
recibido_probable · por_recibir · no_ha_llegado; tarjetas sin datos: sin_datos; suscripciones: cobrado · por_debitar ·
no_cobrado; descuentos de nómina: automatico). Un atrasado no desaparece hasta que aparezca el pago o lo marques."""
import calendar
import datetime
import re

import agente

# Cómo se agrupa cada estado: atencion (hay que mirar) · por_hacer (aún no toca) · listo (ya pasó)
GRUPO = {"atrasado": "atencion", "vence_pronto": "atencion", "parcial": "atencion", "no_ha_llegado": "atencion",
         "sin_datos": "atencion", "sin_confirmar": "atencion", "no_cobrado": "atencion",
         "pendiente": "por_hacer", "por_recibir": "por_hacer", "por_confirmar": "por_hacer", "por_debitar": "por_hacer",
         "pagado": "listo", "pagado_probable": "listo", "recibido": "listo", "recibido_probable": "listo",
         "automatico": "listo", "cobrado": "listo", "saltado": "listo"}

ENTRA = ("ingreso", "cobro")


def _iso(d):
    return d.isoformat()


def _f(v):
    return "$" + f"{round(v):,}".replace(",", ".")


def _dia(iso):
    d = datetime.date.fromisoformat(str(iso)[:10])
    return f"{d.day}-{['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'][d.month - 1]}"


def _mes_sig(y, m):
    return (y + 1, 1) if m == 12 else (y, m + 1)


def _mes_ant(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def _clave(periodo, nombre):
    return f"{periodo}|{nombre}"


def _coincide(p, mv):
    """¿Este movimiento es un pago (o cobro) de p? Por el texto 'buscar' y el signo."""
    if not p.get("buscar") or mv.get("Fuente", "").startswith("Descuento de nómina") or abs(mv["Valor"]) < 1000:
        return False
    texto = " ".join(str(mv.get(k) or "") for k in ("Descripción", "Subcategoría", "Tu nota"))
    if not re.search(p["buscar"], texto, re.I):
        return False
    return mv["Valor"] > 0 if p["tipo"] in ENTRA else mv["Valor"] < 0


def _prueba(it):
    """Cómo sabe el estado, para que el usuario (y Claude) sepan cuánto confiar."""
    if it.get("marcado_a_mano"): return "lo marcaste tú"
    if it["estado"] in ("pagado_probable", "recibido_probable"): return "deducido por el monto (confírmalo)"
    if it["tipo"] == "tarjeta":
        if it["estado"] == "sin_datos": return "no sé cuánto debes: dímelo"
        if it.get("estimado"): return "estimado con las compras que avisó la tarjeta (dime cuánto debes)"
        return "lo que debías + compras − pagos que vi"
    if it["tipo"] == "suscripcion": return "cobro en la tarjeta o cuenta" if it.get("evidencia") else "aún no aparece el cobro"
    if it["estado"] == "automatico": return "descuento de nómina (no se ve; se asume)"
    if it["estado"] == "sin_confirmar": return "no lo veo en tus alertas (confírmalo)"
    if it.get("evidencia"): return "movimiento del banco" + (" (monto bajo lo esperado)" if it["estado"] == "parcial" else "")
    return "no aparece ningún pago"


def _vence_tarjeta(t, hoy):
    """Fecha límite que toca: la que calculó el motor o, si ya no debe nada, la próxima con su día de pago."""
    if t.get("vence"):
        return datetime.date.fromisoformat(t["vence"])
    d = t.get("dia_pago")
    if not isinstance(d, int):
        return None
    v = datetime.date(hoy.year, hoy.month, min(d, calendar.monthrange(hoy.year, hoy.month)[1]))
    if v < hoy:
        y, m = _mes_sig(hoy.year, hoy.month)
        v = datetime.date(y, m, min(d, calendar.monthrange(y, m)[1]))
    return v


def lista(movs, pagos, tarjetas=(), suscripciones=(), marcas=None, hoy=None, hasta=None, historia_desde=None):
    """Compromisos del mes anterior, este y lo que vence en los próximos 10 días (o hasta `hasta`).

    movs: movimientos con las columnas del motor (Fecha, Valor, Descripción, Fuente, Categoría, ID…).
    pagos: lista de pagos_config (nombre, dia, monto, tipo, buscar, automatico, solo_mes). Los de tipo "tarjeta" se
      ignoran: las tarjetas salen de `tarjetas` (lo que se debe hoy), no de buscar texto.
    tarjetas: las del motor (nombre, deuda, vence, dia_pago, estimada).
    suscripciones: las de analisis.suscripciones (nombre, mensual, proximo_cobro, ultimo_cobro, ultimo_monto, activa).
    marcas: {id: {"estado": "pagado|saltado|…", "nota": "…"}}, lo que el usuario marcó a mano (gana siempre).
    Un movimiento cuenta para el periodo cuya ventana lo contiene: desde 10 días antes del vencimiento hasta 10 días
    antes del siguiente (así un pago adelantado cuenta).
    historia_desde: desde qué fecha hay correos leídos (la configuración empieza con 1–2 semanas y completa hacia atrás):
      un periodo cuya ventana empieza antes no se puede afirmar como atrasado si no aparece el pago."""
    hoy = hoy or agente.HOY
    marcas = marcas or {}
    y, m = hoy.year, hoy.month
    meses = [_mes_ant(y, m), (y, m), _mes_sig(y, m)]
    desde = datetime.date(*meses[0], 1)
    tope = max(datetime.date(y, m, calendar.monthrange(y, m)[1]), hoy + datetime.timedelta(days=10))
    if hasta:
        tope = max(tope, hasta)
    out, usados = [], set()   # usados: un mismo movimiento no puede pagar "probablemente" dos compromisos
    for p in pagos:
        if p.get("tipo") == "tarjeta" or p.get("dia") in (None, ""):
            continue
        entra = p["tipo"] in ENTRA
        cand = sorted([mv for mv in movs if _coincide(p, mv)], key=lambda mv: mv["Fecha"])
        try:
            esperado = agente.monto_real(p, movs) or p.get("monto")
        except Exception:
            esperado = p.get("monto")
        for (yy, mm) in meses:
            per = f"{yy}-{mm:02d}"
            if p.get("solo_mes") and p["solo_mes"] != per:
                continue
            f0 = agente.fecha_pago(p, yy, mm)
            if f0 < desde or f0 > tope:
                continue
            f1 = agente.fecha_pago(p, *_mes_sig(yy, mm))
            ini, fin = f0 - datetime.timedelta(days=10), f1 - datetime.timedelta(days=10)
            it = {"id": _clave(per, p["nombre"]), "nombre": p["nombre"], "tipo": p["tipo"], "periodo": per, "vence": _iso(f0),
                  "monto_esperado": round(esperado) if esperado else None, "como": p.get("como"),
                  "automatico": bool(p.get("automatico")), "ventana": [_iso(ini), _iso(fin - datetime.timedelta(days=1))]}
            hits = [mv for mv in cand if _iso(ini) <= mv["Fecha"] < _iso(fin)]
            probable = None
            if not hits and esperado and not p.get("automatico"):
                # La alerta no siempre dice a quién le pagaste ("Transferencia a la cuenta *1234"): un movimiento sin
                # clasificar por casi el mismo valor (±2 %) dentro de la ventana es, muy probablemente, este pago.
                cands = [mv for mv in movs if mv.get("Categoría") in agente.CATS_DUDOSAS and not mv.get("Categoría manual")
                         and (mv["Valor"] > 0 if entra else mv["Valor"] < 0) and _iso(ini) <= mv["Fecha"] < _iso(fin)
                         and abs(abs(mv["Valor"]) - esperado) <= 0.02 * esperado and mv.get("ID") not in usados]
                if cands:
                    probable = cands[0]
                    usados.add(probable.get("ID"))
                    hits = [probable]
            pagado = sum(abs(mv["Valor"]) for mv in hits)
            it["pagado"] = round(pagado)
            it["evidencia"] = [{"id": mv.get("ID"), "fecha": mv["Fecha"], "valor": abs(mv["Valor"]),
                                "descripcion": str(mv.get("Descripción", ""))[:80]} for mv in hits]
            if probable:
                est = "recibido_probable" if entra else "pagado_probable"
                it["deduccion"] = (f"No veo a quién fue, pero el {_dia(probable['Fecha'])} {'entraron' if entra else 'salieron'} "
                                   f"{_f(abs(probable['Valor']))}, casi igual a lo esperado ({_f(esperado)}). Lo doy por "
                                   f"{'recibido' if entra else 'pagado'} hasta que digas lo contrario.")
            elif pagado and (not esperado or pagado >= 0.85 * esperado):
                est = "recibido" if entra else "pagado"
            elif pagado:
                est = "parcial"
            elif f0 > hoy:
                est = "por_recibir" if entra else ("vence_pronto" if (f0 - hoy).days <= 3 else "pendiente")
            elif p.get("automatico"):
                est = "automatico" if not p.get("buscar") else ("sin_confirmar" if (hoy - f0).days > 3 else "por_confirmar")
            elif not p.get("buscar") or (not cand and (yy, mm) < (y, m)) or (historia_desde and _iso(ini) < historia_desde):
                # No se puede saber: no dice cómo aparece en el banco, o es de un mes anterior y nunca se ha visto un pago
                # de esto (lo acaba de registrar, o lo paga por un camino sin alertas). Se pregunta; no se alarma.
                est = "sin_confirmar"
                it["nota"] = ("No sé cómo aparece este pago en tus alertas: dime cómo lo pagas." if not p.get("buscar")
                              else "No veo ningún pago de esto en tus alertas: ¿lo pagas por otro lado?")
            elif entra:
                est = "no_ha_llegado" if (hoy - f0).days >= 2 else "por_recibir"
            else:
                est = "atrasado"
            it["estado"] = est
            if est == "atrasado":
                it["dias_atraso"] = (hoy - f0).days
            if it["monto_esperado"]:
                it["falta"] = max(0, it["monto_esperado"] - it["pagado"]) if est in ("parcial", "pendiente", "vence_pronto", "atrasado") else 0
            out.append(it)

    for t in tarjetas:   # lo que se debe hoy en cada tarjeta (extracto o saldo confirmado + compras − pagos)
        vence = _vence_tarjeta(t, hoy)
        it = {"nombre": t["nombre"], "tipo": "tarjeta", "vence": _iso(vence) if vence else None, "automatico": False,
              "monto_esperado": t.get("deuda"), "falta": t.get("deuda"), "pagado": 0, "estimado": bool(t.get("estimada"))}
        it["periodo"] = it["vence"][:7] if it["vence"] else f"{y}-{m:02d}"
        it["id"] = _clave(it["periodo"], t["nombre"])
        if t.get("deuda") is None:
            it["estado"] = "sin_datos"
        elif t["deuda"] <= 1000:
            it.update(estado="pagado", falta=0)
        elif vence is None:
            it["estado"] = "pendiente"
            it["nota"] = "No sé su día límite de pago."
        elif vence < hoy:
            it.update(estado="atrasado", dias_atraso=(hoy - vence).days)
        else:
            it["estado"] = "vence_pronto" if (vence - hoy).days <= 3 else "pendiente"
        out.append(it)

    for s in suscripciones:   # se cobran solas: solo hay que mirar si no cobraron o si cobraron de más
        if not s.get("activa"):
            continue
        ult = datetime.date.fromisoformat(s["ultimo_cobro"]) if s.get("ultimo_cobro") else None
        prox = datetime.date.fromisoformat(s["proximo_cobro"]) if s.get("proximo_cobro") else None
        it = {"nombre": s["nombre"], "tipo": "suscripcion", "automatico": True, "monto_esperado": s.get("mensual"),
              "como": s.get("tarjeta"), "pagado": 0, "evidencia": []}
        if ult and (hoy - ult).days < 25:
            it.update(vence=_iso(ult), estado="cobrado", pagado=round(s.get("ultimo_monto") or 0),
                      evidencia=[{"fecha": _iso(ult), "valor": s.get("ultimo_monto"), "descripcion": s.get("tarjeta", "")}])
        elif prox and prox >= hoy - datetime.timedelta(days=3):
            if prox > tope:
                continue
            it.update(vence=_iso(prox), estado="por_debitar")
        else:
            it.update(vence=_iso(prox) if prox else None, estado="no_cobrado",
                      nota="No ha cobrado cuando tocaba: ¿la cancelaste o falló la tarjeta?")
        it["periodo"] = (it["vence"] or _iso(hoy))[:7]
        it["id"] = _clave(it["periodo"], s["nombre"])
        out.append(it)

    for it in out:
        mk = marcas.get(it["id"])
        if mk:   # lo que el usuario marcó a mano gana: {"estado": "pagado|saltado|…", "nota"}
            it.update({"estado": mk.get("estado", it["estado"]), "nota": mk.get("nota") or it.get("nota"), "marcado_a_mano": True})
            if it["estado"] in ("pagado", "saltado", "recibido"):
                it["falta"] = 0
        it["grupo"] = GRUPO.get(it["estado"], "por_hacer")
        it["prueba"] = _prueba(it)
    out.sort(key=lambda i: (i["vence"] or "9999", i["nombre"]))
    return out


def resumen(items, hoy=None):
    """Cuántos hay en cada grupo y cuánta plata falta pagar de lo que ya venció o vence este mes."""
    hoy = hoy or agente.HOY
    fin_mes = _iso(datetime.date(hoy.year, hoy.month, calendar.monthrange(hoy.year, hoy.month)[1]))
    sale = [i for i in items if i["tipo"] not in ENTRA and i["grupo"] != "listo" and (i.get("vence") or "") <= fin_mes]
    return {"atencion": sum(1 for i in items if i["grupo"] == "atencion"),
            "por_hacer": sum(1 for i in items if i["grupo"] == "por_hacer"),
            "listo": sum(1 for i in items if i["grupo"] == "listo"),
            "atrasados": [i["nombre"] for i in items if i["estado"] == "atrasado"],
            "falta_pagar_este_mes": round(sum(i.get("falta") or 0 for i in sale)),
            "sin_monto": [i["nombre"] for i in sale if i.get("falta") is None]}
