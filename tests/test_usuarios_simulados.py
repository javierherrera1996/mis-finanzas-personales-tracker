"""¿Va a funcionar con usuarios? Cinco personas inventadas, cada una con su propia mezcla de bancos y hábitos, pasan por
todo el recorrido de CHARLIE con el motor empaquetado (el mismo que corre en claude.ai):

  1. Configuración: las últimas 2 semanas de alertas (historia_desde) y la primera revisión de avisos (no manda nada).
  2. Siete actualizaciones que completan la historia una semana hacia atrás, llevando la memoria de los avisos.
  3. Al final: resumen financiero, tablero, simulaciones.

En cada corrida se verifican las reglas que no se pueden romper con nadie: lee todas las alertas, no duplica
movimientos, la plata entre cuentas propias no es gasto, nada anterior a la historia leída queda "atrasado", lo que
tienes − lo que debes cuadra, el tablero cabe en el almacén, máximo 2 correos de avisos al día, máximo 7 preguntas y
ninguna simulación falla. Personas: estudiante sin sueldo (Bancolombia + Nequi), alguien con mucho movimiento
(Bancolombia + tarjeta + Davivienda, ≈ 8 alertas al día), alguien sin alertas en el correo, alguien solo con
Davivienda y alguien con varias deudas. Correr: python -m unittest tests.test_usuarios_simulados"""
import copy, datetime, json, os, random, shutil, stat, subprocess, sys, tempfile, time, unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "claude_ai_skills"))
import empaquetar  # noqa: E402

HOY = datetime.date.today()
D = lambda n: HOY - datetime.timedelta(days=n)
F = lambda d: d.strftime("%d/%m/%Y")
BANCOLOMBIA = "Alertas y Notificaciones <alertasynotificaciones@notificacionesbancolombia.com>"
DAVIVIENDA = "BANCO_DAVIVIENDA@davivienda.com"
DIAS = 63   # 9 semanas: 2 de configuración + 7 hacia atrás


def pesos(v):
    return f"${v:,}".replace(",", ".") + ",00"


def bc(i, fecha, texto):
    return {"id": f"b{i}", "fecha": fecha.isoformat() + "T12:00:00", "de": BANCOLOMBIA, "asunto": "Alertas y Notificaciones",
            "texto": f"Bancolombia: {texto}. ¿Dudas? llamanos"}


def davi(i, fecha, cuenta, valor, clase, lugar):
    return {"id": f"d{i}", "fecha": fecha.isoformat() + "T12:00:00", "de": DAVIVIENDA, "asunto": "DAVIVIENDA",
            "texto": ("DAVIVIENDA \r\n Apreciado(a) CLIENTE:\n Le informamos que se ha registrado el siguiente movimiento de su Cta de Ahorros "
                      f"terminada (o) en ****{cuenta}:\n Fecha: {fecha:%Y/%m/%d}\r\nHora: 12:00:00 \r\nValor Transacción: ${valor:,} \r\n"
                      f"Clase de Movimiento: {clase},\r\nLugar de Transacción: {lugar}\n Atentamente,\n BANCO DAVIVIENDA S.A.")}


def compras(rnd, n_dia, tarjeta, comercios, desde=1, hasta=DIAS, ini=0, credito=False):
    out = []
    for d in range(desde, hasta + 1):
        for _ in range(n_dia if isinstance(n_dia, int) else rnd.choice(n_dia)):
            c, (a, b) = rnd.choice(comercios)
            v = rnd.randrange(a, b, 100)
            out.append(bc(ini + len(out), D(d), f"Compraste {pesos(v)} en {c} con tu {'T.Cred' if credito else 'T.Deb'} *{tarjeta}, el {F(D(d))} a las 12:30"))
    return out


COMERCIOS = [("EXITO CALLE 80", (30000, 180000)), ("RAPPI RESTAURANTES", (20000, 70000)), ("UBER RIDES", (9000, 35000)),
             ("D1 CALLE 85", (10000, 60000)), ("FARMATODO", (15000, 120000)), ("CINE COLOMBIA", (25000, 60000))]


def base(nombre, cuentas, sueldo=None):
    return {"nombre": nombre, "nombre_en_bancos": [nombre.upper()], "cuentas": cuentas, "sueldo": sueldo or {},
            "techo_gasto_mes": 0, "fijos_mes": 0}


