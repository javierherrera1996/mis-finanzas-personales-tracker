"""Los datos del tablero (artifact) de cada usuario, a partir de lo que devuelve el motor.

Claude los guarda en el almacén del artifact en cada actualización, en tres documentos:
  tablero/resumen      lo de arriba: cuánto puede gastar por día, lo que falta pagar, avisos, gasto del mes,
                       suscripciones y deudas
  tablero/compromisos  cada pago del mes con su estado y cómo se sabe
  tablero/movimientos  los movimientos de los últimos 60 días (máximo 1.200, en filas compactas)
Cada documento queda muy por debajo del límite de 256 KiB del almacén. Los botones de la página ("Ya lo pagué",
"No aplica") escriben en marcas/<clave>; la siguiente actualización los pasa a Tu marca del Sheet."""
import datetime
import re

DIAS_MOVS = 60
MAX_MOVS = 1200


def clave(id_):
    """El ID de un compromiso ("2026-11|Arriendo") como nombre de documento válido del almacén."""
    c = re.sub(r"[^A-Za-z0-9_.~:@+-]+", "-", str(id_)).strip("-")
    return (c or "x")[:180]


def armar(res, hoy=None, sheet_url=None):
    hoy = hoy or datetime.date.today()
    r = res.get("resumen", {})
    comps = res.get("compromisos", [])
    an = res.get("analisis", {}) or {}
    avisos = (res.get("avisos") or {}).get("alertas", [])
    ahora = datetime.datetime.now().isoformat(timespec="minutes")
    resumen = {
        "actualizado": ahora, "hoy": hoy.isoformat(), "alertas_hasta": r.get("alertas_hasta"), "sheet_url": sheet_url,
        "kpis": {"plata_en_cuentas": r.get("plata_en_cuentas"), "disponible": r.get("disponible"), "libre": r.get("libre"),
                 "por_dia": r.get("por_dia"), "proximo_sueldo": r.get("proximo_sueldo"), "dias_al_sueldo": r.get("dias_al_sueldo"),
                 "aproximado": bool(r.get("aproximado")), "cuentas_sin_saldo": r.get("cuentas_sin_saldo") or [],
                 "falta_pagar_este_mes": (res.get("compromisos_resumen") or {}).get("falta_pagar_este_mes")},
        "compromisos_resumen": res.get("compromisos_resumen") or {},
        "avisos": [{k: a.get(k) for k in ("id", "severidad", "titulo", "detalle", "accion")} for a in avisos[:12]],
        "gasto_mes": [{"categoria": k, "total": v} for k, v in (r.get("gasto_mes_por_categoria") or {}).items()][:12],
        "gasto_mes_anterior": sum((r.get("gasto_mes_anterior_por_categoria") or {}).values()),
        "suscripciones": [{"nombre": s.get("nombre"), "mensual": s.get("mensual"), "proximo": s.get("proximo_cobro"),
                           "tarjeta": s.get("tarjeta"), "subio": bool(s.get("cambio_precio"))}
                          for s in an.get("suscripciones") or [] if s.get("activa")][:20],
        "suscripciones_total": an.get("suscripciones_total"),
        "deudas": [{"nombre": d.get("nombre"), "saldo": d.get("saldo"), "tasa_ea": d.get("tasa_ea"), "interes_mes": d.get("interes_mes"),
                    "abonar_aqui": bool(d.get("abonar_aqui"))} for d in ((res.get("deudas") or {}).get("deudas") or [])][:12],
        "tarjetas": [{"nombre": t.get("nombre"), "deuda": t.get("deuda"), "vence": t.get("vence"), "corte": t.get("corte"),
                      "estimada": bool(t.get("estimada"))} for t in res.get("tarjetas") or []],
    }
    compromisos = {"actualizado": ahora, "items": [
        {"clave": clave(c["id"]), "id": c["id"], "nombre": c["nombre"], "tipo": c["tipo"], "vence": c.get("vence"),
         "esperado": c.get("monto_esperado"), "pagado": c.get("pagado"), "falta": c.get("falta"), "estado": c["estado"],
         "grupo": c.get("grupo"), "prueba": c.get("prueba"), "nota": c.get("nota") or c.get("deduccion"),
         "marcado": bool(c.get("marcado_a_mano"))} for c in comps]}
    desde = (hoy - datetime.timedelta(days=DIAS_MOVS)).isoformat()
    movs = [m for m in res.get("movimientos") or [] if m.get("Fecha", "") >= desde]
    movs.sort(key=lambda m: (m["Fecha"], m.get("ID", "")), reverse=True)
    movimientos = {"actualizado": ahora, "desde": desde,
                   "columnas": ["fecha", "valor", "descripcion", "categoria", "tipo", "cuenta", "id"],
                   "filas": [[m["Fecha"], m["Valor"], str(m.get("Descripción", ""))[:90],
                              m.get("Categoría manual") or m.get("Categoría", ""), m.get("Tipo manual") or m.get("Tipo", ""),
                              str(m.get("Fuente", "")).replace(" (alerta)", ""), m.get("ID")] for m in movs[:MAX_MOVS]]}
    return {"resumen": resumen, "compromisos": compromisos, "movimientos": movimientos}
