"""Mapa de cuentas: cada producto financiero del usuario (cuenta, billetera, bolsillo, tarjeta, crédito, inversión, CDT)
con su institución y cómo reconocerlo cuando aparece en movimientos de OTRO banco (un PSE a Trii, un retiro de Littio,
el pago de tu tarjeta Falabella desde Davivienda).
Sirve para dos cosas: no contar como gasto o ingreso la plata que se mueve entre tus cosas (transferencias.py) y
calcular la caja y las inversiones sin depender de un banco en particular (saldos()).
Se configura en config.json -> "cuentas"; si no existe, se arma desde las llaves viejas "davivienda"/"bancolombia".
No importa config.py (config.py lo importa a él): así se puede probar sin config.json."""
import calendar, datetime, re, unicodedata

TIPOS = ("ahorros", "corriente", "billetera", "bolsillo", "tarjeta_credito", "credito", "inversion", "cdt")
LIQUIDOS = ("ahorros", "corriente", "billetera")   # caja: plata para gastar (el bolsillo vive DENTRO de una cuenta)
INVERSIONES = ("inversion", "cdt")                 # patrimonio, no caja
# si un movimiento menciona dos productos tuyos, gana el primero de esta lista
PREFERENCIA = ("inversion", "cdt", "tarjeta_credito", "credito", "ahorros", "corriente", "billetera", "bolsillo")
# productos cuyos movimientos ya lee el sistema (clave de la institución, tipo). Al escribir un lector nuevo, agrégalo aquí.
LECTORES = {("davivienda", "ahorros"), ("davivienda", "bolsillo"), ("davivienda", "tarjeta_credito"),
            ("bancolombia", "ahorros"), ("bancolombia", "tarjeta_credito"), ("nu", "tarjeta_credito")}
SINONIMOS = {"rappi": "rappipay", "rappicard": "rappipay", "rappicuenta": "rappipay", "lulobank": "lulo", "nubank": "nu",
             "nucolombia": "nu", "bancofalabella": "falabella", "cmr": "falabella", "colpatria": "scotiabank"}
# Cómo aparece la institución en movimientos de otros bancos cuando la plata va o viene de un producto TUYO.
# Solo nombres que no se confunden con comercios: "RAPPI" a secas es un domicilio y "NEQUI" a secas puede ser Nequi Negocios.
ALIAS = {"trii": r"\bTRII\b", "littio": r"\bLITTIO\b", "tyba": r"\bTYBA\b", "hapi": r"\bHAPI\b", "global66": r"GLOBAL ?66",
         "rappipay": r"RAPPI ?PAY|RAPPI ?CUENTA|RAPPI ?CARD", "lulo": r"LULO ?BANK", "nu": r"\bNU ?(?:COMPA|COLOMBIA|FINANCIERA)|NUBANK",
         "falabella": r"BANCO FALABELLA|\bCMR\b", "nequi": r"RECARGA\w* (?:A |EN )?NEQUI", "daviplata": r"DAVIPLATA"}
# Bancos tradicionales: su nombre solo identifica un producto tuyo cuando es un pago (a tu tarjeta o crédito), no una transferencia
BANCOS = {"bogota": r"(?:BANCO|BCO)\.?\s*(?:DE\s+)?BOGOTA", "occidente": r"(?:BANCO|BCO)\.?\s*(?:DE\s+)?OCCIDENTE",
          "popular": r"(?:BANCO|BCO)\.?\s*POPULAR", "avvillas": r"\bAV\.?\s*VILLAS", "cajasocial": r"CAJA\s*SOCIAL|\bBCSC\b",
          "itau": r"\bITAU\b", "santander": r"(?:BANCO|BCO)\.?\s*SANTANDER|SANTANDER CONSUMER", "bbva": r"\bBBVA\b",
          "scotiabank": r"SCOTIA|COLPATRIA", "bancolombia": r"BANCOLOMBIA", "davivienda": r"DAVIVIENDA"}
