; Inno Setup script for MemoryNest Sync
; Download Inno Setup: https://jrsoftware.org/isinfo.php
; After building with build_installer.bat, run this .iss file in Inno Setup Compiler

[Setup]
AppName=MemoryNest Sync
AppVersion=1.0.0
AppPublisher=ZigGaZa Studio
DefaultDirName={autopf}\MemoryNest Sync
DefaultGroupName=MemoryNest Sync
OutputDir=installer_output
OutputBaseFilename=MemoryNestSync_Setup_v1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\MemoryNest Sync.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; Include all files from PyInstaller output
Source: "dist\MemoryNest Sync\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MemoryNest Sync"; Filename: "{app}\MemoryNest Sync.exe"
Name: "{group}\Uninstall MemoryNest Sync"; Filename: "{uninstallexe}"
Name: "{commondesktop}\MemoryNest Sync"; Filename: "{app}\MemoryNest Sync.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MemoryNest Sync.exe"; Description: "Launch MemoryNest Sync"; Flags: nowait postinstall skipifsilent
