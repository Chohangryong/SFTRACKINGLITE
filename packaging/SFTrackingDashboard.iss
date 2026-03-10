[Setup]
AppName=SF Tracking Dashboard
AppVersion=0.1.0
DefaultDirName={autopf}\SFTrackingDashboard
DefaultGroupName=SF Tracking Dashboard
OutputDir=..\build
OutputBaseFilename=SFTrackingDashboardSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "..\dist\SFTrackingDashboard.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\frontend\dist\*"; DestDir: "{app}\frontend\dist"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SF Tracking Dashboard"; Filename: "{app}\SFTrackingDashboard.exe"
Name: "{commondesktop}\SF Tracking Dashboard"; Filename: "{app}\SFTrackingDashboard.exe"

[Run]
Filename: "{app}\SFTrackingDashboard.exe"; Description: "Launch SF Tracking Dashboard"; Flags: nowait postinstall skipifsilent
