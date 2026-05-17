; Inno Setup script for OpenScenarioDrive
; Run: ISCC setup.iss  (from the repo root, or adjust SourceDir below)
;
; GitHub Actions sets the APP_VERSION env var; locally it falls back to "dev".

#define MyAppName      "OpenScenarioDrive"
#define MyAppPublisher "Hamid Ebadi / Hamid"
#define MyAppURL       "https://github.com/ebadi/OpenScenarioDrive"
#define MyAppExeName   "OpenScenarioDrive.exe"
#define MyAppVersion   GetEnv("APP_VERSION")
#if MyAppVersion == ""
  #define MyAppVersion "dev"
#endif

[Setup]
AppId={{A3B7C2D1-E4F5-4A6B-8C9D-0E1F2A3B4C5D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Output is relative to this .iss file (installer/windows/), so just "Output"
OutputDir=Output
OutputBaseFilename=OpenScenarioDrive-Windows-Setup
SetupIconFile=..\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\..\LICENSE.txt
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; All PyInstaller output - the entire collected folder
; Path is relative to this .iss file - go up two levels to reach the repo root
Source: "..\..\dist\OpenScenarioDrive\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE.txt";            DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\CREDIT.md";              DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
