"""Motor de la skill: corre los mismos lectores, reglas, traslados entre cuentas propias y cálculo de caja de la versión
instalada sobre las alertas que Claude trae con el conector de Gmail. Claude no clasifica ni suma: arma la entrada y copia
la salida al Sheet.

Uso: python motor/procesar.py entrada.json salida.json

entrada.json:
  config               el mismo formato de config.json (cuentas con su saldo, sueldo, nombre_en_bancos, documento…)
  reglas               [{si_aparece, tipo, categoria, subcategoria}]: la pestaña Reglas (texto, no regex)
  fijos                [{nombre, dia, monto, tipo: pago|cobro, buscar}]: la pestaña Fijos (opcional; el sueldo va en config)
  creditos             [{nombre, entidad, saldo, fecha_saldo, tasa_ea, cuota, dia_pago, descuento_nomina, buscar}]: pestaña Créditos
  apartado             plata apartada que no se gasta, en pesos (opcional)
  correos              [{id, fecha, de, asunto, texto, estado?, extraido?}]: filas de la pestaña Correos o recién traídas de
                       Gmail (texto tal cual). extraido = {fecha, valor, descripcion, institucion, producto} si Claude leyó un
                       correo de un banco sin lector; estado "no es movimiento" si Claude ya lo descartó
  movimientos_extra    [{fecha, valor, descripcion, institucion, producto}]: movimientos sin correo
  movimientos_previos  filas que ya están en Movimientos (con Categoría manual, Tipo manual y Tu nota)
  correcciones         {ID: {categoria, subcategoria, tipo, nota}}: las columnas tuyas de Movimientos, para reclasificar todo
  notas_ids            ids de la pestaña Notas (lo que ya se anotó), para marcar qué descubrimientos son nuevos
  objetivo             lo que quiere lograr: saber | gastar_menos | deudas | ahorrar (ordena las acciones)
  ofertas              [{credito, entidad, tasa_ea, costos, condiciones, fuente, fecha}]: tasas que Claude encontró en internet
  tasa_usura           la tasa de usura vigente (Superfinanciera), para marcar deudas por encima
  suscripciones_canceladas  [{nombre, desde}]: las que el usuario canceló, para avisar si siguen cobrando

Dos usos: diario (correos nuevos + los de los últimos días, y movimientos_previos) o reclasificar todo (toda la pestaña
Correos, sin movimientos_previos, con correcciones). Sin correos y con las filas de un período en movimientos_previos,
analiza ese período.

salida.json: nuevos (filas para agregar a Movimientos), actualizar (filas que ya estaban y cambiaron), movimientos (todas,
para reescribir la pestaña al reclasificar), correos_registro (filas de la pestaña Correos con su estado), no_leidos,
cuentas, tarjetas, resumen, deudas, proximos_pagos, calendario, analisis, descubrimientos, faltantes, sueldo_probable,
cobertura (cómo están los datos de cada cuenta), acciones (qué hacer primero), comparacion_ofertas (cuánto ahorraría con
cada oferta) e informe."""
import datetime, html, json, os, re, shutil, sys, tempfile
import reportes

MOTOR = os.path.dirname(os.path.abspath(__file__))
COLUMNAS = ["Fecha", "Valor", "Descripción", "Comercio", "Fuente", "Tipo", "Categoría", "Subcategoría", "Categoría manual", "Tipo manual",
            "Tu nota", "Contraparte", "Correo", "ID"]
ETIQUETAS_DAVI = r"(Fecha:|Hora:|Valor Transacci[oó]n:|Clase de Movimiento:|Respuesta:|Lugar de Transacci[oó]n:|Atentamente)"


def fecha_iso(x):
    """'2026-10-07', '2026/10/07', '07/10/2026' o segundos desde 1970 -> '2026-10-07'."""
    if isinstance(x, (int, float)): return datetime.date.fromtimestamp(x).isoformat()
    x = str(x).strip()[:10]
    m = re.match(r"(\d{4})[-/](\d{2})[-/](\d{2})", x)
    if m: return "-".join(m.groups())
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", x)
    if m: return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    raise ValueError(f"fecha que no entiendo: {x}")


