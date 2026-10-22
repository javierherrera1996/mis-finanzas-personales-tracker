import json, re, datetime
def parse(path="data/davivienda.jsonl"):
    out = []
    for l in open(path):
        r = json.loads(l)
        if not r["from"].startswith("BANCO_DAVIVIENDA"): continue
        b = r["body"]
        prod = re.search(r"movimiento de su\s*(.*?)\s*terminada(?: \(o\))? en \*+(\d+)", b)
        fecha = re.search(r"Fecha:\s*(\d{4}/\d{2}/\d{2})", b)
        val = re.search(r"Valor Transacci[oó]n:\s*\$?\s*([\d,\.]+)", b)
        clase = re.search(r"Clase de Movimiento:\s*(.*?)\n", b)
        lugar = re.search(r"Lugar de Transacci[oó]n:\s*(.*?)\n", b)
        if not (prod and fecha and val):
            continue
        v = val.group(1)
        v = float(v.replace(",", "")) if re.search(r",\d{3}(\D|$)", v) or "," not in v else float(v.replace(".", "").replace(",", "."))
        c = (clase.group(1) if clase else "").strip(" .,")
        c = re.sub(r"\s*\.\s*", " ", c).strip()
        if c.startswith("Lugar de"): c = ""
        lg = (lugar.group(1) if lugar else "").strip()
        out.append({"id": r["id"], "fecha": fecha.group(1).replace("/", "-"), "producto": prod.group(1) or "?",
                    "cuenta": prod.group(2), "valor": v, "clase": c, "lugar": lg})
    return out
if __name__ == "__main__":
    import collections
    t = parse(); print(len(t))
    c = collections.Counter()
    for x in t: c[x["lugar"]] += x["valor"]
    for k, v in c.most_common(120): print(f"{v:>14,.0f}  {k}")