# contexto de pago a una tarjeta, crédito o CDT: "Compra X Compras y Pagos PSE", "Pagaste $ a X desde tu producto", "Pago TC X".
# "pago" a secas no basta: las transferencias a terceros también lo dicen ("Transferencia BANCOLOMBIA <cédula> pago").
PAGO = r"(?=.*(?:\bPSE\b|TARJ|\bTC\b|T\.? ?CRED|CARD|PAGASTE \$|\bCDT\b|DEPOSITO A TERMINO))"
ETIQUETA = {"ahorros": "ahorros", "corriente": "corriente", "billetera": "", "bolsillo": "bolsillo", "tarjeta_credito": "tarjeta",
            "credito": "crédito", "inversion": "", "cdt": "CDT"}


def norm(s):
    """Sin tildes (las descripciones de los bancos vienen con y sin ellas)."""
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))


def clave(institucion):
    """'Banco de Bogotá' -> 'bogota', 'RappiCard' -> 'rappipay', 'AV Villas' -> 'avvillas'."""
    t = re.sub(r"[^a-z0-9 ]", "", norm(institucion).lower()).strip()
    t = re.sub(r"^(banco|bco)\s+(de\s+|del\s+)?", "", t)
    t = t.replace(" ", "")
    return SINONIMOS.get(t, t)


def _nombre_generico(institucion):
    """Patrón para una institución que no está en ALIAS ni BANCOS (p. ej. un CDT en 'Koa')."""
    pal = re.sub(r"[^A-Z0-9 ]", "", norm(institucion).upper()).split()
    if not pal: return None
    if pal[0] in ("BANCO", "BCO"):
        resto = [p for p in pal[1:] if p not in ("DE", "DEL")]
        return r"(?:BANCO|BCO)\.?\s*(?:DE\s+|DEL\s+)?" + r"\s*".join(resto) if resto else None
    return r"\b" + r"\s*".join(pal) + r"\b"


def _compilar(pats):
    pats = [x for x in pats if x]
    return re.compile("|".join(f"(?:{x})" for x in pats), re.I) if pats else None


def _patrones(p):
    """Dos regex que reconocen este producto en la descripción de un movimiento de OTRO producto:
    - propio: alias que puso el usuario, su celular o el número de la cuenta. Vale desde cualquier banco.
    - nombre: el nombre de la institución. Solo vale desde OTRA institución: cada banco pone su nombre en sus propias
      descripciones ("Abono Por Transferencia De Fondos ... App Davivienda")."""
    propio = [p["alias"]] if isinstance(p.get("alias"), str) else list(p.get("alias") or [])
    k, t = p["clave"], p["tipo"]
    if p["celular"]:
        propio.append(rf"(?<!\d){p['celular']}(?!\d)")
    if t in ("ahorros", "corriente") and len(p["terminacion"]) >= 4:
        # "Transferiste $ desde tu cuenta *1234 a la cuenta *00000098765" (Bancolombia) / "Transferencia De Fondos 5504...65" (Davivienda)
        propio.append(rf"(?:a la cuenta|Transferencia De Fondos)\s*\*?\d*{p['terminacion']}\b")
    inst, nombre = ALIAS.get(k) or BANCOS.get(k) or _nombre_generico(p["institucion"]), None
    if inst:
        if k in BANCOS and t in INVERSIONES + ("tarjeta_credito", "credito"):
            nombre = PAGO + ".*(?:" + inst + ")"   # a un banco tradicional también le transfieres a terceros: solo pagos
        elif t in INVERSIONES:
            nombre = inst                           # a una plataforma de inversión solo le mandas plata a la tuya
        elif t in ("tarjeta_credito", "credito"):
            nombre = PAGO + ".*(?:" + inst + ")"
        elif k in ALIAS:                            # billeteras y bancos digitales: la recarga es a tu propia cuenta
            nombre = ALIAS[k]
    return _compilar(propio), _compilar([nombre])


