"""Prepare and build a local Windows x64 capture engine on Ubuntu 24.04 / WSL2.
The user supplies SDK 12.8 Include files. No SDK download or binary upload occurs.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SOURCES={
 'ffmpeg-7.0.2.tar.xz':('https://ffmpeg.org/releases/ffmpeg-7.0.2.tar.xz','8646515b638a3ad303e23af6a3587734447cb8fc0a0c064ecdb8e95c4fd8b389','ffmpeg-7.0.2'),
 'openssl-3.5.9.tar.gz':('https://github.com/openssl/openssl/archive/refs/tags/openssl-3.5.9.tar.gz','796831ec533bf41998eaaee9d632d921b8a69f57394fa4086ff01a941113d26d','openssl-openssl-3.5.9'),
 'srt-1.5.4.tar.gz':('https://github.com/Haivision/srt/archive/refs/tags/v1.5.4.tar.gz','d0a8b600fe1b4eaaf6277530e3cfc8f15b8ce4035f16af4a5eb5d4b123640cdd','srt-1.5.4')}
X264_REV='0480cb05fa188d37ae87e8f4fd8f1aea3711f7ee'
PACKAGES=['build-essential','git','curl','xz-utils','cmake','pkg-config','nasm','perl','python3',
 'autoconf','automake','libtool','gcc-mingw-w64-x86-64-posix','g++-mingw-w64-x86-64-posix','binutils-mingw-w64-x86-64','mingw-w64-tools']

def sdk_version(include):
 text=(include/'DeckLinkAPIVersion.h').read_text(errors='replace')
 match=re.search(r'^\s*#define\s+BLACKMAGIC_DECKLINK_API_VERSION\s+(0x[0-9a-fA-F]+)',text,re.M)
 if not match or int(match[1],16)!=0x0c080000:
  raise ValueError('This tested build requires SDK 12.8 Win/include (0x0c080000). Newer SDKs are not yet supported by this helper. Your files have not been changed.')
 if not ((include/'DeckLinkAPI.idl').is_file() or all((include/n).is_file() for n in ('DeckLinkAPI.h','DeckLinkAPI_i.c'))):
  raise ValueError('Choose Win/include from the SDK: DeckLinkAPI.idl was not found.')
 return int(match[1],16)

def fetch(name,build,run):
 url,digest,directory=SOURCES[name];archive=build/name
 if not archive.exists():
  partial=archive.with_suffix(archive.suffix+'.part')
  run(['curl','--fail','--location','--retry','2',url,'--output',str(partial)])
  if hashlib.sha256(partial.read_bytes()).hexdigest()!=digest:raise ValueError('Source SHA-256 mismatch: '+name)
  partial.replace(archive)
 if hashlib.sha256(archive.read_bytes()).hexdigest()!=digest:raise ValueError('Cached source SHA-256 mismatch: '+name)
 if not (build/directory).exists():
  with tarfile.open(archive) as source:source.extractall(build,filter='data')
 return build/directory

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sdk-include',type=Path,required=True);p.add_argument('--build-dir',type=Path,required=True)
 p.add_argument('--install-deps',action='store_true',help='Install Ubuntu compiler/build packages through sudo apt')
 p.add_argument('--check-only',action='store_true',help='Validate SDK/tool prerequisites without downloads or builds')
 a=p.parse_args(argv);sdk=a.sdk_include.resolve();sdk_version(sdk)
 if sys.platform!='linux':raise ValueError('Run this helper inside Ubuntu 24.04 / WSL2; use Build Extended Capture.cmd on Windows.')
 if a.install_deps and not a.check_only:
  prefix=[] if os.geteuid()==0 else ['sudo']
  if prefix:subprocess.run(['sudo','-v'],check=True)
  subprocess.run([*prefix,'apt-get','update'],check=True)
  subprocess.run([*prefix,'apt-get','install','-y',*PACKAGES],check=True)
 required=['autoconf','automake','libtoolize','git','curl','cmake','pkg-config','nasm','perl','make','x86_64-w64-mingw32-gcc','x86_64-w64-mingw32-g++','x86_64-w64-mingw32-windres']
 missing=[name for name in required if not shutil.which(name)]
 widl=shutil.which('x86_64-w64-mingw32-widl') or shutil.which('widl')
 if (sdk/'DeckLinkAPI.idl').exists() and not widl:missing.append('mingw-w64-tools (widl)')
 if missing:raise ValueError('Missing Ubuntu build tools: '+', '.join(missing)+'. Run with --install-deps, or install the documented apt packages.')
 if a.check_only:
  print('SDK 12.8 and compiler prerequisites validated; no files downloaded or built.');return 0
 build=a.build_dir.resolve();build.mkdir(parents=True,exist_ok=True);deps=build/'deps';deps.mkdir(exist_ok=True)
 env=os.environ.copy();toolbin=build/'toolchain/usr/bin';toolbin.mkdir(parents=True,exist_ok=True)
 for tool in ('gcc','g++'):
  target=toolbin/('x86_64-w64-mingw32-'+tool)
  compiler=shutil.which('x86_64-w64-mingw32-'+tool+'-posix') or shutil.which('x86_64-w64-mingw32-'+tool)
  if not target.exists():target.symlink_to(compiler)
 env['PATH']=str(toolbin)+os.pathsep+env['PATH'];env['PKG_CONFIG_LIBDIR']=str(deps/'lib/pkgconfig');env['PKG_CONFIG_PATH']=''
 env['SPANKVANC_CROSS_BUILD_DIR']=str(build)
 log=build/'bootstrap.log'
 def run(args,cwd=None):
  print('Building:', ' '.join(map(str,args)),flush=True)
  with log.open('a',encoding='utf-8') as output:
   with subprocess.Popen(list(map(str,args)),cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace') as process:
    for line in process.stdout:print(line,end='',flush=True);output.write(line)
    if process.wait():raise RuntimeError('Build command failed. Details: '+str(log))
 include=build/'decklink-headers/include';include.mkdir(parents=True,exist_ok=True)
 if sdk!=include:
  for file in sdk.iterdir():
   if file.is_file() and (file.suffix.lower()=='.idl' or file.name in ('DeckLinkAPIVersion.h','DeckLinkAPI.h','DeckLinkAPI_i.c')):shutil.copy2(file,include/file.name)
 if (include/'DeckLinkAPI.idl').exists():
  for file in include.glob('*.idl'):
   data=file.read_bytes()
   if not data.endswith(b'\n'):file.write_bytes(data+b'\n')
  # Ubuntu MinGW omits COM IDL imports. Obtain Wine's development files
  # as a local package extraction; no Wine runtime installation is required.
  idl=Path('/usr/include/wine/wine/windows')
  if not (idl/'unknwn.idl').is_file():
   package_dir=build/'idl-package';package_dir.mkdir(exist_ok=True)
   idl_root=build/'idl-support';idl=idl_root/'usr/include/wine/wine/windows'
   if not (idl/'unknwn.idl').is_file():
    run(['apt-get','download','libwine-dev'],package_dir)
    packages=sorted(package_dir.glob('libwine-dev_*.deb'),key=lambda path:path.stat().st_mtime)
    if not packages:raise RuntimeError('Wine IDL development package was not downloaded.')
    run(['dpkg-deb','-x',packages[-1],idl_root])
   if not (idl/'unknwn.idl').is_file():raise RuntimeError('Wine IDL import unknwn.idl is missing after extraction.')
  run([widl,'--win64','-I'+str(idl),'-h','-u','DeckLinkAPI.idl'],include)
 for name in SOURCES:fetch(name,build,run)
 klvanc=build/'libklvanc'
 if not (deps/'lib/libklvanc.a').exists():
  if not klvanc.exists():run(['git','clone','https://github.com/stoth68000/libklvanc.git',klvanc])
  run(['git','checkout','--detach','d6915e37067ef9680ef27bb8c12cb6bd743471d2'],klvanc)
  for header in (klvanc/'src').rglob('*.h'):
   header.write_text(header.read_text().replace('<sys/errno.h>','<errno.h>'))
  run(['./autogen.sh','--build'],klvanc)
  run(['./configure','--host=x86_64-w64-mingw32','--prefix='+str(deps),'--disable-shared','--enable-static'],klvanc)
  run(['make','-C','src','-j4'],klvanc);run(['make','-C','src','install'],klvanc)
 x264=build/'x264'
 if not x264.exists():run(['git','clone','https://code.videolan.org/videolan/x264.git',x264])
 run(['git','checkout','--detach',X264_REV],x264)
 if not (deps/'lib/libx264.a').exists():
  run(['./configure','--host=x86_64-w64-mingw32','--cross-prefix=x86_64-w64-mingw32-','--prefix='+str(deps),'--enable-static','--disable-cli','--disable-opencl'],x264)
  run(['make','-j4'],x264);run(['make','install'],x264)
 if not (deps/'lib/libcrypto.a').exists() or not (deps/'lib/libssl.a').exists():
  openssl=build/'openssl-openssl-3.5.9'
  run(['perl','Configure','mingw64','--cross-compile-prefix=x86_64-w64-mingw32-','--prefix='+str(deps),'--libdir=lib','no-shared','no-module','no-tests','no-apps','no-docs','no-legacy'],openssl)
  run(['make','-j4','build_libs'],openssl);run(['make','install_dev'],openssl)
 if not (deps/'lib/libsrt.a').exists():
  compiler_root=Path(shutil.which('x86_64-w64-mingw32-gcc',path=env['PATH'])).resolve().parent.parent/'x86_64-w64-mingw32'
  run(['cmake','-S',build/'srt-1.5.4','-B',build/'srt-build','-DCMAKE_TOOLCHAIN_FILE='+str(ROOT/'windows/mingw-toolchain.cmake'),
       '-DCMAKE_FIND_ROOT_PATH='+str(compiler_root)+';'+str(deps),'-DCMAKE_INSTALL_PREFIX='+str(deps),'-DCMAKE_BUILD_TYPE=Release',
       '-DENABLE_SHARED=OFF','-DENABLE_STATIC=ON','-DENABLE_APPS=OFF','-DENABLE_TESTING=OFF','-DENABLE_STDCXX_SYNC=ON',
       '-DOPENSSL_ROOT_DIR='+str(deps),'-DOPENSSL_USE_STATIC_LIBS=TRUE','-DUSE_ENCLIB=openssl'])
  run(['cmake','--build',build/'srt-build','-j4']);run(['cmake','--install',build/'srt-build'])
 run(['bash',ROOT/'tools/build_windows_capture.sh'])
 result=build/'capture/bin/ffmpeg.exe'
 if not result.is_file():raise RuntimeError('Build completed without the expected Windows executable.')
 (build/'local-build.json').write_text(json.dumps({'ffmpeg':'7.0.2','sdk':'12.8','x264':X264_REV,'source_sha256':{name:values[1] for name,values in SOURCES.items()},'binary_sha256':hashlib.sha256(result.read_bytes()).hexdigest(),'redistributable':False},indent=2)+'\n')
 print('LOCAL BUILD COMPLETE:',result);print('Keep this executable local. Configure decklink_ffmpeg_path; do not upload it as a release asset.')
 return 0

if __name__=='__main__':
 try:raise SystemExit(main())
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:print('Build helper:',error,file=sys.stderr);raise SystemExit(1)