def personas():
    rnd = random.Random(24)
    P = {}
    # 1. Estudiante: Bancolombia + Nequi, sin sueldo (la mamá le pasa plata), pocas compras
    cs = compras(rnd, [0, 1, 1, 2], "1101", COMERCIOS[:4])
    for k, d in enumerate((5, 20, 35, 50)):
        cs.append(bc(900 + k, D(d), f"Recibiste una transferencia por {pesos(800000)} de MARIA MADRE en tu cuenta *1100 el {F(D(d))} a las 09:00"))
    P["estudiante"] = {"config": base("Sara Estudiante", [
        {"institucion": "Bancolombia", "tipo": "ahorros", "terminacion": "1100", "tarjeta_debito": "1101", "saldo": {"valor": 650000, "fecha": D(DIAS + 1).isoformat()}},
        {"institucion": "Nequi", "tipo": "billetera", "celular": "3001112233"}]),
        "correos": cs, "fijos": [{"nombre": "Celular", "dia": 12, "monto": 45000, "tipo": "pago", "buscar": "CLARO"}]}
    # 2. Mucho movimiento: Bancolombia + tarjeta + Davivienda, sueldo, arriendo por PSE, traslado a su Davivienda
    cs = compras(rnd, [2, 3, 4], "2201", COMERCIOS) + compras(rnd, [0, 1], "2244", COMERCIOS[1:], ini=5000, credito=True)
    for k, d in enumerate((2, 32, 62)):
        cs.append(bc(8000 + k, D(d), f"Recibiste un pago de Nomina de EMPRESA GRANDE SAS por {pesos(9000000)} en tu cuenta *2200 el {F(D(d))} a las 08:10"))
        cs.append(bc(8100 + k, D(d - 1 if d > 1 else d), f"Pagaste {pesos(2500000)} a INMOBILIARIA CENTRO por PSE desde tu cuenta *2200 el {F(D(d - 1 if d > 1 else d))} a las 10:00"))
        cs.append(bc(8200 + k, D(d), f"Transferiste {pesos(2000000)} desde tu cuenta *2200 a la cuenta *5555 el {F(D(d))} a las 11:00"))
    for k, d in enumerate(range(3, DIAS, 9)):
        cs.append(davi(8300 + k, D(d), "5555", rnd.randrange(20000, 150000, 1000), "Compra en Establecimiento", "OXXO CALLE 85"))
    P["mucho_movimiento"] = {"config": base("Andres Mucho", [
        {"institucion": "Bancolombia", "tipo": "ahorros", "terminacion": "2200", "tarjeta_debito": "2201", "saldo": {"valor": 3000000, "fecha": D(DIAS + 1).isoformat()}},
        {"institucion": "Bancolombia", "tipo": "tarjeta_credito", "terminacion": "2244", "dia_pago": 15, "dia_corte": 30},
        {"institucion": "Davivienda", "tipo": "ahorros", "terminacion": "5555", "saldo": {"valor": 1000000, "fecha": D(DIAS + 1).isoformat()}}],
        {"dia_pago": "penultimo_habil", "neto_que_llega": 9000000}),
        "correos": cs, "fijos": [{"nombre": "Arriendo", "dia": D(1).day, "monto": 2500000, "tipo": "pago", "buscar": "INMOBILIARIA CENTRO"}],
        "creditos": [{"nombre": "Libre inversión", "entidad": "Banco", "saldo": 25000000, "tasa_ea": 21, "cuota": 900000, "dia_pago": 5}]}
    # 3. Sin alertas en el correo: todo a mano
    P["sin_alertas"] = {"config": base("Camila Manual", [
        {"institucion": "BBVA", "tipo": "ahorros", "terminacion": "7700", "saldo": {"valor": 2300000, "fecha": HOY.isoformat()}},
        {"institucion": "BBVA", "tipo": "tarjeta_credito", "terminacion": "7711", "dia_pago": 20, "saldo": {"valor": 900000, "fecha": HOY.isoformat()}}],
        {"dia_pago": 30, "neto_que_llega": 3800000}),
        "correos": [], "fijos": [{"nombre": "Arriendo", "dia": 5, "monto": 1200000, "tipo": "pago", "buscar": "ARRIENDO"},
                                 {"nombre": "Internet", "dia": 15, "monto": 90000, "tipo": "pago", "buscar": ""}]}
    # 4. Solo Davivienda (las alertas llegan con el texto en una sola línea a veces)
    cs = []
    for k, d in enumerate(range(1, DIAS + 1)):
        for j in range(rnd.choice([0, 1, 2, 3])):
            m = davi(len(cs), D(d), "3300", rnd.randrange(8000, 200000, 500), "Compra en Establecimiento", rnd.choice(["OXXO CALLE 85", "CARULLA 93", "TERPEL AV 68"]))
            if j % 2:
                m["texto"] = " ".join(m["texto"].split())
            cs.append(m)
    P["solo_davivienda"] = {"config": base("Diego Davivienda", [
        {"institucion": "Davivienda", "tipo": "ahorros", "terminacion": "3300", "saldo": {"valor": 1800000, "fecha": D(DIAS + 1).isoformat()}}],
        {"dia_pago": 15, "neto_que_llega": 3000000}), "correos": cs, "fijos": []}
    # 5. Varias deudas
    cs = compras(rnd, [1, 2, 3], "6601", COMERCIOS, ini=0) + compras(rnd, [0, 1], "6644", COMERCIOS[:3], ini=7000, credito=True)
    for k, d in enumerate((4, 34)):
        cs.append(bc(9000 + k, D(d), f"Recibiste un pago de Nomina de OFICINA SAS por {pesos(4200000)} en tu cuenta *6600 el {F(D(d))} a las 08:10"))
    P["deudas"] = {"config": base("Lucia Deudas", [
        {"institucion": "Bancolombia", "tipo": "ahorros", "terminacion": "6600", "tarjeta_debito": "6601", "saldo": {"valor": 900000, "fecha": D(DIAS + 1).isoformat()}},
        {"institucion": "Bancolombia", "tipo": "tarjeta_credito", "terminacion": "6644", "dia_pago": 25, "tasa_ea": 28,
         "saldo": {"valor": 3500000, "fecha": D(DIAS + 1).isoformat()}}], {"dia_pago": 30, "neto_que_llega": 4200000}),
        "correos": cs, "fijos": [],
        "creditos": [{"nombre": "Libre inversión", "entidad": "Banco A", "saldo": 15000000, "tasa_ea": 24, "cuota": 650000, "dia_pago": 10},
                     {"nombre": "Vehículo", "entidad": "Banco B", "saldo": 30000000, "tasa_ea": 15, "cuota": 1100000, "dia_pago": 20},
                     {"nombre": "ICETEX", "entidad": "ICETEX", "saldo": 12000000, "tasa_ea": 6, "cuota": 280000, "dia_pago": 5}]}
    return P


