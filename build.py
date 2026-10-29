"""Consolida todas las fuentes en una sola tabla de movimientos categorizados -> data/movimientos.json"""
import json, re, collections, hashlib, os
from parse_extractos import todos
from parse_otros import nu_todos, bancolombia
from parse_davi import parse as alertas_davi
from config import C, BANCO, regex_propio, regex_celulares

DESDE = C.get("desde", "2025-01-01")

# (regex sobre la descripción, tipo, categoría, subcategoría)
# tipo: Ingreso | Gasto | Deuda (pago de créditos) | Financiamiento (dinero prestado que entra) | Interno (entre cuentas propias)
REGLAS = [tuple(r) for r in C.get("reglas_personales", [])] + [
    (r"BUSCALIBR", "Gasto", "Educación", "Libros"),
    (r"MERCADO ?PAGO\*MERCADOLI|MERCADOLIBRE|MERCADO LIBRE", "Gasto", "Compras", "Mercado Libre"),
    (r"MERCADO ?PAGO|MERCADOPAGO", "Gasto", "Compras", "Pago por Mercado Pago (tienda online, sin detalle)"),
    (r"LICORERA|LICORES", "Gasto", "Ocio", "Licor"),
    # un retiro en cajero es efectivo, sin importar el lugar del cajero (Portal 170, Lourdes, Zipaquirá…)
    (r"Retiro en Cajero|Retiro con Tarjeta Cajero|Retiraste \$|Retiro Efectivo", "Gasto", "Efectivo", "Retiros"),
    (r"REDIFE CAPITAL|NC REDIFERIDO", "Interno", "Rediferido tarjeta (deuda pasada a cuotas, no es gasto nuevo)", ""),
    (r"REDIFE INTER", "Gasto", "Intereses y comisiones", "Intereses tarjeta"),
    # --- movimientos internos ---
    (r"Pago Tarj\. Credito|Pago Tarjeta de Credito|Pago en Aliado 5523\d{12}", "Interno", "Pago tarjeta Davivienda", ""),
    (r"Abono por avance|Abono Avance Tc|Abono Uso Tarjeta de Credito|^AVANCE APP|Hiciste un avance|^Avance", "Interno", "Avance tarjeta de crédito", ""),
    (r"Bolsillo", "Interno", "Bolsillo Davivienda", ""),
    (r"NU Compa|NU Colombia Compa", "Interno", "Pago tarjeta Nu", ""),
    (r"Daviplata|DAVIPLATA", "Gasto", "Gastos vía Daviplata (sin detalle)", ""),
    (r"pagaste \$[\d,\.]+ por codigo QR|pagaste \$[\d,\.]+ por QR", "Gasto", "Otros", "Pago con QR (Bancolombia)"),
    (regex_propio(), "Interno", "Entre mis cuentas", ""),   # transferencias a mi nombre (config.json)
    (r"Debitamos de tu cuenta/bolsillo .* tarjeta de credito|abonar a la deuda", "Interno", "Pago tarjeta Bancolombia", ""),
    (r"Transferencia Desde Davivienda A Llave|Transferencia A Llave Davivienda", "Interno", "Entre mis cuentas", ""),
    # --- financiamiento / deudas ---
    (r"Desembolso Credito", "Financiamiento", "Desembolso de crédito", ""),
    (r"^HIPOTECA|Credito Hipotecario", "Deuda", "Crédito hipotecario", ""),
    (r"Pago Credito Nro\.|Pago en Aliado 59|Pago a Credito", "Deuda", "Créditos de consumo / libranza", ""),
    (r"ICETEX", "Deuda", "ICETEX", ""),
    (r"INTERES CORRIEN|INTERES MORA|Intereses", "Gasto", "Intereses y comisiones", "Intereses tarjeta"),
    (r"CUOTA DE MANEJO|CUOTA DE SEGURO|COMISION|Comision|Gravamen|4x1000|Cuota de manejo", "Gasto", "Intereses y comisiones", "Comisiones / 4x1000"),
    # --- ingresos ---
    (r"Abono Nomina|Abono en Cuenta ADMON DE PERSONAL", "Ingreso", "Salario", "Nómina Davivienda"),
    (r"^LIBRANZA NOMINA", "Ingreso", "Salario", "Libranza descontada de nómina (estimado)"),
    (r"^CUOTA LIBRANZA NOMINA", "Deuda", "Créditos de consumo / libranza", "Libranza descontada de nómina"),
    (r"Rendimientos|Abono X Gravamen", "Ingreso", "Rendimientos", ""),
    (r"Devolucion|Reversion|Reversada|Recibiras", "Ingreso", "Devoluciones", ""),
    # --- gastos ---
    (r"ENEL|CODENSA|VANTI|GAS NATURAL|ACUEDUCTO", "Gasto", "Vivienda", "Servicios públicos"),
    (r"COMUNICACION CELULAR|COMCEL|CLARO|MOVISTAR|TIGO", "Gasto", "Vivienda", "Celular / internet"),
    (r"\bDIAN\b|Impuestos|SIMIT|Retencion en la Fuente", "Gasto", "Impuestos", ""),
    (r"UBER|DIDI|CABIFY|INDRIVE|TRANSMILENIO|TU LLAVE|TERPEL|BIOMAX|EDS |ESTACION DE SERVICIO|PEAJE|TERMINAL|PARQUEADERO|TAXI|PRIMAX|TEXACO|FLIXBUS", "Gasto", "Transporte", ""),
    (r"RAPPI|IFOOD|DOMICILIOS", "Gasto", "Comida", "Domicilios"),
    (r"CARULLA|EXITO|\bD1\b|\bARA\b|OLIMPICA|JUMBO|OXXO|DOLLARCITY|MERCADO|SURTIMAX|FRUVER|AUTO SERVICIO|SUPERMERCADO|PASTELER|PANADER|LICORERA|CIGARRERIA", "Gasto", "Comida", "Mercado y tiendas"),
    (r"\bREST|RESTAURANTE|\bCAFE\b|\bBAR\b|BURGER|HAMBURGUESA|PIZZA|CREPES|MC DONALD|FRISBY|CORRAL|KFC|SUSHI|WOK|TACO|STARBUCKS|JUAN VALDEZ|TOSTAO|BOLD\*|BOLD SA\*|COCINA|GASTRONOM|PARRILLA|ASADERO|HELADERIA|TST\*|SQ \*", "Gasto", "Comida", "Restaurantes y bares"),
    (r"CLIC ?AIR|SATENA|AVIANCA|LATAM|\bCOPA\b|UNITED|AMERICAN AIR|IBERIA|RYANAIR|WINGO|JETSMART|AEROVIAS|LIFEMILES|DESPEGAR|EXPEDIA|EDREAMS|AIRBNB|BOOKING|HOSTEL|HOTEL|HILTON|MARRIOTT|Trip\.com|VIATOR|GetYourGuide|HOLAFLY|Cajero Internacional|comercio internacional|Compra Internacional", "Gasto", "Viajes", ""),
    (r"SMART ?FIT|BODYTECH|ENFORMA|GIMNASIO|\bGYM\b|DECATHLON|ASICS|IRONMAN|SPORT", "Gasto", "Deporte", ""),
    (r"UNIVERSIDAD|\bUNIV\b|PONTIFICIA|PLATZI|COURSERA|UDEMY|DUOLINGO|TOEFL|BUSCALIBRE|PANAMERICANA|LIBRER", "Gasto", "Educación", ""),
    (r"ANTHROPIC|CLAUDE|OPENAI|CHATGPT|CURSOR|GOOGLE \*?CLOUD|GOOGLE \*Workspace|NOTION|GITHUB|VERCEL|GODADDY|MIDJOURNEY|\bAWS\b|MICROSOFT", "Gasto", "Tecnología y software", ""),
    (r"GOOGLE ONE|SPOTIFY|NETFLIX|DISNEY|HBO|hbomax|AMAZON PRIME|PRIME VIDEO|YOUTUBE|APPLE\.COM|GOOGLE PLAY|UBER ONE|\bMAX\b|DEEZER|PARAMOUNT|CRUNCHYROLL", "Gasto", "Suscripciones", ""),
    (r"ODONT|DROGUER|FARMAC|CRUZ VERDE|COLSUBSIDIO|\bMEDIC|CLINICA|LABORATORIO|SALUD|OPTICA|EPS\b", "Gasto", "Salud", ""),
    (r"ZARA|H&M|FALABELLA|ADIDAS|NIKE|ARTURO CALLE|VELEZ|KOAJ|STUDIO F|TENNIS|DAFITI|MERCADOLIBRE|AMAZON|KTRONIX|ALKOSTO|IKEA|HOMECENTER|TEMU|SHEIN", "Gasto", "Compras", ""),
    (r"CINE|CINEMARK|PROCINAL|TUBOLETA|TICKET|TEATRO|FEVER|CONCIERTO", "Gasto", "Entretenimiento", ""),
    (r"TEMBICI", "Gasto", "Transporte", "Bicicletas"),
    (r"FONDO ROTATORIO DEL MIN", "Gasto", "Trámites", "Pasaporte / Cancillería"),
    (r"\bADDI\b|addi\.com", "Gasto", "Compras", "Compra a cuotas con Addi"),
    (r"Planilla Unica|\bPILA\b", "Gasto", "Seguridad social (PILA)", "Aportes como independiente"),
    (r"Retiro|Retiraste|\bATM\b|Cajero", "Gasto", "Efectivo", "Retiros"),
    (r"Transferencia|Transferiste|transferiste|Transf |Llave|llave|Transfiya|codigo QR|por QR|Compra A Comercio Llave|Pago A Llave", "Gasto", "Transferencias a terceros", ""),
]


