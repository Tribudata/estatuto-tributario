"""
Texto completo de las sentencias de la relatoría tradicional del Consejo de Estado.

La relatoría entrega cada sentencia por número de relatoría (NR) en
  https://servicios.consejodeestado.gov.co/WebRelatoria/FileReferenceServlet?corp=ce&ext=html&file=<NR>
(o en Word, ext=doc, cuando no hay versión HTML), siempre como descarga. Este script guarda una copia
limpia del texto para mostrarla en el sitio: data/sentencias/<año>/<NR>.html (fragmento HTML saneado).

Uso:
  python scripts/textos_sentencias.py --desde-lotes carpeta
      carpeta con cej_textos_*.json.gz ({NR: html}) y cej_docs_*.json.gz ({NR: .doc en base64}),
      descargados con el navegador. Los .doc se convierten con LibreOffice (soffice --headless).
  python scripts/textos_sentencias.py
      descarga los textos que falten (si el servidor de la relatoría responde desde donde se ejecute).
"""
import base64
import gzip
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from bs4 import BeautifulSoup, Comment, Doctype

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "data" / "sentencias"
JURIS = RAIZ / "data" / "jurisprudencia"
SERVLET = "https://servicios.consejodeestado.gov.co/WebRelatoria/FileReferenceServlet?corp=ce&ext={ext}&file={nr}"

PERMITIDAS = {"p", "br", "b", "i", "u", "sup", "sub", "table", "thead", "tbody", "tr", "td", "th", "ul", "ol", "li", "blockquote"}
EQUIVALENTES = {"strong": "b", "em": "i", "h1": "p", "h2": "p", "h3": "p", "h4": "p", "h5": "p", "h6": "p",
                "center": "p", "dd": "p", "dt": "p", "s": None, "strike": None}


def sanear(html_txt: str) -> str:
    """Deja solo marcado de texto (párrafos, negrita, cursiva, tablas, listas). Sin atributos salvo colspan/rowspan."""
    s = BeautifulSoup(html_txt, "html.parser")
    for t in s.find_all(["script", "style", "head", "title", "meta", "link", "img", "object", "iframe", "svg", "form", "input", "button"]):
        t.decompose()
    for c in s.find_all(string=lambda x: isinstance(x, (Comment, Doctype))):
        c.extract()
    for t in list(s.find_all(True)):
        nombre = t.name.lower()
        if nombre in EQUIVALENTES and EQUIVALENTES[nombre]:
            negrita = nombre.startswith("h")
            t.name = EQUIVALENTES[nombre]
            if negrita and t.get_text(strip=True):
                b = s.new_tag("b")
                for hijo in list(t.contents):
                    b.append(hijo.extract())
                t.append(b)
        elif nombre not in PERMITIDAS:
            t.unwrap()
            continue
        t.attrs = {k: v for k, v in t.attrs.items() if k in ("colspan", "rowspan") and str(v).isdigit()}
    # párrafos vacíos y saltos sobrantes
    for p in s.find_all("p"):
        if not p.get_text(strip=True).replace("\xa0", "") and not p.find("table"):
            p.decompose()
    for td in s.find_all(["td", "th"]):
        for p in td.find_all("p"):
            p.unwrap()
    for b in s.find_all(["b", "i", "u"]):
        if not b.get_text(strip=True):
            b.unwrap()
    out = str(s)
    out = re.sub(r"(?:\s*<br\s*/?>\s*){2,}", "<br/>", out)
    out = re.sub(r"[ \t\r\n\xa0]+", " ", out)
    out = re.sub(r"\s*(</?(?:p|table|tr|td|th|tbody|thead|ul|ol|li|blockquote)\b[^>]*>)\s*", r"\1", out)
    out = re.sub(r"</b><b>", "", out)
    return out.strip()


def anios_por_nr() -> dict:
    out = {}
    for f in JURIS.glob("*.json"):
        for v in json.loads(f.read_text(encoding="utf-8")).values():
            if v.get("nr"):
                out[v["nr"]] = (v.get("fecha") or "0000")[:4]
    return out


def guardar(nr: str, anio: str, html_txt: str) -> bool:
    limpio = sanear(html_txt)
    if len(re.sub(r"<[^>]+>", "", limpio)) < 400:
        return False
    destino = CARPETA / anio / f"{nr}.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(limpio + "\n", encoding="utf-8")
    return True


def convertir_docs(docs: dict) -> dict:
    """{NR: bytes .doc} -> {NR: html} con LibreOffice."""
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "in").mkdir()
        for nr, datos in docs.items():
            (tmp / "in" / f"{nr}.doc").write_bytes(datos)
        archivos = sorted((tmp / "in").glob("*.doc"))
        for i in range(0, len(archivos), 60):
            subprocess.run(["soffice", "--headless", "--convert-to", "html:HTML (StarWriter):UTF8", "--outdir", str(tmp / "out")]
                           + [str(a) for a in archivos[i:i + 60]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1800)
        for f in (tmp / "out").glob("*.html"):
            out[f.stem] = f.read_text(encoding="utf-8", errors="replace")
    return out


def desde_lotes(carpeta: Path):
    anios = anios_por_nr()
    ok = sin = 0
    for f in sorted(carpeta.glob("cej_textos_*.json.gz")):
        for nr, h in json.load(gzip.open(f, "rt", encoding="utf-8")).items():
            if nr in anios and guardar(nr, anios[nr], h):
                ok += 1
            else:
                sin += 1
    docs = {}
    for f in sorted(carpeta.glob("cej_docs_*.json.gz")):
        for nr, b64 in json.load(gzip.open(f, "rt", encoding="utf-8")).items():
            if nr in anios:
                docs[nr] = base64.b64decode(b64)
    convertidos = convertir_docs(docs) if docs else {}
    for nr, h in convertidos.items():
        if guardar(nr, anios[nr], h):
            ok += 1
        else:
            sin += 1
    faltan = sorted(set(anios) - {p.stem for p in CARPETA.rglob("*.html")})
    print(f"Textos de sentencias: {ok} guardados ({len(convertidos)} convertidos desde Word), {sin} vacíos; "
          f"sin texto: {len(faltan)}")
    return faltan


def incremental(maximo: int = 300, pausa: float = 0.5) -> int:
    import requests
    anios = anios_por_nr()
    hechos = {p.stem for p in CARPETA.rglob("*.html")}
    n = 0
    for nr, anio in sorted(anios.items()):
        if nr in hechos or n >= maximo:
            continue
        try:
            r = requests.get(SERVLET.format(ext="html", nr=nr), timeout=60)
            if r.ok and len(r.content) > 500 and guardar(nr, anio, r.content.decode(r.encoding or "utf-8", "replace")):
                n += 1
            else:
                d = requests.get(SERVLET.format(ext="doc", nr=nr), timeout=60)
                if d.ok and len(d.content) > 2000:
                    h = convertir_docs({nr: d.content}).get(nr)
                    if h and guardar(nr, anio, h):
                        n += 1
        except Exception as e:  # noqa: BLE001
            print(f"  {nr}: {e}")
        time.sleep(pausa)
    print(f"Textos de sentencias: {n} nuevos")
    return n


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--desde-lotes":
        desde_lotes(Path(sys.argv[2]))
    else:
        incremental()
