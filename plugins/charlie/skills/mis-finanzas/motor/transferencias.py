"""Plata que se mueve entre TUS productos (cuentas, billeteras, tarjetas, créditos, inversiones, CDTs): no es gasto ni ingreso.
PSE es un medio de pago, no un comercio: un PSE a Trii o a Littio es plata que sigue siendo tuya, sacar de Trii no es un
ingreso y una compra de cartera solo cambia de banco la deuda.
Corre en build.py después de las REGLAS y antes de las ediciones manuales (overrides), que siempre ganan.
Funciones puras sobre las filas de movimientos.json: se prueban sin Gmail ni config.json (tests/)."""
import datetime, re
from cuentas import contraparte, de_fuente, INVERSIONES

CARTERA = r"COMPRA (?:DE )?CARTERA|TRASLADO DE CARTERA|CARTERA COMPRADA"
ENTRA_LLAVE = r"Transferencia De Otra Entidad A Llave|Transferencia Recibidas Con Llave"
SALE_TRANSF = r"Llave|llave|Transf|Transferiste"


def _hacia(p, valor):
    """(Tipo, Categoría, Subcategoría) de un movimiento cuya contraparte es el producto propio p."""
    t, sale = p["tipo"], valor < 0
    if t in INVERSIONES:
        return "Interno", "Hacia mis inversiones" if sale else "Desde mis inversiones", p["nombre"]
    if t == "tarjeta_credito":
        return ("Interno", f"Pago tarjeta {p['institucion']}", "") if sale else ("Interno", "Avance tarjeta de crédito", p["nombre"])
    if t == "credito":
        return ("Deuda", "Créditos de consumo / libranza", p["nombre"]) if sale else ("Financiamiento", "Desembolso de crédito", p["nombre"])
    if t == "billetera" and not p["se_lee"]:
        # no vemos lo que pasa adentro: lo que le mandas se cuenta como gastado allá y lo que vuelve resta de ese gasto
        return "Gasto", "Gastos vía billetera (sin detalle)", f"{'A' if sale else 'De'} mi {p['institucion']} (gastado desde allá)"
    return "Interno", "Entre mis cuentas", f"{'→' if sale else '←'} {p['nombre']}"


def marcar(out, productos, propio=r"(?!x)x", dias=1):
    """Reclasifica en `out` (filas de movimientos.json) lo que es plata entre tus productos. Devuelve cuántas filas cambió."""
    n = 0
    # 1. Compra de cartera: un banco le paga tu deuda a otro; de tu bolsillo no sale nada
    for r in out:
        if re.search(CARTERA, r["Descripción"], re.I):
            r["Tipo"], r["Categoría"], r["Subcategoría"] = "Interno", "Compra de cartera (la deuda pasa de un banco a otro)", ""
            n += 1
    # 2. La descripción nombra un producto tuyo: PSE a tu Trii, retiro de Littio, pago de tu tarjeta en otro banco, tu cuenta *1234
    for r in out:
        if r["Tipo"] not in ("Gasto", "Ingreso"): continue
        p = contraparte(r["Descripción"], productos, r["Fuente"], r["Valor"])
        if p:
            r["Tipo"], r["Categoría"], r["Subcategoría"] = _hacia(p, r["Valor"])
            r["Contraparte"] = p["id"]
            n += 1
    # 3. Sale de una cuenta y entra a otra tuya (a tu nombre o por llave): mismo valor y fecha (±dias)
    d = lambda s: datetime.date.fromisoformat(s)
    dueno = {f: de_fuente(f, productos) for f in {r["Fuente"] for r in out}}
    nombre = lambda r: dueno[r["Fuente"]]["nombre"] if dueno[r["Fuente"]] else r["Fuente"][:11].strip()
    ent = [r for r in out if r["Valor"] > 0 and not r.get("Contraparte") and re.search(propio + "|" + ENTRA_LLAVE, r["Descripción"], re.I)]
    sal = [r for r in out if r["Valor"] < 0 and r["Tipo"] != "Interno" and re.search(SALE_TRANSF, r["Descripción"])]
    usados = set()
    for e in ent:
        for s in sal:
            if id(s) in usados: continue
            if dueno[s["Fuente"]] or dueno[e["Fuente"]]:
                if dueno[s["Fuente"]] is dueno[e["Fuente"]]: continue
            elif s["Fuente"][:6] == e["Fuente"][:6]: continue
            if abs(s["Valor"] + e["Valor"]) < 1 and abs((d(s["Fecha"]) - d(e["Fecha"])).days) <= dias:
                for r in (s, e):
                    r["Tipo"], r["Categoría"], r["Subcategoría"] = "Interno", "Entre mis cuentas", f"{nombre(s)} → {nombre(e)}"
                usados.add(id(s)); n += 1
                break
    return n
