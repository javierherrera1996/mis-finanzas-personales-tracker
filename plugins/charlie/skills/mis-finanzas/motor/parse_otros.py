"""Lee extractos de tarjeta Nu (.txt) y alertas Bancolombia (data/otros.jsonl)."""
import re, glob, json, datetime
from config import BANCO
M3 = {m: i + 1 for i, m in enumerate("ENE FEB MAR ABR MAY JUN JUL AGO SEP OCT NOV DIC".split())}
co = lambda s: float(s.replace(".", "").replace(",", "."))   # 1.234.567,89
us = lambda s: float(s.replace(",", ""))                       # 1,234,567.89

def nu(path):
    t = open(path).read()
    out = []
    pat = re.compile(r"(\d{2}) ([A-Z]{3})\n(\d{4})\n(.+?)\s*(-?)\$([\d\.]+,\d{2}) (\d+) de (\d+) ", re.S)
    for m in pat.finditer(t):
        desc = re.sub(r"\s+", " ", m.group(4)).strip()
        if len(desc) > 60: continue
        v = co(m.group(6))
        out.append({"fuente": "Nu TC", "cuenta": "Nu", "fecha": f"{m.group(3)}-{M3[m.group(2)]:02d}-{m.group(1)}",
                    "valor": v if m.group(5) == "-" else -v, "desc": desc, "cuotas": f"{m.group(7)} de {m.group(8)}", "archivo": path})
    return out

def nu_todos():
    d = {}
    for f in sorted(glob.glob("pdfs/nu/*Nu_20*.txt")):
        for x in nu(f):
            d.setdefault((x["fecha"], x["valor"], x["desc"]), x)  # misma compra a cuotas aparece en varios extractos
    return list(d.values())

def cuenta_nu():
    """Saldo de la Cuenta Nu (ahorros) y sus cajitas según el último extracto mensual, o None si no hay extractos."""
    fs = sorted(glob.glob("pdfs/nu/*CuentaNu_*.txt"))
    if not fs: return None
    t = open(fs[-1]).read()
    g = lambda k: (lambda m: co(m.group(1)) if m else 0.0)(re.search(k + r"\n?\$([\d\.]+,\d{2})", t))
    per = re.search(r"Período\n\d{2} - (\d{2}) ([A-Z]{3}) (\d{4})", t)
    fecha = f"{per.group(3)}-{M3[per.group(2)]:02d}-{per.group(1)}" if per else ""
    return {"cuenta": g("Dinero en tu Cuenta Nu"), "cajitas": g("Dinero en tus cajitas"), "fecha": fecha,
            "movimientos": "No hiciste movimientos" not in t, "archivo": fs[-1]}

def bancolombia(path="data/otros.jsonl"):
    out = []
    for l in open(path):
        r = json.loads(l)
        if "bancolombia" not in (r["from"] or "").lower(): continue
        b = re.sub(r"\s+", " ", r["body"])
        m = re.search(r"Bancolombia: (.*?)(?:\. ?Con |\. ?¿Dudas|\. ?Dudas|\. ?Si tienes|\. ?¿Tienes|\. ?Siempre|\. ?Veras|$)", b)
        if not m: continue
        txt = m.group(1)
        if re.search(r"no fue exitosa|rechaz", txt, re.I): continue
        mc = re.search(r"(?:\$|COP)\s?([\d\.]+,\d{2})(?!\d)", txt)
        mu = re.search(r"\$([\d,]+(?:\.\d{2})?)(?![\d,])", txt)
        if mc: monto = co(mc.group(1))
        elif mu: monto = us(mu.group(1))
        else: continue
        f1 = re.search(r"(\d{4})/(\d{2})/(\d{2})", txt); f2 = re.search(r"(\d{2})/(\d{2})/(\d{2,4})", txt)
        if f1: f = f"{f1.group(1)}-{f1.group(2)}-{f1.group(3)}"
        elif f2: f = f"{'20' + f2.group(3) if len(f2.group(3)) == 2 else f2.group(3)}-{f2.group(2)}-{f2.group(1)}"
        else: f = datetime.date.fromtimestamp(r["date"]).isoformat()
        entra = re.match(r"(\w+, )?(recibiste|recibiras|te consignaron)", txt, re.I)
        cta = re.search(r"T\.? ?Cred(?:ito)?\s*(?:MASTER\s*)?\*+(\d{4})|tarjeta de credito (?:MASTER )?\*+(\d{4})|T\.Deb \*+(\d{4})|desde tu (?:cuenta|producto) \*?(\d{4})|en tu cuenta \*+(\d{4})|tu cuenta \*(\d{4})", txt)
        aho = BANCO.get("ahorros") or "?"
        cuenta = next((g for g in cta.groups() if g), "?") if cta else (aho if "AHORROS" in txt else "?")
        if cuenta and cuenta == BANCO.get("tarjeta_debito"): cuenta = aho   # tarjeta débito de la cuenta de ahorros
        out.append({"fuente": "Bancolombia", "cuenta": cuenta, "fecha": f,
                    "valor": monto * (1 if entra else -1), "desc": txt[:200], "id": r["id"]})
    return out

if __name__ == "__main__":
    n = nu_todos(); b = bancolombia()
    print("Nu", len(n), min(x["fecha"] for x in n), max(x["fecha"] for x in n))
    print("Bancolombia", len(b))
    for x in sorted(b, key=lambda x: x["fecha"])[:3] + sorted(b, key=lambda x: -abs(x["valor"]))[:12]:
        print(x["fecha"], f"{x['valor']:>12,.0f}", x["desc"][:120])