SIMULACIONES = [{"tipo": "me_alcanza", "monto": 150000}, {"tipo": "ahorrar_para", "monto": 2000000, "fecha": (HOY + datetime.timedelta(days=150)).isoformat()},
                {"tipo": "salir_de_deudas", "extra_mes": 300000}, {"tipo": "recortar", "categoria": "Comida", "porcentaje": 20}]


class UsuariosSimulados(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="charlie-usuarios-")
        cls.motor = os.path.join(empaquetar.armar(cls.dir), "motor", "procesar.py")
        for b, _, fs in os.walk(cls.dir):
            for f in fs: os.chmod(os.path.join(b, f), stat.S_IREAD)
        cls.personas = personas()

    @classmethod
    def tearDownClass(cls):
        for b, _, fs in os.walk(cls.dir):
            for f in fs: os.chmod(os.path.join(b, f), stat.S_IREAD | stat.S_IWRITE)
        shutil.rmtree(cls.dir, ignore_errors=True)

    def correr(self, entrada):
        d = tempfile.mkdtemp(dir=self.dir)
        with open(os.path.join(d, "entrada.json"), "w") as f:
            json.dump(entrada, f, ensure_ascii=False)
        t = time.time()
        r = subprocess.run([sys.executable, "-S", "-W", "ignore", self.motor, "entrada.json", "salida.json"], cwd=d, capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        self.assertLess(time.time() - t, 60, "el motor tardó demasiado")
        return json.load(open(os.path.join(d, "salida.json")))

    def revisar(self, nombre, p, s, correos, historia_desde):
        quien = f"{nombre} (historia desde {historia_desde})"
        self.assertEqual(s["lectura"]["correos"] if correos else 0, len(correos), quien + ": no leyó todas las alertas")
        self.assertEqual(s["no_leidos"], [], quien + ": hay alertas que el motor no entendió")
        ids = [m["ID"] for m in s["movimientos"]]
        self.assertEqual(len(ids), len(set(ids)), quien + ": movimientos duplicados")
        self.assertIsInstance(s["resumen"]["por_dia"], (int, float), quien)
        for c in s["compromisos"]:
            if c.get("ventana") and c["ventana"][0] < historia_desde:
                self.assertNotEqual(c["estado"], "atrasado", f"{quien}: {c['nombre']} {c['periodo']} atrasado sin historia para saberlo")
        b = s["tablero"]["cuentas"]["balance"]
        self.assertEqual(b["patrimonio"], b["activo"] - b["pasivo"], quien)
        for parte, doc in s["tablero"].items():
            self.assertLess(len(json.dumps(doc, ensure_ascii=False).encode()), 256 * 1024, f"{quien}: tablero/{parte} no cabe en el almacén")
        rf = s["resumen_financiero"]
        self.assertLessEqual(len(rf["preguntas"]), 7, quien)
        self.assertTrue(rf["texto"].startswith("## Tu resumen financiero"), quien)
        for sim in s["simulaciones"]:
            self.assertNotIn("No pude simularlo", sim["texto"], f"{quien}: {sim}")

    def recorrido(self, nombre):
        p = self.personas[nombre]
        todos = sorted(p["correos"], key=lambda c: c["fecha"])
        memoria, correos_enviados_hoy = [], 0
        for semana in range(0, 8):   # 0 = configuración (2 semanas); 1..7 = una semana más hacia atrás cada día
            hd = D(14 + 7 * semana).isoformat()
            correos = [c for c in todos if c["fecha"][:10] >= hd]
            entrada = {"config": copy.deepcopy(p["config"]), "correos": correos, "fijos": p.get("fijos", []), "creditos": p.get("creditos", []),
                       "historia_desde": hd, "avisos_memoria": memoria, "simulaciones": SIMULACIONES, "objetivo": "saber"}
            s = self.correr(entrada)
            self.revisar(nombre, p, s, correos, hd)
            av = s["avisos"]
            if semana == 0:
                self.assertFalse(av["enviar"], f"{nombre}: la primera revisión no debe mandar correo")
            if av["enviar"]:
                correos_enviados_hoy += 1
                memoria = av["memoria_si_envias"]
            elif av.get("memoria_si_no_envias"):
                memoria = av["memoria_si_no_envias"]
        self.assertLessEqual(correos_enviados_hoy, 2, f"{nombre}: más de 2 correos de avisos en un día")
        return s

    def test_estudiante_sin_sueldo(self):
        s = self.recorrido("estudiante")
        self.assertGreater(len(s["movimientos"]), 20)
        cel = [c for c in s["compromisos"] if c["nombre"] == "Celular"]
        self.assertTrue(cel and all(c["estado"] == "sin_confirmar" for c in cel), "un pago que nunca aparece en las alertas se pregunta, no se marca atrasado")

    def test_mucho_movimiento(self):
        s = self.recorrido("mucho_movimiento")
        tras = [m for m in s["movimientos"] if "a la cuenta *5555" in m["Descripción"]]
        self.assertTrue(tras and all(m["Tipo"] == "Interno" for m in tras), "la plata a su propia Davivienda contó como gasto")
        nomina = [m for m in s["movimientos"] if m["Categoría"] == "Salario"]
        self.assertGreaterEqual(len(nomina), 2)
        arr = [c for c in s["compromisos"] if c["nombre"] == "Arriendo" and c["estado"] in ("pagado", "pagado_probable")]
        self.assertTrue(arr, "no reconoció el arriendo pagado por PSE")
        self.assertGreater(s["tablero"]["cuentas"]["balance"]["pasivo"], 0)
        self.assertGreater(s["resumen"]["por_dia"], 0, "con sueldo y gasto normal debe quedar algo por día")

    def test_sin_alertas_en_el_correo(self):
        p = self.personas["sin_alertas"]
        s = self.correr({"config": copy.deepcopy(p["config"]), "correos": [], "fijos": p["fijos"], "historia_desde": HOY.isoformat(),
                         "simulaciones": SIMULACIONES})
        self.revisar("sin_alertas", p, s, [], HOY.isoformat())
        self.assertGreater(s["resumen"]["plata_en_cuentas"], 0)
        self.assertFalse([c for c in s["compromisos"] if c["estado"] == "atrasado"], "sin alertas nada puede quedar como atrasado")
        self.assertTrue(s["resumen_financiero"]["preguntas"], "sin alertas debe preguntar lo básico")

    def test_solo_davivienda(self):
        s = self.recorrido("solo_davivienda")
        self.assertEqual(len([m for m in s["movimientos"] if "Davivienda" in m["Fuente"]]), len(self.personas["solo_davivienda"]["correos"]))
        # no le llega el sueldo a esta cuenta: el saldo calculado da negativo, que es imposible → cifra aproximada y pide el saldo de hoy
        self.assertTrue(s["resumen"]["cuentas_negativas"] and s["resumen"]["aproximado"])
        self.assertTrue(any(f["prioridad"] == 1 and "negativo" in f["que_falta"] for f in s["faltantes"]))

    def test_varias_deudas(self):
        s = self.recorrido("deudas")
        sal = next(x for x in s["simulaciones"] if x["tipo"] == "salir_de_deudas")["resultado"]
        self.assertLess(sal["meses_con"], sal["meses_sin"])
        self.assertEqual(sal["orden"][0]["credito"], "Libre inversión", "lo extra debe ir primero a la de mayor tasa")
        self.assertEqual(s["tablero"]["cuentas"]["creditos"][0]["nombre"] if s["tablero"]["cuentas"]["creditos"] else None, "Libre inversión")


if __name__ == "__main__":
    unittest.main()
