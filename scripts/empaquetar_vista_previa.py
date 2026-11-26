"""
Empaqueta site/ en una vista previa compacta (pocos archivos) para publicarla como artifact de Claude:
los artículos del ET y del DUR se agrupan en paquetes JSON y una sola página articulo.html
los muestra según #<id> (art-240, dur-1.2.1.5.3.4).
Uso: python scripts/empaquetar_vista_previa.py [carpeta_salida]
"""
import json
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from documentos import DOCUMENTOS  # noqa: E402
SITE = RAIZ / "site"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "vista_previa"
TAM_PAQUETE = 2_400_000
RECORTE = int(__import__("os").environ.get("RECORTE_SENTENCIAS", "0"))
DIRS = {v["dir"]: v["prefijo"] for v in DOCUMENTOS.values()}
CLAVE_DIR = {v["dir"]: k for k, v in DOCUMENTOS.items()}


NR_ID = {}


def enlaces(h: str) -> str:
    h = h.replace('href="../index.html?ver=', 'href="index.html?ver=')
    h = re.sub(r'href="(?:\.\./)?sentencias/(\d+)\.html"', lambda m: f'href="articulo.html#{NR_ID.get(m.group(1), "")}"', h)
    return re.sub(r'href="(?:\.\./)?(' + "|".join(DIRS) + r')/([^"?#]+)\.html(?:\?[^"]*)?"',
                  lambda m: f'href="articulo.html#{DIRS[m.group(1)]}{m.group(2)}"', h)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "paquetes").mkdir(parents=True)
    shutil.copytree(SITE / "assets", OUT / "assets")
    shutil.copytree(SITE / "data", OUT / "data")
    for f in ["index.html", "disposiciones-finales.html", "novedades.html"] + [v["pre"] for v in DOCUMENTOS.values()]:
        h = enlaces((SITE / f).read_text(encoding="utf-8")).replace('<body class="', '<body data-preview="1" class="')
        (OUT / f).write_text(h, encoding="utf-8")

    for f in (SITE / "sentencias").glob("*.html") if (SITE / "sentencias").exists() else []:
        m = re.search(r'<article class="articulo[^"]*" data-id="([^"]+)"', f.read_text(encoding="utf-8")[:20000])
        if m:
            NR_ID[f.stem] = m.group(1)
    mapa, paquete, tam, n = {}, {}, 0, 0

    def volcar():
        nonlocal paquete, tam, n
        if paquete:
            (OUT / "paquetes" / f"p{n}.json").write_text(json.dumps(paquete, ensure_ascii=False), encoding="utf-8")
            n += 1
            paquete, tam = {}, 0

    for carpeta, pref in DIRS.items():
        orden = [x[0] for x in json.loads((SITE / "data" / f"busqueda-{CLAVE_DIR[carpeta]}.json").read_text(encoding="utf-8"))]
        for aid in orden:
            h = (SITE / carpeta / f"{aid[len(pref):]}.html").read_text(encoding="utf-8")
            titulo = re.search(r"<title>(.*?)</title>", h, re.S).group(1)
            cuerpo = re.search(r'(<article class="articulo[^"]*".*?</article>)', h, re.S).group(1)
            cuerpo = re.sub(r'href="([^"/#:?]+)\.html"', lambda m: f'href="articulo.html#{pref}{m.group(1)}"', cuerpo)  # paginación
            cuerpo = enlaces(cuerpo).replace('href="../', 'href="').replace('src="../', 'src="')
            paquete[aid] = [titulo, cuerpo]
            mapa[aid] = n
            tam += len(cuerpo)
            if tam > TAM_PAQUETE:
                volcar()
        volcar()
    for nr, sid in sorted(NR_ID.items()):
        h = (SITE / "sentencias" / f"{nr}.html").read_text(encoding="utf-8")
        titulo = re.search(r"<title>(.*?)</title>", h, re.S).group(1)
        cuerpo = re.search(r'(<article class="articulo.*?</article>)', h, re.S).group(1)
        cuerpo = enlaces(cuerpo).replace('href="../index.html"', 'href="index.html"').replace('href="../', 'href="')
        if RECORTE:   # la vista previa (artifact) tiene un tope de 256 MiB: texto recortado
            m = re.search(r'(<section class="texto-sentencia"[^>]*>\s*<h2>[^<]*</h2>)(.*?)(</section>)', cuerpo, re.S)
            if m and len(m.group(2)) > RECORTE:
                corte = m.group(2).rfind("</p>", 0, RECORTE)
                corte = corte + 4 if corte > 0 else RECORTE
                nota = ('<p class="ayuda"><b>Vista previa:</b> se muestra el comienzo de la sentencia. En el sitio publicado '
                        '(estatuto.tribudata.co) aparece el texto completo.</p>')
                cuerpo = cuerpo[:m.start(2)] + m.group(2)[:corte] + nota + cuerpo[m.end(2):]
        paquete[sid] = [titulo, cuerpo]
        mapa[sid] = n
        tam += len(cuerpo)
        if tam > TAM_PAQUETE:
            volcar()
    volcar()
    (OUT / "data" / "mapa-vista.json").write_text(json.dumps(mapa, separators=(",", ":")), encoding="utf-8")

    molde = (SITE / "articulos" / "1.html").read_text(encoding="utf-8")
    molde = molde.replace('href="../', 'href="').replace('src="../', 'src="').replace('action="../', 'action="')
    molde = molde.replace('data-prefijo="../"', 'data-prefijo="" data-preview="1"')
    molde = re.sub(r'<article class="articulo[^"]*".*?</article>', '<p class="cargando">Cargando artículo…</p>', molde, flags=re.S)
    molde = re.sub(r'<script type="application/ld\+json">.*?</script>', "", molde, flags=re.S)
    molde = molde.replace('<script src="assets/app.js" defer></script>', """<script>
(function () {
  var id = decodeURIComponent((location.hash || "#art-1").slice(1));
  var D = window.ETC_DOCS, doc = "et";
  Object.keys(D).forEach(function (k) { if (id.indexOf(D[k].prefijo) === 0) doc = k; });
  document.body.setAttribute("data-doc", doc);
  if (doc === "jur") document.body.classList.add("pag-sentencia");
  var cab = document.querySelector(".lateral-cab span"); if (cab) cab.textContent = D[doc].nombre;
  fetch("data/mapa-vista.json").then(function (r) { return r.json(); }).then(function (m) {
    if (!(id in m)) id = "art-1";
    return fetch("paquetes/p" + m[id] + ".json").then(function (r) { return r.json(); });
  }).then(function (p) {
    document.title = p[id][0];
    document.getElementById("contenido").innerHTML = p[id][1];
    var s = document.createElement("script"); s.src = "assets/app.js"; document.body.appendChild(s);
    window.scrollTo(0, 0);
  });
  window.addEventListener("hashchange", function () { if (location.hash.length > 1 && location.hash !== "#contenido") location.reload(); });
})();
</script>""")
    (OUT / "articulo.html").write_text(molde, encoding="utf-8")
    archivos = [p for p in OUT.rglob("*") if p.is_file()]
    print(f"Vista previa: {len(archivos)} archivos, {n} paquetes -> {OUT}")


if __name__ == "__main__":
    main()
