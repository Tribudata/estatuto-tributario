"""
Genera el sitio estático "Estatuto Tributario concordado" de Tribudata.co a partir de:
  data/estatuto.json   (Estatuto Tributario, Decreto 624 de 1989)
  data/dur1625.json    (Decreto 1625 de 2016, Único Reglamentario en Materia Tributaria)

Salida (carpeta site/):
  index.html                    portada: buscador en vivo + índices de ambos documentos
  articulos/<n>.html            una página por artículo del ET
  dur/<n>.html                  una página por artículo del DUR 1625
  preliminar.html, disposiciones-finales.html, dur-preliminar.html, novedades.html
  assets/                       css + js
  data/                         árboles, índices de búsqueda (JSON)
  api/                          un JSON por artículo con texto, desplegables y concordancias (base para IA / MCP)

Uso: python scripts/construir_sitio.py [--base-url https://estatuto.tribudata.co/] [--salida carpeta]
"""
import argparse
import html as H
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from concordar import concordar, tipos_relacion, referencias_internas  # noqa: E402
from documentos import DOCUMENTOS, doc_de_id  # noqa: E402

CAMBIOS = RAIZ / "data" / "cambios.json"
PLANTILLAS = RAIZ / "plantillas"
BASE_GRAF = "https://normograma.dian.gov.co/dian/compilacion/graficas/"
BASE_DOCS = "https://normograma.dian.gov.co/dian/compilacion/docs/"
MARCA = "Tribudata.co"

ap = argparse.ArgumentParser()
ap.add_argument("--base-url", default="https://estatuto.tribudata.co/")
ap.add_argument("--salida", default=str(RAIZ / "site"))
ARGS, _ = ap.parse_known_args()
SITE = Path(ARGS.salida)
BASE_URL = ARGS.base_url.rstrip("/") + "/"
E = H.escape

DOCINFO = {k: dict(v, fin=("disposiciones-finales.html" if k == "et" else v["pre"])) for k, v in DOCUMENTOS.items()}
DOCS, ANCLAS, ARTS, REL = {}, {}, {}, {}
TIPOREL = {}        # (artículo de menor rango, artículo de mayor rango) -> reglamenta | cita | concordancia
REFS, CITADO = {}, {}   # remisiones dentro de la misma norma: id -> [ids a los que remite] / [ids que lo citan]
CONC = {}          # doctrina DIAN: id -> ficha
DOCT = {}          # id de artículo -> [ids de conceptos que lo citan]
CITA = {}          # id de concepto -> [ids de artículos citados]
JUR = {}           # jurisprudencia Consejo de Estado (Sección Cuarta): id -> ficha
MODS = {}          # id de artículo -> número de normas que lo modificaron
JURA = {}          # id de artículo -> [ids de sentencias que lo aplican]
CITAJ = {}         # id de sentencia -> [ids de artículos]
CTCP = {}          # conceptos del Consejo Técnico de la Contaduría Pública: id -> ficha
CTCPA = {}         # id de artículo -> [ids de conceptos CTCP que lo citan]
CITAT = {}         # id de concepto CTCP -> [ids de artículos citados]
# los enlaces de vista rápida (doctrina y sentencias) apuntan a una URL interna: el visor del inicio
# (index.html?ver=<id>). Así ningún entorno que intercepte enlaces externos impide la vista rápida,
# y el enlace se puede abrir en otra pestaña o compartir.
VER = "../index.html?ver="
RE_DOCS_URL = re.compile(r'href="https://normograma\.dian\.gov\.co/dian/compilacion/docs/([^"#]+)\.htm(#[^"]*)?"( target="_blank" rel="noopener")?')


def doc_de(aid: str) -> str:
    return doc_de_id(aid)


def archivo(aid: str) -> str:
    return aid[len(DOCINFO[doc_de(aid)]["prefijo"]):]


def ruta(aid: str) -> str:
    return f"{DOCINFO[doc_de(aid)]['dir']}/{archivo(aid)}.html"


def etiqueta_art(a) -> str:
    return a["numero"] if a.get("anexo") else f"Art. {a['numero']}"


# ------------------------------------------------------------------ texto
SIGLAS = {"IVA", "ICR", "DIAN", "CHC", "GMF", "ECE", "UVT", "ZESE", "ZOMAC", "IPC", "TRM", "NIT", "RUT", "CDT",
          "ESAL", "ICA", "INC", "CERT", "PYME", "PYMES", "ONG", "ZF", "SAS", "S.A.", "S.A.S.", "TIC", "ACPM",
          "CIF", "FOB", "CTI", "CREE", "FINDETER", "ICETEX", "SENA", "ICBF", "FONADE", "IFRS", "NIIF", "OCDE", "CBDT",
          "RST", "SIMPLE.", "CNV", "PIB", "TES", "SECOP", "MUISCA", "RUB", "SAGRILAFT", "CRS", "FATCA", "NIIF.", "COP"}
ROMANOS = re.compile(r"^[IVXLC]+[.,;:)]?$")


def oracion(t: str) -> str:
    """Convierte títulos en MAYÚSCULAS a tipo oración, respetando siglas, romanos y notas <...>."""
    if not t:
        return t
    out = []
    for parte in re.split(r"(<[^>]*>)", t):
        if parte.startswith("<"):
            interior = parte[1:-1]
            out.append("<" + oracion(interior) + ">" if len(interior.split()) > 3 else parte)
            continue
        letras = [c for c in parte if c.isalpha()]
        if not parte.strip() or not letras or sum(c.isupper() for c in letras) / len(letras) < 0.7:
            out.append(parte)
            continue
        nuevos = []
        for tk in re.split(r"(\s+)", parte):
            base = tk.strip("().,;:\"'")
            if base.upper() in SIGLAS or ROMANOS.match(tk) or (tk.startswith("(") and len(base) <= 6 and base.isupper()):
                nuevos.append(tk)
            else:
                nuevos.append(tk.lower())
        out.append("".join(nuevos))
    r = "".join(out)
    r = re.sub(r"(^|[.:]\s+)([a-záéíóúñü])", lambda m: m.group(1) + m.group(2).upper(), r)
    r = re.sub(r"^(\s*<[^>]*>\s*)([a-záéíóúñü])", lambda m: m.group(1) + m.group(2).upper(), r)
    for a, b in (("Titulo", "Título"), ("Capitulo", "Capítulo"), ("Articulo", "Artículo"), ("Seccion", "Sección")):
        r = re.sub(rf"\b{a}\b", b, r)
    return r


def sin_notas(t: str) -> str:
    t = re.sub(r"\s*<[^>]*>\s*", " ", t)
    return re.sub(r"\s*<[^>]*$", "", t).strip()


def titulo_bonito(t: str) -> str:
    return re.sub(r"&lt;(.*?)&gt;", r'<span class="nota-ed">&lt;\1&gt;</span>', E(t))


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# ------------------------------------------------------------------ enlaces
def resolver(fr: str, prefijo: str, graf: set, doc_actual: str) -> str:
    def h(m):
        destino, ancla = m.group(1), H.unescape(m.group(2))
        v = ANCLAS.get(destino, {}).get(ancla)
        if v and v.startswith("art/"):
            aid = v[4:]
            return f'href="{prefijo}{ruta(aid)}" class="ref" data-ref="{aid}"'
        if v and v.startswith("sec/"):
            return f'href="{prefijo}index.html#{v[4:]}"'
        return f'href="{BASE_DOCS}{DOCINFO[destino]["archivo"]}.htm#{E(ancla)}" target="_blank" rel="noopener"'

    fr = re.sub(r'href="et:x/([a-z0-9]+)/([^"]+)"', h, fr)
    fr = re.sub(r'href="et:nota/([^"]+)"', lambda m: f'href="{prefijo}{DOCINFO[doc_actual]["fin"]}#{m.group(1)}"', fr)

    def s(m):
        nombre = m.group(1)
        if nombre in graf:
            return f'src="{prefijo}graficas/{nombre}" loading="lazy"'
        return f'src="{BASE_GRAF}{nombre}" loading="lazy"'

    fr = re.sub(r"""src=["']et:img/([^"']+)["']""", s, fr)
    fr = re.sub(r'<a class="bookmarkaj" name="(NP\d+)">', r'<a class="bookmarkaj" id="\1" name="\1">', fr)
    # enlaces a conceptos/oficios DIAN del catálogo: vista rápida
    if CONC:
        def c(m):
            cid = "c-" + m.group(1)
            if cid in CONC:
                return f'href="{VER}{cid}" class="ref" data-ref="{cid}" data-externo="{m.group(1)}"'
            return m.group(0)
        fr = RE_DOCS_URL.sub(c, fr)
    # enlaces en texto plano (p. ej. PDF de anexos publicados en el Diario Oficial)
    fr = re.sub(r'(?<=[\s>:])(https?://(?:[^<"\n]+?\.pdf\b|[^\s<"]+))',
                lambda m: f'<a href="{m.group(1).replace(" ", "%20")}" target="_blank" rel="noopener">{m.group(1)}</a>', fr)
    return fr


# ------------------------------------------------------------------ plantilla
FUENTES = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500;1,600'
    '&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&display=swap" rel="stylesheet">'
)
LOGO = ('<svg class="logo" viewBox="0 0 32 32" aria-hidden="true"><rect x="3" y="18" width="7" height="11" rx="1"/>'
        '<rect x="12.5" y="11" width="7" height="18" rx="1"/><rect x="22" y="3" width="7" height="26" rx="1"/></svg>')
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' "
           "fill='%230B1F3A'/%3E%3Crect x='5' y='18' width='6' height='9' fill='%23C9A227'/%3E%3Crect x='13' y='12' width='6' "
           "height='15' fill='%23C9A227'/%3E%3Crect x='21' y='6' width='6' height='21' fill='%23C9A227'/%3E%3C/svg%3E")
# la presentación se muestra al entrar desde fuera del sitio; no al volver al inicio desde un artículo ni al llegar con ?q=
INTRO_HEAD = ("<script>(function(){var d=document.documentElement,interno=false;"
              "try{interno=!!document.referrer&&new URL(document.referrer).origin===location.origin}catch(e){}"
              "d.className+=(/[?&](q|ver)=/.test(location.search)||interno)?' sin-intro':' con-intro'})();</script>")
