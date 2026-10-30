"""Compactador PDF: sube Word/imágenes/PDF desde el navegador, los convierte, los une en el orden elegido y los comprime."""
import atexit
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file
from pypdf import PdfReader, PdfWriter
from PIL import Image

WORD_EXT = {".doc", ".docx", ".odt", ".rtf", ".txt"}
IMG_EXT = {".jpg", ".jpeg", ".png"}
PDF_EXT = {".pdf"}
SUPPORTED = WORD_EXT | IMG_EXT | PDF_EXT

# Clave que llega desde la página -> preset de Ghostscript (None = sin pérdida)
PRESETS = {
    "screen": "/screen",   # 72 dpi, máxima compresión
    "ebook": "/ebook",     # 150 dpi, equilibrado
    "printer": "/printer", # 300 dpi, alta calidad
    "none": None,          # sin pérdida
}

NO_WINDOW = {"creationflags": 0x08000000} if sys.platform == "win32" else {}


# ---------------- Motor de conversión ----------------

def find_soffice():
    candidatos = []
    if sys.platform == "darwin":
        candidatos.append("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    elif sys.platform == "win32":
        for var in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(var)
            if base:
                candidatos.append(os.path.join(base, "LibreOffice", "program", "soffice.exe"))
    for nombre in ("soffice", "libreoffice"):
        ruta = shutil.which(nombre)
        if ruta:
            candidatos.insert(0, ruta)
    for c in candidatos:
        if os.path.exists(c):
            return c
    return None


def find_ghostscript():
    if sys.platform == "win32":
        nombres = ("gswin64c", "gswin32c")
        extra = []
    else:
        nombres = ("gs",)
        extra = ["/opt/homebrew/bin/gs", "/usr/local/bin/gs"]
    for nombre in nombres:
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    for ruta in extra:
        if os.path.exists(ruta):
            return ruta
    return None


def word_a_pdf(origen, carpeta, soffice):
    perfil = tempfile.mkdtemp(prefix="lo_")
    cmd = [
        soffice,
        f"-env:UserInstallation={Path(perfil).as_uri()}",
        "--headless", "--convert-to", "pdf",
        "--outdir", carpeta, origen,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300, **NO_WINDOW)
    finally:
        shutil.rmtree(perfil, ignore_errors=True)
    salida = Path(carpeta) / (Path(origen).stem + ".pdf")
    if not salida.exists():
        raise RuntimeError("No se pudo convertir un archivo de Word.")
    return str(salida)


def imagen_a_pdf(origen, destino):
    with Image.open(origen) as im:
        im.convert("RGB").save(destino, "PDF", resolution=150.0)


def comprimir(origen, destino, gs, preset):
    """Devuelve el motor usado: 'ghostscript' o 'pypdf' (respaldo sin pérdida)."""
    if gs and preset:
        cmd = [
            gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5",
            f"-dPDFSETTINGS={preset}", "-dNOPAUSE", "-dBATCH", "-dQUIET",
            f"-sOutputFile={destino}", origen,
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=900, **NO_WINDOW)
        if r.returncode == 0 and os.path.exists(destino):
            return "ghostscript"

    lector = PdfReader(origen)
    escritor = PdfWriter(clone_from=lector)
    for pagina in escritor.pages:
        pagina.compress_content_streams()
    escritor.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    with open(destino, "wb") as f:
        escritor.write(f)
    return "pypdf"


def generar_pdf(archivos, destino, preset, progreso):
    """archivos: lista de dicts con 'path' y 'name', en el orden final."""
    gs = find_ghostscript()
    soffice = None
    trabajo = tempfile.mkdtemp(prefix="compactador_")
    try:
        partes = []
        total = len(archivos)
        for i, arch in enumerate(archivos):
            ruta, nombre = arch["path"], arch["name"]
            ext = Path(nombre).suffix.lower()
            progreso(f"Procesando {i + 1}/{total}: {nombre}", 0.8 * i / total)
            if ext in PDF_EXT:
                partes.append(ruta)
            elif ext in IMG_EXT:
                pdf = os.path.join(trabajo, f"img_{i}.pdf")
                imagen_a_pdf(ruta, pdf)
                partes.append(pdf)
            else:
                if soffice is None:
                    soffice = find_soffice()
                    if soffice is None:
                        raise RuntimeError(
                            "Para convertir Word necesitas instalar LibreOffice (gratuito, libreoffice.org).")
                carpeta = os.path.join(trabajo, f"w_{i}")
                os.makedirs(carpeta)
                partes.append(word_a_pdf(ruta, carpeta, soffice))

        progreso("Uniendo PDFs en el orden elegido...", 0.85)
        unido = os.path.join(trabajo, "unido.pdf")
        escritor = PdfWriter()
        for p in partes:
            escritor.append(p)
        with open(unido, "wb") as f:
            escritor.write(f)

        progreso("Comprimiendo...", 0.9)
        return comprimir(unido, destino, gs, preset)
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)


