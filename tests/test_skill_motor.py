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

    def test_primer_uso_sin_cuentas(self):
        # antes de saber qué tiene el usuario, el motor corre igual y dice qué productos se ven en sus alertas
        s = self.correr({"config": {"sueldo": {}}, "correos": correos()})
        vistos = {(p["institucion"], p["terminacion"]): p["pista"] for p in s["productos_vistos"]}
        self.assertEqual(vistos, {("Bancolombia", "4455"): "cuenta", ("Bancolombia", "1234"): "tarjeta débito",
                                  ("Bancolombia", "8899"): "tarjeta de crédito"})

    def test_correo_repetido_y_cuantos_llegaron(self):
        # el mismo correo en dos páginas o dos hilos no puede volverse dos movimientos
        s = self.correr({"config": CONFIG, "correos": correos() + correos()[:2]})
        self.assertEqual(len(s["nuevos"]), len(ALERTAS))
        self.assertEqual(s["lectura"]["repetidos_descartados"], 2)
        self.assertEqual(s["lectura"]["por_banco"], {"bancolombia": len(ALERTAS)})
        self.assertEqual(sum(s["lectura"]["por_semana_desde_el_lunes"].values()), len(ALERTAS))

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

    def test_deudas_calendario_e_informe(self):
        cfg = copy.deepcopy(CONFIG)
        tc = next(c for c in cfg["cuentas"] if c["tipo"] == "tarjeta_credito")
        tc.update(saldo={"valor": 1000000, "fecha": "2026-09-29"}, dia_pago=15, tasa_ea="28,5")
        creditos = [{"nombre": "Libre inversión", "entidad": "Banco", "saldo": 10000000, "tasa_ea": 18.99, "cuota": 500000, "dia_pago": 5,
                     "buscar": "PAGO CREDITO"},
                    {"nombre": "ICETEX", "entidad": "ICETEX", "saldo": 20000000, "tasa_ea": 0.051, "cuota": 400000, "dia_pago": 5},
                    {"nombre": "Libranza", "entidad": "Banco", "saldo": 5000000, "tasa_ea": 15, "cuota": 300000, "dia_pago": 28, "descuento_nomina": True}]
        fijos = [{"nombre": "Arriendo", "dia": 1, "monto": 1200000, "tipo": "pago", "buscar": "ARRIENDO"}]
        s = self.correr({"config": cfg, "correos": correos(), "creditos": creditos, "fijos": fijos, "apartado": 1000000})
        # deudas de mayor a menor tasa; se abona al crédito más caro, no a la tarjeta ni al más barato
        deu = s["deudas"]
        self.assertEqual([x["nombre"] for x in deu["deudas"]], ["Bancolombia tarjeta *8899", "Libre inversión", "Libranza", "ICETEX"])
        self.assertEqual([x["nombre"] for x in deu["deudas"] if x.get("abonar_aqui")], ["Libre inversión"])
        self.assertEqual(deu["deudas"][0]["saldo"], 1000000 + 120000)
        self.assertEqual(deu["total_creditos"], 35000000)
        self.assertIn("ICETEX", deu["consejo"])
        # un evento mensual por pago, cuota y tarjeta; lo de nómina sale solo y no avisa
        ev = {x["id"]: x for x in s["calendario"]}
        self.assertEqual(ev["mis-finanzas:pago-arriendo"]["recurrencia"], "RRULE:FREQ=MONTHLY;BYMONTHDAY=1")
        self.assertEqual(len(ev["mis-finanzas:pago-arriendo"]["avisos_minutos_antes"]), 2)
        self.assertEqual(ev["mis-finanzas:tarjeta-8899"]["recurrencia"], "RRULE:FREQ=MONTHLY;BYMONTHDAY=15")
        self.assertIn("sale solo", ev["mis-finanzas:pago-cuota-libranza"]["titulo"])
        self.assertEqual(ev["mis-finanzas:pago-cuota-libranza"]["avisos_minutos_antes"], [])
        self.assertIn("Arriendo", ev["mis-finanzas:sueldo"]["descripcion"])
        self.assertEqual(s["resumen"]["apartado"], 1000000)
        # el informe del lunes trae las secciones de la versión instalada
        t = s["informe"]["texto"]
        for parte in ("POR DÍA", "ANTES DEL SUELDO", "ESTA SEMANA", "PRÓXIMOS PAGOS", "DEUDAS", "👉 Libre inversión", "¿QUÉ FUE ESTO?"):
            self.assertIn(parte, t)
        self.assertIn("/día", s["informe"]["asunto"])

    def test_analisis_descubrimientos_y_lo_que_falta(self):
        cfg = copy.deepcopy(CONFIG)
        cfg["sueldo"]["neto_que_llega"] = 4600000   # le llegaron 4.500.000: el sueldo cambió
        def alerta(i, fecha, texto):
            return {"id": f"z{i}", "fecha": fecha + "T12:00:00", "de": BANCOLOMBIA, "asunto": "Alertas y Notificaciones",
                    "texto": f"Bancolombia: {texto}. ¿Dudas? llamanos"}
        mas = [alerta(1, "2026-10-05", "Transferiste $80.000,00 desde tu cuenta *4455 a la llave 0099887766 el 05/10/2026 a las 10:00"),
               alerta(2, "2026-10-19", "Transferiste $70.000,00 desde tu cuenta *4455 a la llave 0099887766 el 19/10/2026 a las 10:00"),
               alerta(3, "2026-10-21", "Compraste $30.000,00 en NETFLIX.COM con tu T.Cred *7070, el 21/10/2026 a las 08:00")]
        s = self.correr({"config": cfg, "correos": correos() + mas, "notas_ids": ["suscripcion:netflix"]})
        a = s["analisis"]
        self.assertEqual(a["por_mes"]["2026-09"]["ingresos"], 4500000)
        self.assertEqual(a["por_mes"]["2026-10"]["gastos"], 85000 + 120000 + 200000 + 80000 + 70000 + 30000)
        self.assertEqual([(x["nombre"], x["mensual"], x["ultimo_cobro"]) for x in a["suscripciones"]], [("Netflix", 30000, "2026-10-21")])
        d = {x["id"]: x for x in s["descubrimientos"]}
        self.assertIn("2 veces", d["destino:0099887766"]["texto"])           # transferencias repetidas al mismo destino
        self.assertIn("producto:bancolombia-7070", d)                       # una tarjeta que no está en sus cuentas
        self.assertIn("sueldo:2026-09-30", d)                               # el sueldo llegó distinto
        self.assertFalse(d["suscripcion:netflix"]["nuevo"])                 # ya estaba en Notas
        self.assertTrue(d["destino:0099887766"]["nuevo"])
        falta = [x["que_falta"] for x in s["faltantes"] if x["prioridad"] == 1]
        self.assertIn("Cuánto tienes hoy en Nequi", falta)
        self.assertIn("Cuánto debes hoy en Bancolombia tarjeta *8899", falta)
        self.assertIn("LO QUE DESCUBRÍ", s["informe"]["texto"])
        self.assertIn("ME FALTA SABER", s["informe"]["texto"])

    def test_registro_de_correos(self):
        codigo = {"id": "c1", "fecha": "2026-10-23T09:00:00", "de": BANCOLOMBIA, "asunto": "Código",
                  "texto": "Este es tu código Bancolombia: 181569. No lo compartas."}
        descartado = dict(codigo, id="c2", estado="no es movimiento")
        nequi = {"id": "n1", "fecha": "2026-10-23T10:00:00", "de": "Nequi <notificaciones@nequi.com.co>", "asunto": "Pagaste",
                 "texto": "Pagaste $30.000 en TIENDA D1", "extraido": {"fecha": "2026-10-23", "valor": -30000, "descripcion": "Pago en TIENDA D1",
                                                                      "institucion": "Nequi", "producto": "3109998877"}}
        s = self.correr({"config": CONFIG, "correos": correos() + [codigo, descartado, nequi]})
        reg = {x["ID del correo"]: x for x in s["correos_registro"]}
        self.assertEqual(len(reg), len(ALERTAS) + 3)
        self.assertEqual(reg["m0"]["Estado"], "movimiento")
        self.assertEqual(reg["c1"]["Estado"], "sin leer")
        self.assertEqual(reg["c2"]["Estado"], "no es movimiento")
        self.assertEqual(reg["n1"]["Estado"], "lo leyó Claude")
        self.assertEqual([x["id"] for x in s["no_leidos"]], ["c1"])   # lo que Claude ya descartó no se vuelve a preguntar
        # cada movimiento queda ligado a su correo, y el correo a sus movimientos
        for m in s["nuevos"]:
            self.assertIn(m["ID"], reg[m["Correo"]]["Movimientos"])
        self.assertEqual(next(m for m in s["nuevos"] if m["Correo"] == "n1")["Valor"], -30000)

    def test_reclasificar_todo_conserva_tus_correcciones(self):
        primera = self.correr({"config": CONFIG, "correos": correos()})
        exito = next(m for m in primera["nuevos"] if "EXITO" in m["Descripción"])
        nequi = next(m for m in primera["nuevos"] if m["Valor"] == -200000)
        corr = {exito["ID"]: {"categoria": "Mercado", "subcategoria": "Mercado del mes", "nota": "lo de la semana"},
                nequi["ID"]: {"categoria": "Entre mis cuentas", "tipo": "Interno"}}
        # reclasificar: toda la pestaña Correos, sin movimientos previos, con las columnas tuyas de Movimientos
        s = self.correr({"config": CONFIG, "correos": correos(), "correcciones": corr})
        m = {x["ID"]: x for x in s["movimientos"]}
        self.assertEqual(len(m), len(ALERTAS))
        self.assertEqual((m[exito["ID"]]["Categoría"], m[exito["ID"]]["Categoría manual"], m[exito["ID"]]["Tu nota"]),
                         ("Mercado", "Mercado", "lo de la semana"))
        self.assertEqual((m[nequi["ID"]]["Tipo"], m[nequi["ID"]]["Tipo manual"]), ("Interno", "Interno"))
        self.assertEqual(s["analisis"]["por_mes"]["2026-10"]["gastos"], 85000 + 120000)   # lo interno ya no es gasto

    def test_traslado_que_encuentra_su_pareja_despues(self):
        cfg = copy.deepcopy(CONFIG)
        next(c for c in cfg["cuentas"] if c["institucion"] == "Nequi").update(saldo={"valor": 100000, "fecha": "2026-10-21"})
        d1 = self.correr({"config": cfg, "correos": correos()})
        antes = next(m for m in d1["nuevos"] if m["Valor"] == -200000)
        self.assertEqual(antes["Tipo"], "Gasto")   # todavía nadie lee Nequi: la plata que va allá se da por gastada
        # al día siguiente Claude lee la alerta de Nequi; se vuelven a pasar los correos de los últimos días
        nequi = {"id": "n1", "fecha": "2026-10-22T09:05:00", "de": "Nequi", "asunto": "Recibiste", "texto": "Recibiste $200.000 de LAURA PRUEBA",
                 "extraido": {"fecha": "2026-10-22", "valor": 200000, "descripcion": "Recibiste de LAURA PRUEBA", "institucion": "Nequi",
                              "producto": "3109998877"}}
        d2 = self.correr({"config": cfg, "correos": correos()[-2:] + [nequi], "movimientos_previos": d1["nuevos"]})
        self.assertEqual([m["ID"] for m in d2["actualizar"]], [antes["ID"]])
        self.assertEqual(d2["actualizar"][0]["Tipo"], "Interno")
        self.assertEqual([m["Tipo"] for m in d2["nuevos"]], ["Interno"])

    def test_fijos_como_los_escribe_claude(self):
        # así quedó la pestaña Fijos en una prueba real: el sueldo, lo apartado y el techo como filas, y días en texto
        cfg = copy.deepcopy(CONFIG)
        cfg["sueldo"]["dia_pago"] = "penúltimo hábil"
        cfg["cuentas"].append({"institucion": "Bancolombia", "tipo": "bolsillo", "terminacion": "9999", "dentro_de": "4455"})
        fijos = [{"nombre": "Sueldo", "dia": "penúltimo hábil", "monto": 4500000, "tipo": "cobro"},
                 {"nombre": "Plata apartada", "dia": "", "monto": 10000000, "tipo": ""},
                 {"nombre": "Techo de gasto del día a día al mes", "dia": "", "monto": 2500000, "tipo": ""},
                 {"nombre": "Provisión renta → bolsillo", "dia": "penúltimo hábil", "monto": 300000, "tipo": "pago"},
                 {"nombre": "Arriendo", "dia": "5", "monto": 1200000, "tipo": "Pago"}]
        s = self.correr({"config": cfg, "correos": correos(), "fijos": fijos})
        nombres = [x["titulo"] for x in s["calendario"]]
        self.assertTrue(any("Arriendo" in t for t in nombres) and any("Provisión renta" in t for t in nombres))
        self.assertFalse(any("Plata apartada" in t or "Techo" in t or t.startswith("💵 Sueldo") for t in nombres))
        self.assertEqual(next(x for x in s["calendario"] if x["id"] == "mis-finanzas:sueldo")["recurrencia"],
                         "RRULE:FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-2")
        self.assertIn("Cuánto tienes hoy en Bancolombia bolsillo *9999", [x["que_falta"] for x in s["faltantes"]])

    def test_patrones_con_dos_meses(self):
        # un usuario nuevo, sin pagos fijos: el motor ve en dos meses de alertas lo que se repite
        def alerta(i, fecha, texto):
            return {"id": f"p{i}", "fecha": fecha + "T12:00:00", "de": BANCOLOMBIA, "asunto": "Alertas y Notificaciones",
                    "texto": f"Bancolombia: {texto}. ¿Dudas? llamanos"}
        corr, i = [], 0
        for mes, dia_arr in (("09", "04"), ("10", "06")):
            i += 1; corr.append(alerta(i, f"2026-{mes}-{dia_arr}", f"Pagaste $1.500.000,00 a INMOBILIARIA EJEMPLO SAS desde tu producto *4455 el {dia_arr}/{mes}/2026 10:00:00"))
            i += 1; corr.append(alerta(i, f"2026-{mes}-15", f"Compraste COP45.900,00 en NETFLIX.COM, el 15/{mes}/2026 a las 08:00. Esta compra esta asociada a T.Cred *8899"))
            i += 1; corr.append(alerta(i, f"2026-{mes}-20", f"Recibiste una transferencia por $700.000,00 de CARLOS PEREZ en tu cuenta *4455 el 20/{mes}/2026"))
            for k in range(5):   # un hábito: muchas veces al mes, montos y días distintos
                i += 1; corr.append(alerta(i, f"2026-{mes}-{10 + k:02d}", f"Compraste COP{12 + k}.000,00 en UBER RIDES, el {10 + k}/{mes}/2026 a las 22:00. Esta compra esta asociada a T.Cred *8899"))
        s = self.correr({"config": CONFIG, "correos": corr})
        pa = s["analisis"]["patrones"]
        fijos = {x["con"]: x for x in pa["pagos_que_se_repiten"]}
        self.assertEqual((fijos["INMOBILIARIA EJEMPLO"]["monto_tipico"], fijos["INMOBILIARIA EJEMPLO"]["meses"]), (1500000, 2))
        self.assertIn("NETFLIX COM", fijos)
        self.assertNotIn("UBER RIDES", fijos)                                   # es un hábito, no un pago fijo
        self.assertEqual([x["con"] for x in pa["habitos"]], ["UBER"])
        self.assertEqual([x["con"] for x in pa["ingresos_que_se_repiten"]], ["CARLOS PEREZ"])
        ids = [x["id"] for x in s["descubrimientos"]]
        self.assertIn("patron:inmobiliaria-ejemplo", ids)
        self.assertIn("ingreso:carlos-perez", ids)

    def test_primer_valor_del_onboarding(self):
        # usuaria nueva que todavía no ha dicho su sueldo: el motor lo propone, dice cómo están sus datos y qué hacer primero
        cfg = copy.deepcopy(CONFIG)
        cfg["sueldo"] = {}
        def alerta(i, fecha, texto):
            return {"id": f"o{i}", "fecha": fecha + "T12:00:00", "de": BANCOLOMBIA, "asunto": "Alertas y Notificaciones",
                    "texto": f"Bancolombia: {texto}. ¿Dudas? llamanos"}
        corr, i = [], 0
        for f_ in ("2026-09-29", "2026-10-29"):   # penúltimo día hábil de cada mes
            i += 1; corr.append(alerta(i, f_, f"Recibiste un pago de Nomina de EMPRESA EJEMPLO SAS por $4.500.000,00 en tu cuenta *4455 el {f_[8:]}/{f_[5:7]}/2026"))
        for mes in ("09", "10"):
            for k in range(6):
                i += 1; corr.append(alerta(i, f"2026-{mes}-{10 + k:02d}", f"Compraste COP{40 + k}.000,00 en RAPPI COLOMBIA, el {10 + k}/{mes}/2026 a las 20:00. Esta compra esta asociada a T.Deb *1234"))
        s = self.correr({"config": cfg, "correos": corr, "objetivo": "gastar_menos"})
        self.assertEqual(s["sueldo_probable"]["monto"], 4500000)
        self.assertEqual(s["sueldo_probable"]["dia"], "penultimo_habil")
        self.assertIn("Rappi", s["acciones"][0])
        cob = {x["nombre"]: x for x in s["cobertura"]}
        self.assertEqual(cob["Bancolombia ahorros *4455"]["movimientos"], 2 + 12)
        self.assertIn("no manda alertas", cob["Trii"]["nota"])
        self.assertIn("Rappi", s["informe"]["texto"].split("UNA COSA PARA ESTA SEMANA")[1])

    def test_ofertas_y_corte_de_tarjeta(self):
        cfg = copy.deepcopy(CONFIG)
        next(c for c in cfg["cuentas"] if c["tipo"] == "tarjeta_credito").update(saldo={"valor": 1000000, "fecha": "2026-09-29"}, dia_corte=8, dia_pago=25)
        creditos = [{"nombre": "Libre inversión", "entidad": "Banco", "saldo": 20000000, "tasa_ea": 22, "cuota": 700000, "dia_pago": 5},
                    {"nombre": "ICETEX", "entidad": "ICETEX", "saldo": 10000000, "tasa_ea": 5, "cuota": 300000, "dia_pago": 5}]
        ofertas = [{"credito": "Libre inversión", "entidad": "Otro banco", "tasa_ea": 16, "costos": 200000, "fuente": "ejemplo.com", "fecha": "2026-10-01"},
                   {"credito": "ICETEX", "entidad": "Otro banco", "tasa_ea": 16, "fuente": "ejemplo.com"},   # más cara: no vale la pena
                   {"credito": "Bancolombia tarjeta *8899", "entidad": "Compra de cartera", "tasa_ea": 15, "fuente": "ejemplo.com"}]
        s = self.correr({"config": cfg, "correos": correos(), "creditos": creditos, "ofertas": ofertas, "tasa_usura": "21,5"})
        co = {(o["credito"], o["tasa_oferta"]): o for o in s["comparacion_ofertas"]["ofertas"]}
        li = co[("Libre inversión", 0.16)]
        self.assertTrue(li["vale_la_pena"])
        self.assertLess(li["meses_con_la_oferta"], li["meses_que_faltan"])
        self.assertGreater(li["ahorro_cuota_mismo_plazo"], 0)
        self.assertFalse(co[("ICETEX", 0.16)]["vale_la_pena"])
        self.assertGreater(co[("Bancolombia tarjeta *8899", 0.15)]["ahorro_total_un_ano"], 0)
        self.assertEqual([x["credito"] for x in s["comparacion_ofertas"]["sobre_usura"]], ["Libre inversión", "Bancolombia tarjeta *8899"])
        tc = next(t for t in s["tarjetas"] if "8899" in t["nombre"])
        self.assertTrue(tc["corte"].endswith("-08"))
        self.assertTrue(any(x["titulo"].startswith("✂️ Corte") for x in s["calendario"]))
        self.assertIn("PARA MEJORAR TUS DEUDAS", s["informe"]["texto"])

    def test_no_se_cuanto_debo_en_la_tarjeta(self):
        """Paso 5 de la configuración: "no sé" vale. Lo que debe en la tarjeta se estima con las compras que avisó y la
        cifra por día queda marcada como aproximada; lo que falta se pide después."""
        import datetime
        hace = datetime.date.today() - datetime.timedelta(days=10)
        texto = f"Compraste $120.000,00 en RESTAURANTE EJEMPLO con tu T.Cred *8899, el {hace:%d/%m/%Y} a las 21:00"
        cs = [{"id": "tc1", "fecha": hace.isoformat() + "T21:00:00", "de": BANCOLOMBIA, "asunto": "Alertas y Notificaciones",
               "texto": f"Bancolombia: {texto}. ¿Dudas? llamanos"}]
        s = self.correr({"config": copy.deepcopy(CONFIG), "correos": cs})
        tc = next(t for t in s["tarjetas"] if "8899" in t["nombre"])
        self.assertTrue(tc["estimada"])
        self.assertEqual(tc["deuda"], 120000)
        self.assertTrue(s["resumen"]["aproximado"])
        self.assertIn(tc["nombre"], s["resumen"]["tarjetas_estimadas"])
        self.assertTrue(any(f["id"].startswith("deuda:") and f["prioridad"] == 1 for f in s["faltantes"]))

    def test_compromisos_del_mes(self):
        """Cada pago del mes con su estado y cómo se sabe: pagado por el texto, pagado_probable por el monto (±2 %),
        atrasado si no aparece, la tarjeta con lo que se debe, y la marca del usuario gana."""
        import datetime
        hoy = datetime.date.today()
        d_arr, d_ing, d_gym, d_tc = (hoy - datetime.timedelta(days=n) for n in (6, 3, 2, 5))

        def alerta(i, fecha, texto):
            return {"id": f"c{i}", "fecha": fecha.isoformat() + "T10:00:00", "de": BANCOLOMBIA, "asunto": "Alertas y Notificaciones",
                    "texto": f"Bancolombia: {texto}. ¿Dudas? llamanos"}
        cs = [alerta(1, d_arr, f"Pagaste $1.800.000,00 a INMOBILIARIA EJEMPLO por PSE desde tu cuenta *4455 el {d_arr:%d/%m/%Y} a las 10:00"),
              alerta(2, d_ing, f"Transferiste $672.000,00 desde tu cuenta *4455 a la cuenta *55501234567 el {d_ing:%d/%m/%Y} a las 09:00"),
              alerta(3, d_tc, f"Compraste $95.000,00 en RESTAURANTE EJEMPLO con tu T.Cred *8899, el {d_tc:%d/%m/%Y} a las 21:00"),
              # el gimnasio ya se había pagado antes: así el de este periodo, sin pago, es atrasado (y no "sin confirmar")
              alerta(4, d_gym - datetime.timedelta(days=31), f"Pagaste $150.000,00 a GYM EJEMPLO por PSE desde tu cuenta *4455 el "
                     f"{d_gym - datetime.timedelta(days=31):%d/%m/%Y} a las 10:00")]
        fijos = [{"nombre": "Arriendo", "dia": d_arr.day, "monto": 1800000, "tipo": "pago", "buscar": "INMOBILIARIA EJEMPLO"},
                 {"nombre": "Clases de inglés", "dia": d_ing.day, "monto": 672000, "tipo": "pago", "buscar": "EMETHOD"},
                 {"nombre": "Gimnasio", "dia": d_gym.day, "monto": 150000, "tipo": "pago", "buscar": "GYM EJEMPLO"},
                 {"nombre": "Administración", "dia": d_arr.day, "monto": 380000, "tipo": "pago", "buscar": ""}]
        cfg = copy.deepcopy(CONFIG)
        next(c for c in cfg["cuentas"] if c["tipo"] == "tarjeta_credito").update(dia_pago=(hoy + datetime.timedelta(days=12)).day)
        s = self.correr({"config": cfg, "correos": cs, "fijos": fijos})
        por = {(c["nombre"], c["vence"]): c for c in s["compromisos"]}
        arr = por[("Arriendo", d_arr.isoformat())]
        self.assertEqual((arr["estado"], arr["prueba"]), ("pagado", "movimiento del banco"))
        ing = por[("Clases de inglés", d_ing.isoformat())]
        self.assertEqual(ing["estado"], "pagado_probable")
        self.assertIn("casi igual", ing["deduccion"])
        gym = por[("Gimnasio", d_gym.isoformat())]
        self.assertEqual((gym["estado"], gym["grupo"], gym["dias_atraso"], gym["falta"]), ("atrasado", "atencion", 2, 150000))
        self.assertIn("Gimnasio", s["compromisos_resumen"]["atrasados"])
        # sin saber cómo aparece en el banco no se puede afirmar que está atrasado: se pregunta
        adm = por[("Administración", d_arr.isoformat())]
        self.assertEqual((adm["estado"], adm["grupo"], adm["prueba"]), ("sin_confirmar", "atencion", "no lo veo en tus alertas (confírmalo)"))
        self.assertTrue(any(a["titulo"].startswith("¿Ya pagaste Administración") and a["severidad"] == "amarillo" for a in s["avisos"]["alertas"]))
        tc = next(c for c in s["compromisos"] if c["tipo"] == "tarjeta")
        self.assertTrue(tc["prueba"].startswith("estimado"))
        self.assertEqual(tc["falta"], 95000)
        # la marca del usuario gana y la prueba lo dice
        s2 = self.correr({"config": cfg, "correos": cs, "fijos": fijos, "marcas_compromisos": {gym["id"]: {"estado": "pagado", "nota": "en efectivo"}}})
        g2 = next(c for c in s2["compromisos"] if c["id"] == gym["id"])
        self.assertEqual((g2["estado"], g2["prueba"], g2["falta"], g2["nota"]), ("pagado", "lo marcaste tú", 0, "en efectivo"))
        # avisos: la primera revisión no manda nada (lo acaba de ver) y deja la memoria para la pestaña Avisos
        av = s["avisos"]
        self.assertFalse(av["enviar"])
        self.assertTrue(any(x.get("id", "").startswith(f"compromiso:{gym['id']}") for x in av["memoria_si_no_envias"]))
        self.assertTrue(any(a["titulo"].startswith("Gimnasio") and a["severidad"] == "rojo" for a in av["alertas"]))
        s3 = self.correr({"config": cfg, "correos": cs, "fijos": fijos, "avisos_memoria": av["memoria_si_no_envias"]})
        self.assertFalse(s3["avisos"]["enviar"])
        self.assertEqual(s3["avisos"]["motivo"], "nada nuevo ni urgente")

    def test_datos_del_tablero(self):
        """El tablero (artifact del usuario) recibe tres documentos que caben en el almacén (256 KiB cada uno), con claves
        de documento válidas para las marcas y sin cifras inventadas."""
        import re as _re
        s = self.correr({"config": copy.deepcopy(CONFIG), "correos": correos(), "sheet_url": "https://docs.google.com/spreadsheets/d/x"})
        t = s["tablero"]
        self.assertEqual(set(t), {"resumen", "cuentas", "reportes", "compromisos", "movimientos", "metas"})
        for parte, doc in t.items():
            self.assertLess(len(json.dumps(doc, ensure_ascii=False).encode()), 200 * 1024, parte)
        self.assertEqual(t["resumen"]["kpis"]["por_dia"], s["resumen"]["por_dia"])
        self.assertEqual(t["resumen"]["sheet_url"], "https://docs.google.com/spreadsheets/d/x")
        for c in t["compromisos"]["items"]:
            self.assertRegex(c["clave"], r"^[A-Za-z0-9_.~:@+-]+$")
        self.assertEqual(t["movimientos"]["columnas"][:2], ["fecha", "valor"])
        # cuentas: lo que tienes menos lo que debes; reportes: el flujo por mes sale del mismo análisis del motor
        b = t["cuentas"]["balance"]
        self.assertEqual(b["patrimonio"], b["activo"] - b["pasivo"])
        self.assertEqual({f["mes"]: f["ingresos"] for f in t["reportes"]["flujo"]},
                         {k: v["ingresos"] for k, v in list(s["analisis"]["por_mes"].items())[-12:]})
        self.assertEqual(len(t["resumen"]["gasto_diario"]) >= 28, True)
        # metas: el avance se mide con el saldo de la cuenta o el crédito que la mide
        cfg = copy.deepcopy(CONFIG)
        metas = [{"meta": "Viaje", "tipo": "ahorro", "monto": 6400000, "fecha": "2030-01-01", "medir": "Bancolombia ahorros *4455"},
                 {"meta": "Algo", "tipo": "ahorro", "monto": 100, "medir": "Cuenta que no existe"}]
        s2 = self.correr({"config": cfg, "correos": correos(), "metas": metas})
        viaje, otra = s2["tablero"]["metas"]["items"]
        saldo = next(c["saldo"] for c in s2["cuentas"] if c["nombre"] == "Bancolombia ahorros *4455")
        self.assertAlmostEqual(viaje["progreso"], min(1, saldo / 6400000))
        self.assertIn("No encuentro", otra["nota"])

    def test_comercio_de_bancolombia(self):
        """El comercio de "Compraste $85.000,00 en EXITO CALLE 80 con tu T.Deb …" es EXITO CALLE 80 (antes salía "ste $85.000,00 en …")."""
        s = self.correr({"config": copy.deepcopy(CONFIG), "correos": correos()})
        com = {r["Comercio"] for r in s["movimientos"]}
        self.assertIn("EXITO CALLE 80", com)
        self.assertIn("TRII SAS", com)
        self.assertFalse([c for c in com if c.startswith(("ste ", "aste "))])

    def test_historia_por_etapas(self):
        """Configuración por etapas: con correos solo desde historia_desde, un pago cuya ventana empieza antes queda
        sin_confirmar (no atrasado) y los meses incompletos no cuentan en los promedios."""
        import datetime
        hoy = datetime.date.today()
        d_gym = hoy - datetime.timedelta(days=2)
        fijos = [{"nombre": "Gimnasio", "dia": d_gym.day, "monto": 150000, "tipo": "pago", "buscar": "GYM EJEMPLO"}]
        hd = (hoy - datetime.timedelta(days=5)).isoformat()
        s = self.correr({"config": copy.deepcopy(CONFIG), "correos": correos(), "fijos": fijos, "historia_desde": hd})
        gym = next(c for c in s["compromisos"] if c["nombre"] == "Gimnasio" and c["vence"] == d_gym.isoformat())
        self.assertEqual(gym["estado"], "sin_confirmar")
        rep = s["tablero"]["reportes"]
        self.assertEqual(rep["historia_desde"], hd)
        self.assertTrue(all(f["parcial"] for f in rep["flujo"] if f["mes"] + "-01" < hd))
        self.assertFalse([m for m in rep["meses_base"] if m + "-01" < hd])

    def test_simulaciones_y_resumen_financiero(self):
        """Habla con tus cuentas: las cifras de "¿y si…?" salen del motor, y la configuración cierra con el resumen
        financiero y preguntas numeradas."""
        creditos = [{"nombre": "Libre inversión", "entidad": "Banco", "saldo": 20000000, "tasa_ea": 22, "cuota": 700000, "dia_pago": 5},
                    {"nombre": "ICETEX", "entidad": "ICETEX", "saldo": 10000000, "tasa_ea": 5, "cuota": 300000, "dia_pago": 5}]
        sims = [{"tipo": "abono_extra", "credito": "libre", "monto_mes": 500000},
                {"tipo": "salir_de_deudas", "extra_mes": 300000},
                {"tipo": "me_alcanza", "monto": 100000},
                {"tipo": "ahorrar_para", "monto": 3000000, "fecha": "2027-06-01", "meta": "el viaje"},
                {"tipo": "recortar", "categoria": "Comida", "porcentaje": 30},
                {"tipo": "cancelar", "suscripcion": "No existe"},
                {"tipo": "otra_cosa"}]
        s = self.correr({"config": copy.deepcopy(CONFIG), "correos": correos(), "creditos": creditos, "simulaciones": sims})
        ab, sal, alc, aho, rec, can, otra = s["simulaciones"]
        self.assertLess(ab["resultado"]["meses_con"], ab["resultado"]["meses_sin"])
        self.assertGreater(ab["resultado"]["ahorro_intereses"], 0)
        self.assertIn("Libre inversión", ab["texto"])
        self.assertLessEqual(sal["resultado"]["meses_con"], sal["resultado"]["meses_sin"])
        self.assertEqual(sal["resultado"]["orden"][0]["credito"], "Libre inversión")   # lo extra va primero a la de mayor tasa
        self.assertIn("alcanza", alc["resultado"])
        self.assertGreater(aho["resultado"]["al_mes"], 0)
        self.assertNotIn("error", rec["resultado"], rec["texto"])
        self.assertAlmostEqual(rec["resultado"]["ahorro_ano"], rec["resultado"]["ahorro_mes"] * 12, delta=12)
        self.assertEqual(can["resultado"].get("error"), "suscripcion")
        self.assertEqual(otra["error"], "tipo")
        rf = s["resumen_financiero"]
        self.assertTrue(rf["texto"].startswith("## Tu resumen financiero"))
        self.assertEqual([p["n"] for p in rf["preguntas"]], list(range(1, len(rf["preguntas"]) + 1)))
        self.assertLessEqual(len(rf["preguntas"]), 7)
        self.assertIn("Tu resumen financiero", rf["html"])
        self.assertEqual(rf["secciones"]["hoy"]["diferencia"], rf["secciones"]["hoy"]["lo_que_tienes"] - rf["secciones"]["hoy"]["lo_que_debes"])

    def test_suscripciones_claras(self):
        def alerta(i, fecha, comercio, valor):
            return {"id": f"s{i}", "fecha": fecha + "T12:00:00", "de": BANCOLOMBIA, "asunto": "Alertas y Notificaciones",
                    "texto": f"Bancolombia: Compraste COP{valor},00 en {comercio}, el {fecha[8:]}/{fecha[5:7]}/2026 a las 08:00. Esta compra esta asociada a T.Cred *8899. ¿Dudas? llamanos"}
        corr = [alerta(1, "2026-08-15", "NETFLIX.COM", "38.900"), alerta(2, "2026-09-15", "NETFLIX.COM", "38.900"),
                alerta(3, "2026-10-15", "NETFLIX.COM", "44.900"),                                      # subió de precio
                alerta(4, "2026-10-03", "SPOTIFY", "18.500"), alerta(5, "2026-10-04", "SPOTIFY", "18.500"),   # cobro doble
                alerta(6, "2026-09-05", "TINDER", "49.000"), alerta(7, "2026-10-05", "TINDER", "49.000"),     # la canceló el 20-sep
                alerta(8, "2026-09-02", "GIMNASIO BARRIO", "90.000"), alerta(9, "2026-10-02", "GIMNASIO BARRIO", "90.000"),
                alerta(10, "2026-09-20", "RESTAURANTE EJEMPLO", "60.000"), alerta(11, "2026-10-20", "RESTAURANTE EJEMPLO", "60.000")]
        s = self.correr({"config": CONFIG, "correos": corr, "suscripciones_canceladas": [{"nombre": "Tinder", "desde": "2026-09-20"}]})
        su = {x["nombre"]: x for x in s["analisis"]["suscripciones"]}
        self.assertEqual(su["Netflix"]["cambio_precio"], {"de": 38900, "a": 44900, "fecha": "2026-10-15"})
        self.assertEqual((su["Netflix"]["mensual"], su["Netflix"]["al_ano"], su["Netflix"]["dia_de_cobro"]), (44900, 44900 * 12, 15))
        self.assertEqual(su["Netflix"]["proximo_cobro"][:7], "2026-11")
        self.assertEqual(su["Spotify"]["duplicado"], ["2026-10-04"])
        self.assertEqual(su["Tinder"]["cobro_tras_cancelar"], ["2026-10-05"])
        self.assertFalse(su["Gimnasio Barrio"]["conocida"])             # no está en la lista, pero cobra igual cada mes
        self.assertNotIn("Restaurante Ejemplo", su)                      # comida que se repite no es una suscripción
        ids = [x["id"] for x in s["descubrimientos"]]
        for k in ("precio:netflix:2026-10-15", "duplicado:spotify:2026-10-04", "tras-cancelar:tinder:2026-10-05"):
            self.assertIn(k, ids)
        self.assertIn("SUSCRIPCIONES:", s["informe"]["texto"])

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