INTRO = """<div id="intro" class="intro" role="dialog" aria-label="Presentación de Tribudata.co">
  <div class="intro-in">
    <svg class="intro-logo" viewBox="0 0 32 32" aria-hidden="true"><rect class="b1" x="3" y="18" width="7" height="11" rx="1"/><rect class="b2" x="12.5" y="11" width="7" height="18" rx="1"/><rect class="b3" x="22" y="3" width="7" height="26" rx="1"/></svg>
    <p class="intro-marca">Tribudata.co</p>
    <span class="intro-filete" aria-hidden="true"></span>
    <p class="intro-lema">Analytics and Taxes</p>
    <p class="intro-claim">Tecnología Tributaria a Tu Alcance</p>
  </div>
  <button type="button" class="intro-omitir">Omitir</button>
</div>
<script>(function(){var i=document.getElementById("intro");if(!i)return;
if(document.documentElement.classList.contains("sin-intro")){i.remove();return}
var hecho=false;function fin(){if(hecho)return;hecho=true;i.classList.add("intro-fin");setTimeout(function(){i.remove()},420)}
i.addEventListener("click",fin);document.addEventListener("keydown",function(e){if(e.key==="Escape")fin()});
setTimeout(function(){hecho=true;i.remove()},4050)})();</script>"""
# tema claro/oscuro: se fija antes de pintar (sin parpadeo); por omisión sigue la preferencia del sistema
TEMA_HEAD = ('<meta name="color-scheme" content="light dark">'
             '<script>(function(){var t;try{t=JSON.parse(localStorage.getItem("etc_tema"))}catch(e){}'
             'if(t!=="oscuro"&&t!=="claro")t="oscuro";'
             'document.documentElement.setAttribute("data-tema",t)})();</script>')
BTN_TEMA = ('<button type="button" class="btn-tema" aria-label="Cambiar entre modo claro y oscuro" title="Modo claro / oscuro">'
            '<svg class="i-luna" viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7z"/></svg>'
            '<svg class="i-sol" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/></svg>'
            '</button>')
CASA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>'


DOCS_JS = json.dumps(dict({k: {"prefijo": v["prefijo"], "dir": v["dir"], "corto": v["corto"], "nombre": v["nombre"]}
                           for k, v in DOCINFO.items()},
                          doc={"prefijo": "c-", "dir": "", "corto": "Doctrina DIAN", "nombre": "Doctrina DIAN (conceptos y oficios)",
                               "externo": BASE_DOCS},
                          jur={"prefijo": "s-", "dir": "", "corto": "Consejo de Estado",
                               "nombre": "Jurisprudencia del Consejo de Estado, Sección Cuarta"},
                          ctcp={"prefijo": "t-", "dir": "", "corto": "CTCP",
                                "nombre": "Conceptos del Consejo Técnico de la Contaduría Pública"}), ensure_ascii=False, separators=(",", ":"))


def pagina(titulo, desc, cuerpo, prefijo, canonical, clase="", extra_head="", doc="et", meta=None):
    corte = E(meta["corte_normograma"]) if meta else ""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(titulo)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(canonical)}">
<meta property="og:site_name" content="{MARCA}">
<meta property="og:title" content="{E(titulo)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{E(canonical)}">
{FUENTES}
<link rel="icon" href="{FAVICON}">
{TEMA_HEAD}
<link rel="stylesheet" href="{prefijo}assets/estilos.css">
{extra_head}
{INTRO_HEAD if clase == "pag-portada" else ""}
</head>
<body class="{clase}" data-prefijo="{prefijo}" data-doc="{doc}">
{INTRO if clase == "pag-portada" else ""}
<a class="saltar" href="#contenido">Saltar al contenido</a>
<header class="barra">
  <div class="barra-in">
    <button class="btn-menu" aria-label="Abrir índice" aria-controls="lateral" aria-expanded="false"><span></span><span></span><span></span></button>
    <a class="marca" href="{prefijo}index.html">{LOGO}<span class="marca-txt"><b>{MARCA}</b><small class="lema">Analytics and Taxes</small><small class="claim">Tecnología Tributaria a Tu Alcance</small></span></a>
    <form class="buscador-barra" action="{prefijo}index.html" method="get" role="search" autocomplete="off">
      <input type="search" name="q" placeholder="Buscar en ET, DUR, Res. 227, doctrina DIAN, Consejo de Estado y CTCP…" aria-label="Buscar en el Estatuto Tributario, el Decreto 1625 y la Resolución 227" aria-autocomplete="list">
    </form>
    {BTN_TEMA}
    <a class="btn-inicio" href="{prefijo}index.html" title="Volver al inicio">{CASA}<span>Inicio</span></a>
  </div>
</header>
<div class="marco">
  <aside id="lateral" class="lateral" aria-label="Índice del documento">
    <div class="lateral-cab">
      <span>{E(DOCINFO[doc]['nombre'])}</span>
      <label class="chk"><input type="checkbox" id="ocultar-derogados"> Ocultar derogados</label>
      <input type="search" class="filtro-indice" data-arbol="#arbol" placeholder="Buscar en el índice: número o tema…" aria-label="Buscar en el índice" autocomplete="off">
      <p class="filtro-cuenta" aria-live="polite"></p>
    </div>
    <nav id="arbol" class="arbol-lateral"><p class="cargando">Cargando índice…</p></nav>
  </aside>
  <main id="contenido" class="principal">
{cuerpo}
  </main>
</div>
<footer class="pie">
  <div class="pie-in">
    <p><b>Fuente:</b> Compilación Jurídica de la DIAN — Normograma:
    {" · ".join(f'<a href="{BASE_DOCS}{v["archivo"]}.htm" target="_blank" rel="noopener">{E(v["nombre"])}</a>' for v in DOCINFO.values())}
    (texto, notas de vigencia, concordancias, doctrina y jurisprudencia).
    Última actualización de la fuente: {corte}. Jurisprudencia: relatorías del Consejo de Estado (SAMAI · Mi Relatoría y relatoría tradicional), Sección Cuarta.</p>
    <p>Herramienta de consulta. No sustituye las ediciones oficiales publicadas en el Diario Oficial. · <a href="{prefijo}novedades.html">Novedades</a> · <a href="{prefijo}preliminar.html">Advertencias</a></p>
    <p class="pie-marca">{MARCA} · Asesoría Tributaria y Analítica de Datos</p>
  </div>
