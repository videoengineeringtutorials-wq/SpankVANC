"""Verify raw local UDP datagrams, TS headers, continuity and PMT references.
Tests only loopback; an optional SCTE-bearing fixture can be supplied as --input.
"""
import argparse,json,socket,subprocess,threading,time
from pathlib import Path
from verify_scte_ts import sections,inspect
p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--input',type=Path);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--wine');a=p.parse_args()
a.output_dir.mkdir(parents=True,exist_ok=True)
source=a.input or a.output_dir/'source.ts'
if not a.input:
 subprocess.run(['ffmpeg','-v','error','-n','-f','lavfi','-i','testsrc2=size=640x360:rate=30','-f','lavfi','-i','sine=sample_rate=48000','-t','4','-c:v','libx264','-threads:v','2','-preset','veryfast','-c:a','aac','-f','mpegts',str(source)],check=True)
sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024);sock.bind(('127.0.0.1',0));sock.settimeout(.2)
port=sock.getsockname()[1];datagrams=[];done=threading.Event()
def receive():
 while not done.is_set():
  try:datagrams.append(sock.recv(65535))
  except socket.timeout:pass
reader=threading.Thread(target=receive);reader.start()
path='Z:'+str(source.resolve()).replace('/','\\') if a.wine else str(source.resolve())
args=[a.ffmpeg,'-hide_banner','-nostdin','-v','error','-re','-copyts','-i',path,'-map','0','-c','copy','-f','mpegts',f'udp://127.0.0.1:{port}?pkt_size=1316']
try:
 process=subprocess.run(([a.wine]+args) if a.wine else args,capture_output=True,text=True,timeout=60)
 assert process.returncode==0,process.stderr
 time.sleep(.5)
finally:done.set();reader.join();sock.close()
assert datagrams and all(len(d)%188==0 and len(d)<=1316 for d in datagrams), sorted(set(map(len,datagrams)))
raw=b''.join(datagrams);target=a.output_dir/'received.ts';target.write_bytes(raw)
found=sections(raw);allowed={0,0x11,0x1fff};counts={};last={};discontinuities=0;tei=0;scrambled=0
for _,s in found:
 if s[0]==0:
  for i in range(8,len(s)-4,4):allowed.add(((s[i+2]&31)<<8)|s[i+3])
 if s[0]==2:
  allowed.add(((s[8]&31)<<8)|s[9]);offset=12+((s[10]&15)<<8|s[11])
  while offset+5<=len(s)-4:
   allowed.add(((s[offset+1]&31)<<8)|s[offset+2]);offset+=5+((s[offset+3]&15)<<8|s[offset+4])
for i in range(0,len(raw),188):
 t=raw[i:i+188];assert t[0]==0x47
 pid=((t[1]&31)<<8)|t[2];counts[pid]=counts.get(pid,0)+1;tei+=bool(t[1]&128);scrambled+=bool(t[3]&192)
 afc=t[3]>>4&3;assert afc
 if afc&2:assert t[4]<=183
 discontinuity=bool(afc&2 and t[4]>0 and t[5]&128)
 if discontinuity:last.pop(pid,None)
 if afc&1 and pid!=0x1fff:
  cc=t[3]&15
  if pid in last and cc!=(last[pid]+1)%16:discontinuities+=1
  last[pid]=cc
unknown=sorted(set(counts)-allowed)
assert not unknown and not tei and not scrambled and not discontinuities,(unknown,tei,scrambled,discontinuities)
report={'datagrams':len(datagrams),'datagram_sizes':sorted(set(map(len,datagrams))),'packets':len(raw)//188,'pids':{hex(k):v for k,v in sorted(counts.items())},'unreferenced_pids':unknown,'transport_errors':tei,'scrambled_packets':scrambled,'continuity_errors':discontinuities,'scte_sections':len(inspect(target)['sections']),'windows_binary_under_wine':bool(a.wine)}
(a.output_dir/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
