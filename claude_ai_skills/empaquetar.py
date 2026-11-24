"""Arma claude_ai_skills/mis-finanzas.zip: SKILL.md + motor/ (procesar.py, festivos) + los módulos del motor y data_inicial
copiados de la raíz del repo, para que la skill corra exactamente el mismo código que la versión instalada.
Además deja el plugin en plugins/mis-finanzas/ (lo que instala Claude desde el marketplace de este repo).
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


def armar_plugin(destino, nombre="mis-finanzas-plugin"):
    """El mismo contenido como plugin de Claude (claude.com/docs/plugins/build): .claude-plugin/plugin.json, la skill en
    skills/mis-finanzas/, comandos en commands/ y el README. Se sube en Customize > Plugins > Add > Upload plugin, o se
    publica en un repo de GitHub como marketplace."""
    d = os.path.join(destino, nombre)
    os.makedirs(os.path.join(d, "skills"))
    armar(os.path.join(d, "skills"))
    shutil.copytree(os.path.join(AQUI, "plugin"), d, dirs_exist_ok=True)
    return d


def comprimir(carpeta, zp):
    base = os.path.dirname(carpeta)
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for raiz, _, files in os.walk(carpeta):
            for f in sorted(files):
                z.write(os.path.join(raiz, f), os.path.relpath(os.path.join(raiz, f), base))
    print(zp, len(zipfile.ZipFile(zp).namelist()), "archivos")


def publicar_en_repo():
    """Deja el plugin armado en plugins/mis-finanzas/: de ahí lo instala Claude cuando agregan este repo como marketplace
    (.claude-plugin/marketplace.json en la raíz). Hay que correrlo y hacer commit cada vez que cambie la skill o el motor;
    tests/test_plugin_repo.py falla si quedó desactualizado."""
    plugins = os.path.join(RAIZ, "plugins")
    shutil.rmtree(os.path.join(plugins, "mis-finanzas"), ignore_errors=True)
    os.makedirs(plugins, exist_ok=True)
    d = armar_plugin(plugins, "mis-finanzas")
    print(d, sum(len(f) for _, _, f in os.walk(d)), "archivos")


if __name__ == "__main__":
    tmp = tempfile.mkdtemp()
    comprimir(armar(tmp), os.path.join(AQUI, "mis-finanzas.zip"))
    comprimir(armar_plugin(os.path.join(tmp, "plugin")), os.path.join(AQUI, "mis-finanzas-plugin.zip"))
    shutil.rmtree(tmp)
    publicar_en_repo()
