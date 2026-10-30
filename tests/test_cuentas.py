"""Mapa de cuentas y caja (cuentas.py): configuraciones viejas, de qué producto es cada movimiento y saldos sin depender
de Davivienda. Correr: python -m unittest discover -s tests"""
import datetime, unittest
import cuentas

HOY = datetime.date(2026, 10, 29)
LEGADO = {"davivienda": {"cuenta_principal": "1111", "cuenta_afc": "2222", "bolsillo": "3333", "tarjeta_credito": "4444"},
          "bancolombia": {"ahorros": "5555", "tarjeta_credito": "6666", "tarjeta_debito": "7777"},
          "celulares_propios": ["3001234567"]}


def fila(fuente, valor, fecha, **x):
    return {"Fecha": fecha, "Fuente": fuente, "Valor": valor, "Descripción": "", "Tipo": "Gasto", "Categoría": "", **x}


class Configuracion(unittest.TestCase):
    def test_config_vieja_sigue_funcionando(self):
        p = {x["id"]: x for x in cuentas.normalizar(LEGADO)}
        self.assertEqual(p["Davivienda bolsillo *3333"]["dentro_de"], "1111")
        self.assertEqual(p["Davivienda AFC *2222"]["tipo"], "ahorros")
        self.assertEqual(p["Nequi 3001234567"]["tipo"], "billetera")
        self.assertTrue(p["Bancolombia ahorros *5555"]["se_lee"])
        self.assertFalse(p["Nequi 3001234567"]["se_lee"])

    def test_formato_nuevo_da_los_mismos_datos_a_los_lectores(self):
        nuevo = cuentas.normalizar({"cuentas": [
            {"institucion": "Davivienda", "tipo": "ahorros", "terminacion": "1111"},
            {"institucion": "Davivienda", "tipo": "ahorros", "terminacion": "2222", "nombre": "AFC"},
            {"institucion": "Davivienda", "tipo": "bolsillo", "terminacion": "3333", "dentro_de": "1111"},
            {"institucion": "Davivienda", "tipo": "tarjeta_credito", "terminacion": "4444"},
            {"institucion": "Bancolombia", "tipo": "ahorros", "terminacion": "5555", "tarjeta_debito": "7777"},
            {"institucion": "Bancolombia", "tipo": "tarjeta_credito", "terminacion": "6666"}]})
        self.assertEqual(cuentas.legado_davivienda(nuevo), LEGADO["davivienda"])
        self.assertEqual(cuentas.legado_bancolombia(nuevo), LEGADO["bancolombia"])

    def test_tipo_invalido(self):
        with self.assertRaises(ValueError):
            cuentas.normalizar({"cuentas": [{"institucion": "X", "tipo": "acciones"}]})

    def test_clave_de_institucion(self):
        self.assertEqual(cuentas.clave("Banco de Bogotá"), "bogota")
        self.assertEqual(cuentas.clave("RappiCard"), "rappipay")
        self.assertEqual(cuentas.clave("AV Villas"), "avvillas")
        self.assertEqual(cuentas.clave("Banco Caja Social"), "cajasocial")


class DeQueProductoEs(unittest.TestCase):
    P = cuentas.normalizar({**LEGADO, "cuentas": None})

    def nombre(self, fuente):
        p = cuentas.de_fuente(fuente, self.P)
        return p and p["id"]

    def test_fuentes(self):
        self.assertEqual(self.nombre("Davivienda Ahorros *1111 (alerta)"), "Davivienda ahorros *1111")
        self.assertEqual(self.nombre("Davivienda Ahorros *3333 (alerta)"), "Davivienda bolsillo *3333")
        self.assertEqual(self.nombre("Bancolombia TC *6666 (alerta)"), "Bancolombia tarjeta *6666")
        self.assertEqual(self.nombre("Bancolombia Ahorros *7777 (alerta)"), "Bancolombia ahorros *5555")   # su tarjeta débito
        self.assertIsNone(self.nombre("Descuento de nómina (estimado)"))

    def test_saldo_confirmado_por_correo(self):
        bancolombia = cuentas.para_saldo("Bancolombia (cuenta de ahorros)", self.P)
        self.assertEqual(bancolombia["id"], "Bancolombia ahorros *5555")
        self.assertIsNone(cuentas.para_saldo("Tarjeta Bancolombia (deuda)", self.P))   # deuda: no es caja
        self.assertIsNone(cuentas.para_saldo("Efectivo en la billetera", self.P))
        self.assertEqual(cuentas.para_saldo("Nequi", self.P)["id"], "Nequi 3001234567")