def normalizar(cfg):
    """Lista de productos con campos completos a partir de config.json (formato nuevo "cuentas" o llaves viejas)."""
    out, ids = [], set()
    crudos = list(cfg.get("cuentas") or [])
    if crudos:   # celulares que quedaron en la llave vieja y no están como billetera en "cuentas"
        tiene = {re.sub(r"\D", "", str(x.get("celular") or "")) for x in crudos}
        crudos += [x for x in _desde_legado({"celulares_propios": cfg.get("celulares_propios", [])}) if x["celular"] not in tiene]
    else:
        crudos = _desde_legado(cfg)
    for x in crudos:
        p = dict(x)
        p["tipo"] = p.get("tipo", "ahorros")
        if p["tipo"] not in TIPOS:
            raise ValueError(f"config.json -> cuentas: el tipo '{p['tipo']}' no existe; usa uno de: {', '.join(TIPOS)}")
        p["institucion"] = (p.get("institucion") or "").strip()
        p["clave"] = clave(p["institucion"])
        p["terminacion"] = str(p.get("terminacion") or "").strip().lstrip("*")
        p["celular"] = re.sub(r"\D", "", str(p.get("celular") or ""))
        p["dentro_de"] = str(p.get("dentro_de") or "").strip().lstrip("*")
        p["tarjeta_debito"] = str(p.get("tarjeta_debito") or "").strip().lstrip("*")
        p["nombre"] = p.get("nombre") or " ".join(x for x in (p["institucion"], ETIQUETA[p["tipo"]],
                                                                 "*" + p["terminacion"] if p["terminacion"] else "") if x)
        p["id"] = p["nombre"] if p["nombre"] not in ids else f"{p['nombre']} ({len(out) + 1})"
        ids.add(p["id"])
        p["se_lee"] = bool(p.get("se_lee", (p["clave"], p["tipo"]) in LECTORES))
        p["patron"], p["patron_nombre"] = _patrones(p)
        out.append(p)
    return out


def _desde_legado(cfg):
    """Configuraciones anteriores al mapa de cuentas (llaves "davivienda", "bancolombia" y "celulares_propios")."""
    d, b, out = cfg.get("davivienda") or {}, cfg.get("bancolombia") or {}, []
    if d.get("cuenta_principal"): out.append({"institucion": "Davivienda", "tipo": "ahorros", "terminacion": d["cuenta_principal"]})
    if d.get("cuenta_afc"): out.append({"institucion": "Davivienda", "tipo": "ahorros", "terminacion": d["cuenta_afc"], "nombre": f"Davivienda AFC *{d['cuenta_afc']}"})
    if d.get("bolsillo"): out.append({"institucion": "Davivienda", "tipo": "bolsillo", "terminacion": d["bolsillo"], "dentro_de": d.get("cuenta_principal", "")})
    if d.get("tarjeta_credito"): out.append({"institucion": "Davivienda", "tipo": "tarjeta_credito", "terminacion": d["tarjeta_credito"]})
    if b.get("ahorros"): out.append({"institucion": "Bancolombia", "tipo": "ahorros", "terminacion": b["ahorros"], "tarjeta_debito": b.get("tarjeta_debito", "")})
    if b.get("tarjeta_credito"): out.append({"institucion": "Bancolombia", "tipo": "tarjeta_credito", "terminacion": b["tarjeta_credito"]})
    for cel in cfg.get("celulares_propios", []):   # antes no se sabía si era Nequi o Daviplata: quedan las dos
        if cel and cel != "3000000000":
            out += [{"institucion": "Nequi", "tipo": "billetera", "celular": cel, "nombre": f"Nequi {cel}"},
                    {"institucion": "Daviplata", "tipo": "billetera", "celular": cel, "nombre": f"Daviplata {cel}"}]
    return out


