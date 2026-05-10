#ifndef MyAppVersion
#define MyAppVersion "1.0.0"
#endif

#define MyAppName "ForgePlay Helper"
#define MyAppExeName "ForgePlayHelper.exe"
#define MyAppPublisher "ForgePlay"
#define MyAppUrl "https://github.com/us74k5/forgeplay"
#define ChromeStoreUrl "https://chromewebstore.google.com/detail/blajipppfpmpaihhhkjmigapehckddie"

[Setup]
AppId={{9FD10EA4-C494-4797-A554-2C2E58605C2E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppUrl}
AppSupportURL={#MyAppUrl}
AppUpdatesURL={#MyAppUrl}
DefaultDirName={localappdata}\ForgePlay\ForgePlay Helper
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir={#SourcePath}
OutputBaseFilename=ForgePlaySetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{localappdata}\ForgePlay"

[Files]
Source: "{#SourcePath}\..\helper\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\ForgePlay Helper"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\ForgePlay Helper"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\ForgePlay Helper"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[InstallDelete]
Type: files; Name: "{userstartup}\YT Local Helper.lnk"
Type: files; Name: "{userstartup}\YT Local Playback.lnk"

[UninstallDelete]
Type: files; Name: "{userstartup}\ForgePlay Helper.lnk"

[UninstallRun]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--shutdown"; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "ShutdownForgePlayHelper"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,ForgePlay Helper}"; Flags: nowait postinstall skipifsilent runhidden
Filename: "{#ChromeStoreUrl}"; Description: "Open the ForgePlay Chrome extension"; Flags: shellexec nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WizardSilent()) then
  begin
    MsgBox(
      'ForgePlay Helper has been installed and will start automatically when you sign in.' + #13#10#13#10 +
      'If Chrome asks, add or enable the ForgePlay extension from the page that opens next.' + #13#10#13#10 +
      'Diagnostic log: %LOCALAPPDATA%\ForgePlay\forgeplay.log',
      mbInformation,
      MB_OK);
  end;
end;
