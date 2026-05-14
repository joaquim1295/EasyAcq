; Inno Setup 6 — gera instalador a partir de dist\EasyAcq (apos PyInstaller).
; Instalacao por utilizador (sem admin): %LocalAppData%\Programs\EasyAcq
; Compilar: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\EasyAcq.iss
; (ou scripts\build_release.ps1 -Installer)

#define MyAppName "EasyAcq"
#define MyAppVersion "0.2.1"
#define MyAppPublisher "EasyAcq"
#define MyAppExeName "EasyAcq.exe"
#define DistDir "..\\dist\\EasyAcq"
#define MyIcon "..\\assets\\easyacq.ico"

[Setup]
AppId={{E8A3C2B1-9F0D-4E5A-B6C7-D8E9F0A1B2C3}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Windows 10 (64 bits) minimo — ver https://jrsoftware.org/ishelp/index.php?topic=winvernotes
MinVersion=10.0.10240
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableDirPage=no
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=EasyAcq_Setup_{#MyAppVersion}
SetupIconFile={#MyIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]

function VCRedist64Present: Boolean;
begin
  Result := RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64');
end;

function VisaLikelyPresent: Boolean;
begin
  Result := FileExists(ExpandConstant('{sys}\visa32.dll'))
    or RegKeyExists(HKLM64, 'SOFTWARE\IVI Foundation\VISA\');
end;

function InitializeSetup: Boolean;
var
  Err: Integer;
begin
  Result := True;
  if not VCRedist64Present then
  begin
    if MsgBox(
      'Nao foi detetado o «Microsoft Visual C++ Redistributable 2015-2022» (x64).' + #13#10 +
      'Sem este runtime o EasyAcq pode nao arrancar apos a instalacao.' + #13#10 + #13#10 +
      'Abrir a pagina oficial da Microsoft para descarregar o instalador?',
      mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist', '', '', SW_SHOWNORMAL, ewNoWait, Err);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not VisaLikelyPresent then
      MsgBox(
        'Nao foi detetado o NI-VISA (VISA Runtime).' + #13#10 +
        'O multimetro SDM3055 precisa do NI-VISA instalado.' + #13#10 + #13#10 +
        'Descarregue em:' + #13#10 +
        'https://www.ni.com/en/support/downloads/drivers.download-ni-visa.html',
        mbInformation, MB_OK);
  end;
end;
