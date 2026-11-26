/* Estatuto Tributario concordado — Tribudata.co
   Búsqueda en vivo (ET + DUR 1625), vista rápida de concordancias, índice lateral, filtros y resaltado.
   Sin dependencias. */
(function () {
  "use strict";
  var P = document.body.getAttribute("data-prefijo") || "";
  var DOC = document.body.getAttribute("data-doc") || "et";
  var PREVIEW = document.body.getAttribute("data-preview") === "1";
  var DOCS = window.ETC_DOCS || { et: { prefijo: "art-", dir: "articulos", corto: "ET", nombre: "Estatuto Tributario" } };
  var CLAVES = Object.keys(DOCS);
  var NOMBRE = {}, CORTO = {};
  CLAVES.forEach(function (k) { NOMBRE[k] = DOCS[k].nombre; CORTO[k] = DOCS[k].corto; });
  var LETRA = /[a-z0-9ñ]/;
  var STOP = ["de", "la", "el", "los", "las", "del", "en", "y", "o", "a", "por", "para", "con", "que", "se", "un", "una", "al", "lo", "su", "sus"];
  var guardar = function (k, v) { try { localStorage.setItem("etc_" + k, JSON.stringify(v)); } catch (e) {} };
  var leer = function (k, d) { try { var v = localStorage.getItem("etc_" + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } };
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var norm = function (s) { return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var docDe = function (id) { for (var i = 0; i < CLAVES.length; i++) if (id.indexOf(DOCS[CLAVES[i]].prefijo) === 0) return CLAVES[i]; return "et"; };
  var FICHAS = { doc: 1, jur: 1, ctcp: 1 };
  var SAMAI = "https://samai.consejodeestado.gov.co/TitulacionRelatoria/ResultadoBuscadorProvidenciasTituladas.aspx?BusquedaDictionary=";
  var RELAT = "https://servicios.consejodeestado.gov.co/WebRelatoria/FileReferenceServlet?corp=ce&ext=html&file=";
  var urlSamai = function (rad) {
    return SAMAI + encodeURIComponent(JSON.stringify({ corporacion: "1100103", modo: "2", filtro: "", busqueda: rad, searchMode: "all", orderby: "FechaProvidencia desc", PaginaActual: "0" }));
  };
  var urlJur = function (id) {
    var m = id.match(/^s-r(\d+)-/); if (m) return PREVIEW ? "articulo.html#" + encodeURIComponent(id) : P + "sentencias/" + m[1] + ".html";
    m = id.match(/^s-(\d+)-/); return m ? urlSamai(m[1]) : "#";
  };
  var urlArt = function (id) {
    if (id.indexOf("s-") === 0) return urlJur(id);
    if (id.indexOf("t-") === 0) return urlVer(id);
    var d0 = DOCS[docDe(id)];
    if (d0 && d0.externo) return d0.externo + id.slice(d0.prefijo.length) + ".htm";
    if (PREVIEW) return "articulo.html#" + encodeURIComponent(id);
    var d = DOCS[docDe(id)];
    return P + d.dir + "/" + encodeURIComponent(id.slice(d.prefijo.length)) + ".html";
  };
  /* vista rápida enlazable: index.html?ver=<id> (URL interna; el texto completo externo va aparte) */
  var urlVer = function (id) { return (PREVIEW ? "" : P) + "index.html?ver=" + encodeURIComponent(id); };
  var rotulo = function (num, doc) { return FICHAS[doc] || /^anexo/i.test(num) ? num : "Art. " + num; };
  var esDoc = function (id) { return id.indexOf("c-") === 0 || id.indexOf("s-") === 0 || id.indexOf("t-") === 0; };
  var anioDe = function (id) { if (id.indexOf("t-") === 0) { var t = id.match(/^t-(\d{4})-/); return t ? t[1] : null; } var m = id.indexOf("s-") === 0 ? id.match(/-(\d{4})\d{4}$/) : id.match(/_(\d{4})[a-z]?$/); return m ? m[1] : null; };
  var cache = {};
  function json(ruta) {
    if (!cache[ruta]) cache[ruta] = fetch(P + ruta).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
    return cache[ruta];
  }
  function toast(t) {
    var d = document.createElement("div"); d.className = "toast"; d.textContent = t; document.body.appendChild(d);
    setTimeout(function () { d.remove(); }, 1800);
  }
  var params = new URLSearchParams(location.search);

  /* ================= menú móvil y derogados ================= */
  /* modo claro / oscuro (el tema inicial lo fija el <head> antes de pintar) */
  var raizDoc = document.documentElement;
  function aplicarTema(t) {
    raizDoc.setAttribute("data-tema", t);
    $$(".btn-tema").forEach(function (b) { b.setAttribute("aria-pressed", t === "oscuro" ? "true" : "false"); });
  }
  aplicarTema(raizDoc.getAttribute("data-tema") === "oscuro" ? "oscuro" : "claro");
  $$(".btn-tema").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = raizDoc.getAttribute("data-tema") === "oscuro" ? "claro" : "oscuro";
      raizDoc.classList.add("cambiando-tema"); aplicarTema(t); guardar("tema", t);
      setTimeout(function () { raizDoc.classList.remove("cambiando-tema"); }, 260);
    });
  });
  /* modo oscuro por defecto; el botón guarda la elección de cada visitante */

  /* tres barras: en pantallas anchas con índice fijo lo oculta o lo muestra; en el resto abre el índice como panel */
  var bm = $(".btn-menu"), B = document.body;
  var indiceFijo = function () { return window.innerWidth > 980 && !B.classList.contains("pag-portada") && !B.classList.contains("pag-sentencia"); };
  function cerrarMenu() { B.classList.remove("menu-abierto"); if (bm) bm.setAttribute("aria-expanded", "false"); }
  if (bm) {
    bm.setAttribute("aria-expanded", indiceFijo() ? "true" : "false");
    bm.addEventListener("click", function (e) {
      e.stopPropagation();
      if (indiceFijo()) {
        var oculto = B.classList.toggle("indice-oculto");
        bm.setAttribute("aria-expanded", oculto ? "false" : "true");
        bm.setAttribute("aria-label", oculto ? "Mostrar índice" : "Ocultar índice");
        guardar("indiceOculto", oculto);
      } else {
        var abierto = B.classList.toggle("menu-abierto");
        bm.setAttribute("aria-expanded", abierto ? "true" : "false");
        if (abierto) { var f = $(".lateral .filtro-indice"); if (f && window.innerWidth > 980) setTimeout(function () { f.focus(); }, 60); }
      }
    });
    if (indiceFijo() && leer("indiceOculto", false)) { B.classList.add("indice-oculto"); bm.setAttribute("aria-expanded", "false"); bm.setAttribute("aria-label", "Mostrar índice"); }
    document.addEventListener("click", function (e) {
      if (B.classList.contains("menu-abierto") && !e.target.closest(".lateral") && !e.target.closest(".btn-menu")) cerrarMenu();
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && B.classList.contains("menu-abierto")) cerrarMenu(); });
  }
  var chkDer = $("#ocultar-derogados");
  function aplicarDerogados(v) { document.body.classList.toggle("ocultar-derogados", !!v); if (chkDer) chkDer.checked = !!v; }
  aplicarDerogados(leer("ocultarDerogados", false));
  if (chkDer) chkDer.addEventListener("change", function () { guardar("ocultarDerogados", chkDer.checked); aplicarDerogados(chkDer.checked); });

  /* ================= árbol lateral ================= */
  var art = $(".articulo[data-id]");
  var actual = art ? art.getAttribute("data-id") : null;
  var contArbol = $("#arbol");
  function pintarArbol(nodos, ruta) {
    var h = "<ul>";
    nodos.forEach(function (n) {
      if (Array.isArray(n)) {
        h += '<li class="' + (n[3] ? "derogado" : "") + '"><a href="' + urlArt(n[0]) + '"' +
          (n[0] === actual ? ' class="actual" aria-current="page"' : "") + "><b>" + esc(n[1]) + "</b> " + esc(n[2]) + "</a></li>";
      } else {
        h += '<li class="n' + n.n + '"><details' + (ruta[n.i] ? " open" : "") + "><summary>" + esc(n.t) + "</summary>" + pintarArbol(n.h, ruta) + "</details></li>";
      }
    });
    return h + "</ul>";
  }
  function rutaDe(nodos, id, acc) {
    for (var i = 0; i < nodos.length; i++) {
      var n = nodos[i];
      if (Array.isArray(n)) { if (n[0] === id) return acc; }
      else { acc[n.i] = 1; var r = rutaDe(n.h, id, acc); if (r) return r; delete acc[n.i]; }
    }
    return null;
  }
  var arbolCargado = null;
  function cargarArbol(doc) {
    if (!contArbol || arbolCargado === doc) return;
    arbolCargado = doc;
    var cab = $(".lateral-cab > span"); if (cab && DOCS[doc]) cab.textContent = DOCS[doc].nombre;
    contArbol.innerHTML = '<p class="cargando">Cargando índice…</p>';
    json("data/arbol-" + doc + ".json").then(function (arbol) {
      contArbol.innerHTML = pintarArbol(arbol, (actual && rutaDe(arbol, actual, {})) || {});
      var a = $("a.actual", contArbol);
      if (a) a.scrollIntoView({ block: "center" });
      var f = $(".lateral .filtro-indice"); if (f && f.value.trim()) filtrarIndice(f);
    }).catch(function () { arbolCargado = null; contArbol.innerHTML = '<p class="cargando">No se pudo cargar el índice. <a href="' + P + 'index.html">Ver el índice en el inicio</a></p>'; });
  }
  if (contArbol && !document.body.classList.contains("pag-portada") && !document.body.classList.contains("pag-sentencia")) cargarArbol(DOCS[DOC] && DOCS[DOC].dir ? DOC : "et");
  // en la portada el índice lateral (menú móvil) se carga al abrir el menú, con el documento de la pestaña activa
  if (bm && document.body.classList.contains("pag-portada")) bm.addEventListener("click", function () {
    var t = $(".pestana.activa"); cargarArbol(t ? t.getAttribute("data-tab") : "et");
  });
  if (bm && document.body.classList.contains("pag-sentencia")) bm.addEventListener("click", function () { cargarArbol("et"); });

  /* ================= buscador dentro del índice ================= */
  function filtrarIndice(input) {
    var cont = $(input.getAttribute("data-arbol")); if (!cont) return;
    var salida = input.parentNode.querySelector(".filtro-cuenta");
    var q = input.value.trim();
    var detalles = $$("details", cont);
    if (!q) {
      $$("li", cont).forEach(function (li) { li.classList.remove("fi-oculto", "fi-ok"); });
      detalles.forEach(function (d) { if (d.hasAttribute("data-fi")) { d.open = d.getAttribute("data-fi") === "1"; d.removeAttribute("data-fi"); } });
      if (salida) salida.textContent = "";
      return;
    }
    detalles.forEach(function (d) { if (!d.hasAttribute("data-fi")) d.setAttribute("data-fi", d.open ? "1" : "0"); });
    var mn = q.match(/^(?:art(?:[ií]culo|\.)?\s*)?(\d+(?:[.\-]\d+)*(?:-?[a-z])?)$/i);
    var num = mn ? norm(mn[1]) : null, T = terminos(q).todos, n = 0;
    var coincide = function (txt) { txt = norm(txt); return T.length > 0 && T.every(function (w) { return idx(txt, w) > -1; }); };
    var lis = $$("li", cont).reverse();
    lis.forEach(function (li) {
      var d = li.querySelector(":scope > details");
      if (!d) {
        var a = li.querySelector("a"), b = a && a.querySelector("b");
        var nb = b ? norm(b.textContent.trim()).replace(/^art\.?\s*/, "") : "";
        var ok = num ? (nb === num || nb.indexOf(num + "-") === 0 || nb.indexOf(num + ".") === 0) : coincide(a ? a.textContent : li.textContent);
        li.classList.toggle("fi-oculto", !ok); li.classList.toggle("fi-ok", ok); if (ok) n++;
      } else {
        var propio = !num && coincide(d.querySelector(":scope > summary").textContent);
        var hijos = $$(":scope > ul > li", d).some(function (x) { return !x.classList.contains("fi-oculto"); });
        if (propio) $$("li", d).forEach(function (x) { if (x.classList.contains("fi-oculto")) { x.classList.remove("fi-oculto"); x.setAttribute("data-fi-sub", ""); } });
        li.classList.toggle("fi-oculto", !(propio || hijos));
        d.open = hijos;
      }
    });
    if (salida) salida.textContent = n ? n.toLocaleString("es-CO") + (n === 1 ? " artículo" : " artículos") : "Sin coincidencias en el índice";
  }
  $$(".filtro-indice").forEach(function (inp) {
    var t; inp.addEventListener("input", function () { clearTimeout(t); t = setTimeout(function () { filtrarIndice(inp); }, 140); });
    inp.addEventListener("keydown", function (e) { if (e.key === "Escape") { inp.value = ""; filtrarIndice(inp); } });
  });

  /* ================= herramientas del artículo ================= */
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-accion]");
    if (!b) return;
    var acc = b.getAttribute("data-accion");
    if (acc === "expandir" || acc === "contraer") {
      $$(".principal details.desp").forEach(function (d) { if (!d.classList.contains("oculto-filtro")) d.open = acc === "expandir"; });
    } else if (acc === "copiar") {
      var url = location.href.split("?")[0].split("#")[0];
      (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () { toast("Enlace copiado"); }, function () { toast(url); });
    } else if (acc === "expandir-indice") {
      var abrir = b.textContent.indexOf("Expandir") === 0;
      $$("details", b.closest(".indice-doc")).forEach(function (d) { d.open = abrir; });
      b.textContent = abrir ? "Contraer todo" : "Expandir todo";
    }
  });
  var filtrosOff = leer("filtrosOff", {});
  function aplicarFiltros() {
    $$(".principal details.desp").forEach(function (d) { d.classList.toggle("oculto-filtro", !!filtrosOff[d.getAttribute("data-tipo")]); });
    $$("[data-filtro]").forEach(function (c) { c.checked = !filtrosOff[c.getAttribute("data-filtro")]; });
    $$(".toc li").forEach(function (li) { var a = li.querySelector("a"), t = a && a.className.match(/toc-(\w+)/); li.hidden = !!(t && filtrosOff[t[1]]); });
  }
  $$("[data-filtro]").forEach(function (c) {
    c.addEventListener("change", function () { filtrosOff[c.getAttribute("data-filtro")] = !c.checked; guardar("filtrosOff", filtrosOff); aplicarFiltros(); });
  });
  aplicarFiltros();

  /* ================= resaltado (?r=términos) ================= */
  function terminos(q) {
    var frases = [], resto = q.replace(/"([^"]+)"/g, function (_, f) { frases.push(norm(f.trim())); return " "; });
    var pal = norm(resto).split(/[^a-z0-9ñ.\-]+/).map(function (w) { return w.replace(/^[.\-]+|[.\-]+$/g, ""); })
      .filter(function (w) { return w.length > 1 && STOP.indexOf(w) < 0; });
    return { frases: frases, palabras: pal, todos: frases.concat(pal), literal: norm(resto).replace(/[^a-z0-9ñ.\-]+/g, " ").trim() };
  }
  function resaltar(raiz, terms) {
    terms = terms.filter(function (t) { return t.length > 2; });
    if (!terms.length) return;
    var walker = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, null), nodos = [], n, primero = null;
    while ((n = walker.nextNode())) nodos.push(n);
    nodos.forEach(function (nodo) {
      var t = nodo.nodeValue, nt = norm(t), cortes = [];
      terms.forEach(function (q) { var i = idx(nt, q); while (i > -1) { cortes.push([i, i + q.length]); i = idx(nt, q, i + q.length); } });
      if (!cortes.length || nt.length !== t.length) return;
      cortes.sort(function (a, b) { return a[0] - b[0]; });
      var frag = document.createDocumentFragment(), pos = 0;
      cortes.forEach(function (c) {
        if (c[0] < pos) return;
        frag.appendChild(document.createTextNode(t.slice(pos, c[0])));
        var m = document.createElement("mark"); m.textContent = t.slice(c[0], c[1]); frag.appendChild(m);
        if (!primero) primero = m;
        pos = c[1];
      });
      frag.appendChild(document.createTextNode(t.slice(pos)));
      nodo.parentNode.replaceChild(frag, nodo);
    });
    /* la reglamentación (DUR 1625 / Res. 227) y las listas de doctrina y sentencias se quedan plegadas */
    $$("mark", raiz).forEach(function (m) { var d = m.closest("details"); if (d && !d.closest(".desp-concordia,.desp-doctrinadian,.desp-jurce,.desp-ctcp")) d.open = true; });
    var visible = $$("mark", raiz).filter(function (m) { return !m.closest(".desp-concordia,.desp-doctrinadian,.desp-jurce,.desp-ctcp"); });
    primero = visible[0] || null;
    if (primero) setTimeout(function () { primero.scrollIntoView({ block: "center" }); }, 60);
  }
  if (params.get("r") && $(".cuerpo-norma")) resaltar($(".cuerpo-norma"), terminos(params.get("r")).todos);

  /* ================= vista rápida (concordancias sin salir de la página) ================= */
  var vista = null, pila = [];
  function crearVista() {
    if (vista) return vista;
    var velo = document.createElement("div"); velo.className = "vista-velo"; velo.hidden = true;
    vista = document.createElement("aside");
    vista.className = "vista"; vista.setAttribute("role", "dialog"); vista.setAttribute("aria-modal", "false"); vista.setAttribute("aria-label", "Vista rápida del artículo");
    vista.innerHTML = '<div class="vista-cab"><button type="button" class="vista-atras" aria-label="Volver" hidden>←</button>' +
      '<span class="vista-doc"></span><div class="vista-acc"><button type="button" class="btn btn-sec btn-fav vista-fav" data-fav=""></button>' +
      '<button type="button" class="btn btn-sec vista-cita" title="Copiar la cita en formato jurídico">Cita</button><a class="btn btn-sec vista-nueva" target="_blank" rel="noopener">Pestaña nueva ↗</a>' +
      '<a class="btn vista-ir">Ir al artículo</a><button type="button" class="vista-cerrar" aria-label="Cerrar">×</button></div></div>' +
      '<div class="vista-cuerpo" tabindex="-1"></div>';
    document.body.appendChild(velo); document.body.appendChild(vista);
    velo.addEventListener("click", cerrarVista);
    $(".vista-cerrar", vista).addEventListener("click", cerrarVista);
    $(".vista-fav", vista).addEventListener("click", function () {
      var id = pila[pila.length - 1], a = $(".vista-cuerpo article", vista);
      var t = a ? ((($(".art-num", a) || {}).textContent || "").replace(/\s+/g, " ").trim() + " — " + ((($("h1", a) || {}).textContent) || "").trim()) : id;
      toast(alternarFav(id, t) ? "Guardado en este navegador" : "Quitado de guardados");
    });
    $(".vista-cita", vista).addEventListener("click", function () { copiar(citaDe(pila[pila.length - 1], $(".vista-cuerpo article", vista)), "Cita copiada"); });
    $(".vista-atras", vista).addEventListener("click", function () { pila.pop(); var id = pila.pop(); if (id) abrirVista(id); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && document.body.classList.contains("vista-abierta")) cerrarVista(); });
    return vista;
  }
  function cerrarVista() {
    document.body.classList.remove("vista-abierta");
    if (vista) { vista.previousSibling.hidden = true; }
    pila = [];
    /* devuelve el foco a donde estaba (p. ej. el buscador, que vuelve a mostrar sus sugerencias) */
    if (focoPrevio && document.contains(focoPrevio) && focoPrevio.focus) { try { focoPrevio.focus({ preventScroll: true }); } catch (e) {} }
    focoPrevio = null;
    if (params.get("ver")) { params.delete("ver"); var qs = params.toString(); history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash); }
  }
  function fichaConcepto(id) {
    var anio = anioDe(id);
    var p = anio ? Promise.resolve(anio) : cargarIndice().then(function () {
      for (var i = 0; i < datos.length; i++) if (datos[i].id === id) return datos[i].anio || "0";
      return "0";
    });
    return p.then(function (a) { return json("data/doctrina/" + a + ".json"); }).then(function (d) {
      var c = d[id]; if (!c) throw new Error("sin ficha");
      var url = urlArt(id);
      var sec = function (t, v) { return v ? '<h3 class="c-sub">' + t + '</h3><p class="c-txt">' + esc(v) + "</p>" : ""; };
      var chips = (c.cat || []).concat(c.cl ? [c.cl] : []).concat(c.b ? [c.b] : []).map(function (x) { return '<span class="chip-c">' + esc(x) + "</span>"; }).join("");
      var citas = (c.c || []).map(function (x) {
        return '<li><a class="ref" data-ref="' + x[0] + '" href="' + urlArt(x[0]) + '"><span class="badge badge-' + docDe(x[0]) + '">' + esc(CORTO[docDe(x[0])]) + " " + esc(x[1]) + "</span> " + esc(x[2]) + "</a></li>";
      }).join("");
      return '<article class="articulo concepto" data-id="' + id + '"><header class="art-cab"><p class="art-num"><span class="badge badge-doc">Doctrina DIAN</span> ' +
        esc(c.r) + (c.f ? " · " + esc(c.f) : "") + chipEstado(c.e) + "</p><h1>" + esc(c.t || c.r) + "</h1></header>" +
        (chips ? '<p class="chips-c">' + chips + "</p>" : "") + (c.n ? '<p class="nota-c">' + esc(c.n) + "</p>" : "") +
        sec("Problema jurídico", c.p) + sec("Tesis jurídica", c.te) + sec("Descriptores", c.d) + sec("Fuentes formales", c.fu) +
        sec("Extracto", c.x ? c.x + (c.x.length >= 1200 ? " …" : "") : "") +
        (citas ? '<h3 class="c-sub">Normas que cita (enlazadas en este sitio)</h3><ul class="lista-concordia">' + citas + "</ul>" : "") +
        '<p class="c-pie"><a class="btn" href="' + url + '" target="_blank" rel="noopener">Leer el texto completo en el normograma DIAN ↗</a></p></article>';
    });
  }
  function fichaSentencia(id) {
    var anio = anioDe(id) || "0";
    return json("data/jurisprudencia/" + anio + ".json").then(function (d) {
      var c = d[id]; if (!c) throw new Error("sin ficha");
      var sec = function (t, v) { return v ? '<h3 class="c-sub">' + t + '</h3><p class="c-txt">' + esc(v) + "</p>" : ""; };
      var chips = [c.ti && c.ti !== "Sentencia" ? c.ti : "", c.cl].filter(Boolean).map(function (x) { return '<span class="chip-c">' + esc(x) + "</span>"; }).join("") + chipEstado(c.e || c.dc);
      var dato = function (k, v) { return v ? "<dt>" + k + "</dt><dd>" + esc(v) + "</dd>" : ""; };
      var probs = (c.pr || []).map(function (x) {
        var corta = x[1] || "", larga = x[2] || "", r = "";
        if (larga) r = '<details class="pj-det"><summary class="pj-r">Respuesta: <b>' + esc(corta || "ver") + '</b><span class="pj-mas" aria-hidden="true"></span><span class="sr">Ver la respuesta desarrollada</span></summary><p class="pj-tesis">' + esc(larga) + (larga.length >= 1800 ? " …" : "") + "</p></details>";
        else if (corta) r = '<p class="pj-r">Respuesta: <b>' + esc(corta) + "</b></p>";
        return '<li><p class="pj">' + esc(x[0]) + "</p>" + r + "</li>";
      }).join("");
      var citas = (c.c || []).map(function (x) {
        return '<li><a class="ref" data-ref="' + x[0] + '" href="' + urlArt(x[0]) + '"><span class="badge badge-' + docDe(x[0]) + '">' + esc(CORTO[docDe(x[0])]) + " " + esc(x[1]) + "</span> " + esc(x[2]) + "</a></li>";
      }).join("");
      var botones = (c.u ? '<a class="btn" href="' + (PREVIEW ? "articulo.html#" + encodeURIComponent(id) : P + c.u) + '" target="_blank" rel="noopener">Texto completo de la sentencia ↗</a> ' : "") +
        (c.us ? '<a class="btn btn-sec" href="' + c.us + '" target="_blank" rel="noopener">Ver en SAMAI ↗</a>' : "");
      return '<article class="articulo concepto sentencia" data-id="' + id + '"><header class="art-cab"><p class="art-num"><span class="badge badge-jur">Consejo de Estado</span> ' +
        esc(c.r) + (c.f ? " · " + esc(c.f) : "") + "</p><h1>" + esc(c.t || c.r) + "</h1></header>" +
        (chips ? '<p class="chips-c">' + chips + "</p>" : "") +
        '<dl class="datos-s">' + dato("Providencia del", c.f) + dato("Fecha proceso", c.fq) + dato("Clase del proceso", c.cl) + dato("Sala de decisión", c.sa || "Sección Cuarta") + dato("Sentencia", c.ti || "Sentencia") +
          dato("Ponente", c.po) + dato("Actor", c.ac) + dato("Demandado", c.de) + dato("Radicado", c.ra) + dato("Número interno", c.ni) + dato("Salvamentos y aclaraciones", c.sv) + "</dl>" +
        (probs ? '<h3 class="c-sub">Problema' + ((c.pr || []).length > 1 ? "s" : "") + ' jurídico' + ((c.pr || []).length > 1 ? "s" : "") + '</h3><ol class="lista-pj">' + probs + "</ol>" : "") +
        (c.n ? '<p class="nota-c">' + esc(c.n) + "</p>" : "") +
        sec("Descriptores", c.d) + sec(c.pr && c.pr.length ? "Tesis (extracto de la titulación)" : "Extracto", c.x ? c.x + (c.x.length >= 2500 ? " …" : "") : "") + sec("Fuente formal", c.fu) +
        (citas ? '<h3 class="c-sub">Normas que aplica (enlazadas en este sitio)</h3><ul class="lista-concordia">' + citas + "</ul>" : "") +
        '<p class="c-pie">' + botones + "</p></article>";
    });
  }
  function fichaCtcp(id) {
    return json("data/ctcp/" + (anioDe(id) || "0") + ".json").then(function (d) {
      var c = d[id]; if (!c) throw new Error("sin ficha");
      var sec = function (t, v) { return v ? '<h3 class="c-sub">' + t + '</h3><p class="c-txt">' + esc(v) + "</p>" : ""; };
      var dato = function (k, v) { return v ? "<dt>" + k + "</dt><dd>" + esc(v) + "</dd>" : ""; };
      var citas = (c.c || []).map(function (x) {
        return '<li><a class="ref" data-ref="' + x[0] + '" href="' + urlArt(x[0]) + '"><span class="badge badge-' + docDe(x[0]) + '">' + esc(CORTO[docDe(x[0])]) + " " + esc(x[1]) + "</span> " + esc(x[2]) + "</a></li>";
      }).join("");
      var otras = (c.o || []).map(function (x) { return '<span class="chip-c">' + esc(x) + "</span>"; }).join("");
      return '<article class="articulo concepto concepto-ctcp" data-id="' + id + '" data-externo="' + esc(c.u || "") + '"><header class="art-cab"><p class="art-num"><span class="badge badge-ctcp">CTCP</span> ' +
        esc(c.r) + (c.f ? " · " + esc(c.f) : "") + chipEstado(c.e) + "</p><h1>" + esc(c.t || c.r) + "</h1></header>" +
        '<dl class="datos-s">' + dato("Entidad", "Consejo Técnico de la Contaduría Pública") + dato(c.ti ? "Documento" : "Radicación CTCP", c.ti ? c.ti + " No. " + c.rad.replace(/^DOT\s*/, "") : c.rad) + dato("Fecha", c.f) + dato("Consejero ponente", c.po) + "</dl>" +
        sec("Resumen", c.rs) + sec("Consulta", c.cs) + sec(c.ti ? "Introducción (extracto)" : "Respuesta del CTCP (extracto)", c.x) +
        (citas ? '<h3 class="c-sub">Normas tributarias que cita (enlazadas en este sitio)</h3><ul class="lista-concordia">' + citas + "</ul>" : "") +
        (otras ? '<h3 class="c-sub">Otra normativa concordante</h3><p class="chips-c">' + otras + "</p>" : "") +
        '<p class="c-pie">' + (c.u ? '<a class="btn" href="' + esc(c.u) + '" target="_blank" rel="noopener">Leer el concepto completo en ctcp.gov.co ↗</a>' : "") + "</p></article>";
    });
  }
  function obtenerArticulo(id) {
    if (id.indexOf("t-") === 0) return fichaCtcp(id);
    if (id.indexOf("s-") === 0 && id.indexOf("s-r") !== 0) return fichaSentencia(id);
    if (id.indexOf("c-") === 0) return fichaConcepto(id);
    if (PREVIEW) {
      return json("data/mapa-vista.json").then(function (m) {
        return json("paquetes/p" + m[id] + ".json").then(function (p) { return p[id][1]; });
      });
    }
    return fetch(urlArt(id)).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); }).then(function (t) {
      var d = new DOMParser().parseFromString(t, "text/html");
      var a = d.querySelector("article.articulo");
      return a ? a.outerHTML : "";
    });
  }
  var focoPrevio = null;
  function abrirVista(id) {
    crearVista();
    if (!document.body.classList.contains("vista-abierta")) focoPrevio = document.activeElement;
    pila.push(id);
    var cuerpo = $(".vista-cuerpo", vista);
    $(".vista-doc", vista).innerHTML = '<span class="badge badge-' + docDe(id) + '">' + esc(CORTO[docDe(id)]) + "</span>";
    $(".vista-atras", vista).hidden = pila.length < 2;
    $(".vista-nueva", vista).href = urlArt(id);
    $(".vista-fav", vista).setAttribute("data-fav", id); pintarFav($(".vista-fav", vista));
    $(".vista-ir", vista).href = urlArt(id);
    $(".vista-nueva", vista).hidden = esDoc(id);
    $(".vista-ir", vista).textContent = esDoc(id) ? "Texto completo ↗" : "Ir al artículo";
    if (esDoc(id)) { $(".vista-ir", vista).target = "_blank"; $(".vista-ir", vista).rel = "noopener"; } else { $(".vista-ir", vista).removeAttribute("target"); }
    cuerpo.innerHTML = '<p class="cargando">Cargando artículo…</p>';
    document.body.classList.add("vista-abierta");
    vista.previousSibling.hidden = false;
    obtenerArticulo(id).then(function (html) {
      var tmp = document.createElement("div"); tmp.innerHTML = html;
      var a = tmp.querySelector("article");
      if (!a) throw new Error("vacío");
      $$(".miga, .herramientas, .paginacion", a).forEach(function (x) { x.remove(); });
      $$("details.desp-concordia", a).forEach(function (d) { d.open = false; });
      if (a.getAttribute("data-externo")) $(".vista-ir", vista).href = a.getAttribute("data-externo");
      cuerpo.innerHTML = ""; cuerpo.appendChild(a); cuerpo.scrollTop = 0; cuerpo.focus({ preventScroll: true });
    }).catch(function () {
      cuerpo.innerHTML = '<p>No se pudo cargar la vista rápida. <a href="' + urlArt(id) + '">Abrir el artículo</a></p>';
    });
  }
  /* fase de captura: la vista rápida responde antes que cualquier otro manejador de enlaces */
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a.ref[data-ref]");
    if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault(); e.stopPropagation();
    abrirVista(a.getAttribute("data-ref"));
  }, true);
  if (params.get("ver")) setTimeout(function () { abrirVista(params.get("ver")); }, 0);

  /* ================= motor de búsqueda (ET + DUR) ================= */
  var datos = null, anot = {}, cargandoIdx = null;
  function cargarIndice() {
    if (datos) return Promise.resolve(datos);
    if (cargandoIdx) return cargandoIdx;
    cargandoIdx = Promise.all(CLAVES.map(function (k) { return json("data/busqueda-" + k + ".json").catch(function () { return []; }); })).then(function (r) {
      datos = [];
      CLAVES.forEach(function (doc, k) {
        r[k].forEach(function (x) {
          var e = { doc: doc, id: x[0], num: x[1], epi: x[2], txt: x[3], der: x[4], ub: x[5] || "", est: x[6] || "", k: x[7] || [], nn: norm(x[1]), ne: norm(x[2]), nt: norm(x[3]) };
          if (FICHAS[doc]) { e.cnum = ((x[1].match(/\d+/) || [""])[0]).replace(/^0+/, ""); e.anio = (x[1].match(/(\d{4})\s*$/) || [])[1]; }
          datos.push(e);
        });
      });
      return datos;
    });
    return cargandoIdx;
  }
  function cargarAnot(docs) {
    return Promise.all(docs.map(function (doc) {
      if (anot[doc]) return null;
      return json("data/anotaciones-" + doc + ".json").then(function (d) { anot[doc] = {}; d.forEach(function (x) { anot[doc][x[0]] = { t: x[1], n: norm(x[1]) }; }); });
    }));
  }
  var NUM = /^(?:art(?:iculo|ículo|\.)?\s*)?(\d+(?:\.\d+)*(?:\s*-\s*\d+)*(?:\s*-?\s*[a-z]{1,3})?)\.?$/i;
  /* posición de w en h solo al comienzo de palabra ("iva" no casa con "explicativas") */
  function idx(h, w, d) {
    var i = h.indexOf(w, d || 0);
    while (i > 0 && LETRA.test(h.charAt(i - 1)) && LETRA.test(w.charAt(0))) i = h.indexOf(w, i + 1);
    return i;
  }
  function contar(h, w) { var c = 0, i = idx(h, w); while (i > -1 && c < 30) { c++; i = idx(h, w, i + w.length); } return c; }
  function opciones() {
    var f = $('input[name="fuente"]:checked');
    return { fuente: f ? f.value : "todo", anot: !!($("#en-anotaciones") && $("#en-anotaciones").checked), sinDer: !!($("#sin-derogados") && $("#sin-derogados").checked) };
  }
  function buscar(texto, op) {
    var T = terminos(texto), out = [], m = texto.trim().match(NUM), numB = m ? norm(m[1].replace(/\s+/g, "")) : null;
    datos.forEach(function (a) {
      if (op.fuente !== "todo" && a.doc !== op.fuente) return;
      if (op.sinDer && a.der) return;
      var score = 0, enAnot = false, ok = T.todos.length > 0;
      if (numB && FICHAS[a.doc]) {
        if (a.cnum && a.cnum === numB.replace(/^0+/, "")) score += 5000;
      } else if (numB) {
        if (a.nn === numB) score += 10000;
        else if (a.nn.indexOf(numB + "-") === 0 || a.nn.indexOf(numB + ".") === 0) score += 400 - Math.min(300, a.nn.length * 5);
      }
      var an = op.anot && anot[a.doc] ? anot[a.doc][a.id] : null, enEpi = 0;
      T.todos.forEach(function (w) {
        var e = idx(a.ne, w) > -1, c = contar(a.nt, w), ca = 0;
        if (e) enEpi++;
        if (!e && !c && an) { ca = contar(an.n, w); if (ca) enAnot = true; }
        if (!e && !c && !ca) ok = false;
        score += (e ? 40 : 0) + c * 2 + ca * 0.5;
      });
      if (T.palabras.length > 1) {
        var frase = T.palabras.join(" ");
        if (idx(a.ne, T.literal) > -1) score += 160;
        else if (idx(a.ne, frase) > -1) score += 90; else if (idx(a.nt, T.literal) > -1 || idx(a.nt, frase) > -1) score += 25;
        if (enEpi === T.todos.length) score += 60;  /* todas las palabras en el título */
      }
      if (numB && score >= 100) ok = true;
      if (!ok || score <= 0) return;
      if (a.der) score *= 0.6;
      if (FICHAS[a.doc] && op.fuente === "todo" && score < 5000) score *= 0.55;
      out.push({ a: a, s: score, anot: enAnot });
    });
    out.sort(function (x, y) { return y.s - x.s; });
    return { res: out, T: T };
  }
  function marcar(s, terms) {
    var ns = norm(s), cortes = [];
    terms.forEach(function (w) { if (w.length < 2) return; var i = idx(ns, w); while (i > -1) { cortes.push([i, i + w.length]); i = idx(ns, w, i + w.length); } });
    if (ns.length !== s.length || !cortes.length) return esc(s);
    cortes.sort(function (a, b) { return a[0] - b[0]; });
    var h = "", pos = 0;
    cortes.forEach(function (c) { if (c[0] < pos) return; h += esc(s.slice(pos, c[0])) + "<mark>" + esc(s.slice(c[0], c[1])) + "</mark>"; pos = c[1]; });
    return h + esc(s.slice(pos));
  }
  function fragmento(o, T, largo) {
    var a = o.a, an = o.anot && anot[a.doc] ? anot[a.doc][a.id] : null;
    var src = an ? an.t : a.txt, n = an ? an.n : a.nt, pos = -1;
    for (var i = 0; i < T.todos.length && pos < 0; i++) pos = idx(n, T.todos[i]);
    var ini = Math.max(0, pos - Math.round(largo * 0.4)), fin = Math.min(src.length, Math.max(0, pos) + largo);
    return marcar((ini > 0 ? "… " : "") + src.slice(ini, fin) + (fin < src.length ? " …" : ""), T.todos);
  }
  function enlaceResultado(a, T) {
    if (FICHAS[a.doc]) return urlVer(a.id);
    var rq = T.todos.join(" ");
    return urlArt(a.id) + (!PREVIEW && rq ? "?r=" + encodeURIComponent(rq) : "");
  }

  /* ================= última consulta (para regresar a la búsqueda desde un artículo) ================= */
  function recordarConsulta(t) { try { sessionStorage.setItem("etc_ultima_q", (t || "").trim()); } catch (e) {} }
  function ultimaConsulta() { try { return sessionStorage.getItem("etc_ultima_q") || ""; } catch (e) { return ""; } }

  /* ================= orden fijo por fuente ================= */
  var ORDEN = ["et", "dur", "r227", "doc", "jur", "ctcp"].filter(function (k) { return DOCS[k]; });
  CLAVES.forEach(function (k) { if (ORDEN.indexOf(k) < 0) ORDEN.push(k); });
  function porFuente(res) {
    var g = {};
    res.forEach(function (o) { (g[o.a.doc] = g[o.a.doc] || []).push(o); });
    return ORDEN.filter(function (k) { return g[k]; }).map(function (k) { return { doc: k, items: g[k] }; });
  }
  var PESO = { et: 4, dur: 3, r227: 2, doc: 3, jur: 3, ctcp: 2 };
  var ETQ_SUG = { et: "Estatuto Tributario", dur: "Decreto 1625 de 2016", r227: "Resolución 227 de 2025", doc: "Doctrina DIAN", jur: "Consejo de Estado", ctcp: "Consejo Técnico de la Contaduría Pública" };
  function repartir(tams, pesos, total) {
    /* cupo base por peso (el ET pesa más); lo que no use un grupo pasa a los siguientes, en orden */
    var c = tams.map(function (t, x) { return Math.min(t, pesos[x]); });
    var quedan = total - c.reduce(function (a, b) { return a + b; }, 0);
    for (var x = 0; x < tams.length && quedan > 0; x++) { var d = Math.min(tams[x] - c[x], quedan); c[x] += d; quedan -= d; }
    while (c.reduce(function (a, b) { return a + b; }, 0) > total) { var m = c.indexOf(Math.max.apply(null, c)); c[m]--; }
    return c;
  }
  function unidad(doc, n) {
    if (doc === "doc") return n === 1 ? "concepto u oficio" : "conceptos y oficios";
    if (doc === "jur") return n === 1 ? "sentencia" : "sentencias";
    if (doc === "ctcp") return n === 1 ? "concepto" : "conceptos";
    return n === 1 ? "artículo" : "artículos";
  }

  /* ================= metadatos de cada resultado: ubicación, estado y contadores ================= */
  var miles = function (n) { return Number(n).toLocaleString("es-CO"); };
  function chipEstado(t) {
    if (!t) return "";
    return ' <span class="est est-' + norm(t.split(" ")[0]) + '">' + esc(t) + "</span>";
  }
  function plural(n, s, p) { return miles(n) + " " + (n === 1 ? s : p); }
  function partesMeta(a) {
    var k = a.k || [], out = [];
    if (FICHAS[a.doc]) {
      if (a.ub) out.push(esc(a.ub));
      if (k[0]) out.push(a.doc !== "jur" ? "cita " + plural(k[0], "artículo", "artículos") : "aplica " + plural(k[0], "artículo", "artículos"));
    } else {
      if (a.ub) out.push(esc(a.ub));
      if (k[1]) out.push(plural(k[1], "concepto", "conceptos"));
      if (k[2]) out.push(plural(k[2], "sentencia", "sentencias"));
      if (k[4]) out.push(plural(k[4], "concepto CTCP", "conceptos CTCP"));
    }
    return out;
  }
  function metaLinea(a, cls) {
    var p = partesMeta(a), est = a.est || (a.der ? "Derogado" : "");
    if (!p.length && !est) return "";
    return '<span class="' + cls + '">' + chipEstado(est).trim() + (est && p.length ? " " : "") + p.join('<i class="sep"> · </i>') + "</span>";
  }

  /* ================= sugerencias en vivo bajo el buscador ================= */
  function autocompletar(input, alEnter) {
    var caja = document.createElement("div");
    caja.className = "sugerencias"; caja.id = "sugerencias-" + (input.id || "barra"); caja.setAttribute("role", "listbox"); caja.hidden = true;
    input.setAttribute("aria-controls", caja.id);
    input.parentNode.style.position = "relative";
    input.parentNode.appendChild(caja);
    var sel = -1, ultimo = null, t0;
    function cerrar() { caja.hidden = true; sel = -1; input.setAttribute("aria-expanded", "false"); }
    function pintar(r, texto) {
      ultimo = r;
      var h = "";
      if (!r.res.length) h = '<div class="sug-vacio">Sin coincidencias para «' + esc(texto) + "». Pruebe con menos palabras o active «Incluir notas, concordancias, doctrina y jurisprudencia».</div>";
      /* agrupado por fuente, siempre en este orden y con su subtítulo: ET, DUR 1625, Res. 227, doctrina DIAN, Consejo de Estado.
         Cada fuente con coincidencias tiene su cupo, para que el DUR y la Res. 227 no queden ocultos tras el Estatuto. */
      var grupos = porFuente(r.res), lista = [];
      var cupos = repartir(grupos.map(function (g) { return g.items.length; }), grupos.map(function (g) { return PESO[g.doc] || 2; }), 15 + grupos.reduce(function (n, g) { return g.doc === "ctcp" ? Math.min(PESO.ctcp, g.items.length) : n; }, 0));
      grupos.forEach(function (g, gi) { lista.push(g); lista = lista.concat(g.items.slice(0, cupos[gi])); });
      var i = -1, vistos = lista.filter(function (o) { return !o.items; }).length;
      if (r.res.length) h += '<div class="sug-cab"><span><b>' + miles(vistos) + "</b> de <b>" + miles(r.res.length) + "</b> coincidencia" + (r.res.length === 1 ? "" : "s") + "</span>" +
        '<span class="sug-cab-d">' + grupos.map(function (g) { return CORTO[g.doc] + " " + miles(g.items.length); }).join(" · ") + "</span></div>";
      lista.forEach(function (o) {
        if (o.items) { h += '<div class="sug-sep sug-sep-' + o.doc + '">' + esc(ETQ_SUG[o.doc] || NOMBRE[o.doc]) + " · " + miles(o.items.length) + " " + unidad(o.doc, o.items.length) + "</div>"; return; }
        i++;
        var a = o.a, f = FICHAS[a.doc];
        h += '<a class="sug' + (f ? ' ref" data-ref="' + a.id : "") + '" role="option" id="' + caja.id + "-" + i + '" href="' + enlaceResultado(a, r.T) + '" data-i="' + i + '">' +
          '<span class="sug-t"><span class="badge badge-' + a.doc + '">' + (f ? esc(a.num) : CORTO[a.doc]) + "</span>" + (f ? "" : "<b>" + esc(rotulo(a.num, a.doc)) + "</b> ") + marcar(a.epi, r.T.todos) + "</span>" +
          metaLinea(a, "sug-m") +
          '<span class="sug-s">' + fragmento(o, r.T, 120) + "</span>" +
          '<span class="sug-acc" aria-hidden="true">' + (f ? "Vista rápida" : "Abrir") + "</span></a>";
      });
      h += pie(r.res.length ? '<button type="button" class="sug-todos">Ver los ' + miles(r.res.length) + " resultados</button>" : "");
      caja.innerHTML = h; caja.hidden = false; sel = -1; input.setAttribute("aria-expanded", "true");
      var b = $(".sug-todos", caja); if (b) b.addEventListener("click", function () { cerrar(); alEnter(input.value); });
    }
    function pie(extra) {
      return '<div class="sug-pie"><span class="teclas"><kbd>↑</kbd><kbd>↓</kbd> navegar <kbd>Enter</kbd> abrir <kbd>Esc</kbd> cerrar</span>' + (extra || "") + "</div>";
    }
    /* sugerencias antes de escribir (solo portada): más citados, más modificados, esenciales */
    var DEST = window.ETC_DESTACADOS, GRUPOS_BASE = [["cit", "Más citados"], ["mod", "Más modificados"], ["ese", "Esenciales para estudio"]], GRUPOS = GRUPOS_BASE;
    var grupo = leer("grupo_dest", "cit");
    function pintarDestacados() {
      if (!DEST) { cerrar(); return; }
      var favs = favoritos();
      GRUPOS = favs.length ? GRUPOS_BASE.concat([["fav", "Guardados (" + favs.length + ")"]]) : GRUPOS_BASE;
      DEST.fav = favs.slice(0, 20).map(function (f) { return [f.id, "", f.t, ""]; });
      if (!DEST[grupo] || (grupo === "fav" && !favs.length)) grupo = "cit";
      ultimo = null;
      var h = '<div class="sug-tabs" role="tablist">' + GRUPOS.map(function (g) {
        return '<button type="button" role="tab" class="sug-tab' + (g[0] === grupo ? " activa" : "") + '" aria-selected="' + (g[0] === grupo) + '" data-g="' + g[0] + '">' + g[1] + "</button>";
      }).join("") + "</div>";
      DEST[grupo].forEach(function (x, i) {
        if (grupo === "fav") {
          var dd = docDe(x[0]), f = esDoc(x[0]);
          h += '<a class="sug sug-dest' + (f ? ' ref" data-ref="' + x[0] : "") + '" role="option" id="' + caja.id + "-" + i + '" href="' + (f ? urlVer(x[0]) : urlArt(x[0])) + '" data-i="' + i + '">' +
            '<span class="sug-t"><span class="badge badge-' + dd + '">' + esc(CORTO[dd] || "") + "</span>" + esc(x[2].replace(/^\s*(ET|DUR 1625|Res\. 227|Doctrina DIAN|Consejo de Estado)\s*/, "")) + "</span>" +
            '<span class="sug-acc" aria-hidden="true">' + (f ? "Vista rápida" : "Abrir") + "</span></a>";
          return;
        }
        h += '<a class="sug sug-dest" role="option" id="' + caja.id + "-" + i + '" href="' + urlArt(x[0]) + '" data-i="' + i + '">' +
          '<span class="sug-t"><span class="badge badge-et">ET</span><b>Art. ' + esc(x[1]) + "</b> " + esc(x[2]) + "</span>" +
          '<span class="sug-m">' + esc(x[3]) + "</span>" + '<span class="sug-acc" aria-hidden="true">Abrir</span></a>';
      });
      caja.innerHTML = h + pie('<span class="sug-pista">Escriba un número, concepto o tema</span>');
      caja.hidden = false; sel = -1; input.setAttribute("aria-expanded", "true");
      $$(".sug-tab", caja).forEach(function (b) {
        b.addEventListener("click", function () { grupo = b.getAttribute("data-g"); guardar("grupo_dest", grupo); pintarDestacados(); input.focus(); });
      });
    }
    function actualizar() {
      var texto = input.value.trim();
      if (texto.length < 1) { pintarDestacados(); return; }
      if (!datos) { caja.innerHTML = '<div class="sug-vacio">Cargando índice de búsqueda…</div>'; caja.hidden = false; }
      var op = opciones();
      cargarIndice().then(function () { return op.anot ? cargarAnot(op.fuente === "todo" ? CLAVES : [op.fuente]) : null; })
        .then(function () { if (input.value.trim() === texto) pintar(buscar(texto, op), texto); });
    }
    function mover(d) {
      var items = $$(".sug", caja); if (!items.length) return;
      sel = (sel + d + items.length) % items.length;
      items.forEach(function (x, i) { x.classList.toggle("activa", i === sel); x.setAttribute("aria-selected", i === sel ? "true" : "false"); });
      input.setAttribute("aria-activedescendant", items[sel].id);
      items[sel].scrollIntoView({ block: "nearest" });
    }
    input.addEventListener("input", function () { clearTimeout(t0); t0 = setTimeout(actualizar, 120); recordarConsulta(input.value); });
    input.addEventListener("focus", function () { cargarIndice(); if (input.value.trim() && ultimo) caja.hidden = false; else if (!input.value.trim()) pintarDestacados(); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); if (caja.hidden) actualizar(); else mover(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); mover(-1); }
      else if (e.key === "Escape") { cerrar(); }
      else if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && !input.value && DEST && !caja.hidden) {
        e.preventDefault();
        var gi = GRUPOS.map(function (g) { return g[0]; }).indexOf(grupo);
        grupo = GRUPOS[(gi + (e.key === "ArrowRight" ? 1 : GRUPOS.length - 1)) % GRUPOS.length][0]; guardar("grupo_dest", grupo); pintarDestacados();
      }
      else if (e.key === "Enter") {
        e.preventDefault();
        var items = $$(".sug", caja);
        if (sel > -1 && items[sel]) {
          if (items[sel].getAttribute("data-ref")) { abrirVista(items[sel].getAttribute("data-ref")); return; }
          location.href = items[sel].href; return;
        }
        var m = input.value.trim().match(NUM);
        if (m && ultimo && ultimo.res.length && ultimo.res[0].s >= 10000) { location.href = enlaceResultado(ultimo.res[0].a, ultimo.T); return; }
        cerrar(); alEnter(input.value);
      }
    });
    /* la vista rápida no cierra las sugerencias: al volver de ella siguen a la vista */
    document.addEventListener("click", function (e) {
      if (caja.contains(e.target) || e.target === input || (e.target.closest && e.target.closest(".vista, .vista-velo"))) return;
      cerrar();
    });
    return { actualizar: actualizar, cerrar: cerrar, destacados: pintarDestacados };
  }

  var barra = $(".buscador-barra input");
  if (barra && !document.body.classList.contains("pag-portada")) {
    autocompletar(barra, function (texto) { location.href = P + "index.html?q=" + encodeURIComponent(texto); });
  }

  /* ================= portada: resultados completos, pestañas ================= */
  /* ================= flecha para regresar a la búsqueda (antes del título del artículo) ================= */
  (function () {
    if (document.body.classList.contains("pag-portada")) return;
    var h1 = $("#contenido .art-cab h1");
    if (!h1 || h1.querySelector(".volver-busqueda")) return;
    var uq = ultimaConsulta();
    var rotuloV = uq ? "Volver a los resultados de «" + uq + "»" : "Volver a la búsqueda";
    var a = document.createElement("a");
    a.className = "volver-busqueda";
    a.href = P + "index.html" + (uq ? "?q=" + encodeURIComponent(uq) : "");
    a.title = rotuloV; a.setAttribute("aria-label", rotuloV);
    a.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5.5M11.5 5.5 5 12l6.5 6.5"/></svg>';
    a.addEventListener("click", function (e) {
      /* si se llegó desde la página de resultados, «atrás» la deja tal como estaba (sin presentación) */
      try {
        var r = document.referrer ? new URL(document.referrer) : null;
        var rq = r && r.origin === location.origin ? (new URLSearchParams(r.search).get("q") || "").trim() : "";
        if (rq && rq === uq && history.length > 1) { e.preventDefault(); history.back(); }
      } catch (x) {}
    });
    h1.insertBefore(a, h1.firstChild);
  })();

  /* ================= favoritos, cita jurídica, compartir e imprimir ================= */
  var MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  function favoritos() { var f = leer("fav", []); return Array.isArray(f) ? f : []; }
  function esFav(id) { return favoritos().some(function (x) { return x.id === id; }); }
  function alternarFav(id, titulo) {
    var f = favoritos(), i = -1;
    f.forEach(function (x, k) { if (x.id === id) i = k; });
    if (i > -1) f.splice(i, 1); else f.unshift({ id: id, t: (titulo || "").slice(0, 140), ts: Date.now() });
    guardar("fav", f.slice(0, 200));
    try { document.dispatchEvent(new Event("etc-fav")); } catch (e) {}
    $$("[data-fav]").forEach(function (b) { if (b.getAttribute("data-fav") === id) pintarFav(b); });
    return i < 0;
  }
  function pintarFav(b) {
    var on = esFav(b.getAttribute("data-fav"));
    b.classList.toggle("on", on); b.setAttribute("aria-pressed", on ? "true" : "false");
    b.innerHTML = (on ? "★" : "☆") + '<span class="txt"> ' + (on ? "Guardado" : "Guardar") + "</span>";
    b.title = on ? "Quitar de guardados" : "Guardar en este navegador";
  }
  function titulo(s) { return (s || "").toLowerCase().replace(/(^|[\s(.-])([a-záéíóúñü])/g, function (m, p, c) { return p + c.toUpperCase(); }).replace(/\b(De|Del|La|Las|Los|Y|E)\b/g, function (m) { return m.toLowerCase(); }); }
  function datoS(art, etiqueta) {
    var dt = $$(".datos-s dt", art).filter(function (x) { return x.textContent.trim() === etiqueta; })[0];
    return dt && dt.nextElementSibling ? dt.nextElementSibling.textContent.trim() : "";
  }
  /* cita en el formato usual de los escritos jurídicos colombianos */
  function citaDe(id, art) {
    var d = docDe(id), num = id.replace(/^[a-z0-9]+-/, "");
    if (d === "et") return "Decreto 624 de 1989 (Estatuto Tributario), artículo " + num + ".";
    if (d === "dur") return "Decreto 1625 de 2016 (Decreto Único Reglamentario en Materia Tributaria), artículo " + num + ".";
    if (d === "r227") return "Resolución DIAN 000227 de 2025, artículo " + num + ".";
    var cab = art ? ($(".art-num", art) || {}).textContent || "" : "";
    cab = cab.replace(/^\s*(Doctrina DIAN|Consejo de Estado|CTCP)\s*/, "").replace(/(Revocado|Reconsiderado|Aclarado|Modificado|Suspendido|Accede|Niega|Inhibitorio)( parcialmente)?\s*$/, "").trim();
    var partes = cab.split("·").map(function (x) { return x.trim(); });
    if (d === "ctcp") {
      var rad = datoS(art, "Radicación CTCP"), fe = datoS(art, "Fecha"), dot = datoS(art, "Documento");
      if (dot) return "Consejo Técnico de la Contaduría Pública, " + dot + (fe ? " (" + fe + ")" : "") + ".";
      return "Consejo Técnico de la Contaduría Pública, concepto " + (rad || partes[0].replace(/^Concepto CTCP\s*/, "")) + (fe ? " (" + fe + ")" : "") + ".";
    }
    if (d === "doc") return "DIAN, " + partes[0] + (partes[1] ? " (" + partes[1] + ")" : "") + ".";
    if (d === "jur") {
      var tipo = (datoS(art, "Sentencia") || "sentencia").toLowerCase(), fecha = datoS(art, "Providencia del") || partes[1] || "";
      var rad = datoS(art, "Radicado"), ni = datoS(art, "Número interno"), po = datoS(art, "Ponente");
      return "Consejo de Estado, Sala de lo Contencioso Administrativo, " + (datoS(art, "Sala de decisión") || "Sección Cuarta") + ", " + tipo +
        (fecha ? " de " + fecha : "") + (rad ? ", rad. " + rad + (ni ? " (" + ni + ")" : "") : ni ? ", número interno " + ni : "") + (po ? ", C. P. " + titulo(po) : "") + ".";
    }
    return document.title;
  }
  function copiar(texto, aviso) {
    (navigator.clipboard ? navigator.clipboard.writeText(texto) : Promise.reject()).then(function () { toast(aviso); }, function () { window.prompt("Copie el texto:", texto); });
  }
  function urlAbsoluta(id) { var a = document.createElement("a"); a.href = esDoc(id) ? urlVer(id) : urlArt(id); return a.href; }
  function botonesUso(id, art, tituloTxt, conImprimir) {
    var cont = document.createElement("div"); cont.className = "acciones-uso";
    cont.innerHTML = '<button type="button" class="btn btn-sec btn-fav" data-fav="' + id + '"></button>' +
      '<button type="button" class="btn btn-sec" data-uso="cita" title="Copia la cita en formato jurídico">Copiar cita</button>' +
      (navigator.share ? '<button type="button" class="btn btn-sec" data-uso="compartir">Compartir</button>' : "") +
      (conImprimir ? '<button type="button" class="btn btn-sec" data-uso="imprimir" title="Imprimir o guardar como PDF">Imprimir / PDF</button>' : "");
    pintarFav($(".btn-fav", cont));
    $(".btn-fav", cont).addEventListener("click", function () { toast(alternarFav(id, tituloTxt()) ? "Guardado en este navegador" : "Quitado de guardados"); });
    $$("[data-uso]", cont).forEach(function (b) {
      b.addEventListener("click", function () {
        var u = b.getAttribute("data-uso");
        if (u === "cita") copiar(citaDe(id, art), "Cita copiada");
        else if (u === "compartir") navigator.share({ title: tituloTxt(), text: citaDe(id, art), url: urlAbsoluta(id) }).catch(function () {});
        else if (u === "imprimir") window.print();
      });
    });
    return cont;
  }
  (function () {
    var art = $("#contenido article.articulo"); if (!art) return;
    var id = art.getAttribute("data-id"); if (!id) return;
    var h1 = $(".art-cab h1", art);
    var tit = function () { var n = ($(".art-num", art) || {}).textContent || ""; return (n.replace(/\s+/g, " ").trim() + " — " + (h1 ? h1.textContent.trim() : "")).slice(0, 200); };
    var acc = $(".herramientas .acciones", art);
    if (acc) acc.appendChild(botonesUso(id, art, tit, true));
    else { var barra = document.createElement("div"); barra.className = "herramientas herramientas-min"; barra.appendChild(botonesUso(id, art, tit, true)); var cab = $(".art-cab", art); cab.parentNode.insertBefore(barra, cab.nextSibling); }
  })();

  /* ================= línea de tiempo de reformas (desde las notas de vigencia) ================= */
  var RX_NORMA = /\b(Ley|Decreto(?:\s+Legislativo|\s+Ley|\s+Extraordinario)?|Resoluci[óo]n(?:\s+DIAN)?|Acto\s+Legislativo)\s+(\d+)\s+de\s+(\d{4})/i;
  var RX_VERBO = /\b(modificad|adicionad|adicioad|derogad|sustituid|subrogad|prorrogad|reglamentad)\w*/i;
  var RX_FECHA = /Diario Oficial No\.?\s*[\d.]+\s+de\s+(\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4})/i;
  function normaClave(t) { return norm(t || "").replace(/\s+/g, " ").replace(/^(la|el)\s+/, ""); }
  function eventosVigencia(art) {
    var out = [];
    $$("details.desp-vigencia", art).forEach(function (d) {
      var et = ($(".desp-et", d) || {}).textContent || "";
      if (!/^notas de vigencia/i.test(et.trim())) return;
      $$(".desp-cont > p", d).forEach(function (p) {
        var t = p.textContent.replace(/\s+/g, " ").trim();
        if (!/^-\s*\S/.test(t)) return;
        t = t.replace(/^-\s*/, "");
        var corte = t.match(/(Corte Constitucional|Consejo de Estado)/);
        if (corte) {
          var s = t.match(/\b(Sentencia|Auto)\s+([CA]-\d+(?:-|\s+de\s+)(\d{2,4}))/i), v = t.match(/\b(INEXEQUIBLES?|EXEQUIBLES?|CONDICIONALMENTE|SUSPENDID[OA]S?|NULIDAD|NUL[OA]S?|ESTARSE A LO RESUELTO|INHIBIDA)\b/i);
          if (!s) return;
          var a = s[3].length === 2 ? (+s[3] > 50 ? "19" : "20") + s[3] : s[3];
          out.push({ tipo: "corte", anio: +a, norma: s[1] + " " + s[2], accion: v ? v[1].toLowerCase().replace(/^estarse.*/, "estarse a lo resuelto") : "pronunciamiento", quien: corte[1], texto: t, p: p });
          return;
        }
        var n = t.match(RX_NORMA), vb = t.match(RX_VERBO);
        if (!n || !vb) return;
        var k = t.toLowerCase().indexOf(" por ");
        var accion = (k > 0 && k < 220 ? t.slice(0, k) : vb[0]).replace(/adicioad/i, "adicionad");
        var f = t.match(RX_FECHA);
        out.push({ tipo: /^art[íi]culo (adicionado|creado)/i.test(accion) ? "creacion" : /derogad/i.test(accion) && !/modific|adicion|sustitu/i.test(accion) ? "derogacion" : "reforma",
          anio: +n[3], norma: n[0].replace(/\s+/g, " "), accion: accion, fecha: f ? f[1] : "", texto: t, p: p });
      });
    });
    /* orden cronológico; a igual año, como aparecen (las notas van de la más reciente a la más antigua) */
    out.forEach(function (e, i) { e.i = i; });
    return out.sort(function (x, y) { return x.anio - y.anio || y.i - x.i; });
  }
  (function () {
    var art = $("#contenido article.con-aside"); if (!art) return;
    var ev = eventosVigencia(art); if (!ev.length) return;
    var sec = document.createElement("section");
    sec.className = "linea-tiempo"; sec.setAttribute("data-toc", "Línea de tiempo de reformas"); sec.id = "linea-tiempo";
    var nRef = ev.filter(function (e) { return e.tipo !== "corte"; }).length;
    var h = '<div class="lt-cab"><h2>Línea de tiempo</h2><span>' + nRef + (nRef === 1 ? " norma" : " normas") + " en las notas de vigencia" +
      (ev.some(function (e) { return e.tipo === "corte"; }) ? " · incluye decisiones judiciales" : "") + "</span></div>" +
      '<ol class="lt-eje" role="list">';
    ev.forEach(function (e, i) {
      h += '<li><button type="button" class="lt-nodo lt-' + e.tipo + '" data-i="' + i + '" aria-expanded="false" title="' + esc(e.texto.slice(0, 220)) + '">' +
        '<span class="lt-anio">' + e.anio + '</span><span class="lt-norma">' + esc(e.norma.replace(/^Decreto Legislativo/, "Dto. Leg.").replace(/^Decreto/, "Dto.").replace(/^Resolución/, "Res.").replace(/ de \d{4}$/, "")) + "</span>" +
        '<span class="lt-acc">' + esc(resumenAccion(e)) + "</span></button></li>";
    });
    h += '</ol><div class="lt-detalle" hidden></div>';
    sec.innerHTML = h;
    var ancla = $(".herramientas", art) || $(".art-aside", art);
    ancla.parentNode.insertBefore(sec, ancla);
    var det = $(".lt-detalle", sec), eje = $(".lt-eje", sec);
    eje.scrollLeft = eje.scrollWidth;   /* lo más reciente a la vista */
    $$(".lt-nodo", sec).forEach(function (b) {
      b.addEventListener("click", function () {
        var e = ev[+b.getAttribute("data-i")], abierto = b.getAttribute("aria-expanded") === "true";
        $$(".lt-nodo", sec).forEach(function (x) { x.setAttribute("aria-expanded", "false"); });
        if (abierto) { det.hidden = true; return; }
        b.setAttribute("aria-expanded", "true");
        var v = versionesDe(art), par = v.length ? parVersiones(v, e.norma) : null;
        /* la reforma más reciente, si ninguna versión la nombra: lo anterior es la última versión guardada y lo posterior, el texto vigente */
        var ultima = ev.filter(function (x) { return x.tipo !== "corte"; }).slice(-1)[0];
        if (!par && v.length && e === ultima) par = [0, -1];
        det.innerHTML = '<p class="lt-titulo"><b>' + esc(e.norma) + "</b>" + (e.fecha ? " · Diario Oficial del " + esc(e.fecha) : "") + "</p>" +
          '<p class="lt-texto">' + esc(e.texto) + "</p>" +
          '<p class="lt-botones"><button type="button" class="enlace-btn" data-lt="nota">Ver en las notas de vigencia</button>' +
          (par ? '<button type="button" class="enlace-btn" data-lt="comparar">Comparar el texto antes y después</button>' : "") + "</p>";
        det.hidden = false;
        $("[data-lt=nota]", det).addEventListener("click", function () {
          var d = e.p.closest("details"); d.open = true; e.p.scrollIntoView({ behavior: "smooth", block: "center" });
          e.p.classList.remove("destello"); void e.p.offsetWidth; e.p.classList.add("destello");
        });
        if (par) $("[data-lt=comparar]", det).addEventListener("click", function () { abrirComparador(art, par[0], par[1]); });
      });
    });
  })();
  function resumenAccion(e) {
    if (e.tipo === "corte") return e.accion;
    var a = e.accion.toLowerCase();
    if (/^art[íi]culo /.test(a)) return a.replace(/^art[íi]culo\s+/, "artículo ").replace(/\s+y\s+.*/, "");
    var verbos = (a.match(/(modificad|adicionad|derogad|sustituid|subrogad|prorrogad|reglamentad)\w*/g) || []).map(function (x) { return x.replace(/s$/, ""); });
    var u = verbos.filter(function (x, i) { return verbos.indexOf(x) === i; });
    return u.length ? u.join(" · ") : "reforma";
  }

  /* ================= versiones anteriores y comparación de textos ================= */
  function versionesDe(art) {
    var d = $$("details.desp-anterior", art)[0]; if (!d) return [];
    var cont = $(".desp-cont", d), vs = [], actual = null;
    Array.prototype.forEach.call(cont.children, function (el) {
      var t = el.textContent.replace(/\s+/g, " ").trim();
      var cab = el.tagName === "P" && el.querySelector(".b_aj") && /^Texto\b.{3,200}:$/.test(t);
      if (cab) { actual = { titulo: t.replace(/:$/, ""), nodos: [] }; vs.push(actual); return; }
      if (actual) actual.nodos.push(el);
    });
    return vs;
  }
  function rotuloVersion(v) {
    return v.titulo.replace(/^Texto vigente antes de la modificación introducida por/i, "Antes de la reforma de").replace(/^Texto /, "").replace(/^./, function (c) { return c.toUpperCase(); });
  }
  /* para una norma reformatoria, la pareja [versión anterior, versión posterior] (índices; -1 = texto vigente) */
  function parVersiones(vs, norma) {
    var k = normaClave(norma);
    for (var i = 0; i < vs.length; i++) {
      var t = normaClave(vs[i].titulo);
      if (t.indexOf(k) < 0) continue;
      if (/antes de la modificacion introducida/.test(t)) return [i, i - 1];
      return i + 1 < vs.length ? [i + 1, i] : null;
    }
    return null;
  }
  function textoPlano(nodos, sinNotas) {
    return nodos.map(function (n) {
      var t = n.textContent.replace(/ /g, " ");
      if (sinNotas) t = t.replace(/<[^<>]{2,600}>/g, " ");
      return t.replace(/[ \t]+/g, " ").trim();
    }).filter(Boolean);
  }
  function nodosVigentes(art) { return $$("#texto-vigente > .texto-norma > *", art).filter(function (n) { return n.tagName !== "DETAILS"; }); }
  /* diferencias (Myers) entre dos listas; devuelve [["=",x]|["-",x]|["+",x]] */
  function difer(a, b) {
    var n = a.length, m = b.length, max = n + m, v = { 1: 0 }, traza = [];
    for (var d = 0; d <= max; d++) {
      traza.push(Object.assign({}, v));
      for (var k = -d; k <= d; k += 2) {
        var x = (k === -d || (k !== d && v[k - 1] < v[k + 1])) ? v[k + 1] : v[k - 1] + 1, y = x - k;
        while (x < n && y < m && a[x] === b[y]) { x++; y++; }
        v[k] = x;
        if (x >= n && y >= m) return recorrer(traza, a, b, d);
      }
      if (d > 4000) break;
    }
    return a.map(function (x) { return ["-", x]; }).concat(b.map(function (x) { return ["+", x]; }));
  }
  function recorrer(traza, a, b, D) {
    var x = a.length, y = b.length, out = [];
    for (var d = D; d > 0; d--) {
      var v = traza[d], k = x - y;
      var pk = (k === -d || (k !== d && v[k - 1] < v[k + 1])) ? k + 1 : k - 1;
      var px = v[pk], py = px - pk;
      while (x > px && y > py) { out.push(["=", a[x - 1]]); x--; y--; }
      if (x === px) out.push(["+", b[py]]); else out.push(["-", a[px]]);
      x = px; y = py;
    }
    while (x > 0 && y > 0) { out.push(["=", a[x - 1]]); x--; y--; }
    return out.reverse();
  }
  function palabras(t) { return t.match(/[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+/g) || []; }
  /* fichas: palabras (con cifras como 1.000 o 9,5), signos y espacios; los espacios se conservan para reconstruir el texto */
  function fichas(t) { return t.match(/\s+|[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:[.,][0-9]+)*|[^\s0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/g) || []; }
  function difPalabras(x, y) {
    var ops = difer(fichas(x), fichas(y)), out = "", modo = "=", buf = "";
    function vaciar() { if (!buf) return; out += modo === "=" ? esc(buf) : modo === "-" ? "<del>" + esc(buf) + "</del>" : "<ins>" + esc(buf) + "</ins>"; buf = ""; }
    ops.forEach(function (o) {
      /* un espacio entre dos cambios del mismo tipo se une a ellos para no partir el resaltado */
      var tipo = o[0];
      if (tipo !== modo) { vaciar(); modo = tipo; }
      buf += o[1];
    });
    vaciar();
    return out.replace(/<\/del>(\s+)<del>/g, "$1").replace(/<\/ins>(\s+)<ins>/g, "$1");
  }
  function similitud(x, y) {
    var a = {}, b = {}, inter = 0, na = 0, nb = 0;
    palabras(norm(x)).forEach(function (w) { if (w.length > 2 && !a[w]) { a[w] = 1; na++; } });
    palabras(norm(y)).forEach(function (w) { if (w.length > 2 && !b[w]) { b[w] = 1; nb++; if (a[w]) inter++; } });
    return na + nb ? inter / (na + nb - inter) : 0;
  }
  function comparar(pa, pb) {
    var ops = difer(pa, pb), html = [], cambios = 0, i = 0;
    function ins(t) { cambios++; html.push('<p class="cmp-ins"><ins>' + esc(t) + "</ins></p>"); }
    function del(t) { cambios++; html.push('<p class="cmp-del"><del>' + esc(t) + "</del></p>"); }
    while (i < ops.length) {
      if (ops[i][0] === "=") { html.push('<p class="cmp-igual">' + esc(ops[i][1]) + "</p>"); i++; continue; }
      /* bloque de cambios: cada párrafo suprimido se empareja con el añadido más parecido y se compara palabra por palabra */
      var D = [], I = [];
      while (i < ops.length && ops[i][0] !== "=") { (ops[i][0] === "-" ? D : I).push(ops[i][1]); i++; }
      var j = 0;
      D.forEach(function (d) {
        var mejor = -1, ms = 0.3;
        for (var k = j; k < I.length; k++) { var sm = similitud(d, I[k]); if (sm > ms) { ms = sm; mejor = k; } }
        if (mejor < 0) { del(d); return; }
        while (j < mejor) ins(I[j++]);
        cambios++; html.push('<p class="cmp-mod">' + difPalabras(d, I[mejor]) + "</p>"); j = mejor + 1;
      });
      while (j < I.length) ins(I[j++]);
    }
    return { html: html.join(""), cambios: cambios };
  }
  function abrirComparador(art, ia, ib) {
    var d = $$("details.desp-anterior", art)[0]; if (!d) return;
    d.open = true;
    var c = $(".comparador", d); if (!c) return;
    $("select[data-cmp=a]", c).value = String(ia); $("select[data-cmp=b]", c).value = String(ib);
    c.dispatchEvent(new Event("comparar"));
    c.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  (function () {
    var art = $("#contenido article.articulo"); if (!art) return;
    var vs = versionesDe(art), d = $$("details.desp-anterior", art)[0];
    if (!d || !vs.length) return;
    var opciones = '<option value="-1">Texto vigente</option>' + vs.map(function (v, i) { return '<option value="' + i + '">' + esc(rotuloVersion(v)) + "</option>"; }).join("");
    var c = document.createElement("div"); c.className = "comparador";
    c.innerHTML = '<p class="cmp-cab"><b>Comparar versiones</b> <span>' + (vs.length + 1) + " versiones del texto</span></p>" +
      '<div class="cmp-ctrl"><label><span>Versión anterior</span><select data-cmp="a">' + opciones + '</select></label>' +
      '<label><span>Versión posterior</span><select data-cmp="b">' + opciones + "</select></label>" +
      '<label class="chk"><input type="checkbox" data-cmp="notas" checked> Ocultar notas del editor</label>' +
      '<button type="button" class="btn" data-cmp="ir">Comparar</button></div><div class="cmp-res" hidden></div>';
    var cont = $(".desp-cont", d); cont.insertBefore(c, cont.firstChild);
    $("select[data-cmp=a]", c).value = "0"; $("select[data-cmp=b]", c).value = "-1";
    var res = $(".cmp-res", c);
    function hacer() {
      var ia = +$("select[data-cmp=a]", c).value, ib = +$("select[data-cmp=b]", c).value, sin = $("[data-cmp=notas]", c).checked;
      var ta = textoPlano(ia < 0 ? nodosVigentes(art) : vs[ia].nodos, sin), tb = textoPlano(ib < 0 ? nodosVigentes(art) : vs[ib].nodos, sin);
      var r = comparar(ta, tb);
      res.innerHTML = '<p class="cmp-leyenda"><ins>Texto añadido</ins> <del>Texto suprimido</del> <span>' + (r.cambios ? r.cambios + (r.cambios === 1 ? " párrafo con cambios" : " párrafos con cambios") : "Sin diferencias en el texto") +
        '</span> <label class="chk"><input type="checkbox" data-cmp="solo"' + (c.soloCambios ? " checked" : "") + "> Solo párrafos con cambios</label></p>" + '<div class="cmp-texto' + (c.soloCambios ? " solo-cambios" : "") + '">' + r.html + "</div>";
      res.hidden = false;
      $("[data-cmp=solo]", res).addEventListener("change", function (e) { c.soloCambios = e.target.checked; $(".cmp-texto", res).classList.toggle("solo-cambios", c.soloCambios); });
    }
    c.soloCambios = false;
    $("[data-cmp=ir]", c).addEventListener("click", hacer);
    c.addEventListener("comparar", hacer);
  })();

  /* ================= panel del artículo: tabla de contenido y saltos ================= */
  (function () {
    var art = $("#contenido article.con-aside"), toc = art && $(".toc", art);
    if (!art) return;
    function irA(det) {
      if (!det) return;
      if (det.tagName === "DETAILS") det.open = true;
      det.scrollIntoView({ behavior: "smooth", block: "start" });
      det.classList.remove("destello"); void det.offsetWidth; det.classList.add("destello");
    }
    $$("[data-ir]", art).forEach(function (a) {
      a.addEventListener("click", function (e) { e.preventDefault(); irA($("details." + a.getAttribute("data-ir"), art)); });
    });
    if (!toc) return;
    /* entradas: texto vigente y cada desplegable, en el orden de la página */
    var secciones = [], ol = $("ol", toc);
    var tv = $("#texto-vigente", art);
    if (tv) secciones.push({ el: tv, t: "Texto vigente" });
    $$("[data-toc]", art).forEach(function (el) { secciones.push({ el: el, t: el.getAttribute("data-toc"), tipo: "linea" }); });
    $$(":scope > details.desp, .cuerpo-norma details.desp", art).forEach(function (d, i) {
      var et = $(".desp-et", d); if (!et) return;
      var c = $(".cuenta", et);
      var t = et.textContent.replace(/^⇄\s*/, "").replace(c ? c.textContent : "", "").replace(/[:\s]+$/, "").trim();
      if (!d.id) d.id = "sec-" + (i + 1);
      secciones.push({ el: d, t: t, n: c ? c.textContent : "", tipo: d.getAttribute("data-tipo") });
    });
    secciones.sort(function (x, y) { return x.el.compareDocumentPosition(y.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1; });
    secciones.forEach(function (x) { x.t = x.t.replace(/^[§⚖⇄]\s*/, ""); });
    /* desplegables repetidos del mismo tipo (p. ej. varias «Notas de vigencia») se agrupan en una entrada */
    var vistos = {};
    secciones = secciones.filter(function (x) { var k = x.t.toLowerCase(); if (vistos[k]) return false; vistos[k] = 1; return true; });
    if (secciones.length < 2) return;
    ol.innerHTML = secciones.map(function (x, i) {
      return '<li><a href="#' + (x.el.id || "texto-vigente") + '" data-i="' + i + '" class="toc-' + (x.tipo || "texto") + '">' + esc(x.t) + (x.n ? ' <span>' + esc(x.n) + "</span>" : "") + "</a></li>";
    }).join("");
    toc.hidden = false;
    aplicarFiltros();
    $$("a", ol).forEach(function (a) {
      a.addEventListener("click", function (e) { e.preventDefault(); irA(secciones[+a.getAttribute("data-i")].el); history.replaceState(null, "", location.pathname + location.search + (PREVIEW ? location.hash : "")); });
    });
    /* sección visible resaltada en la tabla de contenido */
    var enlaces = $$("a", ol), activo = -1, pendiente = false;
    function espiar() {
      pendiente = false;
      var tope = (parseInt(getComputedStyle(document.documentElement).getPropertyValue("--alto-barra"), 10) || 68) + 110, mejor = 0;
      secciones.forEach(function (x, i) { var r = x.el.getBoundingClientRect(); if (r.height && r.top <= tope) mejor = i; });
      if (mejor !== activo) { activo = mejor; enlaces.forEach(function (a, i) { a.classList.toggle("activo", i === mejor); }); }
    }
    window.addEventListener("scroll", function () { if (!pendiente) { pendiente = true; requestAnimationFrame(espiar); } }, { passive: true });
    espiar();
  })();

  var q = $("#q");
  if (!q) return;
  var res = $("#resultados"), indice = $("#indice-portada");
  var auto = autocompletar(q, function (texto) { mostrarTodos(texto); });

  function volverInicio() {
    q.value = ""; recordarConsulta(""); res.hidden = true; res.innerHTML = ""; indice.hidden = false; limites = {};
    history.replaceState(null, "", location.pathname);
    window.scrollTo({ top: 0, behavior: "smooth" }); q.focus(); auto.cerrar();
  }
  /* ================= filtros de resultados (con conteos), orden y estado en la dirección ================= */
  var FILTRO = { fu: [], est: [], lib: "", anio: "", orden: "rel" }, ultimaBusqueda = null;
  (function leerFiltros() {
    var lista = function (k) { return (params.get(k) || "").split(",").map(function (x) { return x.trim(); }).filter(Boolean); };
    FILTRO.fu = lista("fu"); FILTRO.est = lista("est");
    FILTRO.lib = params.get("lib") || ""; FILTRO.anio = params.get("anio") || "";
    FILTRO.orden = /^(rel|num|rec)$/.test(params.get("orden") || "") ? params.get("orden") : "rel";
    var f = params.get("f"); if (f) { var rf = $('input[name="fuente"][value="' + f + '"]'); if (rf) rf.checked = true; }
    if (params.get("n") === "1" && $("#en-anotaciones")) $("#en-anotaciones").checked = true;
    if (params.get("sd") === "1" && $("#sin-derogados")) $("#sin-derogados").checked = true;
  })();
  function filtrosActivos() { return FILTRO.fu.length || FILTRO.est.length || FILTRO.lib || FILTRO.anio; }
  function escribirURL(texto) {
    var op = opciones(), u = new URLSearchParams();
    u.set("q", texto);
    if (op.fuente !== "todo") u.set("f", op.fuente);
    if (op.anot) u.set("n", "1");
    if (op.sinDer) u.set("sd", "1");
    if (FILTRO.fu.length) u.set("fu", FILTRO.fu.join(","));
    if (FILTRO.est.length) u.set("est", FILTRO.est.join(","));
    if (FILTRO.lib) u.set("lib", FILTRO.lib);
    if (FILTRO.anio) u.set("anio", FILTRO.anio);
    if (FILTRO.orden !== "rel") u.set("orden", FILTRO.orden);
    if (params.get("vista") || modoVista === "tabla") u.set("vista", modoVista);
    history.replaceState(null, "", location.pathname + "?" + u.toString().replace(/%2C/g, ","));
  }
  /* valores de cada resultado para los filtros */
  function estadoDe(a) {
    var e = a.est || (a.der ? "Derogado" : "");
    if (!e) return FICHAS[a.doc] ? "" : "Vigente";
    return e.replace(/\s+\d{4}$/, "");
  }
  function libroDe(a) {
    if (FICHAS[a.doc] || !a.ub) return "";
    return a.doc + "|" + a.ub.split(",")[0].trim();
  }
  function rotuloLibro(k) { var p = k.split("|"); return (p[0] === "et" ? "" : CORTO[p[0]] + " · ") + p[1]; }
  function anioDeRes(a) {
    if (FICHAS[a.doc]) { var m = a.doc === "jur" ? a.id.match(/-(\d{4})\d{4}$/) : null; return m ? m[1] : (a.anio || ""); }
    var r = (a.est || "").match(/(\d{4})$/); return r ? r[1] : "";
  }
  function fechaClave(a) {
    if (a.doc === "jur") { var m = a.id.match(/-(\d{8})$/); return m ? +m[1] : 0; }
    if (a.doc === "doc" || a.doc === "ctcp") return (+(a.anio || 0)) * 1e6 + (+(a.cnum || 0));
    var r = (a.est || "").match(/(\d{4})$/); return r ? +r[1] * 1e6 : 0;
  }
  function numClave(t) { return (t || "").split(/[^0-9]+/).filter(Boolean).map(function (x) { return ("000000" + x).slice(-6); }).join("."); }
  function pasa(o, sin) {
    var a = o.a;
    if (sin !== "fu" && FILTRO.fu.length && FILTRO.fu.indexOf(a.doc) < 0) return false;
    if (sin !== "est" && FILTRO.est.length && FILTRO.est.indexOf(estadoDe(a)) < 0) return false;
    if (sin !== "lib" && FILTRO.lib && libroDe(a) !== FILTRO.lib) return false;
    if (sin !== "anio" && FILTRO.anio && anioDeRes(a) !== FILTRO.anio) return false;
    return true;
  }
  function contarFaceta(res, sin, valor) {
    var c = {};
    res.forEach(function (o) { if (!pasa(o, sin)) return; var v = valor(o.a); if (v) c[v] = (c[v] || 0) + 1; });
    return c;
  }
  function barraFiltros(r) {
    var R = r.res, h = '<div class="facetas" role="group" aria-label="Filtrar resultados">';
    var cf = contarFaceta(R, "fu", function (a) { return a.doc; });
    h += '<div class="faceta"><span class="faceta-et">Fuente</span><div class="faceta-ops">' + ORDEN.filter(function (k) { return cf[k] || FILTRO.fu.indexOf(k) > -1; }).map(function (k) {
      var on = FILTRO.fu.indexOf(k) > -1;
      return '<button type="button" class="fchip fchip-' + k + (on ? " on" : "") + '" aria-pressed="' + on + '" data-fac="fu" data-val="' + k + '">' + esc(CORTO[k]) + " <span>" + miles(cf[k] || 0) + "</span></button>";
    }).join("") + "</div></div>";
    var ce = contarFaceta(R, "est", estadoDe), ordE = ["Vigente", "Modificado", "Derogado", "Revocado", "Revocado parcialmente", "Reconsiderado", "Reconsiderado parcialmente", "Modificado parcialmente", "Aclarado", "Suspendido", "Accede", "Accede parcialmente", "Niega", "Inhibitorio"];
    var estados = Object.keys(ce).concat(FILTRO.est.filter(function (x) { return !ce[x]; })).sort(function (x, y) { return ordE.indexOf(x) - ordE.indexOf(y); });
    if (estados.length) h += '<div class="faceta"><span class="faceta-et">Estado</span><div class="faceta-ops">' + estados.map(function (v) {
      var on = FILTRO.est.indexOf(v) > -1;
      return '<button type="button" class="fchip est-' + norm(v.split(" ")[0]) + (on ? " on" : "") + '" aria-pressed="' + on + '" data-fac="est" data-val="' + esc(v) + '">' + esc(v) + " <span>" + miles(ce[v] || 0) + "</span></button>";
    }).join("") + "</div></div>";
    var cl = contarFaceta(R, "lib", libroDe), libros = Object.keys(cl).sort(function (x, y) { return ORDEN.indexOf(x.split("|")[0]) - ORDEN.indexOf(y.split("|")[0]) || numClave(x).localeCompare(numClave(y)) || x.localeCompare(y); });
    var ca = contarFaceta(R, "anio", anioDeRes), anios = Object.keys(ca).sort().reverse();
    h += '<div class="faceta faceta-sel">';
    if (libros.length || FILTRO.lib) h += '<label><span class="faceta-et">Libro o parte</span><select data-fac="lib"><option value="">Todos</option>' + libros.map(function (k) {
      return '<option value="' + esc(k) + '"' + (FILTRO.lib === k ? " selected" : "") + ">" + esc(rotuloLibro(k)) + " (" + miles(cl[k]) + ")</option>";
    }).join("") + "</select></label>";
    if (anios.length || FILTRO.anio) h += '<label title="En las normas, año de la última reforma; en doctrina y sentencias, año del concepto o del fallo"><span class="faceta-et">Año</span><select data-fac="anio"><option value="">Todos</option>' + anios.map(function (k) {
      return '<option value="' + k + '"' + (FILTRO.anio === k ? " selected" : "") + ">" + k + " (" + miles(ca[k]) + ")</option>";
    }).join("") + "</select></label>";
    h += '<label><span class="faceta-et">Ordenar</span><select data-fac="orden">' + [["rel", "Relevancia"], ["num", "Número"], ["rec", "Más reciente"]].map(function (o) {
      return '<option value="' + o[0] + '"' + (FILTRO.orden === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
    }).join("") + "</select></label>";
    h += '<span class="faceta-acc">' + (filtrosActivos() ? '<button type="button" class="enlace-btn" data-fac="limpiar">Quitar filtros</button>' : "") +
      '<button type="button" class="enlace-btn" data-fac="copiar" title="Copia la dirección de esta búsqueda con sus filtros">Copiar enlace</button></span>';
    return h + "</div></div>";
  }
  function filtrarResultados(r) {
    var lista = r.res.filter(function (o) { return pasa(o, null); });
    if (FILTRO.orden === "num") lista = lista.slice().sort(function (x, y) { return numClave(x.a.num).localeCompare(numClave(y.a.num)) || x.a.num.localeCompare(y.a.num); });
    else if (FILTRO.orden === "rec") lista = lista.slice().sort(function (x, y) { return fechaClave(y.a) - fechaClave(x.a) || y.s - x.s; });
    return { res: lista, T: r.T, total: r.res.length };
  }

  function mostrarTodos(texto) {
    texto = (texto || "").trim(); recordarConsulta(texto);
    if (!texto) { volverInicio(); return; }
    if (ultimaBusqueda !== null && ultimaBusqueda !== texto) { FILTRO.fu = []; FILTRO.est = []; FILTRO.lib = ""; FILTRO.anio = ""; }
    ultimaBusqueda = texto;
    var op = opciones();
    res.hidden = false; indice.hidden = true;
    res.innerHTML = '<p class="res-cab">Buscando…</p>'; limites = {};
    cargarIndice().then(function () { return op.anot ? cargarAnot(op.fuente === "todo" ? CLAVES : [op.fuente]) : null; }).then(function () {
      var r = buscar(texto, op);
      pintarTodos(r, texto, op);
    });
    escribirURL(texto);
  }
  var modoVista = params.get("vista") === "tabla" ? "tabla" : params.get("vista") === "tarjetas" ? "tarjetas" : leer("vista", "tarjetas");
  var POR_GRUPO = 15, limites = {};
  var ETQ = { et: "Estatuto Tributario", dur: "Decreto 1625 de 2016", r227: "Resolución 227 de 2025", doc: "Conceptos DIAN", jur: "Sentencias del Consejo de Estado", ctcp: "Conceptos del CTCP" };
  function etiquetaGrupo(k) { return ETQ[k] || NOMBRE[k]; }
  function pintarTodos(r0, texto, op) {
    var r = filtrarResultados(r0), barra = r0.res.length ? barraFiltros(r0) : "";
    var grupos = porFuente(r.res), n = r.res.length, vis = 0;
    grupos.forEach(function (g) { g.lim = Math.min(limites[g.doc] || POR_GRUPO, g.items.length); vis += g.lim; });
    var volver = '<button type="button" class="btn btn-volver" data-volver>← Volver al inicio</button>';
    var conmuta = '<div class="vista-sel" role="group" aria-label="Vista de resultados">' +
      ["tarjetas", "tabla"].map(function (v) {
        return '<button type="button" data-vista="' + v + '" aria-pressed="' + (modoVista === v) + '"' + (modoVista === v ? ' class="activa"' : "") + ">" + (v === "tabla" ? "Tabla" : "Tarjetas") + "</button>";
      }).join("") + "</div>";
    var h = '<div class="res-cab">' + volver + '<span class="res-cuenta">' +
      (n ? "Mostrando <b>" + miles(vis) + "</b> de <b>" + miles(n) + "</b> resultado" + (n === 1 ? "" : "s") : "<b>0</b> resultados") +
      (n !== r.total ? ' <em class="filtrado">(filtrados de ' + miles(r.total) + ")</em>" : "") +
      " para «" + esc(texto) + "»<small>" + grupos.map(function (g) { return '<a href="#grupo-' + g.doc + '">' + CORTO[g.doc] + " " + miles(g.items.length) + "</a>"; }).join(" · ") + "</small></span>" +
      (n ? conmuta : "") + "</div>";
    h += barra;
    if (!n) h += r.total ? '<p class="sin-res">Ningún resultado cumple los filtros. <button type="button" class="enlace-btn" data-fac="limpiar">Quitar filtros</button></p>'
      : "<p>Sin resultados. Pruebe con otras palabras, cambie la fuente o active la búsqueda en notas y concordancias.</p>";
    function botonMas(g) {
      var resta = g.items.length - g.lim;
      return resta > 0 ? '<button type="button" class="btn btn-sec btn-mas" data-mas="' + g.doc + '">Ver ' + miles(Math.min(60, resta)) + " más de " + esc(etiquetaGrupo(g.doc)) + " (" + miles(resta) + " restantes)</button>" : "";
    }
    if (n && modoVista === "tabla") {
      h += '<div class="tabla-res-envoltura"><table class="tabla-res"><colgroup><col class="c-f"><col class="c-n"><col><col class="c-u"><col class="c-e"><col class="c-k"><col class="c-k"></colgroup><thead><tr><th scope="col">Fuente</th><th scope="col">Número</th><th scope="col">Título</th>' +
        '<th scope="col">Ubicación / ponente</th><th scope="col">Estado</th><th scope="col" class="num">Conceptos</th><th scope="col" class="num">Sentencias</th></tr></thead>';
      grupos.forEach(function (g) {
        h += '<tbody id="grupo-' + g.doc + '"><tr class="fila-grupo"><th colspan="7" scope="rowgroup">' + esc(etiquetaGrupo(g.doc)) + " · " + miles(g.items.length) + "</th></tr>";
        g.items.slice(0, g.lim).forEach(function (o) {
          var a = o.a, f = FICHAS[a.doc], k = a.k || [], est = a.est || (a.der ? "Derogado" : "");
          h += '<tr><td><span class="badge badge-' + a.doc + '">' + CORTO[a.doc] + "</span></td>" +
            '<td class="n"><a' + (f ? ' class="ref" data-ref="' + a.id + '"' : "") + ' href="' + enlaceResultado(a, r.T) + '">' + esc(rotulo(a.num, a.doc)) + "</a></td>" +
            "<td><span class=\"clamp\">" + marcar(a.epi, r.T.todos) + "</span></td><td class=\"ub\">" + esc(a.ub) + "</td><td>" + chipEstado(est) + "</td>" +
            '<td class="num">' + (f ? "" : k[1] ? miles(k[1]) : "–") + '</td><td class="num">' + (f ? "" : k[2] ? miles(k[2]) : "–") + "</td></tr>";
        });
        var b = botonMas(g); if (b) h += '<tr class="fila-mas"><td colspan="7">' + b + "</td></tr>";
        h += "</tbody>";
      });
      h += "</table></div>";
    } else {
      grupos.forEach(function (g) {
        h += '<section class="grupo-res" id="grupo-' + g.doc + '"><h3 class="res-grupo res-grupo-' + g.doc + '">' + esc(etiquetaGrupo(g.doc)) + " <span>" + miles(g.items.length) + (g.items.length === 1 ? " resultado" : " resultados") + "</span></h3>";
        g.items.slice(0, g.lim).forEach(function (o) {
          var a = o.a;
          h += '<a class="res' + (FICHAS[a.doc] ? ' ref" data-ref="' + a.id : "") + '" href="' + enlaceResultado(a, r.T) + '">' +
            '<div class="res-t"><span class="badge badge-' + a.doc + '">' + CORTO[a.doc] + '</span><span class="n">' + esc(rotulo(a.num, a.doc)) + "</span>" + marcar(a.epi, r.T.todos) + "</div>" +
            metaLinea(a, "res-meta") +
            '<p class="res-s">' + fragmento(o, r.T, 230) + "</p>" +
            '<div class="res-m">' + NOMBRE[a.doc] + (o.anot ? " · coincidencia en notas / concordancias / doctrina / jurisprudencia" : "") + "</div></a>";
        });
        h += botonMas(g) + "</section>";
      });
    }
    if (n > 5) h += '<div class="res-pie">' + volver + "</div>";
    res.innerHTML = h;
    $$("[data-mas]", res).forEach(function (b) {
      b.addEventListener("click", function () {
        var k = b.getAttribute("data-mas"), y = window.scrollY;
        limites[k] = (limites[k] || POR_GRUPO) + 60; pintarTodos(r0, texto, op); window.scrollTo(0, y);
      });
    });
    function rehacer() { limites = {}; escribirURL(texto); var y = window.scrollY; pintarTodos(r0, texto, op); window.scrollTo(0, y); }
    $$("button[data-fac]", res).forEach(function (b) {
      b.addEventListener("click", function () {
        var f = b.getAttribute("data-fac"), v = b.getAttribute("data-val");
        if (f === "limpiar") { FILTRO.fu = []; FILTRO.est = []; FILTRO.lib = ""; FILTRO.anio = ""; FILTRO.orden = "rel"; rehacer(); return; }
        if (f === "copiar") {
          var url = location.href, ok = function () { b.textContent = "Enlace copiado"; setTimeout(function () { b.textContent = "Copiar enlace"; }, 1600); };
          if (navigator.clipboard) navigator.clipboard.writeText(url).then(ok, function () { prompt("Copie el enlace:", url); }); else prompt("Copie el enlace:", url);
          return;
        }
        var arr = FILTRO[f], i = arr.indexOf(v);
        if (i > -1) arr.splice(i, 1); else arr.push(v);
        rehacer();
      });
    });
    $$("select[data-fac]", res).forEach(function (s) {
      s.addEventListener("change", function () { FILTRO[s.getAttribute("data-fac")] = s.value || (s.getAttribute("data-fac") === "orden" ? "rel" : ""); rehacer(); });
    });
    $$("[data-vista]", res).forEach(function (b) {
      b.addEventListener("click", function () {
        modoVista = b.getAttribute("data-vista"); guardar("vista", modoVista);
        var u = new URLSearchParams(location.search); u.set("vista", modoVista);
        history.replaceState(null, "", location.pathname + "?" + u.toString().replace(/%2C/g, ","));
        pintarTodos(r0, texto, op);
      });
    });
  }
  function pintarGuardados() {
    var nav = $(".atajos"); if (!nav) return;
    var cont = $(".favs"), favs = favoritos();
    if (!favs.length) { if (cont) cont.remove(); return; }
    if (!cont) { cont = document.createElement("div"); cont.className = "favs"; nav.parentNode.insertBefore(cont, nav.nextSibling); }
    cont.innerHTML = '<span class="favs-et">★ Guardados</span>' + favs.slice(0, 8).map(function (f) {
      var d = esDoc(f.id), t = f.t.replace(/^\s*(ET|DUR 1625|Res\. 227|Doctrina DIAN|Consejo de Estado)\s*/, "");
      return '<a class="fav-chip' + (d ? ' ref" data-ref="' + f.id : "") + '" href="' + (d ? urlVer(f.id) : urlArt(f.id)) + '" title="' + esc(t) + '"><span>' + esc(d ? t.split(" — ")[0].split(" · ")[0] : CORTO[docDe(f.id)] + " · " + t.split(" — ")[0].replace(/^Artículo /, "Art. ")) + "</span></a>";
    }).join("") + (favs.length > 8 ? '<span class="favs-et">y ' + (favs.length - 8) + " más (en las sugerencias del buscador)</span>" : "");
  }
  pintarGuardados();
  window.addEventListener("storage", pintarGuardados);
  document.addEventListener("etc-fav", pintarGuardados);
  $$(".atajo-tema").forEach(function (b) {
    b.addEventListener("click", function () { q.value = b.getAttribute("data-q"); auto.cerrar(); mostrarTodos(q.value); });
  });
  res.addEventListener("click", function (e) { if (e.target.closest("[data-volver]")) volverInicio(); });
  $$('input[name="fuente"], #en-anotaciones, #sin-derogados').forEach(function (c) {
    c.addEventListener("change", function () { if (!res.hidden) mostrarTodos(q.value); else if (q.value.trim()) auto.actualizar(); });
  });
  q.addEventListener("search", function () { if (!q.value) volverInicio(); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "/" && document.activeElement !== q && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); q.focus(); }
  });

  // pestañas del índice
  function mostrarPestana(doc) {
    $$(".pestana").forEach(function (b) { var on = b.getAttribute("data-tab") === doc; b.classList.toggle("activa", on); b.setAttribute("aria-selected", on ? "true" : "false"); });
    $$(".indice-doc").forEach(function (d) { d.hidden = d.getAttribute("data-doc") !== doc; });
  }
  $$(".pestana").forEach(function (b) { b.addEventListener("click", function () { mostrarPestana(b.getAttribute("data-tab")); }); });
  function abrirHash() {
    var h = decodeURIComponent(location.hash.slice(1));
    if (!h) return;
    if (DOCS[h]) { mostrarPestana(h); return; }
    var el = document.getElementById(h);
    if (!el) return;
    var cont = el.closest(".indice-doc"); if (cont) mostrarPestana(cont.getAttribute("data-doc"));
    var d = el.querySelector("details"); if (d) d.open = true;
    for (var p = el.parentElement; p; p = p.parentElement) if (p.tagName === "DETAILS") p.open = true;
    el.scrollIntoView({ block: "start" });
  }
  abrirHash(); window.addEventListener("hashchange", abrirHash);

  var inicial = params.get("q");
  if (inicial) { q.value = inicial; mostrarTodos(inicial); }
  else if ("requestIdleCallback" in window) requestIdleCallback(function () { cargarIndice(); });
})();
