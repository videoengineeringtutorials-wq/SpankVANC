"""Read-only FFmpeg DeckLink discovery for machines without our SDK diagnostic."""
import re
import subprocess


def strip_prefix(line):
    return re.sub(r'^\s*\[[^\]]+\]\s*', '', line)


def parse_device_names(text):
    names=[]
    for line in text.splitlines():
        line=strip_prefix(line)
        match=re.fullmatch(r"\s*'([^'\r\n]+)'\s*",line)
        if match and match[1] not in names:names.append(match[1])
    return names


def parse_modes(text):
    modes=[]
    for line in text.splitlines():
        line=strip_prefix(line).lstrip()
        if len(line)<5:continue
        code=line[:4]
        if not re.fullmatch(r'[A-Za-z0-9]{3}[A-Za-z0-9 ]',code):continue
        description=line[4:].strip()
        match=re.match(r'(\d+)x(\d+)\s+at\s+(\d+)/(\d+)\s+fps',description)
        if not match or int(match[4])==0:continue
        if any(m['code']==code for m in modes):continue
        modes.append({'code':code,'name':description,'width':int(match[1]),'height':int(match[2]),
                      'duration':int(match[4]),'timescale':int(match[3])})
    return modes


def discover(binary):
    def query(*args):
        # The legacy list commands deliberately exit with a non-zero status.
        p=subprocess.run([binary,'-hide_banner','-nostdin',*args],capture_output=True,
                         text=True,errors='replace',timeout=15)
        return p.stdout+p.stderr
    try:
        text=query('-f','decklink','-list_devices','1','-i','dummy')
        names=parse_device_names(text)
        if not names:
            return [], 'FFmpeg could not list a DeckLink input. Check Desktop Video and run Diagnostics.cmd.'
        if len(names)>16:return [], 'More than 16 DeckLink input devices reported; select a smaller device set'
        devices=[]
        for index,name in enumerate(names):
            modes=parse_modes(query('-f','decklink','-list_formats','1','-i',name))
            devices.append({'device':index,'name':name,'input':True,'output':None,'modes':modes,
                            'discovery':'ffmpeg','mode_error':'' if modes else 'FFmpeg did not report four-character video modes'})
        return devices,''
    except (OSError,subprocess.TimeoutExpired) as exc:
        return [], str(exc)


def option_names(text):
    return sorted(set(re.findall(r'^\s+-([a-zA-Z0-9_]+)\s',text,re.MULTILINE)))


def parse_sink_names(text):
    names = []
    for line in text.splitlines():
        match = re.fullmatch(r'\s*(?:\*\s*)?\S+\s+\[([^\]\r\n]+)\]\s+\([^)]*\)\s*', line)
        if match and match[1] not in names:
            names.append(match[1])
    return names


def discover_outputs(binary):
    """List actual output ports without decoding video or changing profiles."""
    def query(*args):
        p = subprocess.run([binary, '-hide_banner', '-nostdin', *args],
                           capture_output=True, text=True, errors='replace', timeout=15)
        return p.stdout + p.stderr
    try:
        names = parse_sink_names(query('-sinks', 'decklink'))
        if not names:
            # Older FFmpeg builds only expose the legacy list command. Copy
            # synthetic packets so discovery does not depend on a decoder.
            names = parse_device_names(query('-f', 'lavfi', '-i',
                'testsrc2=size=1920x1080:rate=30000/1001', '-c:v', 'copy',
                '-f', 'decklink', '-list_devices', '1', 'dummy'))
        return [{'name': name, 'output': True} for name in names], '' if names else 'No DeckLink output ports reported'
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], str(exc)
