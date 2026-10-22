"""Datos personales del usuario (config.json). Todo lo que cambia de persona a persona sale de aquí."""
import json, os

_DIR = os.path.dirname(os.path.abspath(__file__))
_P = os.path.join(_DIR, "config.json")
if not os.path.exists(_P):
    raise SystemExit("Falta config.json: copia config.ejemplo.json como config.json y llénalo (o pídele a Claude que lo haga contigo).")
C = json.load(open(_P))

DAVI = C.get("davivienda", {})
BANCO = C.get("bancolombia", {})
SUELDO = C.get("sueldo", {})


def regex_propio():
    """Regex de transferencias hechas por/para el propio usuario (su nombre como aparece en los bancos y su documento)."""
    partes = [n for n in C.get("nombre_en_bancos", []) if n and "APELLIDO" not in n]
    # el documento solo como "BANCOLOMBIA <doc>": Davivienda pone tu cédula también en transferencias que haces a OTROS
    if C.get("documento") and C["documento"] != "TU_CEDULA": partes.append("BANCOLOMBIA " + C["documento"])
    return "|".join(partes) or r"(?!x)x"   # nunca coincide si no está configurado


def regex_celulares():
    cel = [c for c in C.get("celulares_propios", []) if c and c != "3000000000"]
    return "|".join(cel) or r"(?!x)x"
