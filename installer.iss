[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=数据集标注工具
AppVersion=1.0.0
AppPublisher=DatasetTool
DefaultDirName={autopf}\数据集标注工具
DefaultGroupName=数据集标注工具
OutputDir=D:\desktop\数据集标注\installer_output
OutputBaseFilename=数据集标注工具_安装包
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=数据集标注工具
UninstallDisplayIcon={app}\数据集标注工具.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"

[Files]
Source: "D:\desktop\数据集标注\dist\数据集标注工具\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\数据集标注工具"; Filename: "{app}\数据集标注工具.exe"
Name: "{group}\卸载数据集标注工具"; Filename: "{uninstallexe}"
Name: "{autodesktop}\数据集标注工具"; Filename: "{app}\数据集标注工具.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\数据集标注工具.exe"; Description: "启动数据集标注工具"; Flags: nowait postinstall skipifsilent
