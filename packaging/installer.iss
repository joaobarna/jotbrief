; Instalador do JB - Jot Brief (Inno Setup 6). Gera dist\JB-Jot-Brief-Setup-<versão>.exe a partir de dist\JotBrief\ (build.ps1).
; Uso: ISCC.exe /DAppVersion=0.1.0 packaging\installer.iss
#define AppName "JB - Jot Brief"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{B4F0A7C2-6D0E-4C55-9C1A-3F7A2E5D9B11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=João Barnabé
AppPublisherURL=https://joao-barnabe.com
DefaultDirName={autopf}\JotBrief
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; instala só para o usuário (sem pedir administrador)
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=JB-Jot-Brief-Setup-{#AppVersion}
SetupIconFile=..\src\jotbrief\assets\jotbrief.ico
UninstallDisplayIcon={app}\JotBrief.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; Flags: unchecked
Name: "startup"; Description: "Abrir o JB junto com o Windows"; Flags: unchecked

[Files]
Source: "..\dist\JotBrief\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\JotBrief.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\JotBrief.exe"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\JotBrief.exe"; Tasks: startup

[Run]
Filename: "{app}\JotBrief.exe"; Description: "Abrir o JB - Jot Brief"; Flags: nowait postinstall skipifsilent

; Os seus dados (reuniões, configuração, vozes) ficam fora da pasta do programa e NÃO são apagados ao desinstalar.
