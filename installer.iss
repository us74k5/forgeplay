[Setup]
AppName=YT Local Playback
AppVersion=1.0
DefaultDirName={pf}\YTLocalPlayback
DefaultGroupName=YT Local Playback
OutputDir=D:\AI\installer_output
OutputBaseFilename=YTLocalPlaybackSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "D:\AI\release\helper\YTLocalHelper.exe"; DestDir: "{app}"
Source: "D:\AI\release\extension\chrome_extension\*"; DestDir: "{app}\chrome_extension"; Flags: recursesubdirs

[Icons]
Name: "{group}\YT Local Helper"; Filename: "{app}\YTLocalHelper.exe"
Name: "{group}\Install Chrome Extension"; Filename: "chrome.exe"; Parameters: "chrome://extensions"

[Run]
Filename: "{app}\YTLocalHelper.exe"; Description: "Launch Helper"; Flags: postinstall nowait

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
 if CurStep=ssPostInstall then
 begin
   MsgBox(
   'In Chrome: enable Developer Mode, click Load Unpacked, select the installed chrome_extension folder.',
   mbInformation,
   MB_OK);
 end;
end;