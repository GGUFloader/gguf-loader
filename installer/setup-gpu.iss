; GGUF Loader CUDA/GPU Installer
; Requires Inno Setup 6+
; Requires NVIDIA GPU with driver >= 550 (CUDA 12.4)

#define MyAppName "GGUF Loader"
#define MyAppVersion "2.3.0"
#define MyAppPublisher "GGUF Loader Team"
#define MyAppURL "https://github.com/gguf-loader/gguf-loader"
#define MyAppExeName "GGUFLoader_WithAddons_GPU.exe"
#define MyAppDescription "Local LLM Runtime - CUDA GPU Accelerated"

[Setup]
AppId={{A1B2C3D4-5E6F-7A8B-9C0D-1E2F3A4B5C6D}
AppName={#MyAppName} (GPU)
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=../dist
OutputBaseFilename=GGUF-Loader-v{#MyAppVersion}-GPU-Setup
SetupIconFile=../icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoDescription={#MyAppDescription}
VersionInfoProductName={#MyAppName} (GPU)
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "../dist/{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "../icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName} (GPU)"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName} (GPU)}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName} (GPU)"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName} (GPU)"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}} (GPU)"; Flags: nowait postinstall skipifsilent

[Registry]
; Register the application for Windows "Apps & Features"
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName} GPU"; ValueType: string; ValueName: "DisplayIcon"; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName} GPU"; ValueType: string; ValueName: "DisplayName"; ValueData: "{#MyAppName} (GPU/CUDA)"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName} GPU"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName} GPU"; ValueType: string; ValueName: "Publisher"; ValueData: "{#MyAppPublisher}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName} GPU"; ValueType: string; ValueName: "URLInfoAbout"; ValueData: "{#MyAppURL}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName} GPU"; ValueType: dword; ValueName: "NoModify"; ValueData: 1; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName} GPU"; ValueType: dword; ValueName: "NoRepair"; ValueData: 1; Flags: uninsdeletekey

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
