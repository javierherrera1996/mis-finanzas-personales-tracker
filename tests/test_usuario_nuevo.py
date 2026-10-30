"""Prueba de humo del onboarding: una usuaria nueva (Bancolombia, tarjeta, Nequi y Trii; sin Davivienda ni extractos) corre
cada paso de la primera actualización con Google simulado, primero sin ningún correo y luego con unas alertas.
Nada debe fallar. Correr: python -m unittest discover -s tests"""
import datetime, glob, json, os, shutil, subprocess, sys, tempfile, unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    import googleapiclient.discovery   # noqa: F401
    HAY_GOOGLE = True
except ImportError:
    HAY_GOOGLE = False

CONFIG = {
    "nombre": "Laura Prueba", "correo": "laura@example.com", "clave_pdf": "52123456", "documento": "52123456", "desde": "2026-01-01",
    "nombre_en_bancos": ["LAURA PRUEBA"],
    "cuentas": [
        {"institucion": "Bancolombia", "tipo": "ahorros", "terminacion": "4455", "tarjeta_debito": "1234", "saldo": {"valor": 3200000, "fecha": "2026-09-29"}},
        {"institucion": "Bancolombia", "tipo": "tarjeta_credito", "terminacion": "8899"},
        {"institucion": "Nequi", "tipo": "billetera", "celular": "3109998877"},
        {"institucion": "Trii", "tipo": "inversion", "saldo": {"valor": 4000000, "fecha": "2026-09-01"}},
    ],
    "sueldo": {"dia_pago": 30, "neto_que_llega": 4500000, "otros_ingresos_mes": 0},
    "techo_gasto_mes": 2500000, "fijos_mes": 0, "excluir_del_variable": "Vivienda|Impuestos", "gasto_ritmo_actual": 0,
    "renta_anual": {"monto": 0, "mes": 10}, "metas_categoria": {}, "libranzas_nomina": [], "netear_con": [], "reglas_personales": [],
}

ALERTAS = [   # (fecha, texto) inventados con el formato de las alertas de Bancolombia
    ("2026-09-30", "Recibiste un pago de Nomina de EMPRESA EJEMPLO SAS por $4.500.000,00 en tu cuenta *4455 el 30/09/2026 a las 08:10"),
    ("2026-10-02", "Pagaste $500.000,00 a TRII SAS por PSE desde tu cuenta *4455 el 02/10/2026 a las 10:00"),
    ("2026-10-15", "Compraste $85.000,00 en EXITO CALLE 80 con tu T.Deb *1234, el 15/10/2026 a las 12:30"),
    ("2026-10-20", "Compraste $120.000,00 en RESTAURANTE EJEMPLO con tu T.Cred *8899, el 20/10/2026 a las 21:00"),
    ("2026-10-22", "Transferiste $200.000,00 desde tu cuenta *4455 a la cuenta *3109998877 el 22/10/2026 a las 09:00"),
]

