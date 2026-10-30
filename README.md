# Compactador PDF

El programa abre una página en tu navegador. Ahí arrastras archivos (Word, PDF o imágenes), los ordenas, y el programa los convierte a PDF, los une en ese orden y los comprime.

## Requisitos para el usuario final

- **LibreOffice** (gratis, libreoffice.org): necesario para convertir Word a PDF.
- **Ghostscript** (opcional, ghostscript.com): necesario para la compresión fuerte. Sin él, solo se aplica compresión sin pérdida.

## Probar en tu computadora (Mac o Windows)

1. Instala Python 3.11 o superior (python.org).
2. Abre una terminal en esta carpeta y ejecuta:

```
pip install -r requirements.txt
python app.py
```

Se abrirá el navegador en la página del programa. Para cerrarlo, usa el botón **Cerrar programa** (o cierra la terminal).

## Obtener el ejecutable sin compilar en tu computadora (recomendado)

Incluí un flujo de GitHub Actions en `.github/workflows/build.yml`. GitHub compila la versión de Windows y la de Mac:

1. Crea un repositorio privado en github.com y sube esta carpeta.
2. Ve a la pestaña **Actions**, elige **Compilar Compactador PDF** y pulsa **Run workflow**. (También se ejecuta solo al subir cambios.)
3. Cuando termine (unos minutos), abre la ejecución y descarga los artefactos:
   - **CompactadorPDF-Windows**: contiene `Compactador PDF.exe`.
   - **CompactadorPDF-Mac**: contiene `CompactadorPDF-mac.zip`. Descomprímelo para obtener la app.

Al abrirlos por primera vez:
- **Windows:** SmartScreen puede advertir que la app no es reconocida. Elige **Más información** → **Ejecutar de todas formas**.
- **Mac:** haz clic derecho sobre la app y elige **Abrir**.

## Compartir con otras personas (sin terminal)

1. En GitHub, ve a **Releases** → **Draft a new release**.
2. En **Choose a tag**, escribe `v1.0` y elige **Create new tag**.
3. Dale un título (por ejemplo, "Compactador PDF 1.0") y pulsa **Publish release**.
4. GitHub compilará la app y adjuntará `Compactador PDF.exe` (Windows) y `CompactadorPDF-mac.zip` (Mac) a esa versión. Tarda unos minutos.
5. Comparte el enlace de la página de Releases. Quien lo use solo descarga el archivo de su sistema y lo abre.

Cada persona que vaya a convertir Word debe instalar **LibreOffice** (libreoffice.org). El resto funciona sin instalar nada más.

Para que no aparezcan avisos de seguridad (SmartScreen en Windows o el bloqueo en Mac), hay que firmar la app con certificados de pago. Sin firma, la primera vez hay que seguir los pasos de la sección anterior.

## Compilar tú mismo

Hay que compilarlo en cada sistema: el `.app` se hace en Mac y el `.exe` en Windows.

**Mac**

```
pyinstaller --windowed --name "Compactador PDF" app.py
```

Resultado: `dist/Compactador PDF.app`. La primera vez, si macOS lo bloquea, haz clic derecho sobre la app y elige **Abrir**.

**Windows**

```
pyinstaller --windowed --onefile --name "Compactador PDF" app.py
```

Resultado: `dist\Compactador PDF.exe`.

## Uso

1. Arrastra los archivos a la página (o haz clic en la zona para elegirlos).
2. Ordénalos con ▲ ▼ o arrastrando dentro de la lista.
3. Elige el nivel de compresión.
4. Pulsa **Crear PDF combinado y comprimido** y descarga el resultado cuando termine.