</footer>
<script>window.ETC_DOCS={DOCS_JS};</script>
<script src="{prefijo}assets/app.js" defer></script>
</body>
</html>
"""


# ------------------------------------------------------------------ desplegables
FILTROS = [
    ("concordia", "Concordancias entre normas"),
    ("doctrinadian", "Conceptos DIAN que lo citan"),
    ("jurce", "Sentencias del Consejo de Estado"),
    ("ctcp", "Conceptos del CTCP"),
    ("vigencia", "Notas de vigencia"),
    ("concordancias", "Concordancias"),
    ("doctrina", "Doctrina"),
    ("jurisprudencia", "Jurisprudencia"),
    ("anterior", "Legislación anterior"),
    ("editor", "Notas del editor"),
]


def clasificar(etiqueta: str, clase: str = "") -> str:
    e = norm(etiqueta)
    for clave, tipo in (("doctrina", "doctrina"), ("jurisprudencia", "jurisprudencia"), ("concordancia", "concordancias"),
                        ("anterior", "anterior"), ("editor", "editor")):
        if clave in e:
            return tipo
    return "vigencia"


def render_bloques(bloques, prefijo, graf, doc):
    out = []
    for b in bloques:
        if b["tipo"] == "texto":
            out.append(f'<div class="texto-norma">{resolver(b["html"], prefijo, graf, doc)}</div>')
        else:
            tipo = clasificar(b["etiqueta"], b["clase"])
            out.append(
                f'<details class="desp desp-{tipo}" data-tipo="{tipo}"><summary><span class="desp-et">{E(b["etiqueta"])}</span></summary>'
                f'<div class="desp-cont">{resolver(b["html"], prefijo, graf, doc)}</div></details>'
            )
    return "\n".join(out)


RANGO = {"et": 0, "dur": 1, "r227": 2}
ETQ_REL = {"reglamenta": ("Reglamenta", "Lo invoca al comienzo o en su epígrafe: lo desarrolla o reglamenta"),
           "cita": ("Cita", "Lo menciona de paso en su texto"),
           "concordancia": ("Concordancia", "Relación señalada por el editor del normograma")}


def tipo_rel(x: str, y: str) -> str:
    """Tipo de relación entre dos artículos de normas distintas (se mira desde el de menor rango)."""
    dx, dy = doc_de(x), doc_de(y)
    bajo, alto = (x, y) if RANGO.get(dx, 9) > RANGO.get(dy, 9) else (y, x)
    return TIPOREL.get((bajo, alto), "concordancia")


def bloque_concordia(a, prefijo):
    doc = doc_de(a["id"])
    out = []
    for otro in DOCINFO:
        lista = REL.get(a["id"], {}).get(otro, [])
        if otro == doc or not lista:
            continue
        verbo = "Reglamentación en" if doc == "et" else "Concordancia con"
        titulo = f'{verbo} {E(DOCINFO[otro]["con_articulo"])} <span class="cuenta">{len(lista)}</span>'
        prioridad = {"reglamenta": 0, "concordancia": 1, "cita": 2}
        lista = sorted(lista, key=lambda oid: prioridad[tipo_rel(a["id"], oid)])  # estable: conserva el orden de la norma
        cuenta = {}
        items = []
        for oid in lista:
            o = ARTS[oid]
            t = tipo_rel(a["id"], oid)
            cuenta[t] = cuenta.get(t, 0) + 1
            url = f"{prefijo}{ruta(oid)}"
            der = ' <span class="etiqueta-estado derogado">Derogado</span>' if o["derogado"] else ""
            items.append(
                f'<li data-rel="{t}"><a class="ref" data-ref="{oid}" href="{url}"><span class="rel rel-{t}" title="{ETQ_REL[t][1]}">{ETQ_REL[t][0]}</span>'
                f'<span class="badge badge-{otro}">{E(etiqueta_art(o))}</span> '
                f'{E(oracion(sin_notas(o["epigrafe"])) or "Sin epígrafe")}{der}</a>'
                f'<a class="nt" href="{url}" target="_blank" rel="noopener" title="Abrir en pestaña nueva" aria-label="Abrir {E(etiqueta_art(o))} en pestaña nueva">↗</a></li>'
            )
        plural = {"reglamenta": ("reglamenta", "reglamentan"), "cita": ("cita", "citan"), "concordancia": ("concordancia del editor", "concordancias del editor")}
        resumen = " · ".join(f"{cuenta[k]} {plural[k][0] if cuenta[k] == 1 else plural[k][1]}" for k in ("reglamenta", "cita", "concordancia") if cuenta.get(k))
        ayuda = f'<p class="ayuda">{resumen}. Clic: vista rápida sin salir de la página · ↗: abrir en pestaña nueva</p>'
        out.append(f'<details class="desp desp-concordia conc-{otro}" data-tipo="concordia"><summary><span class="desp-et">⇄ {titulo}</span></summary>'
                   f'<div class="desp-cont">{ayuda}<ul class="lista-concordia">{"".join(items)}</ul></div></details>')
    return "\n".join(out)


def lista_refs(ids, prefijo, tope=80):
    """Lista compacta de artículos (vista rápida al hacer clic)."""
    li = "".join(f'<li><a class="ref" data-ref="{x}" href="{prefijo}{ruta(x)}" title="{E(oracion(sin_notas(ARTS[x]["epigrafe"]))[:120])}">'
                 f'{E(ARTS[x]["numero"])}</a></li>' for x in ids[:tope] if x in ARTS)
    mas = f'<li class="mas-refs">y {len(ids) - tope} más</li>' if len(ids) > tope else ""
    return f'<ul class="refs-lista">{li}{mas}</ul>'


def panel_cifras(a, prefijo) -> str:
    """Panel lateral del artículo: reformas, concordancias, doctrina, sentencias y remisiones (a / desde)."""
    aid, doc = a["id"], doc_de(a["id"])
    nmod, anio = modificaciones(a)
    MODS[aid] = nmod
    filas = []
    if a["derogado"]:
        filas.append(('<span class="est est-derogado">Derogado</span>', ""))
    elif nmod:
        filas.append((f"<b>{nmod}</b>", f'{"reforma" if nmod == 1 else "reformas"} · última en {anio}'))
    else:
        filas.append(('<span class="est est-vigente">Vigente</span>', "sin reformas registradas"))
    for otro in DOCINFO:
        lst = REL.get(aid, {}).get(otro, [])
        if otro != doc and lst:
            nreg = sum(1 for x in lst if tipo_rel(aid, x) == "reglamenta")
            extra = f" · {nreg} {'reglamenta' if nreg == 1 else 'reglamentan'}" if nreg else ""
            donde = {"et": "artículos del Estatuto", "dur": "artículos del DUR 1625", "r227": "artículos de la Res. 227"}.get(otro, DOCINFO[otro]["corto"])
            filas.append((f'<a href="#" data-ir="conc-{otro}"><b>{len(lst)}</b></a>', f'{donde}{extra}'))
    nd, nj, nt = len(DOCT.get(aid, [])), len(JURA.get(aid, [])), len(CTCPA.get(aid, []))
    if nd:
        filas.append((f'<a href="#" data-ir="desp-doctrinadian"><b>{miles(nd)}</b></a>', "conceptos DIAN"))
    if nj:
        filas.append((f'<a href="#" data-ir="desp-jurce"><b>{miles(nj)}</b></a>', "sentencias del Consejo de Estado"))
    if nt:
        filas.append((f'<a href="#" data-ir="desp-ctcp"><b>{miles(nt)}</b></a>', "conceptos del CTCP" if nt > 1 else "concepto del CTCP"))
    cifras = "".join(f'<div class="cifra"><dt>{v}</dt><dd>{t}</dd></div>' for v, t in filas)
    remite, citan = REFS.get(aid, []), CITADO.get(aid, [])
    refs = ""
    if remite:
        refs += f'<details class="refs"><summary>Remite a <b>{len(remite)}</b></summary>{lista_refs(remite, prefijo)}</details>'
    if citan:
        refs += f'<details class="refs"><summary>Citado por <b>{len(citan)}</b></summary>{lista_refs(citan, prefijo)}</details>'
    return (f'<aside class="art-aside" aria-label="Cifras del artículo"><div class="aside-in">'
            f'<p class="aside-tit">Cifras</p><dl class="cifras-art">{cifras}</dl>{refs}'
            f'<nav class="toc" aria-label="En este artículo" hidden><p class="aside-tit">En este artículo</p><ol></ol></nav>'
            f'</div></aside>')


def tema_limpio(t: str) -> str:
    t = re.sub(r"^\(Tributario\)\s*", "", t or "")
    t = re.sub(r"^\(Int\.?\s*[\w.\-]+\)\s*", "", t)
    return t.strip()


def url_concepto(cid: str) -> str:
    return f"{BASE_DOCS}{cid[2:]}.htm"


def cargar_doctrina():
    carpeta = RAIZ / "data" / "doctrina"
    if not carpeta.exists():
        return
    for f in sorted(carpeta.glob("*.json")):
        CONC.update(json.loads(f.read_text(encoding="utf-8")))
    pref = {k: v["prefijo"] for k, v in DOCINFO.items()}
    for cid, c in CONC.items():
        citas = set()
        for e in c.get("enlaces", []):
            d, _, ancla = e.partition("#")
            v = ANCLAS.get(d, {}).get(ancla)
            if v and v.startswith("art/"):
                citas.add(v[4:])
        for mnc in c.get("menciones", []):
            d, _, num = mnc.partition(":")
            aid = pref.get(d, "") + (num.lower() if "." in num else num)
            if aid in ARTS:
                citas.add(aid)
        CITA[cid] = citas
    # concordancias del editor (desplegables "Doctrina Concordante" de las normas) hacia conceptos del catálogo
    for aid, a in ARTS.items():
        for b in a["bloques"]:
            for stem in re.findall(r'href="https://normograma\.dian\.gov\.co/dian/compilacion/docs/([^"#]+)\.htm', b["html"]):
                if "c-" + stem in CONC:
                    CITA.setdefault("c-" + stem, set()).add(aid)
    for cid, citas in CITA.items():
        for aid in citas:
            DOCT.setdefault(aid, []).append(cid)
    clave = lambda cid: (CONC[cid].get("anio", 0), int(re.sub(r"\D", "", CONC[cid].get("rotulo", "0"))[:9] or 0))
    for aid in DOCT:
        DOCT[aid].sort(key=clave, reverse=True)
    for cid in CITA:
        CITA[cid] = sorted(CITA[cid], key=lambda x: (list(DOCINFO).index(doc_de(x)), x))


def bloque_doctrina(a, prefijo, limite=400):
    lista = DOCT.get(a["id"], [])
    if not lista:
        return ""
    items = []
    for cid in lista[:limite]:
        c = CONC[cid]
        url = url_concepto(cid)
        items.append(f'<li><a class="ref" data-ref="{cid}" href="{VER}{cid}"><span class="badge badge-doc">{E(c.get("rotulo", ""))}</span> '
                     f'{E(tema_limpio(c.get("tema", ""))[:220])}{chip_estado(estado_concepto(c.get("nota", "")))}</a>'
                     f'<a class="nt" href="{url}" target="_blank" rel="noopener" title="Texto completo en el normograma DIAN">↗</a></li>')
    mas = (f'<p class="ayuda">Se muestran los {limite} más recientes de {miles(len(lista))}. Use el buscador con el filtro '
           f'«Doctrina DIAN» para ver el resto.</p>') if len(lista) > limite else ""
    return (f'<details class="desp desp-doctrinadian" data-tipo="doctrinadian"><summary><span class="desp-et">§ Conceptos y oficios DIAN que lo citan '
            f'<span class="cuenta">{miles(len(lista))}</span></span></summary><div class="desp-cont">'
            f'<p class="ayuda">Del más reciente al más antiguo · Clic: problema, tesis y extracto sin salir de la página · ↗: texto completo en el normograma</p>'
            f'<ul class="lista-concordia lista-doctrina">{"".join(items)}</ul>{mas}</div></details>')


sys.path.insert(0, str(Path(__file__).resolve().parent))
from jurisprudencia import url_samai, url_sentencia as url_oficial  # noqa: E402

TEXTOS = {p.stem: p for p in (RAIZ / "data" / "sentencias").rglob("*.html")} if (RAIZ / "data" / "sentencias").exists() else {}


def pagina_sentencia(f: dict) -> str:
    """Ruta (relativa a la raíz del sitio) de la página propia de la sentencia, si es de la relatoría tradicional."""
    return f"sentencias/{f['nr']}.html" if f.get("nr") else ""


def url_sentencia(f: dict, prefijo: str = "") -> str:
    pg = pagina_sentencia(f)
    return prefijo + pg if pg else url_oficial(f)

MESES_ES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()


def fecha_es(iso: str) -> str:
    try:
        a, m, d = iso.split("-")
        return f"{int(d)} de {MESES_ES[int(m) - 1]} de {a}"
    except Exception:
        return iso


def rad_fmt(rad: str) -> str:
    r = re.sub(r"\D", "", rad or "")
    return f"{r[:5]}-{r[5:7]}-{r[7:9]}-{r[9:12]}-{r[12:16]}-{r[16:21]}-{r[21:]}" if len(r) == 23 else rad


def rotulo_sentencia(f: dict) -> str:
    anio = f.get("fecha", "")[:4]
    base = "Sentencia de unificación" if f.get("tipo", "").startswith("Sentencia de unif") else "Sentencia"
    return f"{base} {f['interno']} de {anio}" if f.get("interno") else f"{base} de {fecha_es(f.get('fecha', ''))}"


def titulo_sentencia(f: dict) -> str:
    if f.get("problemas"):
        return f["problemas"][0][0]
    d = f.get("titulo") or (f.get("descriptores") or "").split(" / ")[0]
    cab, _, det = d.partition(" - ")
    t = oracion(cab.strip()) + (f" — {det.strip()}" if det.strip() else "")
    return t or rotulo_sentencia(f)


def cargar_jurisprudencia():
    carpeta = RAIZ / "data" / "jurisprudencia"
    if not carpeta.exists():
        return
    for f in sorted(carpeta.glob("*.json")):
        JUR.update(json.loads(f.read_text(encoding="utf-8")))
    pref = {k: v["prefijo"] for k, v in DOCINFO.items()}
    for sid, f in JUR.items():
        citas = set()
        for mnc in f.get("menciones", []):
            d, _, num = mnc.partition(":")
            aid = pref.get(d, "") + (num.lower() if "." in num else num)
            if aid in ARTS:
                citas.add(aid)
        CITAJ[sid] = sorted(citas, key=lambda x: (list(DOCINFO).index(doc_de(x)), x))
        for aid in citas:
            JURA.setdefault(aid, []).append(sid)
    for aid in JURA:
        JURA[aid].sort(key=lambda sid: (JUR[sid].get("fecha", ""), sid), reverse=True)


def bloque_jurisprudencia(a, limite=300):
    lista = JURA.get(a["id"], [])
    if not lista:
        return ""
    items = []
    for sid in lista[:limite]:
        f = JUR[sid]
        url = url_sentencia(f, "../")
        items.append(f'<li><a class="ref" data-ref="{sid}" href="{VER}{sid}"><span class="badge badge-jur">{E(rotulo_sentencia(f))}</span> '
                     f'{E(titulo_sentencia(f)[:230])}{chip_estado(decision_corta(f.get("decision", "")))}</a>'
                     f'<a class="nt" href="{E(url)}" target="_blank" rel="noopener" title="Abrir la sentencia en una pestaña nueva">↗</a></li>')
    mas = (f'<p class="ayuda">Se muestran las {limite} más recientes de {miles(len(lista))}. Use el buscador con el filtro '
           f'«Consejo de Estado» para ver el resto.</p>') if len(lista) > limite else ""
    return (f'<details class="desp desp-jurce" data-tipo="jurce"><summary><span class="desp-et">⚖ Sentencias del Consejo de Estado que lo aplican '
            f'<span class="cuenta">{miles(len(lista))}</span></span></summary><div class="desp-cont">'
            f'<p class="ayuda">Sección Cuarta · de la más reciente a la más antigua · Clic: problema jurídico, tesis y decisión sin salir de la página · ↗: texto de la sentencia</p>'
            f'<ul class="lista-concordia lista-jur">{"".join(items)}</ul>{mas}</div></details>')


def rotulo_ctcp(f: dict) -> str:
    return f.get("rotulo") or f"Concepto CTCP {f['num']} de {f['anio']}"


def cargar_ctcp():
    carpeta = RAIZ / "data" / "ctcp"
    if not carpeta.exists():
        return
    for f in sorted(carpeta.glob("*.json")):
        CTCP.update(json.loads(f.read_text(encoding="utf-8")))
    pref = {k: v["prefijo"] for k, v in DOCINFO.items()}
    for tid, f in CTCP.items():
        citas = set()
        for mnc in f.get("menciones", []):
            d, _, num = mnc.partition(":")
            aid = pref.get(d, "") + (num.lower() if "." in num else num)
            if aid in ARTS:
                citas.add(aid)
        CITAT[tid] = sorted(citas, key=lambda x: (list(DOCINFO).index(doc_de(x)), x))
        for aid in citas:
            CTCPA.setdefault(aid, []).append(tid)
    for aid in CTCPA:
        CTCPA[aid].sort(key=lambda t: (CTCP[t].get("fecha", ""), t), reverse=True)


def estado_ctcp(f: dict) -> str:
    return "Traslado a la DIAN" if f.get("traslado") else ""


def bloque_ctcp(a, limite=300):
    lista = CTCPA.get(a["id"], [])
    if not lista:
        return ""
    items = []
    for tid in lista[:limite]:
        f = CTCP[tid]
        items.append(f'<li><a class="ref" data-ref="{tid}" href="{VER}{tid}"><span class="badge badge-ctcp">{E(rotulo_ctcp(f))}</span> '
                     f'{E(oracion(f.get("tema", ""))[:220])}{chip_estado(estado_ctcp(f))}</a>'
                     f'<a class="nt" href="{E(f.get("url", ""))}" target="_blank" rel="noopener" title="Texto completo en ctcp.gov.co">↗</a></li>')
    return (f'<details class="desp desp-ctcp" data-tipo="ctcp"><summary><span class="desp-et">◇ Conceptos del CTCP que lo citan '
            f'<span class="cuenta">{miles(len(lista))}</span></span></summary><div class="desp-cont">'
            f'<p class="ayuda">Consejo Técnico de la Contaduría Pública · del más reciente al más antiguo · Clic: consulta, respuesta y normativa concordante sin salir de la página · ↗: PDF en ctcp.gov.co</p>'
            f'<ul class="lista-concordia lista-ctcp">{"".join(items)}</ul></div></details>')


def respuesta_pj(p) -> str:
    """Respuesta corta al problema jurídico; con (+) despliega la respuesta desarrollada (tesis)."""
    corta, larga = (p[1] if len(p) > 1 else ""), (p[2] if len(p) > 2 else "")
    if not corta and not larga:
        return ""
    if not larga:
        return f'<p class="pj-r">Respuesta: <b>{E(corta)}</b></p>'
    return (f'<details class="pj-det"><summary class="pj-r">Respuesta: <b>{E(corta or "ver")}</b>'
            f'<span class="pj-mas" aria-hidden="true"></span><span class="sr">Ver la respuesta desarrollada</span></summary>'
            f'<p class="pj-tesis">{E(larga)}</p></details>')


def datos_sentencia(f: dict) -> list:
    """Filas de datos de la sentencia, en el orden de SAMAI."""
    return [("Providencia del", fecha_es(f.get("fecha", ""))), ("Fecha proceso", fecha_es(f.get("fproc", ""))),
            ("Clase del proceso", f.get("clase", "").replace("LEY 1437 ", "").capitalize()),
            ("Sala de decisión", f.get("sala") or "Sección Cuarta"), ("Sentencia", f.get("tipo") or "Sentencia"),
            ("Ponente", f.get("ponente", "")), ("Actor", f.get("actor", "")), ("Demandado", f.get("demandado", "")),
            ("Radicado", rad_fmt(f.get("rad", ""))), ("Número interno", f.get("interno", "")), ("Número de relatoría", f.get("nr", "")),
            ("Salvamentos y aclaraciones", f.get("salvamentos", ""))]


def html_sentencia(sid: str, f: dict, meta) -> str:
    rot = rotulo_sentencia(f)
    tit = titulo_sentencia(f)
    oficial = url_oficial(f)
    chips = "".join(f'<span class="chip-c">{E(x)}</span>' for x in (
        f.get("tipo") if f.get("tipo", "Sentencia") != "Sentencia" else "",
        f.get("clase", "").replace("LEY 1437 ", "").capitalize()) if x) + chip_estado(decision_corta(f.get("decision", "")))
    dato = lambda k, v: f"<dt>{k}</dt><dd>{E(v)}</dd>" if v else ""
    citas = "".join(
        f'<li><a class="ref" data-ref="{x}" href="../{ruta(x)}"><span class="badge badge-{doc_de(x)}">{E(DOCINFO[doc_de(x)]["corto"])} '
        f'{E(etiqueta_art(ARTS[x]))}</span> {E(oracion(sin_notas(ARTS[x]["epigrafe"]))[:110])}</a></li>' for x in CITAJ.get(sid, []))
    probs = "".join(f'<li><p class="pj">{E(p[0])}</p>{respuesta_pj(p)}</li>' for p in f.get("problemas", []))
    titulacion = "".join(x for x in (
        f'<h3 class="c-sub">Descriptores</h3><p class="c-txt">{E(f["descriptores"])}</p>' if f.get("descriptores") else "",
        f'<h3 class="c-sub">Extracto</h3><p class="c-txt">{E(f["extracto"])}{" …" if len(f.get("extracto", "")) >= 2500 else ""}</p>' if f.get("extracto") else "",
        f'<h3 class="c-sub">Sustento normativo</h3><p class="c-txt">{E(f["fuentes"])}</p>' if f.get("fuentes") else "",
        f'<p class="nota-c">{E(f["nota"])}</p>' if f.get("nota") else "") if x)
    texto = TEXTOS.get(f["nr"])
    cuerpo_texto = (texto.read_text(encoding="utf-8") if texto else
                    f'<p class="ayuda">La relatoría no publica en línea el texto de esta sentencia. Puede intentar descargar el original '
                    f'<a href="{E(oficial)}" target="_blank" rel="noopener">desde la relatoría del Consejo de Estado ↗</a>.</p>')
    cuerpo = f"""<article class="articulo concepto sentencia" data-id="{sid}">
  <nav class="miga" aria-label="Ubicación"><a href="../index.html">Inicio</a> <span>›</span> Consejo de Estado <span>›</span> Sección Cuarta</nav>
  <header class="art-cab">
    <p class="art-num"><span class="badge badge-jur">Consejo de Estado</span> {E(rot)} · {E(fecha_es(f.get("fecha", "")))}</p>
    <h1 class="h1-largo">{E(tit)}</h1>
  </header>
  {f'<p class="chips-c">{chips}</p>' if chips else ''}
  <dl class="datos-s">{"".join(dato(k, v) for k, v in datos_sentencia(f))}</dl>
  {f'<h3 class="c-sub">Problemas jurídicos</h3><ol class="lista-pj">{probs}</ol>' if probs else ''}
  {f'<details class="desp desp-jurce"><summary><span class="desp-et">Titulación de la relatoría</span></summary><div class="desp-cont">{titulacion}</div></details>' if titulacion else ''}
  {f'<details class="desp desp-concordia" open><summary><span class="desp-et">Normas que aplica <span class="cuenta">{len(CITAJ.get(sid, []))}</span></span></summary><div class="desp-cont"><ul class="lista-concordia">{citas}</ul></div></details>' if citas else ''}
  <section class="texto-sentencia" aria-label="Texto de la sentencia">
    <h2>Texto de la sentencia</h2>
    {cuerpo_texto}
  </section>
  <p class="c-pie fuente-s">Fuente: relatoría del Consejo de Estado (NR {E(f["nr"])}). Copia del texto publicada para consulta; el documento oficial puede
  <a href="{E(oficial)}" target="_blank" rel="noopener">descargarse de la relatoría ↗</a>.</p>