# ---------------- Servidor web ----------------

app = Flask(__name__)
TRABAJO = tempfile.mkdtemp(prefix="compactador_web_")
atexit.register(shutil.rmtree, TRABAJO, True)
ARCHIVOS = {}  # id -> {"path", "name", "size"}
TRABAJOS = {}  # id -> estado del PDF que se está generando


@app.get("/")
def index():
    return Response(HTML, mimetype="text/html")


@app.get("/api/config")
def config():
    return jsonify(libreoffice=find_soffice() is not None, ghostscript=find_ghostscript() is not None)


@app.post("/api/subir")
def subir():
    ok, ignorados = [], []
    for f in request.files.getlist("files"):
        nombre = Path(f.filename or "").name
        ext = Path(nombre).suffix.lower()
        if not nombre or ext not in SUPPORTED:
            ignorados.append(nombre or "(sin nombre)")
            continue
        fid = uuid.uuid4().hex
        ruta = os.path.join(TRABAJO, fid + ext)
        f.save(ruta)
        size = os.path.getsize(ruta)
        ARCHIVOS[fid] = {"path": ruta, "name": nombre, "size": size}
        ok.append({"id": fid, "name": nombre, "size": size})
    return jsonify(archivos=ok, ignorados=ignorados)


@app.post("/api/crear")
def crear():
    data = request.get_json(force=True) or {}
    ids = data.get("ids") or []
    clave = data.get("preset", "ebook")
    if not ids:
        return jsonify(error="Agrega al menos un archivo."), 400
    if clave not in PRESETS:
        return jsonify(error="Nivel de compresión no válido."), 400
    try:
        lista = [ARCHIVOS[i] for i in ids]
    except KeyError:
        return jsonify(error="Algún archivo ya no está disponible. Vuelve a agregarlo."), 400

    job = uuid.uuid4().hex
    salida = os.path.join(TRABAJO, job + ".pdf")
    TRABAJOS[job] = {"estado": "procesando", "mensaje": "Iniciando...", "progreso": 0.0,
                     "salida": salida, "mb": 0.0, "aviso": ""}
    threading.Thread(target=_correr, args=(job, lista, salida, PRESETS[clave]), daemon=True).start()
    return jsonify(job=job)


def _correr(job, lista, salida, preset):
    t = TRABAJOS[job]

    def progreso(texto, fraccion):
        t["mensaje"] = texto
        t["progreso"] = fraccion

    try:
        motor = generar_pdf(lista, salida, preset, progreso)
        t.update(estado="listo", mensaje="Listo", progreso=1.0,
                 mb=os.path.getsize(salida) / 1048576)
        if preset and motor != "ghostscript":
            t["aviso"] = ("No se encontró Ghostscript, así que solo se aplicó compresión sin pérdida. "
                          "Instálalo (ghostscript.com) para reducir más el tamaño.")
    except Exception as ex:
        t.update(estado="error", mensaje=str(ex))


@app.get("/api/estado/<job>")
def estado(job):
    t = TRABAJOS.get(job)
    if not t:
        abort(404)
    return jsonify(estado=t["estado"], mensaje=t["mensaje"], progreso=t["progreso"],
                   mb=t["mb"], aviso=t["aviso"])


@app.get("/api/descargar/<job>")
def descargar(job):
    t = TRABAJOS.get(job)
    if not t or t["estado"] != "listo":
        abort(404)
    return send_file(t["salida"], as_attachment=True,
                     download_name="combinado.pdf", mimetype="application/pdf")


@app.post("/api/salir")
def salir():
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return jsonify(ok=True)


HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compactador PDF</title>
<style>
:root{--bg:#f4f6f8;--card:#fff;--ac:#2563eb;--tx:#1f2937;--mut:#6b7280;--bd:#d1d5db}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--tx)}
main{max-width:720px;margin:32px auto;padding:0 16px 40px}
header{display:flex;justify-content:space-between;align-items:center}
h1{font-size:24px;margin:0}
h2{font-size:16px;margin:24px 0 8px}
.zona{border:2px dashed var(--bd);border-radius:12px;padding:28px;text-align:center;background:var(--card);cursor:pointer;color:var(--mut)}
.zona.over{border-color:var(--ac);background:#eff6ff;color:var(--ac)}
#lista{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--bd);border-radius:12px;min-height:56px;overflow:hidden}
#lista li{display:flex;align-items:center;gap:10px;padding:10px 12px;border-bottom:1px solid #eee;cursor:grab;user-select:none}
#lista li:last-child{border-bottom:none}
#lista li.arrastrando{opacity:.4}
#lista li.destino{background:#eff6ff}
#lista li.vacio{color:var(--mut);justify-content:center;cursor:default}
.num{width:26px;height:26px;flex:none;border-radius:50%;background:#e5e7eb;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600}
.nombre{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tam{color:var(--mut);font-size:13px;white-space:nowrap}
.acc{display:flex;gap:4px}
button{font:inherit;border:1px solid var(--bd);background:var(--card);border-radius:8px;padding:6px 10px;cursor:pointer;color:var(--tx)}
button:hover{background:#f9fafb}
button.primario{background:var(--ac);color:#fff;border-color:var(--ac);width:100%;padding:12px;font-size:16px}
button:disabled{opacity:.5;cursor:default}
select{font:inherit;width:100%;padding:10px;border-radius:8px;border:1px solid var(--bd);background:#fff}
.barra{height:10px;background:#e5e7eb;border-radius:6px;overflow:hidden;margin-top:12px}
.barra div{height:100%;width:0;background:var(--ac);transition:width .2s}
#estado{margin-top:10px;color:var(--mut);min-height:20px}
.aviso{background:#fef3c7;color:#92400e;border-radius:8px;padding:10px 12px;margin-bottom:12px}
a.descargar{display:inline-block;margin-top:10px;background:#16a34a;color:#fff;text-decoration:none;padding:10px 16px;border-radius:8px;font-weight:600}
.pequeno{font-size:13px;color:var(--mut)}
</style>
</head>
<body>
<main>
  <header>
    <h1>Compactador PDF</h1>
    <button id="salir" title="Cierra el programa">Cerrar programa</button>
  </header>
  <div id="avisos"></div>

  <h2>1. Agrega tus archivos</h2>
  <div id="zona" class="zona">Arrastra aquí Word, PDF o imágenes<br><span class="pequeno">o haz clic para elegirlos</span></div>
  <input id="input" type="file" multiple accept=".doc,.docx,.odt,.rtf,.txt,.pdf,.jpg,.jpeg,.png" hidden>

  <h2>2. Orden del PDF (arrastra un elemento o usa ▲ ▼)</h2>
  <ul id="lista"></ul>

  <h2>3. Nivel de compresión</h2>
  <select id="preset">
    <option value="ebook" selected>Equilibrado (150 dpi)</option>
    <option value="screen">Máxima compresión (72 dpi)</option>
    <option value="printer">Alta calidad (300 dpi)</option>
    <option value="none">Sin pérdida de calidad</option>
  </select>

  <h2>4. Crear PDF</h2>
  <button id="crear" class="primario" disabled>Crear PDF combinado y comprimido</button>
  <div class="barra"><div id="barra"></div></div>
  <div id="estado">Listo.</div>
  <div id="resultado"></div>
</main>

<script>
const zona = document.getElementById('zona');
const input = document.getElementById('input');
const lista = document.getElementById('lista');
const crear = document.getElementById('crear');
const estado = document.getElementById('estado');
const barra = document.getElementById('barra');
const resultado = document.getElementById('resultado');
const avisos = document.getElementById('avisos');

let items = [];      // {id, name, size}
let dragIdx = null;  // índice del elemento que se reordena

function fmt(b){ return b > 1048576 ? (b/1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b/1024)) + ' KB'; }

function render(){
  lista.innerHTML = '';
  if(!items.length){
    const li = document.createElement('li');
    li.className = 'vacio';
    li.textContent = 'Aún no hay archivos';
    lista.appendChild(li);
  }
  items.forEach((it, i) => {
    const li = document.createElement('li');
    li.draggable = true;
    li.dataset.i = i;
    li.innerHTML = '<span class="num"></span><span class="nombre"></span><span class="tam"></span>' +
      '<span class="acc"><button data-a="up" title="Subir">▲</button>' +
      '<button data-a="down" title="Bajar">▼</button>' +
      '<button data-a="del" title="Quitar">✕</button></span>';
    li.querySelector('.num').textContent = i + 1;
    li.querySelector('.nombre').textContent = it.name;
    li.querySelector('.tam').textContent = fmt(it.size);
    lista.appendChild(li);
  });
  crear.disabled = !items.length;
}

function move(a, b){
  const [x] = items.splice(a, 1);
  items.splice(b, 0, x);
  render();
}

// Botones ▲ ▼ ✕
lista.addEventListener('click', e => {
  const b = e.target.closest('button');
  if(!b) return;
  const i = +b.closest('li').dataset.i;
  if(b.dataset.a === 'up' && i > 0) move(i, i - 1);
  if(b.dataset.a === 'down' && i < items.length - 1) move(i, i + 1);
  if(b.dataset.a === 'del'){ items.splice(i, 1); render(); }
});

// Reordenar arrastrando dentro de la lista
lista.addEventListener('dragstart', e => {
  const li = e.target.closest('li[data-i]');
  if(!li) return;
  dragIdx = +li.dataset.i;
  li.classList.add('arrastrando');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', '');
});
lista.addEventListener('dragover', e => {
  if(dragIdx === null) return;
  e.preventDefault();
  lista.querySelectorAll('.destino').forEach(x => x.classList.remove('destino'));
  const li = e.target.closest('li[data-i]');
  if(li) li.classList.add('destino');
});
lista.addEventListener('drop', e => {
  if(dragIdx === null) return;
  e.preventDefault();
  const li = e.target.closest('li[data-i]');
  const origen = dragIdx;
  dragIdx = null;
  if(li){
    const j = +li.dataset.i;
    if(j !== origen) move(origen, j);
  }
});
lista.addEventListener('dragend', () => { dragIdx = null; render(); });

// Subir archivos: arrastrados desde el escritorio (en cualquier parte de la página) o elegidos con clic
const hayArchivos = e => e.dataTransfer && [...e.dataTransfer.types].includes('Files');
window.addEventListener('dragover', e => { if(hayArchivos(e)) e.preventDefault(); });
window.addEventListener('drop', e => {
  if(!hayArchivos(e)) return;
  e.preventDefault();
  zona.classList.remove('over');
  subir(e.dataTransfer.files);
});
zona.addEventListener('dragenter', e => { if(hayArchivos(e)) zona.classList.add('over'); });
zona.addEventListener('dragleave', () => zona.classList.remove('over'));
zona.addEventListener('click', () => input.click());
input.addEventListener('change', () => { subir(input.files); input.value = ''; });

async function subir(files){
  if(!files || !files.length) return;
  const fd = new FormData();
  for(const f of files) fd.append('files', f, f.name);
  estado.textContent = `Subiendo ${files.length} archivo(s)...`;
  try{
    const r = await fetch('/api/subir', {method: 'POST', body: fd});
    const data = await r.json();
    if(!r.ok) throw new Error(data.error || 'No se pudieron subir los archivos.');
    items.push(...data.archivos);
    render();
    let msg = `${data.archivos.length} archivo(s) agregado(s).`;
    if(data.ignorados.length) msg += ` No compatibles (ignorados): ${data.ignorados.join(', ')}.`;
    estado.textContent = msg;
  }catch(err){
    estado.textContent = 'Error: ' + err.message;
  }
}

crear.addEventListener('click', async () => {
  crear.disabled = true;
  resultado.innerHTML = '';
  barra.style.width = '0%';
  try{
    const r = await fetch('/api/crear', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ids: items.map(x => x.id), preset: document.getElementById('preset').value})
    });
    const data = await r.json();
    if(!r.ok) throw new Error(data.error || 'No se pudo iniciar.');
    seguir(data.job);
  }catch(err){
    estado.textContent = 'Error: ' + err.message;
    crear.disabled = false;
  }
});

function seguir(job){
  const t = setInterval(async () => {
    try{
      const r = await fetch('/api/estado/' + job);
      const s = await r.json();
      estado.textContent = s.mensaje;
      barra.style.width = (s.progreso * 100) + '%';
      if(s.estado === 'listo'){
        clearInterval(t);
        barra.style.width = '100%';
        const a = document.createElement('a');
        a.className = 'descargar';
        a.href = '/api/descargar/' + job;
        a.textContent = `Descargar PDF (${s.mb.toFixed(1)} MB)`;
        resultado.appendChild(a);
        if(s.aviso){
          const p = document.createElement('div');
          p.className = 'aviso';
          p.style.marginTop = '12px';
          p.textContent = s.aviso;
          resultado.appendChild(p);
        }
        estado.textContent = 'PDF listo.';
        crear.disabled = false;
      }
      if(s.estado === 'error'){
        clearInterval(t);
        estado.textContent = 'Error: ' + s.mensaje;
        crear.disabled = false;
      }
    }catch(err){
      clearInterval(t);
      estado.textContent = 'Se perdió la conexión con el programa.';
      crear.disabled = false;
    }
  }, 400);
}

document.getElementById('salir').addEventListener('click', async () => {
  if(!confirm('¿Cerrar el Compactador PDF?')) return;
  try{ await fetch('/api/salir', {method: 'POST'}); }catch(e){}
  document.body.innerHTML = '<main><h1>Programa cerrado</h1><p>Puedes cerrar esta pestaña.</p></main>';
});

fetch('/api/config').then(r => r.json()).then(c => {
  if(!c.libreoffice){
    const d = document.createElement('div');
    d.className = 'aviso';
    d.textContent = 'Para convertir Word necesitas instalar LibreOffice (gratis, libreoffice.org).';
    avisos.appendChild(d);
  }
}).catch(() => {});
render();
</script>
</body>
</html>
"""


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    port = puerto_libre()
    url = f"http://127.0.0.1:{port}"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"Compactador PDF abierto en {url}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
