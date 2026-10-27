; Inno Setup 6 script. Built by build.bat, which passes /DAppVersion=<app.__version__>.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef AppCopyright
  #define AppCopyright ""
#endif
#define AppName "GifShelf"
#define AppExe "GifShelf.exe"

[Setup]
; Never change AppId: it's how Windows recognises upgrades and the uninstall entry.
AppId={{80CB7E02-CD74-4773-88DF-8B922FF174A2}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppCopyright={#AppCopyright}
; File properties of the setup exe.
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
VersionInfoProductTextVersion={#AppVersion}
VersionInfoTextVersion={#AppVersion}
VersionInfoCopyright={#AppCopyright}
DefaultDirName={autopf}\GifShelf
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user install by default (no admin prompt); the dialog lets users pick all-users.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=GifShelf-{#AppVersion}-setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Close a running copy (via Restart Manager) before replacing/removing files.
CloseApplications=yes
; The app holds this mutex while running (main.py, APP_MUTEX). Setup and the
; uninstaller both check it and ask the user to close GifShelf first; without
; it, uninstalling while the app runs leaves its locked files behind.
AppMutex=GifShelf-80CB7E02,Global\GifShelf-80CB7E02

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Drop the previous version's bundled libraries so upgrades don't keep stale files.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\GifShelf\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  DbName = 'library.sqlite3';

{ Same folder as storage.default_app_dir() / settings() in the app. }
function DataDir(): String;
begin
  Result := ExpandConstant('{localappdata}\GifShelf');
end;

function IsThumbnail(const Name: String): Boolean;
var
  Ext: String;
begin
  Ext := Lowercase(ExtractFileExt(Name));
  Result := (Ext = '.gif') or (Ext = '.png');
end;

{ Removes only files the app creates, then folders if they ended up empty,
  so anything else the user keeps in a custom library folder survives. }
procedure DeleteLibrary(const Dir: String);
var
  Thumbs: String;
  FindRec: TFindRec;
begin
  if (Dir = '') or not DirExists(Dir) then
    Exit;
  Thumbs := AddBackslash(Dir) + 'thumbnails';
  if FindFirst(Thumbs + '\*', FindRec) then
  begin
    try
      repeat
        if ((FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) = 0) and IsThumbnail(FindRec.Name) then
          DeleteFile(Thumbs + '\' + FindRec.Name);
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
  RemoveDir(Thumbs);
  DeleteFile(AddBackslash(Dir) + DbName);
  DeleteFile(AddBackslash(Dir) + DbName + '-journal');
  RemoveDir(Dir);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  SettingsFile, LibraryDir: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  if UninstallSilent then
    Exit;  { never delete user data without asking }

  { Read the library location before anything is deleted; no value means the
    default folder. The app writes forward slashes, but QSettings escapes
    backslashes (\\) in values written by older versions, so undo that too.
    If the path can't be read, the library question is simply skipped. }
  SettingsFile := AddBackslash(DataDir()) + 'settings.ini';
  LibraryDir := RemoveQuotes(GetIniString('General', 'storage_dir', '', SettingsFile));
  StringChangeEx(LibraryDir, '\\', '\', True);
  StringChangeEx(LibraryDir, '/', '\', True);
  if LibraryDir = '' then
    LibraryDir := DataDir();

  if FileExists(AddBackslash(LibraryDir) + DbName) and
     (MsgBox('Delete your GIF library?' + #13#10 + #13#10 +
             LibraryDir + #13#10 + #13#10 +
             'This permanently deletes all saved GIF links, tags and thumbnails.' + #13#10 +
             'Choose No to keep it for a later reinstall.',
             mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
    DeleteLibrary(LibraryDir);

  if FileExists(SettingsFile) and
     (MsgBox('Delete your settings?' + #13#10 + #13#10 +
             'Theme and library location (' + SettingsFile + ').' + #13#10 +
             'If you keep your library in a custom folder and delete this, point the app' + #13#10 +
             'back to it after reinstalling via Settings > Database > Change.',
             mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
    DeleteFile(SettingsFile);

  RemoveDir(DataDir());  { only succeeds if nothing is left in it }
end;