def texto_plano(t):
    """El texto del correo como lo deja fetch.py: sin HTML y sin líneas vacías."""
    t = t or ""
    if re.search(r"<(html|body|div|table|p|br)\b", t, re.I):
        t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
        t = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|td|li|h\d)>", "\n", t)
        t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def preparar_correo(c):
    de, texto = c.get("de") or c.get("from") or "", texto_plano(c.get("texto") or c.get("body") or "")
    davi = "banco_davivienda@" in de.lower()
    if davi:   # el lector de Davivienda separa los campos por línea: si el texto llegó en una sola, se las devuelve
        de = "BANCO_DAVIVIENDA@davivienda.com"     # con \r\n, como vienen en el correo original, para dar el mismo texto
        texto = re.sub(r"(?<![\n \t])[ \t]*(?=" + ETIQUETAS_DAVI + ")", "\r\n", texto)
    fecha = c.get("fecha") or c.get("date")
    ts = fecha if isinstance(fecha, (int, float)) else int(datetime.datetime.fromisoformat(fecha_iso(fecha) + "T12:00:00").timestamp())
    return ("davivienda" if davi else "otros"), {"id": str(c["id"]), "date": ts, "from": de, "subject": c.get("asunto") or c.get("subject") or "",
                                                  "body": texto, "atts": []}


def cuenta_de(m, cuentas):
    """La cuenta del mapa a la que pertenece un movimiento leído por Claude (institución + terminación o celular)."""
    inst, prod = (m.get("institucion") or "Otro").strip(), str(m.get("producto") or "").strip().lstrip("*")
    c = next((x for x in cuentas if x.get("institucion", "").lower() == inst.lower() and prod
              and prod in (str(x.get("terminacion", "")), str(x.get("celular", "")), str(x.get("tarjeta_debito", "")))), None)
    if c is None and not prod:
        c = next((x for x in cuentas if x.get("institucion", "").lower() == inst.lower()), None)
    return c


def fuente_extra(m, cuentas):
    """Fuente con el formato del motor ("Nequi Ahorros *3109998877", "Nu TC *1234") para que el saldo caiga en su cuenta."""
    inst, prod = (m.get("institucion") or "Otro").strip(), str(m.get("producto") or "").strip().lstrip("*")
    c = cuenta_de(m, cuentas)
    tipo = "TC" if c and c.get("tipo") == "tarjeta_credito" else "Ahorros"
    term = prod or (c and (c.get("terminacion") or c.get("celular"))) or ""
    return f"{inst} {tipo}" + (f" *{term}" if term else "")


def lectura(correos, repetidos):
    """Cuántos correos llegaron por banco y por semana: para comparar con lo que muestra Gmail y saber si faltan."""
    por_banco, por_semana = {}, {}
    for _, c in correos:
        dom = re.sub(r".*@", "", re.sub(r"[<>\s]", "", c["from"].split("<")[-1])).lower() or "?"
        banco = next((b for b in ("davivienda", "bancolombia", "nequi", "nu.com", "daviplata", "lulo", "rappi", "bbva") if b in dom), dom)
        por_banco[banco] = por_banco.get(banco, 0) + 1
        d = datetime.date.fromisoformat(fecha_iso(c["date"]))
        lunes = (d - datetime.timedelta(days=d.weekday())).isoformat()
        por_semana[lunes] = por_semana.get(lunes, 0) + 1
    fechas = sorted(fecha_iso(c["date"]) for _, c in correos)
    return {"correos": len(correos), "repetidos_descartados": repetidos, "por_banco": por_banco,
            "por_semana_desde_el_lunes": dict(sorted(por_semana.items())), "desde": fechas[0] if fechas else None,
            "hasta": fechas[-1] if fechas else None}