</article>"""
    desc = f"{rot} del Consejo de Estado, Sección Cuarta ({fecha_es(f.get('fecha', ''))}): {tit}"[:300]
    return pagina(f"{rot} — Consejo de Estado, Sección Cuarta | {MARCA}", desc, cuerpo, "../",
                  f"{BASE_URL}{pagina_sentencia(f)}", "pag-sentencia", meta=meta)


def barra_herramientas(tipos_presentes, url_dian):
    chips = "".join(
        f'<label class="chip chip-{t}"><input type="checkbox" data-filtro="{t}" checked> {E(n)}</label>'
        for t, n in FILTROS if t in tipos_presentes
    )
    return f"""<div class="herramientas">
  <div class="acciones">
    <button type="button" class="btn" data-accion="expandir">Expandir todo</button>
    <button type="button" class="btn" data-accion="contraer">Contraer todo</button>
    <button type="button" class="btn btn-sec" data-accion="copiar">Copiar enlace</button>
    <a class="btn btn-sec" href="{E(url_dian)}" target="_blank" rel="noopener">Ver en normograma DIAN ↗</a>
  </div>
  {f'<div class="filtros" aria-label="Mostrar desplegables">{chips}</div>' if chips else ''}
</div>"""


# ------------------------------------------------------------------ árboles
def contar_arts(n):
    return sum(1 if "art" in h else contar_arts(h) for h in n["hijos"])


def arbol_html(nodos, prefijo):
    out = []
    for n in nodos:
        if "art" in n:
            a = ARTS[n["art"]]
            der = " derogado" if a["derogado"] else ""
            out.append(f'<li class="h-art{der}"><a href="{prefijo}{ruta(a["id"])}"><b>{E(etiqueta_art(a))}</b> '
                       f'{titulo_bonito(oracion(a["epigrafe"]))}</a></li>')
        else:
            out.append(f'<li class="h-enc n{n["nivel"]}" id="{n["id"]}"><details><summary>{titulo_bonito(oracion(n["titulo"]))}'
                       f' <span class="cuenta">{contar_arts(n)}</span></summary><ul>{arbol_html(n["hijos"], prefijo)}</ul></details></li>')
    return "".join(out)


def arbol_json(nodos):
    out = []
    for n in nodos:
        if "art" in n:
            a = ARTS[n["art"]]
            out.append([a["id"], a["numero"], oracion(sin_notas(a["epigrafe"]))[:90], 1 if a["derogado"] else 0])
        else:
            out.append({"i": n["id"], "t": oracion(sin_notas(n["titulo"])), "n": n["nivel"], "h": arbol_json(n["hijos"])})
    return out



# ------------------------------------------------------------------ metadatos de resultados (ubicación, estado, contadores)
ORDINAL = {"PRIMERO": "I", "SEGUNDO": "II", "TERCERO": "III", "CUARTO": "IV", "QUINTO": "V", "SEXTO": "VI",
           "SÉPTIMO": "VII", "SEPTIMO": "VII", "OCTAVO": "VIII", "NOVENO": "IX", "DÉCIMO": "X", "PRELIMINAR": "preliminar"}
LIBRO_ET = {"I": "Renta", "II": "Retención", "III": "IVA", "IV": "Timbre", "V": "Procedimiento", "VI": "GMF",
            "VII": "Normalización", "VIII": "Régimen Simple"}
RE_NIVEL = re.compile(r"^\s*(LIBRO|PARTE|T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\s+([A-ZÁÉÍÓÚ0-9\-]+)", re.I)
NIVEL = {"LIBRO": "Libro", "PARTE": "Parte", "TITULO": "Título", "TÍTULO": "Título", "CAPITULO": "Cap.", "CAPÍTULO": "Cap.",
         "SECCION": "Secc.", "SECCIÓN": "Secc."}


ESENCIALES = {"240": "Tarifa de renta", "771-2": "Soporte de costos", "647": "Inexactitud", "26": "Depuración de la renta",
              "107": "Deducciones", "420": "Hechos generadores IVA", "714": "Firmeza", "241": "Tarifa personas naturales",
              "476": "Excluidos de IVA", "555-2": "RUT"}
ATAJOS = ["240", "771-2", "647", "107", "714", "420"]
ATAJOS_TEMA = ["beneficio de auditoría", "factura electrónica", "sanción por inexactitud"]


def ubicacion(a, doc) -> str:
    out = []
    for r in a["ruta"]:
        m = RE_NIVEL.match(r["titulo"])
        if not m:
            continue
        nivel, num = m.group(1).upper(), m.group(2).upper().rstrip(".")
        num = ORDINAL.get(num, num)
        etq = f"{NIVEL.get(nivel, nivel.capitalize())} {num}"
        if doc == "et" and nivel == "LIBRO" and num in LIBRO_ET:
            etq += f" ({LIBRO_ET[num]})"
        if num == "preliminar":
            etq = "Título preliminar"
        out.append(etq)
        if len(out) == 2:
            break
    return ", ".join(out)


RE_MOD = re.compile(r"(modificad|adicionad|sustituid|subrogad|derogad|reformad)\w*\s+(?:t[áa]citamente\s+)?por\s+(?:el|los)\s+"
                    r"(?:art[íi]culos?|numeral|literal)[^<>]{0,60}?\s+(?:de\s+la|del)\s+"
                    r"(Ley|Decreto(?:\s+Legislativo|\s+Ley|\s+Extraordinario)?|Resoluci[óo]n(?:\s+DIAN)?)\s+(\d+[A-Z]?)\s+de\s+(\d{4})", re.I)


def modificaciones(a):
    """(número de normas que modificaron el artículo, año de la última) según sus notas de vigencia;
    no cuenta la norma que lo creó (<Artículo adicionado por …>)."""
    cab = a["texto"][:400]
    m0 = re.search(r"<Art[íi]culo adicionado por[^>]*?(\d+[A-Z]?) de (\d{4})", cab)
    origen = (m0.group(1), m0.group(2)) if m0 else None
    normas = {}
    for b in a["bloques"]:
        if b["tipo"] == "seccion" and b["etiqueta"].lower().startswith("notas de vigencia"):
            t = re.sub(r"<[^>]+>", " ", H.unescape(b["html"]))
            for m in RE_MOD.finditer(t):
                k = (m.group(2).split()[0].lower(), m.group(3), m.group(4))
                if origen and (k[1], k[2]) == origen:
                    continue
                normas[k] = int(m.group(4))
    return len(normas), (max(normas.values()) if normas else 0)


def estado_norma(a, nmod, anio) -> str:
    if a["derogado"]:
        return "Derogado"
    return f"Modificado {anio}" if nmod else "Vigente"


def estado_concepto(nota: str) -> str:
    n = (nota or "").lower()
    if not n or not (n.startswith("<nota de vigencia") or re.search(
            r"(concepto|oficio|presente)\s+(\w+\s+){0,3}(revocad|reconsiderad|modificad|aclarad|adicionad|suspendid)"
            r"|mediante el cual se (aclara|modifica|revoca|reconsidera)", n)):
        return ""
    parc = "parcial" in n
    for k, v in (("revoc", "Revocado"), ("reconsider", "Reconsiderado"), ("suspend", "Suspendido"),
                 ("modific", "Modificado"), ("adicion", "Modificado"), ("aclar", "Aclarado")):
        if k in n:
            return v + (" parcialmente" if parc and v != "Aclarado" and v != "Suspendido" else "")
    return ""


def slug_estado(t: str) -> str:
    return unicodedata.normalize("NFKD", t.split()[0].lower()).encode("ascii", "ignore").decode() if t else ""


def chip_estado(t: str) -> str:
    return f' <span class="est est-{slug_estado(t)}">{E(t)}</span>' if t else ""


def decision_corta(d: str) -> str:
    """Sentido del fallo normalizado; las combinaciones se resumen en la decisión de fondo."""
    partes = [x.strip() for x in (d or "").upper().split("/") if x.strip() not in ("", "NO APLICA", "SV")]
    if not partes:
        return ""
    fondo = [x for x in partes if x != "INHIBITORIO"] or partes
    if len(set(fondo)) > 1:
        return "Accede parcialmente"
    return {"ACCEDE": "Accede", "NIEGA": "Niega", "ACCEDE PARCIALMENTE": "Accede parcialmente",
            "INHIBITORIO": "Inhibitorio"}.get(fondo[0], fondo[0].capitalize())

def texto_busqueda(a) -> str:
    t = a["texto"].replace("\n", " ")
    ep = a["epigrafe"].strip()
    i = t.find(ep[:40]) if ep and ep != "Sin epígrafe" else -1
    if 0 <= i < 60:
        t = t[i + len(ep):].lstrip()
    return t


def plano_html(h: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", H.unescape(h))).strip()


# ------------------------------------------------------------------ main
def main():
    for d, info in DOCINFO.items():
        DOCS[d] = json.loads((RAIZ / "data" / info["json"]).read_text(encoding="utf-8"))
        ANCLAS[d] = DOCS[d]["anclas"]
        for a in DOCS[d]["articulos"]:
            if not a["epigrafe"].strip():
                a["epigrafe"] = "Sin epígrafe"
            ARTS[a["id"]] = a
    REL.update(concordar(DOCS))
    TIPOREL.update(tipos_relacion(DOCS, REL))
    REFS.update(referencias_internas(DOCS))
    for _o, _lst in REFS.items():
        for _x in _lst:
            CITADO.setdefault(_x, []).append(_o)
    _orden = {a["id"]: i for d in DOCS.values() for i, a in enumerate(d["articulos"])}
    for _x in CITADO:
        CITADO[_x].sort(key=lambda y: _orden.get(y, 0))
    cargar_doctrina()
    cargar_jurisprudencia()
    cargar_ctcp()
    meta = DOCS["et"]["meta"]
    cambios = json.loads(CAMBIOS.read_text(encoding="utf-8")) if CAMBIOS.exists() else []

    if SITE.exists():
        for hijo in SITE.iterdir():
            if hijo.name in ("CNAME",):
                continue
            shutil.rmtree(hijo) if hijo.is_dir() else hijo.unlink()
    for sub in ["assets", "data"] + [DOCINFO[d]["dir"] for d in DOCINFO] + [f"api/{d}" for d in DOCINFO]:
        (SITE / sub).mkdir(parents=True, exist_ok=True)
    (SITE / ".nojekyll").write_text("")
    host = re.sub(r"^https?://", "", BASE_URL).split("/")[0]
    if host and not host.endswith("github.io"):
        (SITE / "CNAME").write_text(host + "\n")  # dominio propio para GitHub Pages
    graf = set()
    origen_graf = RAIZ / "data" / "graficas"
    if origen_graf.exists() and any(origen_graf.iterdir()):
        shutil.copytree(origen_graf, SITE / "graficas", dirs_exist_ok=True)
        graf = {p.name for p in origen_graf.iterdir()}
    for f in ("estilos.css", "app.js"):
        shutil.copy(PLANTILLAS / f, SITE / "assets" / f)

    # ---- páginas de artículos (todas las normas)
    for doc, info in DOCINFO.items():
        A = DOCS[doc]["articulos"]
        for i, a in enumerate(A):
            prev_a = A[i - 1] if i > 0 else None
            next_a = A[i + 1] if i + 1 < len(A) else None
            miga = " <span>›</span> ".join(
                f'<a href="../index.html#{r["id"]}">{E(oracion(sin_notas(r["titulo"])))}</a>' for r in a["ruta"])
            tipos = {clasificar(b["etiqueta"]) for b in a["bloques"] if b["tipo"] == "seccion"}
            conc = bloque_concordia(a, "../")
            if conc:
                tipos.add("concordia")
            bdoc = bloque_doctrina(a, "../")
            if bdoc:
                tipos.add("doctrinadian")
                conc += bdoc
            bjur = bloque_jurisprudencia(a)
            if bjur:
                tipos.add("jurce")
                conc += bjur
            bct = bloque_ctcp(a)
            if bct:
                tipos.add("ctcp")
                conc += bct
            url_dian = f'{BASE_DOCS}{info["archivo"]}.htm#{a["ancla_dian"]}'
            estado = '<span class="etiqueta-estado derogado">Derogado</span>' if a["derogado"] else ""
            nav = '<nav class="paginacion">'
            nav += (f'<a class="ant" href="{archivo(prev_a["id"])}.html">← {E(etiqueta_art(prev_a))}<small>{E(oracion(prev_a["epigrafe"])[:70])}</small></a>'
                    if prev_a else "<span></span>")
            nav += (f'<a class="sig" href="{archivo(next_a["id"])}.html">{E(etiqueta_art(next_a))} →<small>{E(oracion(next_a["epigrafe"])[:70])}</small></a>'
                    if next_a else "<span></span>")
            nav += "</nav>"
            cuerpo = f"""<article class="articulo con-aside" data-id="{a['id']}">
  <nav class="miga" aria-label="Ubicación"><a href="../index.html{'' if doc == 'et' else '#' + doc}">{E(info['nombre'])}</a>{' <span>›</span> ' + miga if miga else ''}</nav>
  <header class="art-cab">
    <p class="art-num"><span class="badge badge-{doc}">{E(info['corto'])}</span> {E(a['numero'] if a.get('anexo') else 'Artículo ' + a['numero'])} {estado}</p>
    <h1{' class="h1-largo"' if len(a['epigrafe']) > 95 else ''}>{titulo_bonito(oracion(a['epigrafe']).rstrip('.'))}</h1>
  </header>
  {panel_cifras(a, "../")}
  {barra_herramientas(tipos, url_dian)}
  {conc}
  <div class="cuerpo-norma" id="texto-vigente">
{render_bloques(a['bloques'], '../', graf, doc)}
  </div>
  {nav}
