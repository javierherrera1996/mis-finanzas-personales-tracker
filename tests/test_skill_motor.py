"""El motor de la skill de claude.ai (claude_ai_skills/mis-finanzas/motor/procesar.py) da lo mismo que la versión instalada
con las alertas que Claude trae de Gmail: en una carpeta de solo lectura, sin librerías de afuera, con el texto del correo en
una sola línea y actualizando en dos tandas que se solapan. Correr: python -m unittest discover -s tests"""
import copy, json, os, shutil, stat, subprocess, sys, tempfile, unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "claude_ai_skills"))
sys.path.insert(0, os.path.join(RAIZ, "tests"))
import empaquetar
from test_usuario_nuevo import ALERTAS, CONFIG

BANCOLOMBIA = "Alertas y Notificaciones <alertasynotificaciones@notificacionesbancolombia.com>"
DAVI = ("DAVIVIENDA \r\n Apreciado(a) LAURA:\n Le informamos que se ha registrado el siguiente movimiento de su Cta de Ahorros "
        "terminada (o) en ****7777:\n Fecha: 2026/10/10\r\nHora: 10:00:00 \r\nValor Transacción: $50,000 \r\nClase de Movimiento: "
        "Compra en Establecimiento,\r\nLugar de Transacción: OXXO CALLE 85\n Atentamente,\n BANCO DAVIVIENDA S.A.")


def correos():
    return [{"id": f"m{i}", "fecha": f + "T12:00:00", "de": BANCOLOMBIA, "asunto": "Alertas y Notificaciones",
             "texto": f"Bancolombia: {t}. ¿Dudas? llamanos"} for i, (f, t) in enumerate(ALERTAS)]


class MotorSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="skill-")
        cls.motor = os.path.join(empaquetar.armar(cls.dir), "motor", "procesar.py")
        for base, dirs, files in os.walk(cls.dir):   # en claude.ai la carpeta de la skill puede ser de solo lectura
            for f in files: os.chmod(os.path.join(base, f), stat.S_IREAD)

    @classmethod
    def tearDownClass(cls):
        for base, dirs, files in os.walk(cls.dir):
            for f in files: os.chmod(os.path.join(base, f), stat.S_IREAD | stat.S_IWRITE)
        shutil.rmtree(cls.dir, ignore_errors=True)

    def correr(self, entrada):
        d = tempfile.mkdtemp(dir=self.dir)
        with open(os.path.join(d, "entrada.json"), "w") as f:
            json.dump(entrada, f, ensure_ascii=False)
        r = subprocess.run([sys.executable, "-S", "-W", "ignore", self.motor, "entrada.json", "salida.json"], cwd=d,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        with open(os.path.join(d, "salida.json")) as f:
            return json.load(f)

    def test_igual_que_la_version_instalada(self):
        s = self.correr({"config": CONFIG, "correos": correos()})
        r = s["resumen"]
        # lo mismo que test_usuario_nuevo con el motor instalado
        self.assertEqual(r["plata_en_cuentas"], 3200000 + 4500000 - 500000 - 85000 - 200000)
        self.assertEqual(r["inversiones"], 4000000 + 500000)
        self.assertEqual(len(s["nuevos"]), len(ALERTAS))
        self.assertEqual(s["no_leidos"], [])
        trii = next(m for m in s["nuevos"] if "TRII" in m["Descripción"])
        self.assertEqual((trii["Tipo"], trii["Contraparte"]), ("Interno", "Trii"))

    def test_dos_tandas_que_se_solapan(self):
        todos = correos()
        una = self.correr({"config": CONFIG, "correos": todos})
        t1 = self.correr({"config": CONFIG, "correos": todos[:3]})
        t2 = self.correr({"config": CONFIG, "correos": todos[2:], "movimientos_previos": t1["nuevos"]})
        ids = [m["ID"] for m in t1["nuevos"] + t2["nuevos"]]
        self.assertEqual(sorted(ids), sorted(m["ID"] for m in una["nuevos"]))
        self.assertEqual(t2["resumen"]["plata_en_cuentas"], una["resumen"]["plata_en_cuentas"])

    def test_reglas_tarjeta_y_bancos_sin_lector(self):
        cfg = copy.deepcopy(CONFIG)
        tc = next(c for c in cfg["cuentas"] if c["tipo"] == "tarjeta_credito")
        tc["saldo"] = {"valor": 1000000, "fecha": "2026-09-29"}
        nequi = next(c for c in cfg["cuentas"] if c["institucion"] == "Nequi")
        nequi["saldo"] = {"valor": 100000, "fecha": "2026-10-21"}
        extra = [{"fecha": "2026-10-22", "valor": 200000, "descripcion": "Recibiste de LAURA PRUEBA", "institucion": "Nequi",
                  "producto": "3109998877"},
                 {"fecha": "2026-10-23", "valor": -30000, "descripcion": "Pago en TIENDA D1 desde Nequi", "institucion": "Nequi",
                  "producto": "3109998877"}]
        otro = {"id": "x1", "fecha": "2026-10-23", "de": "Lulo Bank <notificaciones@lulobank.com>", "asunto": "Movimiento",
                "texto": "Hiciste una compra por $10.000"}
        roomie = {"id": "r1", "fecha": "2026-10-25", "de": BANCOLOMBIA, "asunto": "Alertas y Notificaciones",
                  "texto": "Bancolombia: Recibiste una transferencia de CARLOS PEREZ por $1.500.000,00 en tu cuenta *4455 el 25/10/2026 a las 10:00. ¿Dudas? llamanos"}
        s = self.correr({"config": cfg, "correos": correos() + [otro, roomie], "movimientos_extra": extra,
                         "reglas": [{"si_aparece": "EXITO CALLE 80", "tipo": "Gasto", "categoria": "Mercado", "subcategoria": "Mercado del mes"},
                                    {"si_aparece": "CARLOS PEREZ", "tipo": "Gasto", "categoria": "Vivienda", "subcategoria": "Roomie paga su parte"}]})
        exito = next(m for m in s["nuevos"] if "EXITO" in m["Descripción"])
        self.assertEqual((exito["Categoría"], exito["Subcategoría"]), ("Mercado", "Mercado del mes"))
        # lo que paga el roomie resta del gasto de Vivienda: no es ingreso
        carlos = next(m for m in s["nuevos"] if "CARLOS" in m["Descripción"])
        self.assertEqual((carlos["Tipo"], carlos["Categoría"], carlos["Valor"]), ("Gasto", "Vivienda", 1500000))
        deuda = next(t for t in s["tarjetas"] if "8899" in t["nombre"])["deuda"]
        self.assertEqual(deuda, 1000000 + 120000)
        # el Nequi: 100.000 confirmados + los 200.000 que le llegaron desde Bancolombia − 30.000 de la compra (alertas que leyó Claude)
        ne = next(c for c in s["cuentas"] if c["nombre"].startswith("Nequi"))
        self.assertEqual(ne["saldo"], 100000 + 200000 - 30000)
        # y esos 200.000 son plata entre sus cuentas: ni gasto en Bancolombia ni ingreso en Nequi
        traslado = [m for m in s["nuevos"] if abs(m["Valor"]) == 200000]
        self.assertEqual([m["Tipo"] for m in traslado], ["Interno", "Interno"])
        self.assertEqual([x["id"] for x in s["no_leidos"]], ["x1"])

    def test_davivienda_con_el_texto_en_una_linea(self):
        cfg = copy.deepcopy(CONFIG)
        cfg["cuentas"].append({"institucion": "Davivienda", "tipo": "ahorros", "terminacion": "7777", "saldo": {"valor": 500000, "fecha": "2026-10-01"}})
        base = {"id": "d1", "fecha": "2026-10-10T10:00:00", "de": "BANCO_DAVIVIENDA@davivienda.com", "asunto": "DAVIVIENDA"}
        normal = self.correr({"config": cfg, "correos": [dict(base, texto=DAVI)]})
        plano = self.correr({"config": cfg, "correos": [dict(base, texto=" ".join(DAVI.split()))]})
        self.assertEqual(len(normal["nuevos"]), 1)
        self.assertEqual(normal["nuevos"], plano["nuevos"])
        self.assertEqual(normal["nuevos"][0]["Descripción"], "Compra en Establecimiento, OXXO CALLE 85")


if __name__ == "__main__":
    unittest.main()
