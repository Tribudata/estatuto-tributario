"""
Doctrina tributaria DIAN (conceptos y oficios) desde el normograma.

* Catálogo: las 13 páginas t_2_doctrina_tributaria_parte_NN.html (unificados, generales, compilatorios y
  "otros conceptos y oficios" por periodos de años): rótulo, tema, año, categoría.
* Ficha de cada documento (docs/<archivo>.htm): fecha, banco de datos, problema jurídico, tesis jurídica,
  descriptores, fuentes formales, extracto y normas citadas (enlaces del normograma y menciones en texto
  al Estatuto Tributario, al Decreto 1625 de 2016 y a la Resolución DIAN 227 de 2025).
* Resultado: data/doctrina/<año>.json  {id: ficha}  (un archivo por año para mantener el repositorio liviano)

Uso:
  python scripts/doctrina.py                 actualización incremental desde el normograma (descarga solo lo nuevo)
  python scripts/doctrina.py --max 3000      limita cuántos documentos nuevos descarga por corrida
  python scripts/doctrina.py --desde-lotes carpeta   carga inicial desde lotes descargados con el navegador
"""
import gzip
import html as H
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "data" / "doctrina"
SITIO = os.environ.get("ET_NORMOGRAMA", "https://normograma.dian.gov.co/dian/compilacion/")
N_PARTES = 13
CATEGORIA_PARTE = {"01": "Concepto unificado", "02": "Concepto general", "03": "Oficio compilatorio"}
BOGOTA = timezone(timedelta(hours=-5))
MESES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()

# --------------------------------------------------------------------------- utilidades
def plano(fr: str) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</td>|</tr>|</li>", "\n", fr, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = H.unescape(t).replace("\xa0", " ")
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r"\n\s*", "\n", t).strip()


def id_de(archivo: str) -> str:
    return "c-" + archivo.rsplit("/", 1)[-1].replace(".htm", "")


def anio_de(archivo: str, rotulo: str = "") -> int:
    m = re.search(r"_(\d{4})[a-z]?\.htm$", archivo) or re.search(r"de\s+(\d{4})\b", rotulo or "")
    return int(m.group(1)) if m else 0


# --------------------------------------------------------------------------- catálogo
RE_ITEM = re.compile(
    r'<li class="documento-arbol"><a href="docs/([^"#]+\.htm)"[^>]*><span class="id-documento">(.*?)</span></a>'
    r'(?:\s*<br\s*/?>\s*<a [^>]*>\s*<p>(.*?)</p>\s*</a>)?', re.S | re.I)


def parsear_catalogo(partes) -> dict:
    """partes: lista de (numero_parte, html). Devuelve {archivo: {...}}."""
    cat = {}
    for n, t in partes:
        clasif = [(m.start(), plano(m.group(1))) for m in re.finditer(r'<span class="clasificacion-especial">(.*?)</span>', t, re.S)]
        for m in RE_ITEM.finditer(t):
            arch, rotulo, tema = m.group(1), plano(m.group(2)), plano(m.group(3) or "")
            rotulo = re.sub(r"\s+DIAN$", "", rotulo)
            e = cat.setdefault(arch, {"archivo": arch, "rotulo": rotulo, "tema": tema, "categorias": [], "clasificacion": ""})
            if tema and not e["tema"]:
                e["tema"] = tema
            cate = CATEGORIA_PARTE.get(n)
            if cate and cate not in e["categorias"]:
                e["categorias"].append(cate)
            if clasif:
                previas = [c for p, c in clasif if p < m.start()]
                if previas and n == "01":
                    e["clasificacion"] = previas[-1]
    return cat


# --------------------------------------------------------------------------- ficha
DOCS_NORMAS = {"estatuto_tributario": "et", "decreto_1625_2016": "dur", "resolucion_dian_0227_2025": "r227"}
SEP = r"\s*(?:,|;|y|e|o|al|a)\s*"
NUMS_ET = r"(\d+(?:-\d+)*(?:" + SEP + r"\d+(?:-\d+)*)*)"
MODIF = r"(?:,\s*)?(?:(?:y\s+siguientes|inciso[^.;]{0,40}?|par[áa]grafo[^.;]{0,40}?|numeral[^.;]{0,40}?|literal[^.;]{0,40}?)\s+)?"
RE_MENC_ET = re.compile(
    r"\bart(?:[íi]culos?|s?\.)\s+" + NUMS_ET + r"\s*" + MODIF + r"(?:del?\s+)?(?:presente\s+)?"
    r"(?:Estatuto\s+Tributario|E\.\s?T\.?(?=\W)|ET\b)", re.I)
