import sys, os, pypdf
from config import C
PW = C["clave_pdf"]   # los bancos en Colombia suelen usar la cédula como clave de los extractos
def text(fn):
    r = pypdf.PdfReader(fn)
    if r.is_encrypted:
        if not r.decrypt(PW): return None
    return "\n".join((p.extract_text() or "") for p in r.pages)
if __name__ == "__main__":
    for fn in sys.argv[1:]:
        t = text(fn)
        out = fn[:-4] + ".txt"
        if t is None: print("NO ABRE", fn); continue
        open(out, "w").write(t)