def clasificar(desc, valor):
    for pat, tipo, cat, sub in REGLAS:
        if re.search(pat, desc, re.I):
            if tipo in ("Gasto", "Deuda") and valor > 0 and not re.search("|".join(["Daviplata"] + C.get("netear_con", [])), sub + cat, re.I):
                if cat == "Transferencias a terceros":
                    return "Ingreso", "Transferencias recibidas", ""
                return "Ingreso", "Devoluciones", cat
            return tipo, cat, sub
    return ("Gasto", "Otros", "") if valor < 0 else ("Ingreso", "Otros ingresos", "Sin identificar")


def comercio(desc):
    d = re.sub(r"FRANQUICIA.*|Compras y Pagos PSE|Redeban BreB|App Davivienda|App Transaccional|PROCESOS ACH|BTA PROCESOS ESP\.?", "", desc)
    d = re.sub(r"^(Correccion Compra en Establecimiento,|Compra en Establecimiento,|Descuento en Internet,|Compra en comercio internacional|Compra Internacional|Compra|Descuento Por|Descuento|Transferencia)\s*", "", d)
    d = re.sub(r"^PSE\s+", "", d)
    return re.sub(r"\s+", " ", d).strip()[:60]


def main():
    ahorros, tc = todos()
    fin_ahorros = max([x["fecha"] for x in ahorros] or ["0000"])
    fin_tc = max([x["fecha"] for x in tc] or ["0000"])
    alertas = [a for a in alertas_davi() if a["fecha"] >= DESDE] if os.path.exists("data/davivienda.jsonl") else []

    # Enriquecer compras PSE sin nombre (0000000...) con el comercio de la alerta del mismo día y valor
    idx = collections.defaultdict(list)
    for a in alertas:
        idx[(a["fecha"], round(a["valor"]))].append(a)
    for x in ahorros:
        if re.search(r"0000000000000000|comercio internacional|Compra Internacional", x["desc"]) and x["valor"] < 0:
            c = idx.get((x["fecha"], round(-x["valor"]))) or []
            if c and c[0]["lugar"] and not c[0]["lugar"].startswith("0000"):
                x["desc"] = f"Compra {c[0]['lugar']}" + (" (PSE)" if "0000000" in x["desc"] else " (internacional)")
        # Compras con llave (Bre-B) en el extracto no dicen el comercio; la alerta sí ("Lugar de Transacción: SURF HOUSE…")
        elif re.search(r"Compra A Comercio Llave", x["desc"]) and x["valor"] < 0:
            c = [a for a in (idx.get((x["fecha"], round(-x["valor"]))) or []) if a["lugar"] and "App Davivienda" not in a["lugar"]]
            if c: x["desc"] = f"Compra con llave {c[0]['lugar']}"

    movs = []
    for x in ahorros:
        movs.append({**x, "fuente": f"Davivienda Ahorros *{x['cuenta']}"})
    for x in tc:
        movs.append({**x, "fuente": f"Davivienda TC *{x['cuenta']}"})
    # Alertas posteriores al último extracto (octubre 2026)
    for a in alertas:
        if a["producto"].startswith("Cta") and a["fecha"] > fin_ahorros or a["producto"].startswith("Tarjeta") and a["fecha"] > fin_tc:
            signo = 1 if re.match(r"Abono|Deposito|Compra Reversada|Correccion|Anulaci", a["clase"]) else -1
            desc = f"{a['clase']} {a['lugar']}".strip()
            movs.append({"fuente": f"Davivienda {'TC' if a['producto'].startswith('Tarjeta') else 'Ahorros'} *{a['cuenta']} (alerta)",
                         "cuenta": a["cuenta"], "fecha": a["fecha"], "valor": signo * a["valor"], "desc": desc})
    for x in nu_todos():
        movs.append({**x, "fuente": "Nu TC"})
    for x in (bancolombia() if os.path.exists("data/otros.jsonl") else []):
        tcb, aho = BANCO.get("tarjeta_credito", ""), BANCO.get("ahorros", "")
        cta = x["cuenta"] if x["cuenta"] in (tcb, aho) and x["cuenta"] else (aho or x["cuenta"])
        movs.append({**x, "fuente": f"Bancolombia {'TC' if cta == tcb and tcb else 'Ahorros'} *{cta} (alerta)"})

    # Libranzas que se descuentan de la nómina (no pasan por la cuenta): se agregan como ingreso (salario bruto) y como
    # pago de deuda para que ambos queden completos. Se configuran en config.json -> libranzas_nomina: [crédito, cuota, [meses]].
    LIBRANZAS_NOMINA = C.get("libranzas_nomina", [])
    for cred, cuota, meses in LIBRANZAS_NOMINA:
        for mes in meses:
            movs.append({"fuente": "Descuento de nómina (estimado)", "cuenta": "", "fecha": f"{mes}-28", "valor": cuota,
                         "desc": f"LIBRANZA NOMINA crédito {cred} (salario antes del descuento)"})
            movs.append({"fuente": "Descuento de nómina (estimado)", "cuenta": "", "fecha": f"{mes}-28", "valor": -cuota,
                         "desc": f"CUOTA LIBRANZA NOMINA crédito {cred}"})

    out = []
    for m in movs:
        if m["fecha"] < DESDE: continue
        tipo, cat, sub = clasificar(m["desc"], m["valor"])
        # Compras grandes con avance de TC: el avance llega a la cuenta como movimiento interno
        if tipo == "Deuda" and m["valor"] < -5_000_000 and cat != "Crédito hipotecario":
            sub = "Prepago / refinanciación"
        mes = m["fecha"][:7]
        out.append({"Fecha": m["fecha"], "Mes": mes, "Fuente": m["fuente"], "Descripción": m["desc"],
                    "Comercio": comercio(m["desc"]), "Valor": round(m["valor"], 2), "Tipo": tipo,
                    "Categoría": cat, "Subcategoría": sub, "Cuotas": m.get("cuotas", "")})
    out.sort(key=lambda r: (r["Fecha"], r["Fuente"], r["Descripción"], r["Valor"]))
    # Traslados entre MIS cuentas (Davivienda, Bancolombia, Nequi/Daviplata).
    # Se emparejan por mismo valor y fecha (±1 día): la salida de un banco con la entrada a mi nombre en el otro.
    import datetime as _dt
    def _d(s): return _dt.date.fromisoformat(s)
    ent = [r for r in out if r["Valor"] > 0 and re.search(regex_propio() + r"|Transferencia De Otra Entidad A Llave|Transferencia Recibidas Con Llave", r["Descripción"], re.I)]
    sal = [r for r in out if r["Valor"] < 0 and r["Tipo"] != "Interno" and re.search(r"Llave|llave|Transf|Transferiste", r["Descripción"])]
    usados = set()
    for e in ent:
        for s in sal:
            if id(s) in usados or s["Fuente"][:6] == e["Fuente"][:6]: continue
            if abs(s["Valor"] + e["Valor"]) < 1 and abs((_d(s["Fecha"]) - _d(e["Fecha"])).days) <= 1:
                for r, sub in ((s, f"{s['Fuente'][:11].strip()} → {e['Fuente'][:11].strip()}"), (e, f"{s['Fuente'][:11].strip()} → {e['Fuente'][:11].strip()}")):
                    r["Tipo"], r["Categoría"], r["Subcategoría"] = "Interno", "Entre mis cuentas", sub
                usados.add(id(s)); break
    # Mis celulares (Nequi / Daviplata propios): plata mía que luego gasto desde allá (sin detalle)
    for r in out:
        if r["Tipo"] != "Interno" and re.search(regex_celulares(), r["Descripción"]):
            r["Categoría"], r["Subcategoría"] = "Gastos vía Daviplata (sin detalle)", "A mi Nequi/Daviplata (gastado desde allá)"

    # Contactos: números de cuenta/celular o llaves a los que el usuario les puso nombre y categoría (data/contactos.json)
    #   {"3015255261": {"nombre": "María Kamyla", "categoria": "Regalos", "subcategoria": "..."}}
    contactos = json.load(open("data/contactos.json")) if os.path.exists("data/contactos.json") else {}
    for r in out:
        if r["Tipo"] == "Interno": continue
        for num, cdat in contactos.items():
            if num.startswith("_"): continue
            if re.search(r"(?<!\d)0*" + re.escape(num.lstrip("0")) + r"(?!\d)" if num.isdigit() else re.escape(num), r["Descripción"], re.I):
                r["Categoría"] = cdat.get("categoria") or r["Categoría"]
                r["Subcategoría"] = cdat.get("subcategoria") or cdat.get("nombre", "")
                break

    # ID estable por movimiento (para conservar categorías manuales y notas entre actualizaciones)
    seen = collections.Counter()
    for r in out:
        base = f'{r["Fuente"].replace(" (alerta)", "")}|{r["Fecha"]}|{r["Valor"]:.2f}|{r["Descripción"][:60]}'
        seen[base] += 1
        r["ID"] = hashlib.md5(f"{base}|{seen[base]}".encode()).hexdigest()[:10]
    ov = json.load(open("data/overrides.json")) if os.path.exists("data/overrides.json") else {}
    # respuestas a las preguntas automáticas del agente (pestaña Preguntas): texto corto = categoría, largo = nota
    pq = json.load(open("data/preguntas.json")) if os.path.exists("data/preguntas.json") else []
    for p in pq:
        resp = ov.get("respuestas", {}).get(p["q"], "").strip()
        if p.get("id") and resp and p["id"] not in ov.get("movimientos", {}):
            corto = len(resp) <= 40 and "." not in resp
            ov.setdefault("movimientos", {})[p["id"]] = {"categoria": resp[:1].upper() + resp[1:] if corto else "", "nota": "" if corto else resp}
    for r in out:
        o = ov.get("movimientos", {}).get(r["ID"], {})
        r["Categoría manual"] = o.get("categoria", "")
        r["Tu nota"] = o.get("nota", "")
        if r["Categoría manual"]:
            r["Categoría"], r["Subcategoría"] = r["Categoría manual"], o.get("subcategoria", "Clasificado a mano")
            if o.get("tipo"): r["Tipo"] = o["tipo"]
            elif re.search(r"entre mis cuentas|traslado|mis cuentas", r["Categoría manual"], re.I): r["Tipo"] = "Interno"
    json.dump(out, open("data/movimientos.json", "w"), ensure_ascii=False, indent=0)
    return out


if __name__ == "__main__":
    out = main()
    print(len(out), "movimientos")
    c = collections.defaultdict(float)
    for r in out: c[(r["Tipo"], r["Categoría"])] += r["Valor"]
    for k, v in sorted(c.items(), key=lambda i: i[1]): print(f"{v:>16,.0f}  {k[0]:<15} {k[1]}")
