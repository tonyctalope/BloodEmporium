; Installer for this fork. Derived from installation_script.iss, with the author's absolute paths replaced
; by ones relative to the repository, and a distinct AppId / name / install directory so that it installs
; alongside an official Blood Emporium rather than upgrading or uninstalling it.

#define MyAppName "Blood Emporium (Fork)"
#define MyAppExeName "Blood Emporium.exe"
#define MyAppPublisher "IIInitiationnn, forked by tonyctalope"
#define MyAppURL "https://github.com/tonyctalope/BloodEmporium"

; Passed on the command line by the workflow, as absolute paths - Inno resolves relative paths against the
; directory holding this script, not the working directory:
;   ISCC /DMyAppVersion=... /DSourceDir=... /DIconFile=... /O<output dir>

[Setup]
; deliberately NOT the upstream AppId {{090DC74C-55C3-4F44-B473-5DA6D8813E68}
AppId={{581315AB-78DC-4E92-82D2-616B96132D8D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Blood Emporium Fork
AllowNoIcons=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=BloodEmporiumInstaller-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
SetupIconFile={#IconFile}
UpdateUninstallLogAppName=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Dirs]
; the app writes into these at runtime; Inno does not copy empty directories
Name: "{app}\logs"
Name: "{app}\exports"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
