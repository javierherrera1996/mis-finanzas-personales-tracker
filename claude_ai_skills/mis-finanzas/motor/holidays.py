"""Festivos de Colombia sin la librería `holidays` (el entorno de Claude no instala paquetes): solo lo que usa agente.py,
holidays.Colombia(years=...) -> conjunto de fechas. Ley Emiliani: los festivos movibles pasan al lunes siguiente."""
import datetime

FIJOS = [(1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25)]
AL_LUNES = [(1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11)]


def pascua(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l) // 433
    mes = (h + l - 7 * m + 90) // 25
    return datetime.date(y, mes, (h + l - 7 * m + 33 * mes + 19) % 32)


def lunes(f):
    return f + datetime.timedelta(days=(7 - f.weekday()) % 7)


def Colombia(years=()):
    out = set()
    for y in years:
        out.update(datetime.date(y, m, d) for m, d in FIJOS)
        out.update(lunes(datetime.date(y, m, d)) for m, d in AL_LUNES)
        if y >= 2026:   # Virgen de Chiquinquirá (9 de julio), festivo desde 2026
            out.add(lunes(datetime.date(y, 7, 9)))
        p = pascua(y)
        # Jueves y Viernes Santo; Ascensión, Corpus Christi y Sagrado Corazón (ya caen en lunes)
        out.update(p + datetime.timedelta(days=n) for n in (-3, -2, 43, 64, 71))
    return out
