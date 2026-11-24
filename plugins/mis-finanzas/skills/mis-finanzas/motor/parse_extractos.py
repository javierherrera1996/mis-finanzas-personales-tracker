"""Lee los extractos Davivienda (ahorros y tarjeta de crédito) ya convertidos a .txt."""
import re, glob
from config import DAVI
TC = DAVI.get("tarjeta_credito") or "TC"
MESES = {m: i + 1 for i, m in enumerate("ENERO FEBRERO MARZO ABRIL MAYO JUNIO JULIO AGOSTO SEPTIEMBRE OCTUBRE NOVIEMBRE DICIEMBRE".split())}
MES3 = {m: i + 1 for i, m in enumerate("Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split())}
num = lambda s: float(s.replace(",", ""))

def ahorros(path):
    out, cuenta, anio, mes = [], None, None, None
    lines = open(path).read().splitlines()
    for i, l in enumerate(lines):
        if re.fullmatch(r"\d{4} \d{4} \d{4}", l.strip()) and i and "CUENTA DE AHORROS" in lines[i - 1]:
            cuenta = l.strip()[-4:]
        m = re.search(r"INFORME DEL MES:\s*(\w+)\s*/(\d{4})", l)
        if m: mes, anio = MESES[m.group(1).upper()], int(m.group(2))
        m = re.match(r"(\d{2}) (\d{2}) \$ ([\d,]+\.\d{2})([+-]) (\d{4}) (.*)", l)
        if m and cuenta:
            d, mm = int(m.group(1)), int(m.group(2))
            y = anio - 1 if (mes == 1 and mm == 12) else anio
            v = num(m.group(3)) * (1 if m.group(4) == "+" else -1)
            out.append({"fuente": "Davivienda ahorros", "cuenta": cuenta, "fecha": f"{y}-{mm:02d}-{d:02d}",
                        "valor": v, "desc": re.sub(r"\s+", " ", m.group(6)).strip(), "archivo": path})
    return out

def tarjeta(path):
    t = open(path).read()
    if "Detalle de movimientos del mes" not in t: return []
    out = []
    pat = re.compile(r"(\d{2})([A-Z][a-z]{2})(\d{4}) (.+?)\n?\$([\d,]+) (\d+) de (\d+) \$([\d,]+) \$([\d,]+) \$([\d,]+) ([\d,]+) (\d+)", re.S)
    body = t.split("Detalle de movimientos del mes", 1)[1]
    for m in pat.finditer(body):
        desc = re.sub(r"\s+", " ", m.group(4)).strip()
        if len(desc) > 90: continue
        out.append({"fuente": "Davivienda TC", "cuenta": TC,
                    "fecha": f"{m.group(3)}-{MES3[m.group(2)]:02d}-{m.group(1)}",
                    "valor": -num(m.group(5)), "desc": desc, "cuotas": f"{m.group(6)} de {m.group(7)}", "txn": m.group(12), "archivo": path})
    for m in re.finditer(r"(\d{2})([A-Z][a-z]{2})(\d{4}) (COMISION AVANCE|CUOTA DE SEGURO|COMISION[^\n$]*?) (\d{6,}) \$([\d,]+)", t):
        out.append({"fuente": "Davivienda TC", "cuenta": TC, "fecha": f"{m.group(3)}-{MES3[m.group(2)]:02d}-{m.group(1)}",
                    "valor": -num(m.group(6)), "desc": m.group(4).strip(), "cuotas": "", "txn": m.group(5), "archivo": path})
    return out

def todos():
    a, t = [], []
    for f in sorted(glob.glob("pdfs/davivienda/*.txt")):
        a += ahorros(f); t += tarjeta(f)
    # quitar duplicados exactos (mismo extracto bajado dos veces)
    dd = lambda xs: list({(x["cuenta"], x["fecha"], x["valor"], x["desc"]): x for x in xs}.values())
    tc = {}
    for x in t:
        tc.setdefault((x["fecha"], x["txn"], x["valor"]), x)
    return dd(a), list(tc.values())

if __name__ == "__main__":
    import collections
    a, t = todos()
    print(len(a), len(t))
    for k in ("cuenta",):
        print(collections.Counter(x[k] for x in a))
    print(min(x["fecha"] for x in a), max(x["fecha"] for x in a), min(x["fecha"] for x in t), max(x["fecha"] for x in t))
    print(collections.Counter(x["fecha"][:7] for x in t))
