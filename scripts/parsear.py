"""
Convierte un documento del normograma DIAN (<doc>.htm + js/<doc>.js) en un JSON estructurado:
árbol (libros/partes/títulos/capítulos/secciones), artículos y sus desplegables
(Notas de Vigencia, Concordancias, Doctrina, Jurisprudencia, Legislación Anterior, Notas del Editor).

Documentos soportados: los registrados en scripts/documentos.py
(et = Estatuto Tributario, dur = Decreto 1625 de 2016, r227 = Resolución DIAN 227 de 2025).

Uso:  python scripts/parsear.py <et|dur|r227> [carpeta_fuente] [salida.json]
"""
import hashlib
import html as H
import json
import re
import sys
import unicodedata
from pathlib import Path

BASE_DOCS = "https://normograma.dian.gov.co/dian/compilacion/docs/"
BASE_GRAF = "https://normograma.dian.gov.co/dian/compilacion/graficas/"

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from documentos import DOCUMENTOS as DOCS, ARCHIVO_A_DOC  # noqa: E402

args = sys.argv[1:]
DOC = args.pop(0) if args and args[0] in DOCS else "et"
CFG = DOCS[DOC]
FUENTE = Path(args[0]) if len(args) > 0 else RAIZ / "data" / CFG["fuente"]
SALIDA = Path(args[1]) if len(args) > 1 else RAIZ / "data" / CFG["json"]


def leer(p: Path) -> str:
    # El normograma declara ISO-8859-1 y usa entidades HTML; cp1252 es superconjunto seguro.
    return p.read_bytes().decode("cp1252", errors="replace")


def plano(fragmento: str) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</td>|</tr>", "\n", fragmento, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = H.unescape(t).replace("\xa0", " ")
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*", "\n", t)
    return t.strip()


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "x"


# ---------------------------------------------------------------- JS (desplegables)
def parsear_js(js: str) -> dict:
    pat = re.compile(
        r'function insRow(\d+)\(\)\s*\{\s*var description = new Array\(\);\s*'
        r'description\[0\] = "(.*?)";\s*var z=',
        re.S,
    )
    out = {}
    for num, cont in pat.findall(js):
        cont = cont.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")
        cont = re.sub(r"^\s*<tbody>\s*<tr>\s*<td>", "", cont)
        cont = re.sub(r"</td>\s*</tr>\s*</tbody>\s*$", "", cont)
        out[int(num)] = cont.strip()
    return out


ETIQUETAS = {
    "jurisprucdencia concordante": "Jurisprudencia Concordante",
    "jurisprudencia concordante": "Jurisprudencia Concordante",
}
CLASE_CAJA = {"caja_vja_v": "vigencia", "caja_vja_c": "concordancia", "caja_vja_la": "anterior"}


def normalizar_etiqueta(et: str):
    et = plano(et)
    nota = None
    if len(et) > 60:  # caso raro: el editor puso una nota completa como título del desplegable
        nota, et = et, "Notas del Editor"
    et = ETIQUETAS.get(et.lower(), et)
    return et, nota


# ---------------------------------------------------------------- enlaces e imágenes
def reescribir(fr: str, anclas=None) -> str:
    """Enlaces a ET o DUR -> marcador interno et:x/<doc>/<ancla> (se resuelve al construir el sitio)."""
    def href(m):
        q, url = m.group(1), m.group(2)
        if url.startswith(("http://", "https://", "mailto:")):
            return f'href={q}{url}{q} target="_blank" rel="noopener"'
        if url.startswith("javascript:"):
            return 'href="#"'
        doc, _, frag = url.partition("#")
        destino = DOC if doc == "" else ARCHIVO_A_DOC.get(doc)
        frag_u = H.unescape(frag)
        if destino:
            if destino == DOC and re.fullmatch(r"NP\d+", frag_u):
                return f'href="et:nota/{frag_u}"'
            if frag_u and frag_u not in ("0", "INICIO"):
                return f'href="et:x/{destino}/{H.escape(frag_u, quote=True)}"'
            return f'href="{BASE_DOCS}{DOCS[destino]["archivo"]}.htm" target="_blank" rel="noopener"'
        return f'href="{BASE_DOCS}{url}" target="_blank" rel="noopener"'

    fr = re.sub(r"""href=(["'])(.*?)\1""", href, fr, flags=re.I)

    def src(m):
        q, url = m.group(1), m.group(2)
        nombre = url.rsplit("/", 1)[-1]
        if "graficas/" in url:
            return f"src={q}et:img/{nombre}{q}"
        return f"src={q}{BASE_DOCS}{url}{q}"

    fr = re.sub(r"""src=(["'])(?!https?:)(.*?)\1""", src, fr, flags=re.I)
    return fr


