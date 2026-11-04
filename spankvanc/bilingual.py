"""Serial, phrase-atomic CC1/CC2 journal with a bounded transmission backlog."""
from pathlib import Path
import threading
import time
import unicodedata

from .captions import BASIC, SPECIAL, EXTENDED
from .whisper_worker import encode_text, odd, wrap_words


def encode_spanish(text):
    basic = {chr(i): i for i in range(32, 127) if i not in BASIC}
    basic.update({char: code for code, char in BASIC.items()})
    special = {char: (0x19, 0x30+i) for i, char in enumerate(SPECIAL)}
    extended = {char: (0x1a+group, 0x20+i) for group, chars in enumerate(EXTENDED) for i, char in enumerate(chars)}
    text = unicodedata.normalize('NFC', text).translate(str.maketrans({'’':"'", '‘':"'", '“':'"', '”':'"', '–':'-', '…':'...'}))
    pairs = []
    def control(a, b):
        pairs.extend(((a,b), (a,b)))
    for line in wrap_words(' '.join(text.split())):
        control(0x1c, 0x25) # channel 2, RU2
        control(0x1c, 0x2d)
        control(0x1c, 0x70) # row 15, column zero
        control(0x1c, 0x24)
        pending = []
        def flush():
            if len(pending)%2: pending.append(0)
            pairs.extend(zip(pending[::2],pending[1::2]))
            pending.clear()
        for char in line:
            if char in basic:
                pending.append(basic[char])
            elif char in special:
                flush();control(*special[char])
            elif char in extended:
                # Extended characters replace the preceding fallback glyph.
                pending.append(ord('?'));flush();control(*extended[char])
            else:
                fallback=unicodedata.normalize('NFKD',char).encode('ascii','ignore').decode()
                pending.append(basic.get(fallback,ord('?')))
        flush()
    return bytes(odd(value) for pair in pairs for value in pair)


class BilingualJournal:
    def __init__(self, path, rate=30000/1001):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=self.path.open('wb',buffering=0)
        self.lock=threading.Lock()
        self.end=time.monotonic()
        self.rate=rate
        self.closed=False
        self.skipped=0
        self.spanish_written=0
        self.clear()

    def append(self, payload, spanish=False):
        with self.lock:
            if self.closed:return False
            now=time.monotonic()
            # Reserve capacity for English; never let translation accumulate
            # seconds of stale text while recognition continues.
            duration=len(payload)/2/self.rate
            limit=4 if spanish else 10
            if max(self.end,now)+duration>now+limit:
                self.skipped+=1
                return False
            if self.stream.tell()+len(payload)>64*1024*1024:
                self.skipped+=1
                return False
            self.stream.write(payload)
            self.end=max(self.end,now)+duration
            if spanish:self.spanish_written+=1
            return True

    def english(self, text):
        return self.append(encode_text(text))

    def spanish(self, text):
        return self.append(encode_spanish(text),spanish=True)

    def clear(self):
        self.append(bytes(odd(v) for pair in [(0x14,0x2c)]*2+[(0x1c,0x2c)]*2 for v in pair))

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed=True
                self.stream.close()

    def state(self):
        with self.lock:
            return {'skipped':self.skipped,'spanish_written':self.spanish_written,
                    'backlog_ms':round(max(0,self.end-time.monotonic())*1000),'active':not self.closed}
