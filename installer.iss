; Instalador de Windows para Compactador PDF (Inno Setup 6)

[Setup]
AppName=Compactador PDF
AppVersion=1.1
AppPublisher=PixlJeans
DefaultDirName={autopf}\Compactador PDF
DefaultGroupName=Compactador PDF
OutputDir=dist
OutputBaseFilename=CompactadorPDF-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\Compactador PDF.exe

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\Compactador PDF.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Compactador PDF"; Filename: "{app}\Compactador PDF.exe"
Name: "{autodesktop}\Compactador PDF"; Filename: "{app}\Compactador PDF.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Compactador PDF.exe"; Description: "Abrir Compactador PDF"; Flags: nowait postinstall skipifsilent
