[Setup]
AppId={{7D770166-86C6-44D6-B291-4D8D6F5CC8C8}}
AppName=SF Express Tracking Lite
AppVersion=0.1.1
DefaultDirName={localappdata}\Programs\SFTrackingLite
DefaultGroupName=SF Express Tracking Lite
OutputDir=..\build
OutputBaseFilename=SFTrackingLiteSetup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Files]
Source: "..\dist\SFTrackingLite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SF Express Tracking Lite"; Filename: "{app}\SFTrackingLite.exe"
Name: "{autodesktop}\SF Express Tracking Lite"; Filename: "{app}\SFTrackingLite.exe"

[Run]
Filename: "{app}\SFTrackingLite.exe"; Description: "SF Express Tracking Lite 실행"; Flags: nowait postinstall skipifsilent
