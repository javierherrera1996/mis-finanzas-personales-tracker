"""Motor de la skill: corre los mismos lectores, reglas, traslados entre cuentas propias y cálculo de caja de la versión
instalada sobre las alertas que Claude trae con el conector de Gmail. Claude no clasifica ni suma: arma la entrada y copia
la salida al Sheet.

Uso: python motor/procesar.py entrada.json salida.json

entrada.json:
  config               el mismo formato de config.json (cuentas con su saldo, sueldo, nombre_en_bancos, documento…)
  reglas               [{si_aparece, tipo, categoria, subcategoria}]: la pestaña Reglas (texto, no regex)
  fijos                [{nombre, dia, monto, tipo: pago|cobro, buscar}]: la pestaña Fijos (opcional; el sueldo va en config)
  apartado             plata apartada que no se gasta, en pesos (opcional)
  correos              [{id, fecha, de, asunto, texto}]: las alertas tal cual vienen de Gmail (texto completo, no resumen)
  movimientos_extra    [{fecha, valor, descripcion, institucion, producto}]: alertas de bancos sin lector, que Claude leyó
  movimientos_previos  filas que ya están en el Sheet (Fecha, Valor, Descripción, Fuente, Tipo, Categoría, Subcategoría, ID)

salida.json: nuevos (filas para agregar al Sheet), no_leidos (correos que ningún lector entendió), cuentas, resumen."""
import datetime, html, json, os, re, shutil, sys, tempfile

MOTOR = os.path.dirname(os.path.abspath(__file__))
COLUMNAS = ["Fecha", "Valor", "Descripción", "Comercio", "Fuente", "Tipo", "Categoría", "Subcategoría", "Contraparte", "ID"]
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


def fijo(p):
    """Fila de la pestaña Fijos -> pago de data/pagos_config.json. 'buscar' es texto tal como sale en el banco (no regex)."""
    tipo = p.get("tipo") or "pago"
    dia = p.get("dia") if p.get("dia") == "penultimo_habil" else int(p.get("dia") or 1)
    return {"nombre": p["nombre"], "dia": dia, "monto": float(p.get("monto") or 0), "como": p.get("como", ""), "automatico": False,
            "tipo": "servicio" if tipo == "pago" else tipo, "buscar": re.escape(p["buscar"].strip()) if p.get("buscar") else ""}


def fila_previa(r):
    f = fecha_iso(r["Fecha"])
    return {"Fecha": f, "Mes": f[:7], "Fuente": r.get("Fuente", ""), "Descripción": r.get("Descripción", ""),
            "Comercio": r.get("Comercio", ""), "Valor": float(r["Valor"]), "Tipo": r.get("Tipo", ""), "Categoría": r.get("Categoría", ""),
            "Subcategoría": r.get("Subcategoría", ""), "Contraparte": r.get("Contraparte", ""), "ID": r.get("ID", ""),
            "Tu nota": r.get("Nota", "")}


