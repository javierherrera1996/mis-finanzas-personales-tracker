"""Arma claude_ai_skills/mis-finanzas.zip: SKILL.md + motor/ (procesar.py, festivos) + los módulos del motor y data_inicial
copiados de la raíz del repo, para que la skill corra exactamente el mismo código que la versión instalada.
Uso: python claude_ai_skills/empaquetar.py"""
import os, shutil, tempfile, zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SKILL = os.path.join(AQUI, "mis-finanzas")
# solo Python estándar: nada de Google, PDFs ni red (el entorno de Claude no instala paquetes)
MODULOS = ["agente", "build", "config", "cuentas", "deudas", "parse_creditos", "parse_davi", "parse_extractos", "parse_otros",
           "tarjetas", "transferencias"]


def armar(destino):
    """Copia la skill completa (con el motor) en destino/mis-finanzas y devuelve esa ruta."""
    d = os.path.join(destino, "mis-finanzas")
    shutil.copytree(SKILL, d, ignore=shutil.ignore_patterns("__pycache__"))
    for m in MODULOS:
        shutil.copy(os.path.join(RAIZ, m + ".py"), os.path.join(d, "motor"))
    shutil.copytree(os.path.join(RAIZ, "data_inicial"), os.path.join(d, "motor", "data_inicial"))
    return d


if __name__ == "__main__":
    tmp = tempfile.mkdtemp()
    d = armar(tmp)
    zp = os.path.join(AQUI, "mis-finanzas.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(d):
            for f in sorted(files):
                z.write(os.path.join(base, f), os.path.relpath(os.path.join(base, f), tmp))
    shutil.rmtree(tmp)
    print(zp, sum(1 for _ in zipfile.ZipFile(zp).namelist()), "archivos")