RE_MENC_DUR = re.compile(
    r"\bart(?:[íi]culos?|s?\.)\s+(\d+(?:\.\d+){2,}(?:" + SEP + r"\d+(?:\.\d+){2,})*)\.?\s*" + MODIF +
    r"(?:del?\s+)?(?:Decreto\s+(?:Único\s+Reglamentario\s+(?:en\s+Materia\s+Tributaria\s+)?)?(?:número\s+|No\.\s*)?(?:1625\s+de\s+2016|Único\s+Reglamentario)|DUR\b)", re.I)
RE_MENC_R227 = re.compile(
    r"\bart(?:[íi]culos?|s?\.)\s+(\d+(?:\.\d+)+(?:" + SEP + r"\d+(?:\.\d+)+)*)\.?\s*" + MODIF +
    r"de\s+la\s+Resoluci[óo]n\s+(?:DIAN\s+)?(?:número\s+|No\.\s*)?0*227\s+de\s+2025", re.I)


RE_FORMULA = re.compile(
    r"(Subdirecci[óo]n|Direcci[óo]n de Gesti[óo]n Jur[íi]dica|Oficina Jur[íi]dica|este despacho|esta dependencia).{0,120}"
    r"(facultad|competen)|absolver las consultas|resolver las consultas|en atenci[óo]n a (la|su) (consulta|solicitud)|"
    r"mediante (el )?radicado|de conformidad con el numeral \d+ del art[íi]culo \d+ del decreto|cordial saludo", re.I)


def _celda(fr, rotulo):
    m = re.search(r"<td[^>]*>\s*" + rotulo + r"\s*</td>\s*<td[^>]*>(.*?)</td>", fr, re.S | re.I)
    return plano(m.group(1)) if m else ""