# ---------------------------------------------------------------- bloques
RE_CAJA = re.compile(
    r'<div>\s*<a class="caja_vja_encabezado[^"]*" href="javascript:insRow(\d+)\(\)">(.*?)</a>\s*</div>\s*'
    r'<table id="Table\1" class="([^"]*)"[^>]*>\s*</table>',
    re.S | re.I,
)
RE_IRARRIBA = re.compile(r'<div class="ir-arriba">.*?</div>', re.S | re.I)
RE_ANCLA_VACIA = re.compile(r"<p>\s*<a name=\"[^\"]*\">\s*</a>\s*</p>", re.I)


def bloques_de(fr: str, cajas: dict, anclas: dict):
    fr = RE_IRARRIBA.sub("", fr)
    fr = RE_ANCLA_VACIA.sub("", fr)
    # el ancla del artículo/encabezado se vuelve texto destacado
    fr = re.sub(r'<a\b[^>]*\bname="[^"]*"[^>]*>(.*?)</a>', r'<strong class="ancla">\1</strong>', fr, flags=re.S | re.I)
    bloques, pos = [], 0
    for m in RE_CAJA.finditer(fr):
        previo = fr[pos:m.start()].strip()
        if previo and plano(previo):
            bloques.append({"tipo": "texto", "html": reescribir(previo, anclas)})
        etiqueta, nota = normalizar_etiqueta(m.group(2))
        cont = cajas.get(int(m.group(1)), "")
        if nota:
            cont = f"<p><em>{H.escape(nota)}</em></p>" + cont
        bloques.append({
            "tipo": "seccion",
            "etiqueta": etiqueta,
            "clase": CLASE_CAJA.get(m.group(3).split()[0], "otra") if etiqueta != "Notas del Editor" else "editor",
            "html": reescribir(cont, anclas),
        })
        pos = m.end()
    resto = fr[pos:].strip()
    if resto and plano(resto):
        bloques.append({"tipo": "texto", "html": reescribir(resto, anclas)})
    return bloques


# ---------------------------------------------------------------- artículos
RE_NUM = re.compile(
    r"^ART[IÍ]CULO\s+(\d+(?:\s*-\s*\d+)*(?:\s*-?\s*(?-i:BIS|[A-Z])\b)?|[A-ZÁÉÍÓÚÑ]+)\s*(?:o\.|º\.?|°\.?)?\s*\.?\s*(.*)$",
    re.S | re.I,
)


RE_NUM_DUR = re.compile(r"^ART[IÍ]CULO\s+(\d+(?:\.\d+)+(?:-\d+)?)\.?\s*(.*)$", re.S | re.I)


def datos_articulo(texto_ancla: str, nombre_ancla: str):
    t = re.sub(r"\s+", " ", texto_ancla).strip()
    m = RE_NUM_DUR.match(t)
    if m:
        return m.group(1), m.group(2).strip()
    m = RE_NUM.match(t)
    if m:
        num = re.sub(r"\s+", "", m.group(1)).upper().replace("BIS", "-BIS").replace("--", "-")
        epi = m.group(2).strip()
    else:
        num, epi = nombre_ancla, t
    if num.isalpha():
        num = num.capitalize()  # "Adicional"
    return num, epi


def titulo_encabezado(fr: str) -> str:
    """Título de un encabezado: el párrafo del ancla y los párrafos centrados que lo siguen inmediatamente."""
    fr = RE_IRARRIBA.sub("", fr)
    partes, pos = [], 0
    for i, m in enumerate(re.finditer(r"<p\b([^>]*)>(.*?)</p>", fr, re.S | re.I)):
        if i > 0 and (fr[pos:m.start()].strip() or "centrado" not in m.group(1)):
            break
        t = plano(m.group(2)).replace("\n", " ")
        if t:
            partes.append(t)
        pos = m.end()
        if i >= 4:
            break
    return re.sub(r"\s+", " ", " ".join(partes)).strip()


def nivel_encabezado(t: str, visto_libro: bool) -> int:
    u = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper().strip()
    if CFG["niveles"]:
        for pal, nivel in CFG["niveles"]:
            if u.startswith(pal):
                return nivel
        return 6
    if u.startswith("LIBRO"):
        return 1
    if u.startswith("TITULO"):
        return 1 if not visto_libro else 2
    if u.startswith("CAPITULO"):
        return 3
    return 4


