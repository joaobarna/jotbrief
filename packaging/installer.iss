; Instalador do SaidKeep (Inno Setup 6). Gera dist\SaidKeep-Setup-<versão>.exe a partir de dist\SaidKeep\ (build.ps1).
; Uso: ISCC.exe /DAppVersion=0.1.0 packaging\installer.iss
#define AppName "SaidKeep"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

; Os seus dados (reuniões, configuração, vozes) ficam fora da pasta do programa e NÃO são apagados ao desinstalar.

[Setup]
AppId={{B4F0A7C2-6D0E-4C55-9C1A-3F7A2E5D9B11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=João Barnabé
AppPublisherURL=https://joao-barnabe.com
DefaultDirName={autopf}\SaidKeep
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; instala só para o usuário (sem pedir administrador)
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=SaidKeep-Setup-{#AppVersion}
SetupIconFile=..\src\saidkeep\assets\saidkeep.ico
UninstallDisplayIcon={app}\SaidKeep.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; Flags: unchecked
Name: "startup"; Description: "Abrir o SaidKeep junto com o Windows"; Flags: unchecked

[Files]
Source: "..\dist\SaidKeep\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\SaidKeep.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\SaidKeep.exe"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\SaidKeep.exe"; Tasks: startup

[InstallDelete]
; atualização de quem tinha o app com o nome antigo (JB - Jot Brief): tira o executável e os atalhos velhos
Type: files; Name: "{app}\JotBrief.exe"
Type: files; Name: "{autoprograms}\JB - Jot Brief.lnk"
Type: files; Name: "{autodesktop}\JB - Jot Brief.lnk"
Type: files; Name: "{userstartup}\JB - Jot Brief.lnk"

[Run]
Filename: "{app}\SaidKeep.exe"; Description: "Abrir o SaidKeep"; Flags: nowait postinstall skipifsilent
; atualização feita de dentro do app: o app se fechou e o instalador o reabre ao terminar
Filename: "{app}\SaidKeep.exe"; Flags: nowait; Check: RelaunchRequested

[Code]
function RelaunchRequested: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;
