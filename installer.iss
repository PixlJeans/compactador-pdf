#define MiApp "Compactador PDF"
#define MiVersion "1.0.0"
#define MiExe "CompactadorPDF.exe"

[Setup]
AppId={{8F3C2A71-4B6D-4E92-9A15-7C2D5E8B1F04}
AppName={#MiApp}
AppVersion={#MiVersion}
AppPublisher=PixlJeans
DefaultDirName={autopf}\{#MiApp}
DefaultGroupName={#MiApp}
DisableProgramGroupPage=yes
OutputDir=instaladores
OutputBaseFilename=CompactadorPDF-{#MiVersion}-win64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MiExe}
WizardImageStretch=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\CompactadorPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MiApp}"; Filename: "{app}\{#MiExe}"
Name: "{group}\Desinstalar {#MiApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MiApp}"; Filename: "{app}\{#MiExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MiExe}"; Description: "Abrir {#MiApp}"; Flags: nowait postinstall skipifsilent