def main():
    doc = leer(FUENTE / f"{CFG['archivo']}.htm")
    cajas = parsear_js(leer(FUENTE / f"{CFG['archivo']}.js"))
    corte = (FUENTE / "corte.txt").read_text(encoding="latin-1").strip() if (FUENTE / "corte.txt").exists() else ""
    cab = json.loads((FUENTE / "headers.json").read_text()) if (FUENTE / "headers.json").exists() else {}

    ini = doc.index('<a name="documento_top"></a>')
    fin = len(doc)
    for marca in ('<div class="barra-creditos', "<footer"):
        k = doc.find(marca, ini)
        if k > 0:
            fin = min(fin, k)
    cuerpo = doc[ini:fin]

    # -------- recorrer anclas en orden
    anclas_raw = []
    for m in re.finditer(r'<a\b[^>]*\bname="([^"]*)"[^>]*>(.*?)</a>', cuerpo, flags=re.S | re.I):
        nombre, txt = H.unescape(m.group(1)), plano(m.group(2))
        if nombre == "documento_top":
            continue
        if not txt:
            # ancla vacía seguida de un artículo sin ancla propia: <p><A name="LIBRO 1"></A></p><p>ARTÍCULO 1.2.1.22.68 ...
            sig = re.match(r"\s*</p>\s*(<p[^>]*>)(.*?)</p>", cuerpo[m.end():m.end() + 3000], re.S | re.I)
            if sig and "name=" not in sig.group(2):
                linea = plano(sig.group(2)).split("\n")[0]
                if re.match(r"^ART[IÍ]CULO\s", linea, re.I):
                    titulo = re.match(r"^(ART[IÍ]CULO\s+[\d.\-]+\.?\s*[^<]*?\.)(\s|$)", linea)
                    anclas_raw.append({"nombre": nombre, "texto": (titulo.group(1) if titulo else linea[:200]).strip(),
                                       "pos": m.end() + sig.start(1)})
            continue
        if len(txt) <= 3:
            # ancla mal cerrada en la fuente, p. ej. <a name="868">A</A>RTICULO 868. UNIDAD DE VALOR TRIBUTARIO...
            contexto = plano(cuerpo[m.start():m.start() + 1200]).split("\n")[0]
            if re.match(r"^ART[IÍ]CULO\s", contexto, re.I):
                txt = contexto.split("<")[0].strip()[:300]
        p_ini = cuerpo.rfind("<p", 0, m.start())
        anclas_raw.append({"nombre": nombre, "texto": txt, "pos": p_ini})

    notas_pos = next((a["pos"] for a in anclas_raw if re.fullmatch(r"NP\d+", a["nombre"])), None)
    elementos = [a for a in anclas_raw if not re.fullmatch(r"NP\d+", a["nombre"])]

    # -------- identificar artículos/encabezados y asignar ids únicos
    usados, visto_libro = set(), False
    # anexos de normas reglamentarias: se publican como páginas propias (pseudo-artículos)
    previo_anexo = False
    depurados = []
    for a in elementos:
        m_anexo = re.match(r"^ANEXO\s+(?:N[ÚU]MERO\s+|NO\.\s*)?([\w.\-]+?)\.?(?:\s|$)", a["texto"], re.I) if DOC != "et" else None
        if m_anexo and not re.match(r"^ANEXOS\b", a["texto"], re.I):
            a["anexo"] = m_anexo.group(1)
            previo_anexo = True
        elif previo_anexo and not re.match(r"^ART[IÍ]CULO\s", a["texto"], re.I) and nivel_encabezado(a["texto"], True) == 6:
            continue  # ancla interna dentro del contenido de un anexo: se integra al anexo anterior
        else:
            previo_anexo = False
        depurados.append(a)
    elementos = depurados

    for a in elementos:
        if a.get("anexo"):
            cod = a["anexo"]
            slug = CFG["prefijo"] + "anexo-" + slugify(cod)
            base, k = slug, 2
            while slug in usados:
                slug, k = f"{base}-{k}", k + 1
            a.update(tipo="art", id=slug, numero=f"Anexo {cod}", epigrafe="")
        elif re.match(r"^ART[IÍ]CULO\s", a["texto"], re.I):
            num, epi = datos_articulo(a["texto"], a["nombre"])
            slug = CFG["prefijo"] + (num.lower() if "." in num else slugify(num))
            if slug in usados:  # artículos repetidos (<SIC>, BIS, INEXEQUIBLE): usar el ancla DIAN
                slug = CFG["prefijo"] + slugify(a["nombre"])
            base, k = slug, 2
            while slug in usados:
                slug, k = f"{base}-{k}", k + 1
            a.update(tipo="art", id=slug, numero=num, epigrafe=epi)
        else:
            nivel = nivel_encabezado(a["texto"], visto_libro)
            if a["texto"].upper().startswith("LIBRO"):
                visto_libro = True
            base = ("s-" if DOC == "et" else DOC[0] + "-" if DOC == "dur" else DOC + "-") + slugify(a["texto"])[:50]
            slug, k = base, 2
            while slug in usados:
                slug, k = f"{base}-{k}", k + 1
            a.update(tipo="enc", id=slug, nivel=nivel)
        usados.add(a["id"])

    # mapa de anclas originales -> id (para reescribir enlaces internos)
    mapa = {}
    for a in elementos:
        mapa.setdefault(a["nombre"], ("art/" if a["tipo"] == "art" else "sec/") + a["id"])

    # -------- cortar bloques
    limites = [a["pos"] for a in elementos] + [notas_pos or len(cuerpo)]
    preliminar_html = cuerpo[:limites[0]]
    final_html = ""
    articulos, arbol, pila = [], [], []
    for i, a in enumerate(elementos):
        fr = cuerpo[limites[i]:limites[i + 1]]
        if i == len(elementos) - 1 and DOC == "et":
            corte_final = re.search(r'<p><span class="b_aj">ARTICULO SEGUNDO', fr)
            if corte_final:
                final_html, fr = fr[corte_final.start():], fr[:corte_final.start()]
        bloques = bloques_de(fr, cajas, mapa)
        titulo = titulo_encabezado(fr) or a["texto"]
        if a.get("anexo"):
            epi = re.sub(r"^ANEXO\s+(?:N[ÚU]MERO\s+|NO\.\s*)?[\w.\-]+?\.?\s+", "", titulo, flags=re.I)
            a["epigrafe"] = (epi.split("<")[0].strip() or epi.strip() or titulo)[:300]
        if a["tipo"] == "enc":
            nodo = {"id": a["id"], "nivel": a["nivel"], "titulo": titulo, "hijos": []}
            resto = len(" ".join(plano(b["html"]) for b in bloques if b["tipo"] == "texto")) - len(titulo)
            if resto > 250:  # el encabezado trae texto propio (p. ej. un artículo sin ancla): se conserva
                nodo["contenido"] = bloques
            secciones = [b for b in bloques if b["tipo"] == "seccion"]
            if secciones:
                nodo["secciones"] = secciones
            while pila and pila[-1]["nivel"] >= a["nivel"]:
                pila.pop()
            (pila[-1]["hijos"] if pila else arbol).append(nodo)
            pila.append(nodo)
        else:
            ruta = [{"id": n["id"], "titulo": n["titulo"]} for n in pila]
            primero = plano(bloques[0]["html"]) if bloques else ""
            derogado = bool(re.search(r"<\s*(?:Art[íi]culo|Anexo)\s+derogad", primero[:400], re.I))
            texto = "\n".join(plano(b["html"]) for b in bloques if b["tipo"] == "texto")
            anot = "\n".join(f"[{b['etiqueta']}] " + plano(b["html"]) for b in bloques if b["tipo"] == "seccion")
            art = {
                "id": a["id"],
                "numero": a["numero"],
                "ancla_dian": a["nombre"],
                "titulo": a["numero"] if a.get("anexo") else f"Artículo {a['numero']}",
                "anexo": bool(a.get("anexo")),
                "epigrafe": a["epigrafe"],
                "derogado": derogado,
                "ruta": ruta,
                "bloques": bloques,
                "texto": texto,
                "anotaciones": anot,
            }
            art["hash"] = hashlib.sha1(json.dumps(bloques, ensure_ascii=False).encode()).hexdigest()[:16]
            articulos.append(art)
            (pila[-1]["hijos"] if pila else arbol).append({"art": a["id"]})

    notas_html = cuerpo[notas_pos:] if notas_pos else ""
    notas_html = re.sub(r"</div>\s*</div>\s*</div>\s*$", "", notas_html.strip())

    datos = {
        "meta": {
            "doc": DOC,
            "titulo": CFG["largo"],
            "corto": CFG["corto"],
            "fuente": BASE_DOCS + CFG["archivo"] + ".htm",
            "editor_fuente": "Compilación Jurídica de la DIAN — Avance Jurídico Casa Editorial Ltda.",
            "corte_normograma": corte,
            "last_modified": cab.get("last_modified", ""),
            "total_articulos": len(articulos),
            "total_desplegables": sum(1 for a in articulos for b in a["bloques"] if b["tipo"] == "seccion"),
        },
        "preliminar": bloques_de(preliminar_html, cajas, mapa),
        "final": bloques_de(final_html, cajas, mapa),
        "notas_pie": reescribir(notas_html, mapa),
        "anclas": {k: v for k, v in mapa.items()},
        "arbol": arbol,
        "articulos": articulos,
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    print(f"OK {len(articulos)} artículos, {datos['meta']['total_desplegables']} desplegables -> {SALIDA}")


if __name__ == "__main__":
    main()
