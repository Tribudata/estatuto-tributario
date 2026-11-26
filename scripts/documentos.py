"""
Registro de documentos del normograma DIAN que integra el sitio.
Para agregar una norma nueva basta con añadir una entrada aquí (y descargar su fuente con actualizar.py).
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

DOCUMENTOS = {
    "et": {
        "archivo": "estatuto_tributario",            # nombre en normograma.dian.gov.co/dian/compilacion/docs/
        "prefijo": "art-",                            # prefijo de los ids de artículo
        "fuente": "fuente",                           # carpeta en data/ con la copia de la fuente
        "json": "estatuto.json",                      # salida del parser en data/
        "dir": "articulos",                           # carpeta de las páginas en el sitio
        "pre": "preliminar.html",                     # página de encabezado/notas
        "nombre": "Estatuto Tributario",
        "con_articulo": "el Estatuto Tributario",
        "corto": "ET",
        "largo": "Estatuto Tributario (Decreto 624 de 1989)",
        "niveles": None,                              # reglas propias (ver parsear.nivel_encabezado)
        "min_htm": 1_000_000, "min_js": 2_000_000, "min_funciones": 5000,
    },
    "dur": {
        "archivo": "decreto_1625_2016",
        "prefijo": "dur-",
        "fuente": "fuente_dur",
        "json": "dur1625.json",
        "dir": "dur",
        "pre": "dur-preliminar.html",
        "nombre": "Decreto 1625 de 2016",
        "con_articulo": "el Decreto 1625 de 2016",
        "corto": "DUR 1625",
        "largo": "Decreto 1625 de 2016 — Único Reglamentario en Materia Tributaria",
        "niveles": [("LIBRO", 1), ("PARTE", 2), ("TITULO", 3), ("CAPITULO", 4), ("SECCION", 5)],
        "min_htm": 2_000_000, "min_js": 2_000_000, "min_funciones": 3000,
    },
    "r227": {
        "archivo": "resolucion_dian_0227_2025",
        "prefijo": "r227-",
        "fuente": "fuente_res227",
        "json": "res227.json",
        "dir": "res227",
        "pre": "res227-preliminar.html",
        "nombre": "Resolución DIAN 227 de 2025",
        "con_articulo": "la Resolución DIAN 227 de 2025",
        "corto": "Res. 227",
        "largo": "Resolución DIAN 227 de 2025 — Resolución Única en Materia Tributaria, Aduanera y Cambiaria",
        "niveles": [("PARTE", 1), ("ANEXOS", 1), ("INSTRUCTIVOS", 1), ("TITULO", 2), ("ANEXO", 2), ("CAPITULO", 3),
                    ("SECCION", 4), ("SUBSECCION", 5)],
        "min_htm": 1_000_000, "min_js": 100_000, "min_funciones": 200,
    },
}

ARCHIVO_A_DOC = {v["archivo"] + ".htm": k for k, v in DOCUMENTOS.items()}


def doc_de_id(aid: str) -> str:
    for k, v in DOCUMENTOS.items():
        if aid.startswith(v["prefijo"]):
            return k
    return "et"
