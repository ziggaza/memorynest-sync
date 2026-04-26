; Inno Setup script for MemoryNest Sync
; Download Inno Setup: https://jrsoftware.org/isinfo.php
;
; This file is REWRITTEN automatically by build_installer.bat with the
; current APP_VERSION extracted from main.py — do not hand-edit the
; AppVersion or OutputBaseFilename lines (they will be overwritten on
; every build). Everything else is preserved.

[Setup]
AppName=MemoryNest Sync
AppVersion=1.3.3
AppPublisher=ZigGaZa Studio
AppPublisherURL=https://ziggaza.github.io/memorynest-sync/
DefaultDirName={autopf}\MemoryNest Sync
DefaultGroupName=MemoryNest Sync
OutputDir=installer_output
OutputBaseFilename=MemoryNestSync_Setup_v1.3.3
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\MemoryNest Sync.exe

; Allow user to choose install dir (default: Program Files), and let them
; install for the current user only without admin elevation if they prefer.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Runtime data (logs, settings, sound cache, user config) is written to
; %LOCALAPPDATA%\MemoryNest Sync\ — never inside the install dir — so the
; app works regardless of where the user installs it.

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

[UninstallDelete]
; Note: we deliberately do NOT delete %LOCALAPPDATA%\MemoryNest Sync\ on
; uninstall — user's logs / settings / event rules persist for future
; reinstall. They can be cleared manually from %LOCALAPPDATA% if desired.
