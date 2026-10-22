"""Línea de tiempo: asigna movimientos a viajes/proyectos de data/viajes.json y resume el gasto de cada uno."""
import json, re, collections
EXCL = {"Vivienda", "Impuestos", "Suscripciones", "Tecnología y software", "Seguridad social (PILA)", "Intereses y comisiones"}


def grupo(r):
    d, c = r["Descripción"], r["Categoría"]
    if re.search(r"5150|IRONMAN|FINISHER", d, re.I): return "Inscripción y fotos de carrera"
    if re.search(r"DECATHLON|ASICS|BICI", d, re.I): return "Equipo (bici, reloj, ropa)"
    if re.search(r"SURF|BUCEO|DIVE", d) or r.get("_surf"): return "Buceo y surf"
    if re.search(r"AVIANCA|DESPEGAR|AEROVIAS|CLIC ?AIR|LATAM|UNITED|COPA|WINGO|AERO ?REPUBLICA|LIFEMILES|RYANAIR|FLIXBUS|TRAINLINE|EDREAMS", d, re.I): return "Vuelos y transporte largo"
    if re.search(r"HOTEL|HOSTEL|BOOKING|AIRBNB|HILTON|MARRIOTT|Trip\.com|EXPEDIA", d, re.I): return "Alojamiento"
    if c == "Comida" or "QR" in r["Subcategoría"]: return "Comida y pagos locales"
    if c == "Transporte": return "Transporte local"
    if c in ("Transferencias a terceros", "Gastos vía Daviplata (sin detalle)", "Efectivo"): return "Transferencias y efectivo"
    if c == "Familia": return "Regalo"
    if re.search("HOLAFLY", d, re.I): return "Tours, compras y otros"
    return "Tours, compras y otros"


def asignar(movs):
    cfg = json.load(open("data/viajes.json"))["viajes"]
    out = collections.OrderedDict((v["nombre"], []) for v in cfg)
    usado = set()
    # 1) primero las compras asignadas explícitamente (reservas, equipo, regalos): ganan sobre las fechas
    for v in cfg:
        for f, pat in v.get("extra", []):
            for r in movs:
                if r["Fecha"] == f and r["Valor"] < 0 and r["Tipo"] == "Gasto" and r["ID"] not in usado and re.search(pat, r["Descripción"] + " " + str(int(-r["Valor"])), re.I):
                    if pat == "2200000": r = {**r, "_surf": True}
                    usado.add(r["ID"]); out[v["nombre"]].append(r)
        if v.get("solo_patron"):
            for r in movs:
                if re.search(v["solo_patron"], r["Descripción"]) and r["Valor"] < 0 and r["ID"] not in usado:
                    usado.add(r["ID"]); out[v["nombre"]].append(r)
        if v["nombre"].startswith("Regalo"):
            for r in movs:
                if r["Fecha"] == "2025-12-25" and re.search("Avianca|Despegar", r["Descripción"]) and r["ID"] not in usado:
                    usado.add(r["ID"]); out[v["nombre"]].append(r)
    # 2) luego todo lo gastado durante las fechas del viaje
    for v in cfg:
        if v.get("solo_patron") or v.get("solo_extra"): continue
        for r in movs:
            if (v["desde"] <= r["Fecha"] <= v["hasta"] and (r["Valor"] < 0 or r["Categoría"] == "Viajes") and r["Tipo"] == "Gasto" and r["ID"] not in usado
                    and r["Categoría"] not in EXCL and not re.search(r"Curso de inglés|Platzi", r["Subcategoría"] + r["Descripción"])):
                usado.add(r["ID"]); out[v["nombre"]].append(r)
    return cfg, out


def resumen(movs):
    cfg, out = asignar(movs)
    filas = []
    for v in cfg:
        rows = out[v["nombre"]]; g = collections.defaultdict(float)
        for r in rows: g[grupo(r)] -= r["Valor"]
        filas.append({"nombre": v["nombre"], "desde": v["desde"], "hasta": v["hasta"], "total": round(sum(g.values())), "grupos": dict(g), "n": len(rows), "nota": v.get("nota", "")})
    return filas, out


if __name__ == "__main__":
    filas, _ = resumen(json.load(open("data/movimientos.json")))
    for f in filas:
        print(f"{f['desde']} {f['nombre'][:42]:42} {f['total']:>12,} | " + " · ".join(f"{k} {v/1e6:.2f}" for k, v in sorted(f['grupos'].items(), key=lambda i: -i[1])))
    print("TOTAL", f"{sum(f['total'] for f in filas):,}")