def registro_correos(entrada, correos, leidos, movs):
    """Filas de la pestaña Correos (el registro crudo): cada correo con su estado y los movimientos que salieron de él."""
    por_correo = {}
    for r in movs:
        if r.get("Correo"): por_correo.setdefault(r["Correo"], []).append(r["ID"])
    previo = {str(c["id"]): c for c in entrada}
    out = []
    for _, c in correos:
        p = previo.get(c["id"], {})
        if c["id"] in leidos: estado = "movimiento"
        elif p.get("extraido"): estado = "lo leyó Claude"
        elif (p.get("estado") or "").startswith("no es"): estado = "no es movimiento"
        else: estado = "sin leer"
        out.append({"ID del correo": c["id"], "Fecha": fecha_iso(c["date"]), "Remitente": p.get("de") or p.get("from") or c["from"],
                    "Asunto": c["subject"], "Texto": p.get("texto") or p.get("body") or c["body"], "Estado": estado,
                    "Movimientos": ", ".join(por_correo.get(c["id"], []))})
    return out


def productos_vistos(movs):
    """Productos que aparecen en las alertas (institución, terminación y si parece cuenta o tarjeta): para armar la tabla
    del primer uso cuando todavía no hay cuentas configuradas."""
    out = {}
    for r in movs:
        m = re.match(r"(\S+) (?:TC|Ahorros) \*(\w+)", r["Fuente"])
        if not m: continue
        d = r["Descripción"]
        # la terminación que dice la alerta manda: un lector puede asignarle a la cuenta una tarjeta que no está en el mapa
        tc = re.search(r"T\.? ?Cred(?:ito)?\s*(?:MASTER\s*)?\*+(\d{4})|tarjeta de cr[eé]dito (?:MASTER )?\*+(\d{4})", d, re.I)
        td = re.search(r"T\.? ?Deb\s*\*+(\d{4})", d, re.I)
        if tc: term, pista = next(g for g in tc.groups() if g), "tarjeta de crédito"
        elif td: term, pista = td.group(1), "tarjeta débito"
        else: term, pista = m.group(2), "tarjeta de crédito" if " TC " in r["Fuente"] else "cuenta"
        x = out.setdefault((m.group(1), term), {"institucion": m.group(1), "terminacion": term, "pista": pista, "movimientos": 0})
        x["movimientos"] += 1
    return sorted(out.values(), key=lambda x: -x["movimientos"])


def dia_de_pago(x):
    """'penúltimo hábil', 'penultimo_habil', 30, '30' -> 'penultimo_habil' o 30 (None si no es un día)."""
    t = str(x or "").strip().lower()
    if re.match(r"pen[uú]ltimo", t): return "penultimo_habil"
    return int(t) if t.isdigit() and 1 <= int(t) <= 31 else None


def es_fijo(p):
    """Solo pagos y cobros del mes con día: el sueldo, la plata apartada o el techo no son pagos (si llegan aquí, se ignoran)."""
    return (str(p.get("tipo") or "pago").lower() in ("pago", "cobro") and dia_de_pago(p.get("dia")) is not None
            and not re.search(r"sueldo|salario|apartad|techo", str(p.get("nombre", "")), re.I))


def fijo(p):
    """Fila de la pestaña Fijos -> pago de data/pagos_config.json. 'buscar' es texto tal como sale en el banco (no regex)."""
    tipo = str(p.get("tipo") or "pago").lower()
    dia = dia_de_pago(p.get("dia"))
    return {"nombre": p["nombre"], "dia": dia, "monto": float(p.get("monto") or 0), "como": p.get("como", ""), "automatico": False,
            "tipo": "servicio" if tipo == "pago" else tipo, "buscar": re.escape(p["buscar"].strip()) if p.get("buscar") else ""}