</article>"""
            nombre_doc = info["nombre"]
            rotulo = a["numero"] if a.get("anexo") else f"Artículo {a['numero']}"
            desc = f"{rotulo} — {nombre_doc}: {a['epigrafe']} " + texto_busqueda(a)[:150]
            ld = {"@context": "https://schema.org", "@type": "Legislation", "name": f"{nombre_doc}, {rotulo.lower()}",
                  "legislationIdentifier": f"{info['largo']}, {rotulo.lower()}", "legislationJurisdiction": "CO", "isBasedOn": url_dian}
            html = pagina(
                f"{rotulo} {nombre_doc} — {sin_notas(oracion(a['epigrafe'])).rstrip('.')} | {MARCA}",
                desc[:300], cuerpo, "../", f"{BASE_URL}{ruta(a['id'])}", "pag-articulo", doc=doc, meta=meta,
                extra_head=f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>')
            (SITE / ruta(a["id"])).write_text(html, encoding="utf-8")

            api = {
                "id": a["id"], "documento": info["largo"], "numero": a["numero"], "epigrafe": a["epigrafe"],
                "derogado": a["derogado"], "ruta": [r["titulo"] for r in a["ruta"]], "url": f"{BASE_URL}{ruta(a['id'])}",
                "fuente": url_dian, "texto": a["texto"],
                "concordancias": {DOCINFO[o]["largo"]: [{"id": x, "numero": ARTS[x]["numero"], "epigrafe": ARTS[x]["epigrafe"]}
                                                        for x in lst] for o, lst in REL.get(a["id"], {}).items()},
                "doctrina_dian": [{"id": c, "rotulo": CONC[c].get("rotulo"), "tema": tema_limpio(CONC[c].get("tema", "")),
                                   "url": url_concepto(c)} for c in DOCT.get(a["id"], [])],
                "jurisprudencia_consejo_estado": [{"id": x, "rotulo": rotulo_sentencia(JUR[x]), "fecha": JUR[x].get("fecha"),
                                                   "radicado": rad_fmt(JUR[x].get("rad", "")), "url": BASE_URL + pagina_sentencia(JUR[x]) if JUR[x].get("nr") else url_oficial(JUR[x])}
                                                  for x in JURA.get(a["id"], [])],
                "conceptos_ctcp": [{"id": x, "rotulo": rotulo_ctcp(CTCP[x]), "fecha": CTCP[x].get("fecha"), "tema": CTCP[x].get("tema"),
                                    "url": CTCP[x].get("url")} for x in CTCPA.get(a["id"], [])],
                "desplegables": [{"tipo": clasificar(b["etiqueta"]), "etiqueta": b["etiqueta"],
                                  "texto": re.sub(r"\s+\n", "\n", re.sub(r"<[^>]+>", "", H.unescape(b["html"].replace("</p>", "\n"))).strip())}
                                 for b in a["bloques"] if b["tipo"] == "seccion"],
            }
            (SITE / "api" / doc / f"{archivo(a['id'])}.json").write_text(json.dumps(api, ensure_ascii=False), encoding="utf-8")

        # índices JSON por documento
        (SITE / "data" / f"arbol-{doc}.json").write_text(
            json.dumps(arbol_json(DOCS[doc]["arbol"]), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        busq = []
        for a in A:
            nmod, anio = modificaciones(a)
            ncon = sum(len(l) for l in REL.get(a["id"], {}).values())
            MODS[a["id"]] = nmod
            busq.append([a["id"], a["numero"], oracion(a["epigrafe"]), texto_busqueda(a), 1 if a["derogado"] else 0,
                         ubicacion(a, doc), estado_norma(a, nmod, anio), [ncon, len(DOCT.get(a["id"], [])), len(JURA.get(a["id"], [])), nmod, len(CTCPA.get(a["id"], []))]])
        (SITE / "data" / f"busqueda-{doc}.json").write_text(json.dumps(busq, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        anot = [[a["id"], " ".join(f"[{b['etiqueta']}] " + plano_html(b["html"]) for b in a["bloques"]
                                   if b["tipo"] == "seccion" and clasificar(b["etiqueta"]) != "anterior")] for a in A]
        (SITE / "data" / f"anotaciones-{doc}.json").write_text(json.dumps(anot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- doctrina DIAN: índices de búsqueda y fichas por año
    if CONC:
        (SITE / "data" / "doctrina").mkdir(parents=True, exist_ok=True)
        orden = sorted(CONC, key=lambda c: (-CONC[c].get("anio", 0), c))
        busq = [[c, CONC[c].get("rotulo", ""), tema_limpio(CONC[c].get("tema", "")),
                 " ".join(x for x in (CONC[c].get("descriptores", ""), CONC[c].get("banco", ""), CONC[c].get("clasificacion", ""),
                                      " ".join(CONC[c].get("categorias", []))) if x), 0,
                 (CONC[c].get("categorias") or [""])[0], estado_concepto(CONC[c].get("nota", "")), [len(CITA.get(c, []))]] for c in orden]
        (SITE / "data" / "busqueda-doc.json").write_text(json.dumps(busq, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        anot = [[c, " ".join(x for x in (CONC[c].get("problema", ""), CONC[c].get("tesis", ""), CONC[c].get("fuentes", "")) if x)]
                for c in orden]
        (SITE / "data" / "anotaciones-doc.json").write_text(json.dumps(anot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        por_anio = {}
        for c in orden:
            k = CONC[c]
            por_anio.setdefault(k.get("anio", 0), {})[c] = {
                "r": k.get("rotulo", ""), "t": tema_limpio(k.get("tema", "")), "f": k.get("fecha", ""), "b": k.get("banco", ""),
                "p": k.get("problema", ""), "te": k.get("tesis", ""), "d": k.get("descriptores", ""), "fu": k.get("fuentes", ""),
                "x": k.get("extracto", ""), "n": k.get("nota", ""), "cat": k.get("categorias", []), "cl": k.get("clasificacion", ""),
                "e": estado_concepto(k.get("nota", "")),
                "c": [[x, etiqueta_art(ARTS[x]), oracion(sin_notas(ARTS[x]["epigrafe"]))[:90]] for x in CITA.get(c, [])],
            }
        for anio, dd in por_anio.items():
            (SITE / "data" / "doctrina" / f"{anio}.json").write_text(json.dumps(dd, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- jurisprudencia Consejo de Estado: índices de búsqueda y fichas por año
    if JUR:
        (SITE / "data" / "jurisprudencia").mkdir(parents=True, exist_ok=True)
        orden = sorted(JUR, key=lambda x: (JUR[x].get("fecha", ""), x), reverse=True)
        busq, anot_j, por_anio = [], [], {}
        for sid in orden:
            f = JUR[sid]
            busq.append([sid, rotulo_sentencia(f), titulo_sentencia(f)[:300],
                         " ".join(x for x in (re.sub(r"^MEDIO DE CONTROL DE NULIDAD Y RESTABLECIMIENTO DEL DERECHO / ", "", f.get("descriptores", ""))[:280], f.get("ponente", ""), f.get("actor", ""), f.get("demandado", ""),
                                              f.get("decision", ""), f.get("rad", ""), rad_fmt(f.get("rad", "")), f.get("nr", "")) if x), 0,
                         "C.P. " + " ".join(w.capitalize() for w in f.get("ponente", "").split()[:3]) if f.get("ponente") else "",
                         decision_corta(f.get("decision", "")), [len(CITAJ.get(sid, []))]])
            anot_j.append([sid, " ".join(x for x in (" ".join(p[0] for p in f.get("problemas", [])), f.get("extracto", "")[:1200], f.get("fuentes", "")[:400]) if x)])
            por_anio.setdefault(f.get("fecha", "")[:4] or "0", {})[sid] = {
                "r": rotulo_sentencia(f), "t": titulo_sentencia(f), "f": fecha_es(f.get("fecha", "")), "po": f.get("ponente", ""),
                "ac": f.get("actor", ""), "de": f.get("demandado", ""), "cl": f.get("clase", "").replace("LEY 1437 ", "").capitalize(),
                "ti": f.get("tipo", ""), "dc": (f.get("decision", "") or "").capitalize(), "e": decision_corta(f.get("decision", "")), "sv": f.get("salvamentos", ""),
                "ra": rad_fmt(f.get("rad", "")), "ni": f.get("interno", ""), "d": f.get("descriptores", ""),
                "pr": [[p[0], p[1] if len(p) > 1 else "", (p[2] if len(p) > 2 else "")[:1800]] for p in f.get("problemas", [])],
                "fq": fecha_es(f.get("fproc", "")), "sa": f.get("sala") or "Sección Cuarta",
                # el extracto se omite cuando cada problema ya trae su respuesta desarrollada
                "x": "" if f.get("problemas") and all(len(p) > 2 and p[2] for p in f["problemas"]) else f.get("extracto", ""), "fu": f.get("fuentes", ""), "n": f.get("nota", ""),
                "u": pagina_sentencia(f), "uo": url_oficial(f) if f.get("nr") else "", "us": url_samai(f["rad"]) if f.get("fuente") == "samai" else "",
                "c": [[x, etiqueta_art(ARTS[x]), oracion(sin_notas(ARTS[x]["epigrafe"]))[:90]] for x in CITAJ.get(sid, [])],
            }
        (SITE / "data" / "busqueda-jur.json").write_text(json.dumps(busq, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (SITE / "data" / "anotaciones-jur.json").write_text(json.dumps(anot_j, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for anio, dd in por_anio.items():
            (SITE / "data" / "jurisprudencia" / f"{anio}.json").write_text(json.dumps(dd, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- conceptos del CTCP: índices de búsqueda y fichas por año
    if CTCP:
        (SITE / "data" / "ctcp").mkdir(parents=True, exist_ok=True)
        orden = sorted(CTCP, key=lambda x: (CTCP[x].get("fecha", ""), x), reverse=True)
        busq, anot_t, por_anio = [], [], {}
        for tid in orden:
            f = CTCP[tid]
            po = " ".join(w.capitalize() for w in (f.get("ponente") or "").split()[:3])
            busq.append([tid, rotulo_ctcp(f), oracion(f.get("tema", ""))[:300],
                         " ".join(x for x in ((f.get("resumen") or f.get("respuesta", ""))[:600], f"Radicación {f['anio']}-{f['num']}.",
                                              f.get("ponente", ""), " ".join(f.get("otras", []))) if x), 0,
                         ("C.P. " + po) if po else "", estado_ctcp(f), [len(CITAT.get(tid, []))]])
            anot_t.append([tid, " ".join(x for x in (f.get("consulta", ""), f.get("respuesta", "")) if x)])
            por_anio.setdefault(str(f["anio"]), {})[tid] = {
                "r": rotulo_ctcp(f), "t": oracion(f.get("tema", "")), "f": fecha_es(f.get("fecha", "")), "rad": f["num"] if f.get("tipo") else f"{f['anio']}-{f['num']}", "ti": f.get("tipo", ""),
                "rs": f.get("resumen", ""), "cs": f.get("consulta", ""), "x": f.get("respuesta", ""), "po": f.get("ponente", ""),
                "o": f.get("otras", []), "e": estado_ctcp(f), "u": f.get("url", ""),
                "c": [[x, etiqueta_art(ARTS[x]), oracion(sin_notas(ARTS[x]["epigrafe"]))[:90]] for x in CITAT.get(tid, [])],
            }
        (SITE / "data" / "busqueda-ctcp.json").write_text(json.dumps(busq, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (SITE / "data" / "anotaciones-ctcp.json").write_text(json.dumps(anot_t, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for anio, dd in por_anio.items():
            (SITE / "data" / "ctcp" / f"{anio}.json").write_text(json.dumps(dd, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    (SITE / "api" / "indice.json").write_text(json.dumps({
        "meta": {"corte_normograma": meta["corte_normograma"], "documentos": {d: DOCINFO[d]["largo"] for d in DOCINFO}},
        "articulos": [{"id": a["id"], "documento": doc_de(a["id"]), "numero": a["numero"], "epigrafe": a["epigrafe"],
                       "derogado": a["derogado"], "ruta": [r["titulo"] for r in a["ruta"]], "api": f"api/{doc_de(a['id'])}/{archivo(a['id'])}.json"}
                      for d in DOCINFO for a in DOCS[d]["articulos"]],
        "concordancias": REL,
    }, ensure_ascii=False), encoding="utf-8")

    # ---- portada
    n_rel = sum(len(l) for k, v in REL.items() if doc_de(k) == "et" for l in v.values()) + \
        sum(len(l) for k, v in REL.items() if doc_de(k) != "et" for o, l in v.items() if o != "et") // 2
    ult = cambios[0] if cambios else None
    aviso = (f'<a class="aviso-nov" href="novedades.html"><b>Última actualización:</b> {E(ult["fecha"])} — '
             f'{len(ult.get("modificados", []))} modificados, {len(ult.get("nuevos", []))} nuevos</a>') if ult else ""
    radios = "".join(f'<label><input type="radio" name="fuente" value="{d}"> {E(DOCINFO[d]["corto"] if d != "et" else "Estatuto")}</label>' for d in DOCINFO)
    if CONC:
        radios += '<label><input type="radio" name="fuente" value="doc"> Doctrina DIAN</label>'
    if JUR:
        radios += '<label><input type="radio" name="fuente" value="jur"> Consejo de Estado</label>'
    if CTCP:
        radios += '<label><input type="radio" name="fuente" value="ctcp"> CTCP</label>'
    cifras = "".join(f'<li><b>{miles(len(DOCS[d]["articulos"]))}</b><span>{"artículos del ET" if d == "et" else "artículos y anexos " + ("del " if d == "dur" else "de la ") + E(DOCINFO[d]["corto"])}</span></li>' for d in DOCINFO)
    pestanas = "".join(
        f'<button type="button" role="tab" class="pestana{" activa" if d == "et" else ""}" data-tab="{d}" aria-selected="{"true" if d == "et" else "false"}">'
        f'{E(DOCINFO[d]["nombre"])} <span class="cuenta">{miles(len(DOCS[d]["articulos"]))}</span></button>' for d in DOCINFO)
    extras = {"et": '<a class="btn btn-sec" href="preliminar.html">Advertencias y encabezado</a><a class="btn btn-sec" href="disposiciones-finales.html">Disposiciones finales</a>'}
    indices = "".join(
        f'<div class="indice-doc" data-doc="{d}"{"" if d == "et" else " hidden"}><div class="indice-cab"><h2>Índice {"del " + E(DOCINFO[d]["nombre"]) if d != "r227" else "de la " + E(DOCINFO[d]["nombre"])}</h2>'
        f'<div class="acciones"><button type="button" class="btn btn-sec" data-accion="expandir-indice">Expandir todo</button>'
        f'{extras.get(d, f"<a class=\"btn btn-sec\" href=\"{DOCINFO[d]["pre"]}\">Encabezado y considerandos</a>")}</div></div>'
        f'<div class="filtro-portada"><input type="search" class="filtro-indice" data-arbol=".indice-doc[data-doc={d}] .arbol-portada" '
        f'placeholder="Buscar en el índice {"del Estatuto" if d == "et" else "del DUR 1625" if d == "dur" else "de la Resolución 227"}: número de artículo o tema (ej. 240, dividendos, factura electrónica)" '
        f'aria-label="Buscar en el índice" autocomplete="off"><p class="filtro-cuenta" aria-live="polite"></p></div>'
        f'<ul class="arbol-portada">{arbol_html(DOCS[d]["arbol"], "")}</ul></div>' for d in DOCINFO)
    # ---- sugerencias antes de escribir: más citados, más modificados y esenciales (solo Estatuto)
    por_num = {a["numero"]: a for a in DOCS["et"]["articulos"]}
    def item_dest(a, extra):
        return [a["id"], a["numero"], oracion(sin_notas(a["epigrafe"])).rstrip(".")[:80], extra]
    def cuenta_txt(a):
        nd, nj = len(DOCT.get(a["id"], [])), len(JURA.get(a["id"], []))
        return " · ".join(x for x in (f"{miles(nd)} conceptos" if nd else "", f"{miles(nj)} sentencias" if nj else "") if x)
    vivos = [a for a in DOCS["et"]["articulos"] if not a["derogado"]]
    citados = sorted(vivos, key=lambda a: -(len(DOCT.get(a["id"], [])) + len(JURA.get(a["id"], []))))[:6]
    modif = sorted(vivos, key=lambda a: (-MODS.get(a["id"], 0), a["numero"]))[:6]
    esenciales = [por_num[n] for n in ESENCIALES if n in por_num][:6]
    destacados = {
        "cit": [item_dest(a, cuenta_txt(a)) for a in citados],
        "mod": [item_dest(a, f"{MODS[a['id']]} reformas") for a in modif],
        "ese": [item_dest(a, ESENCIALES[a["numero"]]) for a in esenciales],
    }
    atajos = "".join(f'<a class="atajo" href="{ruta(por_num[n]["id"])}">Art. {E(n)}</a>' for n in ATAJOS if n in por_num) + \
        "".join(f'<button type="button" class="atajo atajo-tema" data-q="{E(t)}">{E(t)}</button>' for t in ATAJOS_TEMA)
    portada = f"""<script>window.ETC_DESTACADOS={json.dumps(destacados, ensure_ascii=False)};</script>
