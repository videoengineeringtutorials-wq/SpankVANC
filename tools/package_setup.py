"""Build one public Windows setup EXE from the audited app-only payload."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import zipfile
from check_release_assets import check

ROOT=Path(__file__).resolve().parents[1]
VERSION=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']

def quote(value):return str(value).replace('$','$$').replace('"','$\\"')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--app-zip',type=Path,default=ROOT/f'releases/SpankVANC-{VERSION}-Windows11-x64-App.zip')
    p.add_argument('--output',type=Path,default=ROOT/f'releases/SpankVANC-{VERSION}-Windows11-x64-Setup.exe')
    p.add_argument('--makensis',default=shutil.which('makensis'))
    a=p.parse_args()
    if not a.makensis:raise SystemExit('Install NSIS 3 or supply --makensis /path/to/makensis.')
    check(a.app_zip)
    (ROOT/'build').mkdir(exist_ok=True)
    a.output=a.output.resolve();a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='setup-stage-',dir=ROOT/'build') as temporary:
        stage=Path(temporary)
        with zipfile.ZipFile(a.app_zip) as archive:archive.extractall(stage)
        payload=stage/'SpankVANC-Windows'
        package=json.loads((payload/'PACKAGE.json').read_text())
        if package['app_version']!=VERSION:raise ValueError('The app ZIP version does not match this checkout.')
        for required in ('setup/setup.py','setup/dependencies.json','setup/web/index.html'):
            if not (payload/required).is_file():raise ValueError('App package is missing guided setup: '+required)
        files=[x.relative_to(payload).as_posix() for x in payload.rglob('*') if x.is_file()]
        uninstall='\n'.join('  Delete "$INSTDIR\\'+quote(n.replace('/','\\'))+'"' for n in sorted(files))
        folders=sorted({str(Path(n).parent).replace('/','\\') for n in files if str(Path(n).parent)!='.'},key=lambda n:n.count('\\'),reverse=True)
        uninstall+='\n'+'\n'.join('  RMDir "$INSTDIR\\'+quote(n)+'"' for n in folders)
        script=stage/'setup.nsi'
        script.write_text(r'''
Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"
Var NoIntegration
Name "SpankVANC VERSION setup and repair"
OutFile "OUTPUT"
InstallDir "$LOCALAPPDATA\Programs\SpankVANC\VERSION"
RequestExecutionLevel user
SetCompressor /SOLID zlib
BrandingText "SpankVANC guided setup"
!define MUI_WELCOMEPAGE_TEXT "Install or repair the app and open its guided setup. It downloads speech recognition and builds the DeckLink engine on this PC. Allow Internet access, at least 12 GB of free space and potentially an hour or more. Blackmagic downloads and a Windows restart may be required. No FFmpeg binary, SDK or driver is bundled."
!define MUI_FINISHPAGE_RUN "$INSTDIR\python\pythonw.exe"
!define MUI_FINISHPAGE_RUN_PARAMETERS '-X utf8 $\"$INSTDIR\setup\setup.py$\"'
!define MUI_FINISHPAGE_RUN_TEXT "Open guided setup"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "PAYLOAD/LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Function .onInit
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/NOINTEGRATION" $1
  ${IfNot} ${Errors}
    StrCpy $NoIntegration "yes"
  ${EndIf}
  ${IfNot} ${IsNativeAMD64}
    MessageBox MB_ICONSTOP "This installer requires Windows 11 x64."
    Abort
  ${EndIf}
FunctionEnd
Function .onVerifyInstDir
FunctionEnd
Section "SpankVANC"
  SetShellVarContext current
  InitPluginsDir
  SetOutPath "$PLUGINSDIR\repair-python"
  File /r "PAYLOAD/python/*"
  File /oname=maintenance.py "PAYLOAD/setup/maintenance.py"
  File /oname=incoming.json "PAYLOAD/PACKAGE.json"
  DetailPrint "Checking for an existing or incomplete SpankVANC installation..."
  nsExec::ExecToStack '"$PLUGINSDIR\repair-python\python.exe" -I "$PLUGINSDIR\repair-python\maintenance.py" install "$INSTDIR" "$PLUGINSDIR\repair-python\incoming.json"'
  Pop $0
  Pop $1
  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "$1" /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
  SetOutPath "$INSTDIR"
  File /r /x python "PAYLOAD/*"
  CreateDirectory "$INSTDIR\python"
  CopyFiles /SILENT "$PLUGINSDIR\repair-python\*" "$INSTDIR\python"
  Delete "$INSTDIR\python\maintenance.py"
  Delete "$INSTDIR\python\incoming.json"
  WriteINIStr "$INSTDIR\installer-state.ini" "Installer" "NoIntegration" "$NoIntegration"
  ${If} $NoIntegration != "yes"
  CreateDirectory "$SMPROGRAMS\SpankVANC VERSION"
  CreateShortcut "$SMPROGRAMS\SpankVANC VERSION\Finish setup.lnk" "$INSTDIR\python\pythonw.exe" '-X utf8 "$INSTDIR\setup\setup.py"'
  Delete "$DESKTOP\Finish SpankVANC Setup *.lnk"
  CreateShortcut "$DESKTOP\Finish SpankVANC Setup.lnk" "$INSTDIR\python\pythonw.exe" '-X utf8 "$INSTDIR\setup\setup.py"'
  CreateShortcut "$SMPROGRAMS\SpankVANC VERSION\SpankVANC.lnk" "$INSTDIR\Start SpankVANC.cmd"
  CreateShortcut "$DESKTOP\SpankVANC VERSION.lnk" "$INSTDIR\Start SpankVANC.cmd"
  ${EndIf}
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  ${If} $NoIntegration != "yes"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpankVANC-VERSION" "DisplayName" "SpankVANC VERSION"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpankVANC-VERSION" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpankVANC-VERSION" "DisplayVersion" "VERSION"
  ${EndIf}
SectionEnd
Section "Uninstall"
  SetShellVarContext current
  InitPluginsDir
  CreateDirectory "$PLUGINSDIR\repair-python"
  CopyFiles /SILENT "$INSTDIR\python\*" "$PLUGINSDIR\repair-python"
  CopyFiles /SILENT "$INSTDIR\setup\maintenance.py" "$PLUGINSDIR\repair-python"
  IfFileExists "$PLUGINSDIR\repair-python\python.exe" 0 uninstall_incomplete
  IfFileExists "$PLUGINSDIR\repair-python\maintenance.py" 0 uninstall_incomplete
  nsExec::ExecToStack '"$PLUGINSDIR\repair-python\python.exe" -I "$PLUGINSDIR\repair-python\maintenance.py" uninstall "$INSTDIR"'
  Pop $0
  Pop $1
  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "$1" /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
  Goto uninstall_ready
uninstall_incomplete:
  MessageBox MB_OK|MB_ICONSTOP "Some app files are missing. Run the latest Setup EXE to repair this installation, then uninstall again." /SD IDOK
  SetErrorLevel 2
  Abort
uninstall_ready:
  ReadINIStr $0 "$INSTDIR\installer-state.ini" "Installer" "NoIntegration"
UNINSTALL
  Delete "$INSTDIR\installer-state.ini"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  ${If} $0 != "yes"
  Delete "$DESKTOP\Finish SpankVANC Setup.lnk"
  Delete "$DESKTOP\SpankVANC VERSION.lnk"
  Delete "$SMPROGRAMS\SpankVANC VERSION\Finish setup.lnk"
  Delete "$SMPROGRAMS\SpankVANC VERSION\SpankVANC.lnk"
  RMDir "$SMPROGRAMS\SpankVANC VERSION"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpankVANC-VERSION"
  ${EndIf}
  MessageBox MB_OK "App files were removed. Local settings, recordings, license state, speech downloads and the Linux build environment are preserved." /SD IDOK
SectionEnd
'''.replace('VERSION',VERSION).replace('OUTPUT',quote(a.output)).replace('PAYLOAD',quote(payload)).replace('UNINSTALL',uninstall),encoding='utf-8')
        env=os.environ.copy()
        nsis_dir=Path(a.makensis).resolve().parent.parent/'share/nsis'
        if nsis_dir.is_dir():env['NSISDIR']=str(nsis_dir)
        subprocess.run([str(a.makensis),'-V2',str(script)],env=env,check=True)
    digest=hashlib.sha256(a.output.read_bytes()).hexdigest()
    a.output.with_suffix('.exe.sha256').write_text(digest+'  '+a.output.name+'\n')
    report=dict(version=VERSION,installer=a.output.name,sha256=digest,
        payload_zip=a.app_zip.name,payload_sha256=hashlib.sha256(a.app_zip.read_bytes()).hexdigest(),
        ffmpeg_bundled=False,sdk_bundled=False,driver_bundled=False,
        requires_internet=True,clean_windows_install_verified=False)
    a.output.with_suffix('.exe.json').write_text(json.dumps(report,indent=2)+'\n')
    print(str(a.output)+' ('+str(a.output.stat().st_size)+' bytes)')
    print('SHA256 '+digest)

if __name__=='__main__':main()
