"""Independent TS-section reader used for bench verification (no remuxing)."""
from pathlib import Path
import json
import sys


def crc(data):
    c=0xffffffff
    for b in data:
        c ^= b<<24
        for _ in range(8):c=((c<<1)^(0x04c11db7 if c&0x80000000 else 0))&0xffffffff
    return c


def packet(pid,section,cc=0):
    data=b'\x00'+section
    result=[]
    while data:
        chunk,data=data[:184],data[184:]
        result.append(bytes([0x47,((pid>>8)&0x1f)|(0x40 if not result else 0),pid&255,0x10|(cc&15)])+chunk+b'\xff'*(184-len(chunk)))
        cc+=1
    return b''.join(result)


def sections(data):
    buffers={};expected={};last={};result=[]
    for off in range(0,len(data)-187,188):
        p=data[off:off+188]
        if p[0]!=0x47:raise ValueError('TS sync lost')
        pid=((p[1]&31)<<8)|p[2];afc=p[3]>>4&3
        if not afc&1:continue
        cc=p[3]&15
        if pid in last and cc!=((last[pid]+1)&15):buffers.pop(pid,None)
        last[pid]=cc
        pos=4+(1+p[4] if afc&2 else 0)
        if pos>=188:continue
        payload=p[pos:]
        if p[1]&0x40:
            pointer=payload[0];payload=payload[1:]
            start=payload[pointer:]
            if len(start)<3 or not ((start[0] in (0,2) and start[1]&0xf0==0xb0) or (start[0]==0xfc and start[1]&0xc0==0)):
                buffers.pop(pid,None);continue
            if buffers.get(pid) and pointer:buffers[pid]+=payload[:pointer]
            if buffers.get(pid):
                b=buffers[pid];n=3+((b[1]&15)<<8|b[2]) if len(b)>=3 else 4097
                if len(b)>=n:result.append((pid,bytes(b[:n])))
            buffers[pid]=bytearray(payload[pointer:])
        elif pid in buffers:buffers[pid]+=payload
        else:continue
        while len(buffers.get(pid,b''))>=3:
            b=buffers[pid]
            if b[0]==255:buffers.pop(pid,None);break
            n=3+((b[1]&15)<<8|b[2])
            if n>4096:buffers.pop(pid,None);break
            if len(b)<n:break
            result.append((pid,bytes(b[:n])));buffers[pid]=b[n:]
    return result


def inspect(path):
    found=sections(Path(path).read_bytes());pmts=[];cues=[]
    for pid,s in found:
        if s[0]==2 and crc(s)==0:
            program_info=((s[10]&15)<<8)|s[11];offset=12+program_info;streams=[]
            while offset+5<=len(s)-4:
                typ=s[offset];epid=(s[offset+1]&31)<<8|s[offset+2];length=(s[offset+3]&15)<<8|s[offset+4]
                streams.append({'pid':epid,'type':typ,'descriptors':s[offset+5:offset+5+length].hex()});offset+=5+length
            pmts.append({'pid':pid,'cuei':b'CUEI' in s[12:12+program_info],'streams':streams})
        if s[0]==0xfc:
            assert crc(s)==0,'Invalid SCTE-35 CRC'
            length=(s[11]&15)<<8|s[12];command=s[14:14+length]
            record={'pid':pid,'command_type':s[13],'pts_adjustment':int.from_bytes(s[4:9],'big')&((1<<33)-1),'section':s.hex()}
            if s[13]==5 and len(command)>=5:
                record['event_id']=int.from_bytes(command[:4],'big');record['cancel']=bool(command[4]&128)
                if not record['cancel'] and not command[5]&16:record['pts_time']=int.from_bytes(command[6:11],'big')&((1<<33)-1)
            cues.append(record)
    return {'pmt':pmts[:1],'sections':cues}


if __name__=='__main__':print(json.dumps(inspect(sys.argv[1]),indent=2))
