"""Windows console guide for a local WSL capture-engine build. No cloud uploads."""
from __future__ import annotations
import argparse,json,os,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
DISTRO='Ubuntu-24.04'

def wsl_executable():
    # The System32 launcher can fail in SSH sessions after a WSL upgrade.
    installed=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'WSL'/'wsl.exe'
    return str(installed) if installed.is_file() else 'wsl.exe'

def wsl_path(value,distro=DISTRO):
    return subprocess.check_output([wsl_executable(),'-d',distro,'--exec','wslpath','-a',str(value).replace('\\','/')],text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0).strip()

def save_capture_path(root,binary):
    settings_path=root/'settings.json'
    settings=json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
    if not isinstance(settings,dict):raise ValueError('settings.json must contain an object; it was not replaced.')
    settings['decklink_ffmpeg_path']=str(binary.resolve())
    if not settings.get('ffmpeg_path'):settings['ffmpeg_path']=str(binary.resolve())
    temp=settings_path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(settings,indent=2)+'\n',encoding='utf-8');temp.replace(settings_path)

def verify_capture(binary):
    def query(*args):
        result=subprocess.run([str(binary),'-hide_banner',*args],capture_output=True,text=True,errors='replace',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode:raise ValueError('The new executable could not run. Your saved engine path was not changed.\n'+result.stderr[-1000:])
        return result.stdout+result.stderr
    version=query('-version');options=query('-h','demuxer=decklink');filters=query('-filters');protocols=query('-protocols').split()
    if not all(name in options for name in ('spankvanc_anc','spankvanc_scte35','spankvanc_scte_strict')):raise ValueError('Extended DeckLink options are missing; configuration was not changed.')
    playout=query('-h','muxer=decklink')
    if not all(name in playout for name in ('spankvanc_caption_output','spankvanc_scte_output')):raise ValueError('Extended VANC caption playout is missing; configuration was not changed. Rebuild with the current build-support folder.')
    names={parts[1] for line in filters.splitlines() if len(parts:=line.split())>=2}
    if not {'yadif','scale','pad','setsar','fps','setfield','sidedata'}<=names or 'rtmps' not in protocols:raise ValueError('YouTube filters/RTMPS are missing; configuration was not changed.')
    if 'spankvanc_cc' not in names or 'f32le' not in query('-muxers'):
        raise ValueError('Whisper filter/raw audio tap is missing; configuration was not changed.')
    if 'continuous field-slotted' not in query('-h','filter=spankvanc_cc'):
        raise ValueError('Corrected caption framing is missing; rebuild the engine with current support.')
    print(version.splitlines()[0])

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--sdk-include',type=Path);parser.add_argument('--distro',default=DISTRO);args=parser.parse_args(argv)
    if os.name!='nt':raise ValueError('Run Build Extended Capture.cmd on Windows, or tools/bootstrap_windows_capture.py inside Ubuntu.')
    if not (Path(wsl_executable()).is_file() or shutil.which(wsl_executable())):raise ValueError('WSL is not installed. Follow docs/WINDOWS_BEGINNER.md, then run this helper again.')
    check=subprocess.run([wsl_executable(),'-d',args.distro,'--exec','true'],capture_output=True,timeout=30)
    if check.returncode:raise ValueError('Ubuntu-24.04 is not ready. Install it, restart Windows, and open Ubuntu once to create your Linux username/password. See docs/WINDOWS_BEGINNER.md.')
    support=ROOT/'build-support' if (ROOT/'build-support/tools/bootstrap_windows_capture.py').exists() else ROOT
    helper=support/'tools/bootstrap_windows_capture.py'
    if not helper.is_file():raise ValueError('Build support files are missing. Extract the complete current app/source ZIP.')
    print('This builds your OWN Windows capture engine locally through Ubuntu/WSL.')
    print('It installs Ubuntu build tools (sudo password prompt), downloads pinned source, and compiles. It does not install drivers or upload binaries.')
    print('Allow several GB of free space and potentially an hour or more on a slow PC. Leave this window open.')
    print('Download and extract DeckLink SDK 12.8 from Blackmagic yourself; review/accept its terms. Select its Win\\include folder.')
    include=args.sdk_include or Path(input('Drag the SDK Win\\include folder here, then press Enter: ').strip().strip('"'))
    if not (include/'DeckLinkAPIVersion.h').is_file():raise ValueError('DeckLinkAPIVersion.h was not found in that folder.')
    if input('After accepting the SDK terms yourself, type BUILD to install Ubuntu tools and compile locally: ').strip()!='BUILD':
        print('No build started; configuration unchanged.');return 0
    linux_home=subprocess.check_output([wsl_executable(),'-d',args.distro,'--exec','printenv','HOME'],text=True,encoding='utf-8').strip()
    if not linux_home.startswith('/') or '\n' in linux_home:raise ValueError('Could not determine the Ubuntu home folder.')
    build=linux_home+'/.cache/spankvanc/windows-sdk12.8-ffmpeg7.0.2'
    subprocess.run([wsl_executable(),'-d',args.distro,'--exec','python3',wsl_path(helper,args.distro),'--sdk-include',wsl_path(include.resolve(),args.distro),'--build-dir',build,'--install-deps'],check=True)
    output=ROOT/'capture-ffmpeg-local';output.mkdir(exist_ok=True)
    binary=output/('ffmpeg-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.exe')
    subprocess.run([wsl_executable(),'-d',args.distro,'--exec','cp',build+'/capture/bin/ffmpeg.exe',wsl_path(binary,args.distro)],check=True)
    verify_capture(binary);save_capture_path(ROOT,binary)
    print('SUCCESS: locally built engine checked and saved in settings.json:',binary)
    print('Close any older SpankVANC session, then run Start SpankVANC.cmd. Keep this engine local; do not upload it.')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,subprocess.SubprocessError) as error:print('Local build:',error,file=sys.stderr);raise SystemExit(1)