def fila_previa(r):
    f = fecha_iso(r["Fecha"])
    x = {"Fecha": f, "Mes": f[:7], "Fuente": r.get("Fuente", ""), "Descripción": r.get("Descripción", ""),
         "Comercio": r.get("Comercio", ""), "Valor": float(r["Valor"]), "Tipo": r.get("Tipo", ""), "Categoría": r.get("Categoría", ""),
         "Subcategoría": r.get("Subcategoría", ""), "Contraparte": r.get("Contraparte", ""), "Correo": r.get("Correo", ""), "ID": r.get("ID", ""),
         "Categoría manual": r.get("Categoría manual", ""), "Tipo manual": r.get("Tipo manual", ""), "Tu nota": r.get("Tu nota") or r.get("Nota", "")}
    if x["Categoría manual"]: x["Categoría"] = x["Categoría manual"]   # las columnas del usuario mandan
    if x["Tipo manual"]: x["Tipo"] = x["Tipo manual"]
    return x


def main(entrada, salida):
    e = json.load(open(entrada))
    trabajo = tempfile.mkdtemp(prefix="finanzas-")
    os.makedirs(os.path.join(trabajo, "data"))
    for f in os.listdir(os.path.join(MOTOR, "data_inicial")):
        # copyfile y no copy: si la skill es de solo lectura, copy también copia el permiso y no se podrían reescribir
        shutil.copyfile(os.path.join(MOTOR, "data_inicial", f), os.path.join(trabajo, "data", f))
    cfg = dict(e["config"])
    cfg["cuentas"] = [dict(x) for x in cfg.get("cuentas", [])]
    cfg.setdefault("techo_gasto_mes", 0)   # sin techo no se compara (el motor instalado supone $6.000.000)
    sueldo = dict(cfg.get("sueldo") or {})
    if sueldo.get("dia_pago") is not None:
        sueldo["dia_pago"] = dia_de_pago(sueldo["dia_pago"]) or "penultimo_habil"
    cfg["sueldo"] = sueldo
    for x in cfg["cuentas"]:
        for k in ("dia_pago", "dia_corte"):
            if x.get(k) is not None: x[k] = dia_de_pago(x[k])
    # pestaña Reglas: texto tal como sale en la descripción (no regex), antes de las reglas generales
    cfg["reglas_personales"] = [[re.escape(r["si_aparece"].strip()), r.get("tipo") or "Gasto", r.get("categoria") or "Otros", r.get("subcategoria") or ""]
                                for r in e.get("reglas", []) if (r.get("si_aparece") or "").strip()] + cfg.get("reglas_personales", [])
    # una regla de Gasto que trae plata (el roomie que paga su parte) resta de ese gasto en vez de contar como ingreso
    cfg["netear_con"] = cfg.get("netear_con", []) + [re.escape(r.get("subcategoria") or r.get("categoria") or "")
                                                     for r in e.get("reglas", []) if r.get("tipo") == "Gasto" and (r.get("subcategoria") or r.get("categoria"))]
    for m in e.get("movimientos_extra", []):   # si Claude lee sus alertas, sus movimientos mueven el saldo
        c = cuenta_de(m, cfg["cuentas"])
        if c is not None: c.setdefault("se_lee", True)
    # un correo que llega dos veces (dos páginas o dos hilos que se solapan) sería un movimiento repetido
    vistos, correos = set(), []
    for c in e.get("correos", []):
        if str(c["id"]) not in vistos:
            vistos.add(str(c["id"]))
            correos.append(preparar_correo(c))
    repetidos = len(e.get("correos", [])) - len(correos)
    fechas = ([fecha_iso(c["date"]) for _, c in correos] + [fecha_iso(m["fecha"]) for m in e.get("movimientos_extra", [])]
              + [fecha_iso(c["extraido"]["fecha"]) for c in e.get("correos", []) if c.get("extraido")])
    cfg["desde"] = min(fechas + [cfg.get("desde") or "9999"])
    json.dump(cfg, open(os.path.join(trabajo, "config.json"), "w"), ensure_ascii=False)
    for nombre in ("davivienda", "otros"):
        with open(os.path.join(trabajo, "data", nombre + ".jsonl"), "w") as f:
            for n, c in correos:
                if n == nombre: f.write(json.dumps(c, ensure_ascii=False) + "\n")
    leidos_claude = [dict(c["extraido"], correo=str(c["id"])) for c in e.get("correos", []) if c.get("extraido")]
    for m in leidos_claude:
        c = cuenta_de(m, cfg["cuentas"])
        if c is not None: c.setdefault("se_lee", True)
    extra = [{"fuente": fuente_extra(m, cfg.get("cuentas", [])), "cuenta": str(m.get("producto") or ""), "fecha": fecha_iso(m["fecha"]),
              "valor": float(m["valor"]), "desc": m.get("descripcion", ""), "correo": m.get("correo", "")}
             for m in e.get("movimientos_extra", []) + leidos_claude]
    json.dump(extra, open(os.path.join(trabajo, "data", "movimientos_extra.json"), "w"), ensure_ascii=False)
    # créditos: van a deudas (tasa, intereses, dónde abonar) y su cuota al calendario de pagos (si es de nómina, sale sola)
    creditos = [reportes.credito(x) for x in e.get("creditos", [])]
    json.dump({"creditos": [{"nombre": x["nombre"], "saldo": x["saldo"], "tasa_ea": x["tasa_ea"], "cuota_total": x["cuota"],
                             "descuento_nomina": x["descuento_nomina"]} for x in creditos]},
              open(os.path.join(trabajo, "data", "deudas_config.json"), "w"), ensure_ascii=False)
    pc = json.load(open(os.path.join(trabajo, "data", "pagos_config.json")))
    pc["pagos"] = ([p for p in pc["pagos"] if p.get("tipo") == "ingreso"] + [fijo(p) for p in e.get("fijos") or [] if es_fijo(p)]
                   + [{"nombre": "Cuota " + x["nombre"], "dia": dia_de_pago(x["dia_pago"]), "monto": x["cuota"], "como": x["entidad"],
                       "automatico": x["descuento_nomina"], "tipo": "deuda", "buscar": re.escape(x["buscar"].strip()) if x["buscar"] else ""}
                      for x in creditos if dia_de_pago(x["dia_pago"]) and x["cuota"]])
    json.dump(pc, open(os.path.join(trabajo, "data", "pagos_config.json"), "w"), ensure_ascii=False)
    if e.get("apartado"):
        json.dump({"inversion": e["apartado"]}, open(os.path.join(trabajo, "data", "reservas.json"), "w"))
    # las correcciones del usuario (Categoría manual, Tipo manual, Tu nota) se aplican como en la versión instalada
    json.dump({"movimientos": e.get("correcciones") or {}, "respuestas": {}},
              open(os.path.join(trabajo, "data", "overrides.json"), "w"), ensure_ascii=False)

    # el motor lee config.json junto a sus archivos y la carpeta de la skill puede ser de solo lectura: se copia al temporal
    for f in os.listdir(MOTOR):
        if f.endswith(".py") and f != "procesar.py":
            shutil.copyfile(os.path.join(MOTOR, f), os.path.join(trabajo, f))
    os.chdir(trabajo)
    sys.path.insert(0, trabajo)
    import build, parse_davi, parse_otros, agente
    leidos = {a["id"] for a in parse_davi.parse()} | {b["id"] for b in parse_otros.bancolombia()}
    descartados = {str(c["id"]) for c in e.get("correos", []) if (c.get("estado") or "").startswith("no es")}
    con_extraido = {str(c["id"]) for c in e.get("correos", []) if c.get("extraido")}
    nuevos = build.main()
    for r in nuevos:
        tm = (e.get("correcciones") or {}).get(r["ID"], {}).get("tipo", "")
        r["Tipo manual"] = tm
        if tm: r["Tipo"] = tm
    # el sueldo a veces llega como una transferencia sin nombre: si entra lo mismo que el usuario dijo que le llega, es el sueldo
    neto = (cfg.get("sueldo") or {}).get("neto_que_llega") or 0

    def cerca_del_sueldo(fecha):
        fe = datetime.date.fromisoformat(fecha)
        ant = fe.replace(day=1) - datetime.timedelta(days=1)
        return min(abs((fe - agente.dia_sueldo(y, m)).days) for y, m in ((fe.year, fe.month), (ant.year, ant.month))) <= 4

    for r in nuevos:
        if (neto and r["Tipo"] == "Ingreso" and r["Categoría"] in ("Transferencias recibidas", "Otros ingresos") and not r.get("Categoría manual")
                and abs(r["Valor"] - neto) <= 0.05 * neto and cerca_del_sueldo(r["Fecha"])):
            r["Categoría"], r["Subcategoría"] = "Salario", "Sueldo (por el monto y la fecha)"
    # lo que ya estaba en el Sheet: si al volver a leerlo cambió (p. ej. un traslado que ahora tiene su pareja), se actualiza
    previos = [fila_previa(r) for r in e.get("movimientos_previos", [])]
    por_id = {r["ID"]: r for r in previos}
    actualizar = []
    for r in nuevos:
        p = por_id.get(r["ID"])
        if p and not p["Categoría manual"] and not p["Tipo manual"] and any(p.get(k, "") != r.get(k, "") for k in ("Tipo", "Categoría", "Subcategoría", "Contraparte")):
            p.update({k: r.get(k, "") for k in ("Tipo", "Categoría", "Subcategoría", "Contraparte")})
            actualizar.append(p)
    procesados = nuevos
    nuevos = [r for r in nuevos if r["ID"] not in por_id]
    json.dump(previos + nuevos, open("data/movimientos.json", "w"), ensure_ascii=False)

    est = agente.estado()
    c = est["caja"]
    hoy = agente.HOY
    mes = hoy.strftime("%Y-%m")
    mes_ant = (hoy.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
    todos = previos + nuevos

    def por_categoria(m_):
        out = {}
        for r in todos:
            if r["Mes"] == m_ and r["Tipo"] == "Gasto":
                out[r["Categoría"]] = out.get(r["Categoría"], 0) - r["Valor"]
        return dict(sorted(((k, round(v)) for k, v in out.items()), key=lambda i: -i[1]))

    # tarjetas de crédito: lo que debía (saldo en Cuentas) + compras con la tarjeta − pagos desde otras cuentas
    import cuentas as cu
    tarjetas, por_pagar_tc = [], 0
    pp = est["proximo_pago"]
    for p in agente.PRODUCTOS:
        if p["tipo"] != "tarjeta_credito": continue
        s, t = p.get("saldo"), {"nombre": p["nombre"], "deuda": None, "desde": None, "dia_pago": p.get("dia_pago"), "dia_corte": p.get("dia_corte"),
                                "tasa_ea": reportes.tasa(p.get("tasa_ea")) or None, "terminacion": p.get("terminacion")}
        if isinstance(s, dict) and s.get("valor") is not None and s.get("fecha"):
            post = [r for r in todos if r["Fecha"] > s["fecha"]]
            compras = sum(r["Valor"] for r in post if cu.de_fuente(r["Fuente"], agente.PRODUCTOS) is p)
            pagos = sum(r["Valor"] for r in post if r.get("Contraparte") == p["id"])
            t.update(deuda=round(s["valor"] - compras + pagos), desde=s["fecha"])
        else:
            # No sabe cuánto debe ("no sé" en la configuración): estimado con las compras que avisó la tarjeta en el
            # ciclo que ya cortó (lo que se paga en el próximo vencimiento) o, sin día de corte, en los últimos 30 días.
            ini, fin = (hoy - datetime.timedelta(days=30)).isoformat(), hoy.isoformat()
            if isinstance(p.get("dia_corte"), int):
                dc = min(p["dia_corte"], 28)
                ult = datetime.date(hoy.year, hoy.month, dc)
                if ult >= hoy:
                    ult = datetime.date(hoy.year - (hoy.month == 1), (hoy.month - 2) % 12 + 1, dc)
                ant = datetime.date(ult.year - (ult.month == 1), (ult.month - 2) % 12 + 1, dc)
                ini, fin = ant.isoformat(), ult.isoformat()
            compras = -sum(r["Valor"] for r in todos if ini < r["Fecha"] <= fin and r["Valor"] < 0
                           and cu.de_fuente(r["Fuente"], agente.PRODUCTOS) is p)
            if compras > 0:
                t.update(deuda=round(compras), estimada=True, estimada_con=f"compras que avisó la tarjeta del {ini} al {fin}")
        if t["deuda"] is not None:
            if t["deuda"] > 0 and isinstance(p.get("dia_pago"), int):
                d = p["dia_pago"]
                vence = datetime.date(hoy.year, hoy.month, min(d, 28))
                if vence < hoy:
                    vence = datetime.date(hoy.year + hoy.month // 12, hoy.month % 12 + 1, min(d, 28))
                t["vence"] = vence.isoformat()
                if vence < pp:
                    por_pagar_tc += t["deuda"]
                    est["por_pagar_antes_del_sueldo"].append({"nombre": p["nombre"] + (" (estimado)" if t.get("estimada") else ""),
                                                              "fecha": vence, "monto": t["deuda"]})
        if isinstance(p.get("dia_corte"), int):   # lo que se compre después del corte se paga en el extracto siguiente
            dc = p["dia_corte"]
            corte = datetime.date(hoy.year, hoy.month, min(dc, 28))
            if corte < hoy:
                corte = datetime.date(hoy.year + hoy.month // 12, hoy.month % 12 + 1, min(dc, 28))
            t["corte"] = corte.isoformat()
        tarjetas.append(t)
    est["libre"] -= por_pagar_tc
    est["por_dia"] = round(est["libre"] / est["dias_al_pago"])

    hace45 = (hoy - datetime.timedelta(days=45)).isoformat()   # al reclasificar todo no se pregunta por lo viejo
    dudosos = [r["ID"] for r in nuevos if r["Tipo"] in ("Gasto", "Ingreso") and (r["Categoría"] in agente.CATS_DUDOSAS
               or r["Categoría"] == "Otros ingresos") and abs(r["Valor"]) >= 50000 and r["Fecha"] >= hace45
               and not r.get("Categoría manual") and not r.get("Tu nota")]
    res = {
        "nuevos": [{k: r.get(k, "") for k in COLUMNAS} for r in nuevos],
        "actualizar": [{k: r.get(k, "") for k in COLUMNAS} for r in actualizar],
        "movimientos": [{k: r.get(k, "") for k in COLUMNAS} for r in sorted(todos, key=lambda r: (r["Fecha"], r["ID"]))],
        "correos_registro": registro_correos(e.get("correos", []), correos, leidos, procesados),
        "por_confirmar": dudosos,
        "no_leidos": [{"id": cc["id"], "de": cc["from"], "asunto": cc["subject"]} for _, cc in correos
                      if cc["id"] not in leidos and cc["id"] not in descartados and cc["id"] not in con_extraido],
        "lectura": lectura(correos, repetidos),
        "productos_vistos": productos_vistos(nuevos),
        "cuentas": [{k: f.get(k) for k in ("nombre", "tipo", "saldo", "desde", "origen", "hasta")} for f in c["cuentas"]],
        "tarjetas": tarjetas,
        "resumen": {
            "hoy": hoy.isoformat(), "alertas_hasta": max([r["Fecha"] for r in todos] or [""]),
            "plata_en_cuentas": round(c["total"]), "apartado": round(c.get("reservado_inversion", 0)), "disponible": round(c["disponible"]),
            "inversiones": round(c["inversiones"]), "cuentas_sin_saldo": c["sin_saldo"],
            # la cifra por día es aproximada si faltan saldos o la deuda de una tarjeta salió de las alertas: dilo
            "aproximado": bool(c["sin_saldo"] or [t for t in tarjetas if t.get("estimada") or t["deuda"] is None]),
            "tarjetas_estimadas": [t["nombre"] for t in tarjetas if t.get("estimada")],
            "tarjetas_sin_deuda": [t["nombre"] for t in tarjetas if t["deuda"] is None],
            "proximo_sueldo": est["proximo_pago"].isoformat(), "dias_al_sueldo": est["dias_al_pago"],
            "falta_pagar_antes_del_sueldo": [{"nombre": p["nombre"], "fecha": p["fecha"].isoformat(), "monto": round(p["monto"])}
                                              for p in est["por_pagar_antes_del_sueldo"]],
            "libre": round(est["libre"]), "por_dia": est["por_dia"],
            "gasto_mes_por_categoria": por_categoria(mes), "gasto_mes_anterior_por_categoria": por_categoria(mes_ant),
        },
    }
    # deudas, próximos pagos, eventos de Calendar e informe del lunes
    deu = reportes.lista_deudas(creditos, tarjetas)
    proximos = [{"nombre": p["nombre"].lstrip("💰🏦💳🔁 "), "fecha": p["fecha"].isoformat(), "monto": round(p["monto"]) if p.get("monto") else None,
                 "pagado": bool(p["pagado"]), "automatico": bool(p.get("automatico")), "tipo": p.get("tipo", "")}
                for p in est["proximos"] if p["fecha"] >= hoy - datetime.timedelta(days=3)]
    proximos += [{"nombre": t["nombre"], "fecha": t["vence"], "monto": t["deuda"], "pagado": False, "automatico": False, "tipo": "tarjeta"}
                 for t in tarjetas if t.get("vence")]
    proximos.sort(key=lambda p: p["fecha"])
    preguntar = [r for r in previos if "❓" in (r.get("Tu nota") or "")] + [r for r in nuevos if r["ID"] in dudosos]
    res["deudas"] = deu
    res["proximos_pagos"] = proximos
    res["calendario"] = reportes.eventos_calendario(agente.pagos_config()["pagos"], [p for p in agente.PRODUCTOS if p["tipo"] == "tarjeta_credito"],
                                                    hoy, agente)
    res["analisis"] = reportes.analisis(todos, agente, hoy, {x["nombre"]: x["desde"] for x in e.get("suscripciones_canceladas") or []})
    ya_notas = set(e.get("notas_ids") or [])
    res["descubrimientos"] = [dict(x, nuevo=x["id"] not in ya_notas)
                              for x in reportes.descubrimientos(todos, nuevos, cfg, res["productos_vistos"], res["analisis"], hoy)]
    res["faltantes"] = reportes.faltantes(c["cuentas"], tarjetas, creditos, cfg, hoy)
    # primer uso: el sueldo que se ve en los correos, cómo están los datos de cada cuenta y qué hacer primero
    res["sueldo_probable"] = reportes.sueldo_probable(todos, agente)
    res["cobertura"] = reportes.cobertura(agente.PRODUCTOS, todos, c["cuentas"], cu)
    res["acciones"] = reportes.acciones(e.get("objetivo"), res["analisis"], deu, hoy)
    res["comparacion_ofertas"] = reportes.comparar_ofertas(creditos, tarjetas, e.get("ofertas") or [], e.get("tasa_usura"))
    res["informe"] = reportes.informe(est, res, deu, proximos, preguntar, hoy)
    os.chdir(os.path.dirname(os.path.abspath(salida)) or ".")
    json.dump(res, open(salida, "w"), ensure_ascii=False, indent=1, default=str)
    shutil.rmtree(trabajo, ignore_errors=True)
    r = res["resumen"]
    print(f"{len(correos)} correos ({repetidos} repetidos descartados): {res['lectura']['por_banco']}")
    print(f"{len(res['nuevos'])} movimientos nuevos, {len(res['no_leidos'])} correos sin leer, {len(dudosos)} por confirmar")
    print(f"Plata en cuentas ${r['plata_en_cuentas']:,} | libre ${r['libre']:,} | ${r['por_dia']:,} por día hasta el {r['proximo_sueldo']}".replace(",", "."))


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]))