# corre un script con un Google falso (sin credentials.json ni internet) que responde como Sheets, Drive y Calendar
SIN_GOOGLE = """
import runpy, sys
import googleapiclient.discovery as gd
import auth

class Google:
    pestanas = {}
    def __init__(self, ruta=(), k=None): self.ruta, self.k = ruta, k or {}
    def __getattr__(self, n): return Google(self.ruta + (n,))
    def __call__(self, *a, **k): return Google(self.ruta, k)
    def execute(self, *a, **k):
        r, cuerpo, P = self.ruta, self.k.get("body") or {}, Google.pestanas
        if r == ("spreadsheets", "create"):
            for s in cuerpo.get("sheets", []): P[s["properties"]["title"]] = len(P) + 1
            return {"spreadsheetId": "hoja-falsa"}
        if r == ("spreadsheets", "batchUpdate"):
            for q in cuerpo.get("requests", []):
                if "addSheet" in q: P[q["addSheet"]["properties"]["title"]] = len(P) + 100
                if "deleteSheet" in q: [P.pop(t) for t, i in list(P.items()) if i == q["deleteSheet"]["sheetId"]]
            return {"replies": []}
        if r == ("spreadsheets", "get"): return {"sheets": [{"properties": {"title": t, "sheetId": i}} for t, i in P.items()]}
        if r == ("spreadsheets", "values", "get"): return {"values": []}
        if r == ("files", "create"): return {"id": "doc-falso"}
        if r == ("files", "export"): return b""
        if r == ("events", "list"): return {"items": []}
        return {}

gd.build = lambda *a, **k: Google()
auth.get_creds = lambda *a, **k: None
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


class UsuarioNuevo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="finanzas-nuevo-")
        for f in glob.glob(os.path.join(RAIZ, "*.py")):
            shutil.copy(f, self.dir)
        os.makedirs(os.path.join(self.dir, "data"))
        os.makedirs(os.path.join(self.dir, "pdfs"))
        for f in glob.glob(os.path.join(RAIZ, "data_inicial", "*.json")):
            shutil.copy(f, os.path.join(self.dir, "data"))
        with open(os.path.join(self.dir, "config.json"), "w") as f:
            json.dump(CONFIG, f)
        with open(os.path.join(self.dir, "_sin_google.py"), "w") as f:
            f.write(SIN_GOOGLE)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def correr(self, *args, google=False):
        cmd = [sys.executable, "-W", "ignore"] + (["_sin_google.py"] if google else []) + list(args)
        r = subprocess.run(cmd, cwd=self.dir, capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, f"{' '.join(args)} falló:\n{r.stderr[-3000:]}")
        return r.stdout

    def primera_actualizacion(self):
        """Los pasos de actualizar.py después de bajar correos y PDFs, en el mismo orden."""
        if HAY_GOOGLE:
            self.correr("sheet_sync.py", google=True)
        self.correr("build.py")
        self.correr("-c", "import agente, json; agente.nuevas_preguntas(json.load(open('data/movimientos.json')))")
        if HAY_GOOGLE:
            self.correr("make_sheet.py", google=True)
            self.correr("plan_sheet.py", google=True)
            self.correr("contexto_doc.py", google=True)
            self.correr("calendario.py", google=True)
            self.correr("informe_semanal.py", "--no-enviar", google=True)
        self.correr("estado_general.py")
        self.dia_de_pago = self.correr("dia_de_pago.py", "--simular=2026-10-30", "--no-enviar")
        self.correr("deudas.py")
        self.correr("tarjetas.py")
        return json.loads(self.correr("-c", "import agente, json; e = agente.estado(); "
                                      "print(json.dumps({'caja': e['caja']['total'], 'inversiones': e['caja']['inversiones'], "
                                      "'sin_saldo': e['caja']['sin_saldo'], 'libre': e['libre'], "
                                      "'pagos': [p['nombre'] for p in e['proximos']], 'sueldo': agente.pagos_config()['pagos'][0]}))").strip().splitlines()[-1])

    def test_sin_ningun_correo(self):
        e = self.primera_actualizacion()
        self.assertEqual(e["caja"], 3200000)
        self.assertEqual(e["inversiones"], 4000000)
        self.assertIn("Nequi", e["sin_saldo"])
        # el sueldo sale de config.json (día 30, $4.500.000) y no hay pagos de ejemplo pendientes
        self.assertEqual((e["sueldo"]["dia"], e["sueldo"]["monto"]), (30, 4500000))
        self.assertIn("$4.500.000", self.dia_de_pago)
        self.assertFalse([p for p in e["pagos"] if "EJEMPLO" in p.upper() or "Arriendo" in p])

    def test_con_alertas_de_bancolombia(self):
        with open(os.path.join(self.dir, "data", "otros.jsonl"), "w") as f:
            for i, (fecha, txt) in enumerate(ALERTAS):
                ts = int(datetime.datetime.fromisoformat(fecha + "T12:00:00").timestamp())
                f.write(json.dumps({"id": f"m{i}", "date": ts, "from": "Bancolombia <alertasynotificaciones@notificacionesbancolombia.com>",
                                    "subject": "Alertas y Notificaciones", "body": f"Bancolombia: {txt}. ¿Dudas? llamanos", "atts": []}) + "\n")
        e = self.primera_actualizacion()
        with open(os.path.join(self.dir, "data", "movimientos.json")) as f:
            movs = json.load(f)
        self.assertEqual(len(movs), len(ALERTAS))
        trii = next(m for m in movs if "TRII" in m["Descripción"])
        self.assertEqual(trii["Tipo"], "Interno")   # plata hacia su inversión: ni gasto ni ingreso
        sueldo = next(m for m in movs if m["Valor"] == 4500000)
        self.assertEqual(sueldo["Categoría"], "Salario")
        # caja = saldo confirmado (29-sep) + sueldo − Trii − compra con débito − Nequi; la compra con tarjeta no sale de la cuenta
        self.assertEqual(e["caja"], 3200000 + 4500000 - 500000 - 85000 - 200000)
        self.assertEqual(e["inversiones"], 4000000 + 500000)


if __name__ == "__main__":
    unittest.main()