<section class="heroe">
  <h1>Estatuto Tributario</h1>
  <p class="bajada">El Estatuto Tributario, el Decreto Único Reglamentario 1625 de 2016 y la Resolución DIAN 227 de 2025, enlazados artículo por artículo y con la doctrina DIAN que los interpreta, las sentencias de la Sección Cuarta del Consejo de Estado que los aplican{" y los conceptos del Consejo Técnico de la Contaduría Pública que los citan" if CTCP else ""}. Cada artículo trae sus notas de vigencia, concordancias y jurisprudencia.</p>
  <form id="form-busqueda" class="busqueda-grande" role="search" onsubmit="return false" autocomplete="off">
    <div class="caja-busqueda">
      <input id="q" type="search" placeholder="Artículo, concepto o tema… ej. 240 · 1.2.1.5.3.4 · formato 1001 · concepto 18702 · beneficio de auditoría" autocomplete="off" aria-label="Buscar en el Estatuto Tributario, el Decreto 1625 y la Resolución 227" aria-autocomplete="list" aria-controls="sugerencias-q">
    </div>
    <nav class="atajos" aria-label="Accesos rápidos">{atajos}</nav>
    <div class="opciones-busqueda">
      <div class="segmentos" role="radiogroup" aria-label="Buscar en">
        <label><input type="radio" name="fuente" value="todo" checked> Todo</label>{radios}
      </div>
      <label class="chk"><input type="checkbox" id="en-anotaciones"> Incluir notas, concordancias, doctrina y jurisprudencia</label>
      <label class="chk"><input type="checkbox" id="sin-derogados"> Excluir derogados</label>
    </div>
  </form>
  <ul class="cifras">{cifras}<li><b>{miles(n_rel)}</b><span>concordancias entre normas</span></li>{f'<li><b>{miles(len(CONC))}</b><span>conceptos y oficios DIAN</span></li>' if CONC else ''}{f'<li><b>{miles(len(JUR))}</b><span>sentencias del Consejo de Estado</span></li>' if JUR else ''}{f'<li><b>{miles(len(CTCP))}</b><span>conceptos del CTCP</span></li>' if CTCP else ''}</ul>
  <p class="corte">Texto sincronizado con el normograma de la DIAN · corte del {E(meta['corte_normograma'].split(' (')[0])}</p>
  {aviso}