def extraer(archivo: str, fr: str, anio: int = 0) -> dict:
    anio = anio or anio_de(archivo)
    f = {"fecha": "", "banco": "", "problema": "", "tesis": "", "descriptores": "", "fuentes": "", "extracto": "",
         "enlaces": [], "menciones": [], "nota": ""}
    m = re.search(r'<p class="centrado">\s*\((?:[^)]*?)?(' + "|".join(MESES) + r")\s+(\d{1,2})[^)]*\)\s*</p>", fr, re.I)
    if m:
        f["fecha"] = f"{int(m.group(2))} de {m.group(1).lower()} de {anio}"
    f["banco"] = _celda(fr, r"Banco\s+de\s+Datos")
    f["problema"] = _celda(fr, r"Problema\s+Jur[íi]dico")[:1500]
    f["tesis"] = _celda(fr, r"Tesis\s+Jur[íi]dica")[:2000]
    f["descriptores"] = _celda(fr, r"Descriptores")[:600]
    f["fuentes"] = _celda(fr, r"Fuentes\s+Formales")[:800]
    m = re.match(r"\s*Tema:\s*(.*?)\s*Descriptores:\s*(.*)", f["descriptores"], re.S | re.I)
    if m:
        f["banco"] = f["banco"] or m.group(1).strip()
        f["descriptores"] = m.group(2).strip()
    # notas del editor en el encabezado (p. ej. doctrina revocada o modificada)
    cab = plano(fr[:6000])
    nota = re.search(r"<[^<>]*(?:revoca|modifica|reconsidera|aclara)[^<>]*>", cab, re.I)
    if nota:
        f["nota"] = nota.group(0)[:300]
    # cuerpo: secciones PROBLEMA JURÍDICO / TESIS JURÍDICA / FUNDAMENTACIÓN y extracto
    cuerpo = re.sub(r"<table.*?</table>", " ", fr, flags=re.S | re.I)
    secciones = {"p": [], "te": [], "fu": []}
    actual, resto = None, []
    for seg in re.split(r"(?i)<p\b", cuerpo)[1:]:
        fin_attr = seg.find(">")
        if fin_attr < 0 or "centrado" in seg[:fin_attr]:
            continue
        inner = seg[fin_attr + 1:]
        k = inner.lower().find("</p>")
        inner = inner[:k] if k >= 0 else inner[:4000]
        t = plano(inner).replace("\n", " ")
        if not t:
            continue
        es_titulo = bool(re.fullmatch(r"\s*(?:<span class=\"b_aj\">\s*)+[^<]{3,90}?(?:\s*</span>)+\s*:?\s*", inner, re.I)) and len(t) < 90
        if es_titulo:
            u = t.upper()
            actual = "p" if u.startswith("PROBLEMA") else "te" if u.startswith("TESIS") else \
                "fu" if u.startswith(("FUNDAMENTA", "CONSIDERACIONES", "ANÁLISIS", "ANALISIS")) else None
            continue
        if actual in ("p", "te"):
            secciones[actual].append(t)
        elif actual == "fu":
            secciones["fu"].append(t)
        else:
            resto.append(t)
    if not f["problema"] and secciones["p"]:
        f["problema"] = "\n".join(secciones["p"])[:1500]
    if not f["tesis"] and secciones["te"]:
        f["tesis"] = "\n".join(secciones["te"])[:2000]
    base = secciones["fu"] or resto
    base = [t for t in base if t.lower() != "extracto" and not t.startswith("<") and not RE_FORMULA.search(t[:400])]
    f["extracto"] = " ".join(base)[:1200]
    # normas citadas: enlaces del normograma precedidos de "artículo(s)/art." (no "numeral", "literal"...)
    enl = set()
    for m in re.finditer(r'href="(estatuto_tributario|decreto_1625_2016|resolucion_dian_0227_2025)\.htm#([^"]+)"', fr):
        ancla = H.unescape(m.group(2))
        if ancla in ("0", "INICIO"):
            continue
        cola = plano(fr[max(0, m.start() - 400):m.start()])[-90:]
        cola = re.sub(r"<[^>]*$", "", cola).lower()
        if re.search(r"(numeral|literal|inciso|ordinal|par[áa]grafo|n[uú]mero|no\.)\s*$", cola):
            continue
        if re.search(r"art(?:[íi]culos?|s?\.)", cola.split(".")[-1] if "art" not in cola[-40:] else cola[-40:] + " art."):
            enl.add(f"{DOCS_NORMAS[m.group(1)]}#{ancla}")
    f["enlaces"] = sorted(enl)
    txt = re.sub(r"\s+", " ", plano(fr))
    men = set()
    for m in RE_MENC_ET.finditer(txt):
        for num in re.findall(r"\d+(?:-\d+)*", m.group(1)):
            men.add(f"et:{num}")
    for m in RE_MENC_DUR.finditer(txt):
        for num in re.findall(r"\d+(?:\.\d+){2,}", m.group(1)):
            men.add(f"dur:{num}")
    for m in RE_MENC_R227.finditer(txt):
        for num in re.findall(r"\d+(?:\.\d+){1,}", m.group(1)):
            men.add(f"r227:{num.rstrip('.')}")
    f["menciones"] = sorted(men)
    return f


def ficha(entrada: dict, fr: str) -> dict:
    d = dict(entrada)
    d["id"] = id_de(entrada["archivo"])
    d["anio"] = anio_de(entrada["archivo"], entrada.get("rotulo", ""))
    d.update(extraer(entrada["archivo"], fr, d["anio"]))
    d["leido"] = bool(fr)
    return d


# --------------------------------------------------------------------------- persistencia
def cargar() -> dict:
    con = {}
    if CARPETA.exists():
        for f in sorted(CARPETA.glob("*.json")):
            con.update(json.loads(f.read_text(encoding="utf-8")))
    return {"conceptos": con}


