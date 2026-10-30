"""Plata entre tus productos (transferencias.py). Casos reales de usuarios con muchas cuentas: PSE a Trii/Littio, retiros de
inversiones, compras de cartera, pagos a tarjetas de otros bancos. Correr: python -m unittest discover -s tests"""
import unittest
import cuentas, transferencias

# Usuario con muchos productos: dos bancos que el sistema lee, tarjetas en varios bancos, billeteras, inversiones y CDTs
MAPA = cuentas.normalizar({"cuentas": [
    {"institucion": "Bancolombia", "tipo": "ahorros", "terminacion": "1234"},
    {"institucion": "Bancolombia", "tipo": "tarjeta_credito", "terminacion": "6666"},
    {"institucion": "Davivienda", "tipo": "ahorros", "terminacion": "5678"},
    {"institucion": "Davivienda", "tipo": "tarjeta_credito", "terminacion": "4444"},
    {"institucion": "RappiPay", "tipo": "ahorros", "nombre": "RappiCuenta"},
    {"institucion": "RappiCard", "tipo": "tarjeta_credito"},
    {"institucion": "Nu", "tipo": "tarjeta_credito"},
    {"institucion": "Banco Caja Social", "tipo": "ahorros", "terminacion": "1111"},
    {"institucion": "Banco de Occidente", "tipo": "tarjeta_credito", "terminacion": "4321"},
    {"institucion": "Banco Falabella", "tipo": "tarjeta_credito"},
    {"institucion": "Nequi", "tipo": "billetera", "celular": "3001234567"},
    {"institucion": "Trii", "tipo": "inversion"},
    {"institucion": "Littio", "tipo": "inversion"},
    {"institucion": "Koa", "tipo": "cdt"},
    {"institucion": "Banco Santander", "tipo": "cdt"},
]})
DAVI, BANCO = "Davivienda Ahorros *5678", "Bancolombia Ahorros *1234 (alerta)"


def mov(fuente, valor, desc, tipo=None, cat=None, fecha="2026-10-10"):
    """Fila como la deja build.py después de las REGLAS (por defecto: lo que sale sin regla)."""
    tipo = tipo or ("Gasto" if valor < 0 else "Ingreso")
    cat = cat or ("Otros" if valor < 0 else "Otros ingresos")
    return {"Fecha": fecha, "Fuente": fuente, "Descripción": desc, "Valor": valor, "Tipo": tipo, "Categoría": cat, "Subcategoría": ""}


def marcar(*filas, propio=r"(?!x)x"):
    filas = list(filas)
    transferencias.marcar(filas, MAPA, propio)
    return filas


