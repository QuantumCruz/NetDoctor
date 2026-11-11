
; NetDoctor v1.0.0 Windows installer
; Compile with Inno Setup 6.

#define AppName "NetDoctor"
#define AppVersion "1.0.0"
#define AppPublisher "QuantumCruz"
#define AppExeName "NetDoctor.exe"

[Setup]
AppId={{68beb4c0-4ba4-5378-9e17-40c218469573}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/QuantumCruz/NetDoctor
AppSupportURL=https://github.com/QuantumCruz/NetDoctor/issues
AppUpdatesURL=https://github.com/QuantumCruz/NetDoctor/releases

DefaultDirName={localappdata}\Programs\NetDoctor
DefaultGroupName=NetDoctor

PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

OutputDir=..\release
OutputBaseFilename=NetDoctor-Setup-v1.0.0-x64
SetupIconFile=..\assets\netdoctor.ico
UninstallDisplayIcon={app}\NetDoctor.exe

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
DisableProgramGroupPage=yes

VersionInfoVersion=1.0.0.0
VersionInfoDescription=NetDoctor Windows Installer
VersionInfoProductName=NetDoctor

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\NetDoctor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\NetDoctor"; Filename: "{app}\NetDoctor.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\NetDoctor"; Filename: "{app}\NetDoctor.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\NetDoctor.exe"; Description: "Launch NetDoctor"; Flags: nowait postinstall skipifsilent