def legado_davivienda(productos):
    """El dict viejo config["davivienda"] que siguen usando los lectores de extractos Davivienda."""
    dv = [p for p in productos if p["clave"] == "davivienda"]
    bol = next((p for p in dv if p["tipo"] == "bolsillo"), None)
    aho = [p["terminacion"] for p in dv if p["tipo"] == "ahorros" and p["terminacion"]]
    principal = (bol and bol["dentro_de"]) or (aho[0] if aho else "")
    afc = next((p["terminacion"] for p in dv if p["tipo"] == "ahorros" and "AFC" in p["nombre"].upper()), "") \
        or next((t for t in aho if t != principal), "")
    tc = next((p["terminacion"] for p in dv if p["tipo"] == "tarjeta_credito"), "")
    return {"cuenta_principal": principal, "cuenta_afc": afc, "bolsillo": bol["terminacion"] if bol else "", "tarjeta_credito": tc}


def legado_bancolombia(productos):
    bc = [p for p in productos if p["clave"] == "bancolombia"]
    aho = next((p for p in bc if p["tipo"] == "ahorros"), None)
    tc = next((p for p in bc if p["tipo"] == "tarjeta_credito"), None)
    return {"ahorros": aho["terminacion"] if aho else "", "tarjeta_credito": tc["terminacion"] if tc else "",
            "tarjeta_debito": aho["tarjeta_debito"] if aho else ""}


def de_fuente(fuente, productos):
    """Producto dueño de un movimiento según su Fuente ("Davivienda Ahorros *1111 (alerta)", "Nu TC", "Bancolombia TC *6666")."""
    m = re.match(r"(\S+)\s+(\S+)?", fuente or "")
    if not m: return None
    cands = [p for p in productos if p["clave"] == clave(m.group(1))]
    term = re.search(r"\*(\w+)", fuente)
    if term:
        exacto = [p for p in cands if term.group(1) in (p["terminacion"], p["tarjeta_debito"])]
        if exacto: return exacto[0]
    familia = ("tarjeta_credito",) if m.group(2) == "TC" else ("ahorros", "corriente", "billetera") if m.group(2) == "Ahorros" else TIPOS
    cands = [p for p in cands if p["tipo"] in familia]
    return cands[0] if len(cands) == 1 else None


def contraparte(desc, productos, fuente="", valor=-1):
    """Producto tuyo (distinto del que registra el movimiento) al que va o del que viene la plata, según la descripción."""
    d, origen = norm(desc), de_fuente(fuente, productos)
    inst_origen = origen["clave"] if origen else clave((fuente or "x").split()[0])
    def por_nombre(p):
        if not p["patron_nombre"] or p["clave"] == inst_origen: return False
        # a una tarjeta o crédito se le PAGA; plata que entra desde ella solo si lo dice (avance)
        if p["tipo"] in ("tarjeta_credito", "credito") and valor > 0 and not re.search(r"AVANCE", d, re.I): return False
        return bool(p["patron_nombre"].search(d))
    cands = [p for p in productos if p is not origen and ((p["patron"] and p["patron"].search(d)) or por_nombre(p))]
    return min(cands, key=lambda p: PREFERENCIA.index(p["tipo"])) if cands else None


def para_saldo(nombre, productos):
    """Producto al que corresponde un saldo confirmado por el usuario ("Bancolombia (cuenta de ahorros)", "Nequi", "Trii").
    Las deudas ("Tarjeta Bancolombia (deuda)") no son caja: devuelve None y se quedan como saldo aparte."""
    if re.search(r"tarjeta|deuda|cr[eé]dito", nombre, re.I): return None
    exacto = [p for p in productos if norm(p["nombre"]).lower() == norm(nombre).lower()]
    if exacto: return exacto[0]
    k = clave(re.sub(r"^(cuenta|cta)\s+", "", nombre.split("(")[0].strip(), flags=re.I))
    cands = [p for p in productos if p["clave"] == k and p["tipo"] in LIQUIDOS + INVERSIONES]
    orden = ("ahorros", "corriente", "billetera", "inversion", "cdt")
    return min(cands, key=lambda p: orden.index(p["tipo"])) if cands else None