def main(entrada, salida):
    e = json.load(open(entrada))
    trabajo = tempfile.mkdtemp(prefix="finanzas-")
    os.makedirs(os.path.join(trabajo, "data"))
    for f in os.listdir(os.path.join(MOTOR, "data_inicial")):
        # copyfile y no copy: si la skill es de solo lectura, copy también copia el permiso y no se podrían reescribir
        shutil.copyfile(os.path.join(MOTOR, "data_inicial", f), os.path.join(trabajo, "data", f))
    cfg = dict(e["config"])
    cfg["cuentas"] = [dict(x) for x in cfg.get("cuentas", [])]
    # pestaña Reglas: texto tal como sale en la descripción (no regex), antes de las reglas generales
    cfg["reglas_personales"] = [[re.escape(r["si_aparece"].strip()), r.get("tipo") or "Gasto", r.get("categoria") or "Otros", r.get("subcategoria") or ""]
                                for r in e.get("reglas", []) if (r.get("si_aparece") or "").strip()] + cfg.get("reglas_personales", [])
    # una regla de Gasto que trae plata (el roomie que paga su parte) resta de ese gasto en vez de contar como ingreso
    cfg["netear_con"] = cfg.get("netear_con", []) + [re.escape(r.get("subcategoria") or r.get("categoria") or "")
                                                     for r in e.get("reglas", []) if r.get("tipo") == "Gasto" and (r.get("subcategoria") or r.get("categoria"))]
    for m in e.get("movimientos_extra", []):   # si Claude lee sus alertas, sus movimientos mueven el saldo
        c = cuenta_de(m, cfg["cuentas"])
        if c is not None: c.setdefault("se_lee", True)
    correos = [preparar_correo(c) for c in e.get("correos", [])]
    fechas = [fecha_iso(c["date"]) for _, c in correos] + [fecha_iso(m["fecha"]) for m in e.get("movimientos_extra", [])]
    cfg["desde"] = min(fechas + [cfg.get("desde") or "9999"])
    json.dump(cfg, open(os.path.join(trabajo, "config.json"), "w"), ensure_ascii=False)
    for nombre in ("davivienda", "otros"):
        with open(os.path.join(trabajo, "data", nombre + ".jsonl"), "w") as f:
            for n, c in correos:
                if n == nombre: f.write(json.dumps(c, ensure_ascii=False) + "\n")
    extra = [{"fuente": fuente_extra(m, cfg.get("cuentas", [])), "cuenta": str(m.get("producto") or ""), "fecha": fecha_iso(m["fecha"]),
              "valor": float(m["valor"]), "desc": m.get("descripcion", "")} for m in e.get("movimientos_extra", [])]
    json.dump(extra, open(os.path.join(trabajo, "data", "movimientos_extra.json"), "w"), ensure_ascii=False)
    if e.get("fijos") is not None:
        pc = json.load(open(os.path.join(trabajo, "data", "pagos_config.json")))
        pc["pagos"] = [p for p in pc["pagos"] if p.get("tipo") == "ingreso"] + [fijo(p) for p in e["fijos"] if p.get("tipo") != "ingreso"]
        json.dump(pc, open(os.path.join(trabajo, "data", "pagos_config.json"), "w"), ensure_ascii=False)
    if e.get("apartado"):
        json.dump({"inversion": e["apartado"]}, open(os.path.join(trabajo, "data", "reservas.json"), "w"))

    # el motor lee config.json junto a sus archivos y la carpeta de la skill puede ser de solo lectura: se copia al temporal
    for f in os.listdir(MOTOR):
        if f.endswith(".py") and f != "procesar.py":
            shutil.copyfile(os.path.join(MOTOR, f), os.path.join(trabajo, f))
    os.chdir(trabajo)
    sys.path.insert(0, trabajo)
    import build, parse_davi, parse_otros, agente
    leidos = {a["id"] for a in parse_davi.parse()} | {b["id"] for b in parse_otros.bancolombia()}
    nuevos = build.main()
    previos = [fila_previa(r) for r in e.get("movimientos_previos", [])]
    ya = {r["ID"] for r in previos}
    nuevos = [r for r in nuevos if r["ID"] not in ya]
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
        s, t = p.get("saldo"), {"nombre": p["nombre"], "deuda": None, "desde": None, "dia_pago": p.get("dia_pago")}
        if isinstance(s, dict) and s.get("valor") is not None and s.get("fecha"):
            post = [r for r in todos if r["Fecha"] > s["fecha"]]
            compras = sum(r["Valor"] for r in post if cu.de_fuente(r["Fuente"], agente.PRODUCTOS) is p)
            pagos = sum(r["Valor"] for r in post if r.get("Contraparte") == p["id"])
            t.update(deuda=round(s["valor"] - compras + pagos), desde=s["fecha"])
            if t["deuda"] > 0 and p.get("dia_pago"):
                d = int(p["dia_pago"])
                vence = datetime.date(hoy.year, hoy.month, min(d, 28))
                if vence < hoy:
                    vence = datetime.date(hoy.year + hoy.month // 12, hoy.month % 12 + 1, min(d, 28))
                t["vence"] = vence.isoformat()
                if vence < pp:
                    por_pagar_tc += t["deuda"]
                    est["por_pagar_antes_del_sueldo"].append({"nombre": f"Tarjeta {p['nombre']}", "fecha": vence, "monto": t["deuda"]})
        tarjetas.append(t)
    est["libre"] -= por_pagar_tc
    est["por_dia"] = round(est["libre"] / est["dias_al_pago"])

    dudosos = [r["ID"] for r in nuevos if r["Tipo"] in ("Gasto", "Ingreso") and (r["Categoría"] in agente.CATS_DUDOSAS
               or r["Categoría"] == "Otros ingresos") and abs(r["Valor"]) >= 50000]
    res = {
        "nuevos": [{k: r.get(k, "") for k in COLUMNAS} for r in nuevos],
        "por_confirmar": dudosos,
        "no_leidos": [{"id": cc["id"], "de": cc["from"], "asunto": cc["subject"]} for _, cc in correos if cc["id"] not in leidos],
        "cuentas": [{k: f.get(k) for k in ("nombre", "tipo", "saldo", "desde", "origen", "hasta")} for f in c["cuentas"]],
        "tarjetas": tarjetas,
        "resumen": {
            "hoy": hoy.isoformat(), "alertas_hasta": max([r["Fecha"] for r in todos] or [""]),
            "plata_en_cuentas": round(c["total"]), "apartado": round(c.get("reservado", 0)), "disponible": round(c["disponible"]),
            "inversiones": round(c["inversiones"]), "cuentas_sin_saldo": c["sin_saldo"],
            "proximo_sueldo": est["proximo_pago"].isoformat(), "dias_al_sueldo": est["dias_al_pago"],
            "falta_pagar_antes_del_sueldo": [{"nombre": p["nombre"], "fecha": p["fecha"].isoformat(), "monto": round(p["monto"])}
                                              for p in est["por_pagar_antes_del_sueldo"]],
            "libre": round(est["libre"]), "por_dia": est["por_dia"],
            "gasto_mes_por_categoria": por_categoria(mes), "gasto_mes_anterior_por_categoria": por_categoria(mes_ant),
        },
    }
    os.chdir(os.path.dirname(os.path.abspath(salida)) or ".")
    json.dump(res, open(salida, "w"), ensure_ascii=False, indent=1, default=str)
    shutil.rmtree(trabajo, ignore_errors=True)
    r = res["resumen"]
    print(f"{len(res['nuevos'])} movimientos nuevos, {len(res['no_leidos'])} correos sin leer, {len(dudosos)} por confirmar")
    print(f"Plata en cuentas ${r['plata_en_cuentas']:,} | libre ${r['libre']:,} | ${r['por_dia']:,} por día hasta el {r['proximo_sueldo']}".replace(",", "."))


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]))
