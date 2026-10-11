; Inno Setup script for Euan Paint. Build "dist\Euan Paint.exe" first
; (build_windows.bat), then run build_installer.bat.

#define AppName "Euan Paint"
#define AppVersion "1.0.0"
#define AppExe "Euan Paint.exe"

[Setup]
AppId={{2BC79E4B-FEE5-4B50-BE53-B169F069904C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Salbrox
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
; Per-user install: no admin prompt needed.
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Euan Paint Setup
SetupIconFile=euan-paint-icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
; Close a running copy (it ignores normal close requests) so files can be replaced.
CloseApplications=force
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Put Euan Paint on the desktop"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start Euan Paint now (exit: hold Ctrl+Shift+Q for 3 seconds)"; Flags: nowait postinstall skipifsilent unchecked

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /T /IM ""{#AppExe}"""; Flags: runhidden; RunOnceId: "KillApp"