class Inversiones(unittest.TestCase):
    def test_pse_a_trii_no_es_gasto(self):
        r, = marcar(mov(DAVI, -2_000_000, "Compra TRII SAS Compras y Pagos PSE"))
        self.assertEqual((r["Tipo"], r["Categoría"], r["Contraparte"]), ("Interno", "Hacia mis inversiones", "Trii"))

    def test_pagaste_a_littio_desde_bancolombia(self):
        r, = marcar(mov(BANCO, -1_500_000, "Pagaste $1.500.000,00 a LITTIO SAS desde tu producto *1234 el 20/10/2026 10:00:00"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Interno", "Hacia mis inversiones"))

    def test_retiro_de_trii_no_es_ingreso(self):
        r, = marcar(mov(BANCO, 3_000_000, "Recibiste una transferencia por $3,000,000 de TRII SAS en tu cuenta **1234, el 21/10/2026 a las 10:00",
                        cat="Transferencias recibidas"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Interno", "Desde mis inversiones"))

    def test_cdt_en_banco_tradicional_por_pse(self):
        r, = marcar(mov(DAVI, -10_000_000, "Compra BANCO SANTANDER Compras y Pagos PSE"))
        self.assertEqual((r["Tipo"], r["Categoría"], r["Contraparte"]), ("Interno", "Hacia mis inversiones", "Banco Santander CDT"))

    def test_transferencia_a_un_tercero_en_santander_no_es_mi_cdt(self):
        r, = marcar(mov(DAVI, -1_000_000, "Transferencia BANCO SANTANDER pago arriendo", cat="Transferencias a terceros"))
        self.assertEqual(r["Tipo"], "Gasto")


class Deudas(unittest.TestCase):
    def test_compra_de_cartera_no_es_ingreso(self):
        r, = marcar(mov("Banco de Occidente TC *4321", 8_000_000, "ABONO COMPRA DE CARTERA BANCO DE BOGOTA"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Interno", "Compra de cartera (la deuda pasa de un banco a otro)"))

    def test_pago_tarjeta_falabella_desde_davivienda(self):
        r, = marcar(mov(DAVI, -700_000, "Compra BANCO FALABELLA S A Compras y Pagos PSE"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Interno", "Pago tarjeta Banco Falabella"))

    def test_pago_tarjeta_occidente_desde_bancolombia(self):
        r, = marcar(mov(BANCO, -900_000, "Pagaste $900.000,00 a BANCO DE OCCIDENTE desde tu producto *1234 el 05/10/2026 08:00:00"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Interno", "Pago tarjeta Banco de Occidente"))

    def test_pago_rappicard(self):
        r, = marcar(mov(DAVI, -300_000, "Compra RAPPIPAY Compras y Pagos PSE"))
        self.assertEqual(r["Tipo"], "Interno")

    def test_transferencia_de_un_tercero_que_dice_pago_no_es_avance(self):
        # caso real: plata de la mamá por Bancolombia; antes se leía como avance de la tarjeta Bancolombia
        r, = marcar(mov(DAVI, 2_548_200, "Transferencia BANCOLOMBIA 12345678 transferencia pago transferencia", cat="Transferencias recibidas"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Ingreso", "Transferencias recibidas"))


class NoConfundirConComercios(unittest.TestCase):
    def test_compra_en_tienda_falabella(self):
        r, = marcar(mov("Davivienda TC *4444", -250_000, "FALABELLA CENTRO MAYOR", cat="Compras"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Gasto", "Compras"))

    def test_domicilio_rappi(self):
        r, = marcar(mov("Davivienda TC *4444", -45_000, "RAPPI COLOMBIA*DL", cat="Comida"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Gasto", "Comida"))

    def test_nequi_negocios_no_es_mi_nequi(self):
        r, = marcar(mov("Davivienda TC *4444", -30_000, "WPI*NEQUI NEGOCIOS"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Gasto", "Otros"))

    def test_el_banco_dice_su_nombre_en_sus_propios_movimientos(self):
        # "App Davivienda" en una transferencia recibida en Davivienda no es un pago a la tarjeta Davivienda
        r, = marcar(mov(DAVI, 200_000, "Abono Por Transferencia De Fondos 123456789012345 1234567890 App Davivienda", cat="Transferencias recibidas"))
        self.assertEqual((r["Tipo"], r["Categoría"]), ("Ingreso", "Transferencias recibidas"))


class EntreMisCuentas(unittest.TestCase):
    def test_transferencia_a_mi_cuenta_por_numero(self):
        r, = marcar(mov(BANCO, -1_000_000, "Transferiste $1,000,000.00 desde tu cuenta *1234 a la cuenta *0000004567891111 el 05/10/2026 a las 10:00",
                        cat="Transferencias a terceros"))
        self.assertEqual((r["Tipo"], r["Categoría"], r["Contraparte"]), ("Interno", "Entre mis cuentas", "Banco Caja Social ahorros *1111"))

    def test_transferencia_a_un_tercero_por_numero(self):
        r, = marcar(mov(BANCO, -1_000_000, "Transferiste $1,000,000.00 desde tu cuenta *1234 a la cuenta *0000009876543210 el 05/10/2026 a las 10:00",
                        cat="Transferencias a terceros"))
        self.assertEqual(r["Tipo"], "Gasto")

    def test_mi_nequi_que_no_se_lee_cuenta_como_gastado(self):
        sale, vuelve = marcar(mov(BANCO, -100_000, "Envio a Nequi 3001234567", cat="Transferencias a terceros"),
                              mov(BANCO, 40_000, "Recibiste $40.000 de Nequi 3001234567", cat="Transferencias recibidas"))
        self.assertEqual((sale["Tipo"], sale["Categoría"]), ("Gasto", "Gastos vía billetera (sin detalle)"))
        self.assertEqual((vuelve["Tipo"], vuelve["Valor"]), ("Gasto", 40_000))   # lo que vuelve resta del gasto, no es ingreso

    def test_empareja_salida_y_entrada_a_mi_nombre(self):
        s, e = marcar(mov(DAVI, -500_000, "Transferencia A Llave Otra Entidad Redeban BreB", cat="Transferencias a terceros"),
                      mov(BANCO, 500_000, "JUAN, recibiste una transferencia de JUAN PEREZ por $500.000,00 en tu cuenta *1234",
                          tipo="Interno", cat="Entre mis cuentas", fecha="2026-10-11"), propio="JUAN PEREZ")
        self.assertEqual((s["Tipo"], s["Categoría"]), ("Interno", "Entre mis cuentas"))
        self.assertEqual(s["Subcategoría"], "Davivienda ahorros *5678 → Bancolombia ahorros *1234")

    def test_no_empareja_lejos_en_el_tiempo(self):
        s, e = marcar(mov(DAVI, -500_000, "Transferencia A Llave Otra Entidad Redeban BreB", cat="Transferencias a terceros"),
                      mov(BANCO, 500_000, "JUAN, recibiste una transferencia de JUAN PEREZ por $500.000,00 en tu cuenta *1234",
                          tipo="Interno", cat="Entre mis cuentas", fecha="2026-10-15"), propio="JUAN PEREZ")
        self.assertEqual(s["Tipo"], "Gasto")


if __name__ == "__main__":
    unittest.main()