</section>
<section id="resultados" class="resultados" hidden aria-live="polite"></section>
<section id="indice-portada" class="indice-portada">
  <div class="pestanas" role="tablist">{pestanas}</div>
  {indices}
</section>"""
    (SITE / "index.html").write_text(pagina(
        f"Estatuto Tributario concordado con el DUR 1625 y la Resolución DIAN 227 | {MARCA}",
        "Estatuto Tributario de Colombia, Decreto 1625 de 2016 y Resolución Única DIAN 227 de 2025 concordados: texto vigente, notas de vigencia, concordancias, doctrina DIAN y jurisprudencia, con búsqueda en vivo y actualización automática desde el normograma DIAN.",
        portada, "", BASE_URL, "pag-portada", meta=meta), encoding="utf-8")

    # ---- páginas auxiliares
    def pag_aux(doc, bloques, extra_html, titulo_h1, archivo, titulo, desc):
        tipos = {clasificar(b["etiqueta"]) for b in bloques if b["tipo"] == "seccion"}
        cuerpo = f"""<article class="articulo"><header class="art-cab"><p class="art-num"><span class="badge badge-{doc}">{DOCINFO[doc]['corto']}</span> {E(DOCINFO[doc]['nombre'])}</p><h1>{E(titulo_h1)}</h1></header>
{barra_herramientas(tipos, BASE_DOCS + DOCINFO[doc]['archivo'] + '.htm')}
<div class="cuerpo-norma">{render_bloques(bloques, '', graf, doc)}{extra_html}</div></article>"""
        (SITE / archivo).write_text(pagina(titulo, desc, cuerpo, "", BASE_URL + archivo, doc=doc, meta=meta), encoding="utf-8")

    pag_aux("et", DOCS["et"]["preliminar"], "", "Advertencias y encabezado", "preliminar.html",
            f"Estatuto Tributario — advertencias y encabezado | {MARCA}", "Encabezado del Decreto 624 de 1989 y resumen de notas de vigencia.")
    notas_et = f'<div class="texto-norma notas-pie">{resolver(DOCS["et"]["notas_pie"], "", graf, "et")}</div>'
    pag_aux("et", DOCS["et"]["final"], notas_et, "Disposiciones finales y notas", "disposiciones-finales.html",
            f"Estatuto Tributario — disposiciones finales | {MARCA}", "Artículos segundo a cuarto del Decreto 624 de 1989 y notas de pie de página.")
    for d in DOCINFO:
        if d == "et":
            continue
        notas = f'<div class="texto-norma notas-pie">{resolver(DOCS[d]["notas_pie"], "", graf, d)}</div>' if DOCS[d]["notas_pie"] else ""
        pag_aux(d, DOCS[d]["preliminar"] + DOCS[d]["final"], notas, "Encabezado, considerandos y notas", DOCINFO[d]["pre"],
                f"{DOCINFO[d]['nombre']} — encabezado | {MARCA}", f"Encabezado, considerandos y resumen de notas de vigencia de {DOCINFO[d]['con_articulo']}.")

    items = []
    for c in cambios:
        def lista(ids, clase):
            li = "".join(f'<li><a href="{ruta(i)}"><span class="badge badge-{doc_de(i)}">{DOCINFO[doc_de(i)]["corto"]}</span> '
                         f'{E(etiqueta_art(ARTS[i]))}</a> {E(oracion(ARTS[i]["epigrafe"])[:90])}</li>'
                         if i in ARTS else f"<li>{E(i)}</li>" for i in ids)
            return f'<ul class="lista-cambios {clase}">{li}</ul>' if ids else ""
        items.append(f"""<section class="cambio"><h2>{E(c['fecha'])}</h2><p class="mini">Corte normograma: {E(c.get('corte',''))}</p>
{'<h3>Nuevos</h3>' + lista(c.get('nuevos', []), 'nuevos') if c.get('nuevos') else ''}
{'<h3>Modificados (texto o desplegables)</h3>' + lista(c.get('modificados', []), 'mod') if c.get('modificados') else ''}
{'<h3>Retirados de la compilación</h3>' + lista(c.get('eliminados', []), 'elim') if c.get('eliminados') else ''}
{f"<p>Doctrina DIAN: {miles(c['doctrina_nuevos'])} conceptos u oficios nuevos incorporados.</p>" if c.get('doctrina_nuevos') else ''}
{f"<p>Consejo de Estado: {miles(c['jurisprudencia_nuevas'])} sentencias nuevas de la Sección Cuarta incorporadas.</p>" if c.get('jurisprudencia_nuevas') else ''}{f"<p>CTCP: {miles(c['ctcp_nuevos'])} conceptos nuevos del Consejo Técnico de la Contaduría Pública revisados.</p>" if c.get('ctcp_nuevos') else ''}</section>""")
    nov = f"""<article class="articulo"><header class="art-cab"><p class="art-num">Bitácora</p><h1>Novedades</h1></header>