def fin_de_mes(mes):
    """'2026-09' -> '2026-09-30'."""
    y, m = int(mes[:4]), int(mes[5:7])
    return f"{mes}-{calendar.monthrange(y, m)[1]:02d}"


def saldos(movs, productos, anclas, hoy):
    """Saldo estimado de cada producto con plata = último saldo conocido (ancla) + lo que pasó después.
    anclas: {id: {"valor", "fecha", "origen"}} (origen: extracto | confirmado | config).
    - Productos que el sistema lee: + sus propios movimientos posteriores.
    - Productos que no lee (Trii, un CDT, una cuenta sin alertas): + lo que les mandaste − lo que sacaste desde tus otras cuentas.
    - Billetera que no se lee (Nequi, Daviplata): lo que le mandas se asume gastado, así que solo vale su saldo confirmado
      de los últimos 7 días."""
    por_fuente = {}
    def dueno(f):
        if f not in por_fuente: por_fuente[f] = de_fuente(f, productos)
        return por_fuente[f]
    out = []
    for p in productos:
        if p["tipo"] not in LIQUIDOS + INVERSIONES + ("bolsillo",): continue
        fila = {"id": p["id"], "nombre": p["nombre"], "institucion": p["institucion"], "tipo": p["tipo"], "dentro_de": p["dentro_de"], "terminacion": p["terminacion"],
                "saldo": None, "desde": None, "hasta": None, "origen": None, "viejo": False}
        a = anclas.get(p["id"])
        if a:
            dias = (hoy - datetime.date.fromisoformat(a["fecha"])).days
            fila.update(desde=a["fecha"], hasta=a["fecha"], origen=a["origen"], viejo=dias > 35)
            if p["tipo"] == "billetera" and not p["se_lee"]:
                if dias <= 7: fila["saldo"] = round(a["valor"])
            else:
                if p["se_lee"]:
                    post = [m for m in movs if m["Fecha"] > a["fecha"] and dueno(m["Fuente"]) is p]
                    mov = sum(m["Valor"] for m in post)
                else:
                    post = [m for m in movs if m["Fecha"] > a["fecha"] and m.get("Contraparte") == p["id"]]
                    mov = -sum(m["Valor"] for m in post)
                fila["saldo"] = round(a["valor"] + mov)
                fila["hasta"] = max([m["Fecha"] for m in post] + [a["fecha"]])
        out.append(fila)
    return out


def resumir(filas, reserva_inversion=0):
    """Caja (cuentas y billeteras), bolsillo, disponible para gastar e inversiones, a partir de saldos()."""
    con = [f for f in filas if f["saldo"] is not None]
    total = sum(f["saldo"] for f in con if f["tipo"] in LIQUIDOS)
    hay_bolsillo = any(f["tipo"] == "bolsillo" for f in con)
    bol = sum(f["saldo"] for f in con if f["tipo"] == "bolsillo")   # ya está DENTRO del saldo de su cuenta: no se suma al total
    if hay_bolsillo:   # lo reservado vive en el bolsillo; lo que sobra del bolsillo es colchón
        inv = min(reserva_inversion, max(bol, 0))
        disponible, emergencia = total - bol, bol - inv
    else:              # sin bolsillo, lo reservado se aparta del total
        inv = min(reserva_inversion, max(total, 0))
        disponible, emergencia = total - inv, 0
    return {"total": round(total), "bolsillo": round(bol), "disponible": round(disponible), "reservado_inversion": round(inv),
            "emergencia": round(emergencia), "inversiones": round(sum(f["saldo"] for f in con if f["tipo"] in INVERSIONES)),
            "cuentas": filas, "sin_saldo": [f["nombre"] for f in filas if f["saldo"] is None and f["tipo"] != "bolsillo"]}
