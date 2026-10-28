"""Bounded source caption monitor: CEA-608 CC1–CC4 from A/53 triplets.

It observes incoming data independently of output caption policies. Native 708
triplets are counted, not misrepresented as decoded 708 service text.
"""
from collections import deque
import time

BASIC = {0x2a:'á',0x5c:'é',0x5e:'í',0x5f:'ó',0x60:'ú',0x7b:'ç',0x7c:'÷',0x7d:'Ñ',0x7e:'ñ',0x7f:'█'}
SPECIAL = '®°½¿™¢£♪à\u00a0èâêîôû'
EXTENDED = ('ÁÉÓÚÜü‘¡*’—©℠•“”ÀÂÇÈÊËëÎÏïÔÙùÛ«»', 'ÃãÍÌìÒòÕõ{}\\^_|~ÄäÖöß¥¤│ÅåØø┌┐└┘')
ROWS = (10,10,0,1,2,3,11,12,13,14,4,5,6,7,8,9)


def screen():
    return [[' ']*32 for _ in range(15)]


class Service:
    def __init__(self):
        self.displayed=screen();self.hidden=screen();self.mode='pop';self.row=14;self.column=0
        self.roll=2;self.last_control=None

    @property
    def buffer(self):
        return self.hidden if self.mode=='pop' else self.displayed

    def text(self):
        rows=[''.join(row).rstrip() for row in self.displayed]
        while rows and not rows[0]:rows.pop(0)
        while rows and not rows[-1]:rows.pop()
        return '\n'.join(rows)

    def write(self, char):
        self.buffer[self.row][min(self.column,31)]=char
        self.column=min(32,self.column+1)

    def pair(self,a,b):
        control=0x10<=a<=0x1f
        if control:
            key=(a,b)
            if self.last_control==key:self.last_control=None;return
            self.last_control=key
        else:self.last_control=None
        a_norm=a&0xf7
        if a_norm in (0x14,0x15) and 0x20<=b<=0x2f:
            if b==0x20:self.mode='pop'
            elif b==0x21:self.column=max(0,self.column-1);self.buffer[self.row][self.column]=' '
            elif b==0x24:self.buffer[self.row][min(self.column,31):]=[' ']*(32-min(self.column,31))
            elif b in (0x25,0x26,0x27):
                if self.mode!='roll':self.displayed=screen();self.row=14;self.column=0
                self.mode='roll';self.roll=b-0x23
            elif b==0x29:self.mode='paint'
            elif b==0x2c:self.displayed=screen()
            elif b==0x2d:
                if self.mode=='roll':
                    top=max(0,self.row-self.roll+1)
                    for r in range(top,self.row):self.displayed[r]=self.displayed[r+1][:]
                    self.displayed[self.row]=[' ']*32
                else:self.row=min(14,self.row+1)
                self.column=0
            elif b==0x2e:self.hidden=screen()
            elif b==0x2f:self.displayed,self.hidden=self.hidden,self.displayed;self.mode='pop'
        elif control and 0x40<=b<=0x7f:
            new_row=ROWS[((a&7)<<1)|((b>>5)&1)]
            if self.mode=='roll' and new_row!=self.row:
                old=[r[:] for r in self.displayed[max(0,self.row-self.roll+1):self.row+1]]
                self.displayed=screen();start=new_row-len(old)+1
                for i,row in enumerate(old):
                    if 0<=start+i<15:self.displayed[start+i]=row
            self.row=new_row;self.column=((b&0x0e)>>1)*4 if b&0x10 else 0
        elif a_norm==0x17 and 0x21<=b<=0x23:self.column=min(32,self.column+b-0x20)
        elif a_norm==0x11 and 0x30<=b<=0x3f:self.write(SPECIAL[b-0x30])
        elif a_norm in (0x12,0x13) and 0x20<=b<=0x3f:
            self.column=max(0,self.column-1);self.write(EXTENDED[a_norm-0x12][b-0x20])
        elif a_norm==0x11 and 0x20<=b<=0x2f:self.write(' ')
        elif a>=0x20:
            self.write(BASIC.get(a,chr(a)))
            if b>=0x20:self.write(BASIC.get(b,chr(b)))