<p class="bajada">Cada vez que el normograma DIAN publica una nueva versión del Estatuto, del Decreto 1625 o de la Resolución 227, el sitio se regenera y aquí queda el registro de los artículos que cambiaron.</p>
{''.join(items) or '<p>Aún no se han detectado cambios desde la publicación inicial.</p>'}</article>"""
    (SITE / "novedades.html").write_text(pagina(f"Novedades | {MARCA}", "Registro de artículos del Estatuto Tributario, el DUR 1625 y la Resolución 227 modificados según el normograma DIAN.",
                                                nov, "", BASE_URL + "novedades.html", meta=meta), encoding="utf-8")

    # ---- páginas de sentencias (relatoría tradicional): ficha + texto completo
    paginas_s = []
    if JUR:
        (SITE / "sentencias").mkdir(parents=True, exist_ok=True)
        for sid, f in JUR.items():
            if not f.get("nr"):
                continue
            (SITE / pagina_sentencia(f)).write_text(html_sentencia(sid, f, meta), encoding="utf-8")
            paginas_s.append(pagina_sentencia(f))

    # ---- sitemap / robots
    hoy = datetime.now(timezone.utc).date().isoformat()
    urls = [BASE_URL] + [f"{BASE_URL}{ruta(i)}" for i in ARTS] + [BASE_URL + x for x in paginas_s]
    (SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                      + "".join(f"<url><loc>{u}</loc><lastmod>{hoy}</lastmod></url>" for u in urls) + "</urlset>", encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}sitemap.xml\n")
    print(f"Sitio generado en {SITE}: " + ", ".join(f"{len(DOCS[d]['articulos'])} {DOCINFO[d]['corto']}" for d in DOCINFO) + f", {n_rel} concordancias")


if __name__ == "__main__":
    main()
