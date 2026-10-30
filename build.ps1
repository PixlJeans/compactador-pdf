#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$App   = "Compactador PDF"
$Exe   = "CompactadorPDF"
$Ver   = "1.0.0"
$Root  = $PSScriptRoot
Set-Location $Root

function Paso($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "    $t" -ForegroundColor Green }

# ---------- 1. Python ----------
Paso "Comprobando Python"
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (!(Test-Path $py)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $py = $cmd.Source }
    else {
        Write-Host "Instalando Python 3.12..." -ForegroundColor Yellow
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
        $py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    }
}
if (!(Test-Path $py)) { throw "No se encontró Python. Instálalo desde python.org y vuelve a ejecutar." }
Ok (& $py --version)

# ---------- 2. Dependencias Python ----------
Paso "Instalando dependencias de Python"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet pyinstaller pywebview flask pypdf pillow
Ok "pyinstaller, pywebview, flask, pypdf, pillow"

# ---------- 3. Ghostscript y LibreOffice ----------
Paso "Comprobando Ghostscript y LibreOffice"
$gs = Get-ChildItem "$env:ProgramFiles\gs" -Directory -ErrorAction SilentlyContinue |
      Sort-Object Name -Descending | Select-Object -First 1
if (!$gs) {
    Write-Host "    Instalando Ghostscript..." -ForegroundColor Yellow
    winget install -e --id ArtifexSoftware.GhostScript --accept-package-agreements --accept-source-agreements --silent
}
$lo = "$env:ProgramFiles\LibreOffice\program\soffice.exe"
if (!(Test-Path $lo)) {
    Write-Host "    Instalando LibreOffice (tarda varios minutos)..." -ForegroundColor Yellow
    winget install -e --id TheDocumentFoundation.LibreOffice --accept-package-agreements --accept-source-agreements --silent
}
Ok "Ghostscript y LibreOffice listos"

# ---------- 4. Ejecutable ----------
Paso "Generando el ejecutable con PyInstaller"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
& $py -m PyInstaller --noconfirm --windowed --name $Exe app.py | Out-Null
if (!(Test-Path "dist\$Exe\$Exe.exe")) { throw "PyInstaller no generó el ejecutable." }
Ok "dist\$Exe\$Exe.exe"

# ---------- 5. Inno Setup ----------
Paso "Comprobando Inno Setup"
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (!(Test-Path $iscc)) {
    $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
}
if (!(Test-Path $iscc)) {
    Write-Host "    Instalando Inno Setup..." -ForegroundColor Yellow
    winget install -e --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements --silent
    $iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
}
if (!(Test-Path $iscc)) { throw "No se encontró ISCC.exe. Abre Inno Setup una vez y repite." }
Ok $iscc

# ---------- 6. Instalador ----------
Paso "Compilando el instalador"
New-Item -ItemType Directory -Force instaladores | Out-Null
& $iscc installer.iss | Out-Null
$setup = Get-ChildItem instaladores -Filter "*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (!$setup) { throw "El instalador no se generó." }
Ok $setup.FullName

Write-Host "`nListo. Instalador: $($setup.FullName)" -ForegroundColor Green
Write-Host "MB: $([math]::Round($setup.Length/1MB,1))" -ForegroundColor Green