class Caja(unittest.TestCase):
    def test_sin_davivienda_la_caja_no_da_cero(self):
        p = cuentas.normalizar({"cuentas": [{"institucion": "Bancolombia", "tipo": "ahorros", "terminacion": "1234"}]})
        movs = [fila("Bancolombia Ahorros *1234 (alerta)", -50_000, "2026-10-01"),     # mismo día del saldo: ya está incluido
                fila("Bancolombia Ahorros *1234 (alerta)", -300_000, "2026-10-05"),
                fila("Bancolombia Ahorros *1234 (alerta)", 1_000_000, "2026-10-10")]
        anclas = {"Bancolombia ahorros *1234": {"valor": 2_000_000, "fecha": "2026-10-01", "origen": "confirmado"}}
        c = cuentas.resumir(cuentas.saldos(movs, p, anclas, HOY))
        self.assertEqual((c["total"], c["disponible"], c["sin_saldo"]), (2_700_000, 2_700_000, []))

    def test_cuenta_sin_saldo_se_pregunta(self):
        p = cuentas.normalizar({"cuentas": [{"institucion": "Lulo", "tipo": "ahorros"}]})
        c = cuentas.resumir(cuentas.saldos([], p, {}, HOY))
        self.assertEqual((c["total"], c["sin_saldo"]), (0, ["Lulo ahorros"]))

    def test_bolsillo_no_se_suma_dos_veces(self):
        p = cuentas.normalizar(LEGADO)
        fin = "2026-09-30"
        anclas = {"Davivienda ahorros *1111": {"valor": 20_000_000, "fecha": fin, "origen": "extracto"},   # incluye el bolsillo
                  "Davivienda bolsillo *3333": {"valor": 11_000_000, "fecha": fin, "origen": "extracto"}}
        movs = [fila("Davivienda Ahorros *1111 (alerta)", -1_000_000, "2026-10-03")]
        c = cuentas.resumir(cuentas.saldos(movs, p, anclas, HOY), reserva_inversion=10_000_000)
        self.assertEqual((c["total"], c["bolsillo"], c["disponible"], c["reservado_inversion"], c["emergencia"]),
                         (19_000_000, 11_000_000, 8_000_000, 10_000_000, 1_000_000))

    def test_sin_bolsillo_lo_reservado_se_aparta_del_total(self):
        p = cuentas.normalizar({"cuentas": [{"institucion": "Lulo", "tipo": "ahorros"}]})
        anclas = {"Lulo ahorros": {"valor": 7_000_000, "fecha": "2026-10-20", "origen": "confirmado"}}
        c = cuentas.resumir(cuentas.saldos([], p, anclas, HOY), reserva_inversion=5_000_000)
        self.assertEqual((c["total"], c["disponible"], c["reservado_inversion"]), (7_000_000, 2_000_000, 5_000_000))

    def test_inversiones_suman_aportes_y_no_son_caja(self):
        p = cuentas.normalizar({"cuentas": [{"institucion": "Davivienda", "tipo": "ahorros", "terminacion": "5678"},
                                            {"institucion": "Trii", "tipo": "inversion"}]})
        anclas = {"Trii": {"valor": 5_000_000, "fecha": "2026-09-30", "origen": "confirmado"},
                  "Davivienda ahorros *5678": {"valor": 3_000_000, "fecha": "2026-09-30", "origen": "extracto"}}
        movs = [fila("Davivienda Ahorros *5678", -1_000_000, "2026-10-05", Tipo="Interno", Contraparte="Trii"),
                fila("Davivienda Ahorros *5678", 400_000, "2026-10-20", Tipo="Interno", Contraparte="Trii")]
        c = cuentas.resumir(cuentas.saldos(movs, p, anclas, HOY))
        self.assertEqual((c["inversiones"], c["total"]), (5_600_000, 2_400_000))

    def test_billetera_que_no_se_lee_solo_vale_7_dias(self):
        p = cuentas.normalizar({"cuentas": [{"institucion": "Nequi", "tipo": "billetera", "celular": "3001234567"}]})
        viejo = {"Nequi": {"valor": 300_000, "fecha": "2026-10-19", "origen": "confirmado"}}
        nuevo = {"Nequi": {"valor": 300_000, "fecha": "2026-10-26", "origen": "confirmado"}}
        self.assertEqual(cuentas.resumir(cuentas.saldos([], p, viejo, HOY))["total"], 0)
        self.assertEqual(cuentas.resumir(cuentas.saldos([], p, nuevo, HOY))["total"], 300_000)


if __name__ == "__main__":
    unittest.main()