def guardar(datos: dict):
    CARPETA.mkdir(parents=True, exist_ok=True)
    por_anio = {}
    for cid, c in datos["conceptos"].items():
        por_anio.setdefault(c.get("anio", 0), {})[cid] = c
    for anio, dd in por_anio.items():
        destino = CARPETA / f"{anio}.json"
        nuevo = json.dumps(dict(sorted(dd.items())), ensure_ascii=False, separators=(",", ":"), sort_keys=False)
        if not destino.exists() or destino.read_text(encoding="utf-8") != nuevo:
            destino.write_text(nuevo, encoding="utf-8")


def recorte(t: str) -> str:
    i = t.find('<a name="documento_top">')
    j = t.find('<div class="barra-creditos', max(i, 0))
    return t[max(i, 0): j if j > 0 else len(t)]


# --------------------------------------------------------------------------- modos
def desde_lotes(carpeta: Path):
    """Carga inicial: doctrina_catalogo.txt.gz + doctrina_lote_NN.txt.gz (descargados con el navegador)."""
    s = gzip.open(carpeta / "doctrina_catalogo.txt.gz", "rt", encoding="utf-8").read()
    partes = [p.split("\x1e", 1) for p in s.split("\x1d")]
    cat = parsear_catalogo(partes)
    datos = cargar()
    for lote in sorted(carpeta.glob("doctrina_lote_*.txt.gz")):
        for reg in gzip.open(lote, "rt", encoding="utf-8").read().split("\x1d"):
            if "\x1e" not in reg:
                continue
            ruta, fr = reg.split("\x1e", 1)
            arch = ruta.replace("docs/", "")
            if arch in cat:
                datos["conceptos"][id_de(arch)] = ficha(cat[arch], fr)
    faltan = [a for a in cat if id_de(a) not in datos["conceptos"]]
    for a in faltan:  # quedan en el catálogo aunque no se haya podido leer el texto
        anio = anio_de(a, cat[a]["rotulo"])
        datos["conceptos"][id_de(a)] = dict(cat[a], id=id_de(a), anio=anio, **extraer(a, "", anio))
    guardar(datos)
    print(f"Doctrina: {len(datos['conceptos'])} documentos ({len(faltan)} solo con datos de catálogo)")


def incremental(maximo: int = 1500, pausa: float = 0.4) -> int:
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 TribudataETBot/1.0 (+https://tribudata.co)"})
    partes = []
    for i in range(1, N_PARTES + 1):
        n = f"{i:02d}"
        r = s.get(f"{SITIO}t_2_doctrina_tributaria_parte_{n}.html", timeout=120)
        if r.status_code == 200:  # el normograma publica en ISO-8859-1 con entidades HTML
            partes.append((n, r.content.decode("cp1252", "replace")))
        time.sleep(pausa)
    cat = parsear_catalogo(partes)
    if len(cat) < 1000:
        raise SystemExit("Catálogo de doctrina incompleto; no se actualiza.")
    datos = cargar()
    con = datos["conceptos"]
    # actualizar datos de catálogo (temas, categorías) de lo ya existente
    for a, e in cat.items():
        if id_de(a) in con:
            con[id_de(a)].update({k: e[k] for k in ("rotulo", "tema", "categorias", "clasificacion")})
    nuevos = [a for a in cat if id_de(a) not in con or not con[id_de(a)].get("leido")]
    nuevos.sort(key=lambda a: -anio_de(a, cat[a]["rotulo"]))
    hechos = 0
    for a in nuevos[:maximo]:
        try:
            r = s.get(f"{SITIO}docs/{a}", timeout=60)
            if r.status_code != 200:
                continue
            con[id_de(a)] = ficha(cat[a], recorte(r.content.decode("cp1252", "replace")))
            hechos += 1
        except Exception as e:  # noqa: BLE001
            print(f"  aviso {a}: {e}")
        time.sleep(pausa)
    guardar(datos)
    print(f"Doctrina: {hechos} documentos nuevos o completados; total {len(con)}; pendientes {max(0, len(nuevos) - hechos)}")
    return hechos


if __name__ == "__main__":
    if "--desde-lotes" in sys.argv:
        desde_lotes(Path(sys.argv[sys.argv.index("--desde-lotes") + 1]))
    else:
        mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 1500
        incremental(mx)
