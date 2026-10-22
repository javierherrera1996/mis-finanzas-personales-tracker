"""Lee los extractos de crédito Davivienda (.txt) y devuelve el último saldo de cada crédito, y los saldos de cuentas por mes."""
import re, glob, json

MES = {m: i + 1 for i, m in enumerate("Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split())}
num = lambda s: float(s.replace(",", ""))


def creditos():
    """{numero: {"saldo", "fecha", "archivo"}} con el saldo más reciente de cada crédito."""
    out = {}
    for f in sorted(glob.glob("pdfs/davivienda/*.txt")):
        t = open(f).read()
        n = re.search(r"No del cr[eé]dito:\s*(\d{15})-\d", t) or re.search(r"^(\d{15})-\d", t, re.M)
        s = re.findall(r"Saldo a:\s*(\w{3})\. (\d{1,2})/(\d{4})\s*\$\s*([\d,\.]+)", t)
        if not n or not s: continue
        mes, dia, anio, val = s[-1]
        fecha = f"{anio}-{MES.get(mes[:3].capitalize(), 1):02d}-{int(dia):02d}"
        k = n.group(1)
        if k not in out or fecha >= out[k]["fecha"]:
            out[k] = {"saldo": num(val), "fecha": fecha, "archivo": f}
    return out


def saldos_cuentas():
    """[(mes_informe, cuenta, nuevo_saldo, saldo_bolsillo)] de los extractos de portafolio (ahorros)."""
    MESES = {m: i + 1 for i, m in enumerate("ENERO FEBRERO MARZO ABRIL MAYO JUNIO JULIO AGOSTO SEPTIEMBRE OCTUBRE NOVIEMBRE DICIEMBRE".split())}
    out = {}
    for f in sorted(glob.glob("pdfs/davivienda/*portafolio*.txt")):
        t = open(f).read()
        for m in re.finditer(r"CUENTA DE AHORROS\n(\d{4} \d{4} \d{4})\nINFORME DEL MES: (\w+) /(\d{4}).*?Nuevo Saldo \$([\d,\.]+).*?Saldo Total Bolsillo \$([\d,\.]+)", t, re.S):
            mes = f"{m.group(3)}-{MESES[m.group(2).upper()]:02d}"
            out[(mes, m.group(1)[-4:])] = (num(m.group(4)), num(m.group(5)))
    return [(k[0], k[1], v[0], v[1]) for k, v in sorted(out.items())]


if __name__ == "__main__":
    print(json.dumps(creditos(), indent=1))
    for x in saldos_cuentas()[-6:]: print(x)