class SourceMonitor:
    def __init__(self, source=None):
        self.source=source or {}
        self.services=[Service() for _ in range(4)]
        self.channels=[0,0];self.xds=False;self.history=deque(maxlen=100);self.cues=deque(maxlen=50)
        self.history_text=['']*4;self.history_pts=[-90000]*4
        self.frames=0;self.caption_triplets=0;self.digital_triplets=0;self.invalid=0
        self.scte_packets=0;self.converted=0;self.conversion_error=False
        self.rejected=0;self.rejections=deque(maxlen=50)
        self.pts90k=0;self.signal=False;self.last_update=None

    def feed(self,event):
        self.frames+=1;self.pts90k=int(event.get('pts90k',0));self.signal=bool(event.get('signal'))
        self.last_update=time.monotonic();self.scte_packets+=len(event.get('scte104',[]))
        self.converted+=int(event.get('converted',0));self.conversion_error|=bool(event.get('conversion_error'))
        total=int(event.get('rejected_total',0))
        if total>self.rejected:
            self.rejected=total;self.conversion_error=True
            self.rejections.append({'total':total,'source_pts90k':int(event.get('last_rejected_pts90k',self.pts90k)),
                                    'reason':str(event.get('last_rejection','Rejected SCTE-104 message'))[:512],
                                    'payload_hex':str(event.get('last_rejected_hex',''))[:510],
                                    'received_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
        for cue in event.get('cues',[]):self.cues.append(dict(cue,source_pts90k=self.pts90k))
        if not self.signal:
            for service in self.services:service.displayed=screen()
            return
        try:data=bytes.fromhex(event.get('cc',''))
        except (ValueError,TypeError):self.invalid+=1;return
        if len(data)%3:self.invalid+=1;return
        for i in range(0,len(data),3):
            flags,a,b=data[i:i+3]
            if not flags&4:continue
            kind=flags&3
            if kind>=2:self.digital_triplets+=1;continue
            self.caption_triplets+=1
            if a.bit_count()%2!=1 or b.bit_count()%2!=1:self.invalid+=1;continue
            a&=0x7f;b&=0x7f
            if not a and not b:continue
            if kind==1:
                if 1<=a<=0x0e:self.xds=True;continue
                if a==0x0f:self.xds=False;continue
                if self.xds:
                    if 0x10<=a<=0x1f and 0x20<=b<=0x7f:self.xds=False
                    else:continue
            if 0x10<=a<=0x1f:self.channels[kind]=(a>>3)&1
            service=kind*2+self.channels[kind]
            self.services[service].pair(a,b)
        for i,service in enumerate(self.services):
            text=service.text()
            if text and text!=self.history_text[i] and self.pts90k-self.history_pts[i]>=90000:
                self.history.append({'service':f'CC{i+1}','text':text,'pts90k':self.pts90k})
                self.history_text[i]=text;self.history_pts[i]=self.pts90k

    def state(self,active=False):
        age=None if self.last_update is None else round(time.monotonic()-self.last_update,1)
        status='stopped' if not active else 'waiting' if age is None else 'stale' if age>3 else 'receiving' if self.signal else 'no_signal'
        return {'source':self.source,'status':status,'age_seconds':age,'signal':self.signal,'pts90k':self.pts90k,
                'services':{f'CC{i+1}':s.text() for i,s in enumerate(self.services)},'history':list(self.history),
                'frames':self.frames,'caption_triplets':self.caption_triplets,'digital_triplets':self.digital_triplets,
                'invalid_triplets':self.invalid,'scte104_packets':self.scte_packets,'converted':self.converted,
                'conversion_error':self.conversion_error,'rejected':self.rejected,'rejections':list(self.rejections),'cues':list(self.cues)}
