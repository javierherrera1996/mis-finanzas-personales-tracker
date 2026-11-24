"""Lee los extractos de crédito Davivienda (.txt) y devuelve el último saldo de cada crédito, y los saldos de cuentas por mes."""
import re, glob, json

MES = {m: i + 1 for i, m in enumerate("Ene Feb Mar Abr May Jun Jul Ago Sep Oct Nov Dic".split())}
num = lambda s: float(s.replace(",", ""))


def creditos():
    """{numero: {"saldo", "fecha", "archivo"}} con el saldo más reciente de cada crédito."""
    out = {}
    for f in sorted(glob.glob("pdfs/davivienda/*.txt")):
        # un mismo PDF puede traer varios créditos ("Extracto Crédito" + número): cada bloque se lee por separado
        for t in re.split(r"(?=^Extracto Cr[eé]dito\n)", open(f).read(), flags=re.M):
            n = re.search(r"No del cr[eé]dito:\s*(\d{15})-\d", t) or re.search(r"^(\d{15})-\d", t, re.M)
            s = re.findall(r"Saldo a:\s*(\w{3})\. (\d{1,2})/(\d{4})\s*\$\s*([\d,\.]+)", t)
            if not n or not s: continue
            mes, dia, anio, val = s[-1]
            fecha = f"{anio}-{MES.get(mes[:3].capitalize(), 1):02d}-{int(dia):02d}"
            k = n.group(1)
            # tasa que de verdad cobran (E.A.): "Cte.Cobrada Periodo 18.99% E.A" (consumo) o "Cte.Cobrada 11.50 Efectivo Anual" (vivienda)
            ta = re.search(r"Cte\.Cobrada(?: Periodo)?\s+([\d.]+)\s*%?\s*(?:E\.A|Efectivo Anual)", t)
            cu = re.search(r"Valor Cuota Mes \$([\d,\.]+)", t)
            g = lambda pat: (lambda r: num(r.group(1)) if r else 0.0)(re.search(pat, t))
            pend = re.search(r"No\. Cuotas Pdtes\. Pago Total\s+(\d+)", t) or re.search(r"No\. Cuotas Pdtes\.[^\n]*?(\d+)\s*$", t, re.M)
            if k not in out or fecha >= out[k]["fecha"]:
                out[k] = {"saldo": num(val), "fecha": fecha, "archivo": f,
                          "tasa_ea": float(ta.group(1)) / 100 if ta else None, "cuota": num(cu.group(1)) if cu else None,
                          "seguro_vida": g(r"Seguro de Vida e ITP \$([\d,\.]+)"), "otros_cargos": g(r"Otros Cargos \* \$([\d,\.]+)"),
                          "intereses_mes": g(r"Intereses Corrientes \$([\d,\.]+)"), "abono_capital": g(r"Abonos a Capital \$([\d,\.]+)"),
                          "total_abonado": g(r"Total Abonado: \$([\d,\.]+)"), "anticipado": g(r"Valor Pagado Por Anticipado \$([\d,\.]+)"),
                          "cuotas_pendientes": int(pend.group(1)) if pend else None}
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


def tarjetas():
    """Último extracto de cada tarjeta de crédito: deuda total, pago total, pago mínimo, fecha límite y tasa E.A. (lo que traiga el PDF)."""
    out = {}
    co = lambda s: float(s.replace(".", "").replace(",", "."))
    M3 = {m: i + 1 for i, m in enumerate("ENE FEB MAR ABR MAY JUN JUL AGO SEP OCT NOV DIC".split())}
    # Davivienda: la tasa aplicada a cada compra viene en la última columna del detalle ("... 3216260 28.47"); la primera es la vigente
    for fn in sorted(glob.glob("pdfs/davivienda/*.txt")):
        t = open(fn).read()
        if "Detalle de movimientos del mes" not in t: continue
        tasas = [float(x) for x in re.findall(r" \d{7} (\d{1,2}\.\d{2})\n", t) if float(x) > 0]
        pt = re.search(r"Pago total \$([\d,]+)", t)
        if tasas or pt:
            out["Tarjeta Davivienda"] = {"tasa_ea": tasas[0] / 100 if tasas else None, "pago_total": num(pt.group(1)) if pt else None, "archivo": fn}
    # Nu: tasa en Mes Vencido (M.V.) por compra; resumen con deuda total, pago total/mínimo y fecha límite
    for fn in sorted(glob.glob("pdfs/nu/*.txt")):
        t = open(fn).read()
        mv = [float(x) for x in re.findall(r"(\d{1,2}\.\d{2})%", t)]
        dt = re.search(r"\$([\d\.]+,\d{2})DEUDA TOTAL", t)
        ptot = re.search(r"\$([\d\.]+,\d{2}) a tu pago total", t)
        pmin = re.search(r"PAGO M[ÍI]NIMO \$([\d\.]+,\d{2})", t)
        fl = re.search(r"Fecha l[íi]mite de pago\n(\d{2}) ([A-Z]{3}) (\d{4})", t)
        mora = re.search(r"Intereses de mora \+ \$([\d\.]+,\d{2})", t)
        if dt or ptot:
            out["Tarjeta Nu"] = {"tasa_mv": max(mv) / 100 if mv else None, "tasa_ea": (1 + max(mv) / 100) ** 12 - 1 if mv else None,
                                 "deuda_total": co(dt.group(1)) if dt else None, "pago_total": co(ptot.group(1)) if ptot else None,
                                 "pago_minimo": co(pmin.group(1)) if pmin else None, "intereses_mora": co(mora.group(1)) if mora else 0,
                                 "fecha_limite": f"{fl.group(3)}-{M3[fl.group(2)]:02d}-{fl.group(1)}" if fl else None, "archivo": fn}
    return out


if __name__ == "__main__":
    print(json.dumps(creditos(), indent=1))
    for x in saldos_cuentas()[-6:]: print(x)
