import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent


def mom(body,kind=0x101,extra=b''):
    ops=struct.pack('>HH',kind,len(body))+body+extra
    return b'\xff\xff'+struct.pack('>H',12+len(ops))+bytes([0,0,1,0,0,0,0,2 if extra else 1])+ops


def splice(kind=1,event=42,preroll=4000,duration=300,auto=1):
    return struct.pack('>BIHHHBBB',kind,event,7,preroll,duration,1,2,auto)


def crc(data):
    c=0xffffffff
    for b in data:
        c^=b<<24
        for _ in range(8):c=((c<<1)^(0x04c11db7 if c&0x80000000 else 0))&0xffffffff
    return c


@unittest.skipUnless(shutil.which('g++'),'C++ compiler needed')
class ScteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'scte'
        subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',str(ROOT/'native/check_scte.cpp'),'-o',str(cls.binary)],check=True)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def run_packets(self,packets,pts=90000,ok=True):
        p=subprocess.run([str(self.binary),','.join(p.hex() for p in packets),str(pts)],text=True,capture_output=True)
        self.assertEqual(p.returncode,0 if ok else 1,p.stderr)
        return [bytes.fromhex(l) for l in p.stdout.splitlines()]

    def test_splice_and_independent_section_validation(self):
        section=self.run_packets([b'\x08'+mom(splice())])[0]
        self.assertEqual(section[:1],b'\xfc');self.assertEqual(len(section),3+(int.from_bytes(section[1:3],'big')&4095))
        self.assertEqual(crc(section),0);self.assertEqual(section[13],5)
        self.assertEqual(int.from_bytes(section[14:18],'big'),42)
        self.assertEqual(int.from_bytes(section[20:25],'big')&((1<<33)-1),450000)
        self.assertEqual(int.from_bytes(section[25:30],'big')&((1<<33)-1),2700000)
        if shutil.which('tstabcomp'):
            binary=Path(self.temp.name)/'cue.bin';xml=Path(self.temp.name)/'cue.xml';binary.write_bytes(section)
            subprocess.run(['tstabcomp','--decompile',str(binary),'--output',str(xml)],check=True,capture_output=True)
            data=xml.read_text().replace(',','');self.assertIn('splice_insert',data);self.assertIn('pts_time="450000"',data)

    def test_source_null_request_is_converted(self):
        s=self.run_packets([b'\x08'+mom(b'',0x102)])[0]
        self.assertEqual(len(s),20)
        self.assertEqual(s[13],0)
        self.assertEqual(crc(s),0)

    def test_immediate_in_out_cancel_and_wrap(self):
        for kind in (2,4,5):
            s=self.run_packets([b'\x08'+mom(splice(kind=kind))])[0]
            if kind==5:self.assertEqual(s[18],0xff)
            else:self.assertTrue(s[19]&0x10);self.assertEqual(bool(s[19]&0x80),kind==2)
        s=self.run_packets([b'\x08'+mom(splice(preroll=100))],pts=(1<<33)-900)[0]
        self.assertEqual(int.from_bytes(s[20:25],'big')&((1<<33)-1),8100)

    def test_fragmentation_duplicates_and_orphans(self):
        msg=mom(splice());one=b'\x0c'+msg[:8];two=b'\x0e'+msg[8:20];three=b'\x0a'+msg[20:]
        self.assertEqual(len(self.run_packets([one,two,three])),1)
        duplicates=[one,bytes([one[0]|1])+one[1:],two,bytes([two[0]|1])+two[1:],three,bytes([three[0]|1])+three[1:]]
        self.assertEqual(len(self.run_packets(duplicates)),1)
        self.assertEqual(len(self.run_packets([b'\x08'+msg,b'\x09'+msg])),1)
        self.run_packets([three],ok=False)

    def test_time_signal_descriptors_and_rejection(self):
        descriptor=b'\x00\x08CUEI\x00\x00\x00\x01'
        extra=struct.pack('>HH',0x108,1+len(descriptor))+b'\x01'+descriptor
        s=self.run_packets([b'\x08'+mom(struct.pack('>H',2000),0x104,extra)])[0]
        self.assertEqual(s[13],6);self.assertIn(descriptor,s);self.assertEqual(crc(s),0)
        self.run_packets([b'\x08'+mom(b'',0x777)],ok=False)
        m=bytearray(mom(splice()));m[10]=2
        self.run_packets([b'\x08'+m],ok=False)
        m=bytearray(mom(splice()));m[3]-=1
        self.run_packets([b'\x08'+m],ok=False)

    def test_rejected_cue_recovers_and_strict_stops(self):
        first=b'\x08'+mom(splice(event=42))
        bad=b'\x08'+mom(b'',0x777)
        last=b'\x08'+mom(splice(event=43))
        for invalid in (bad,b'\x0aorphan'):
            packets=','.join(p.hex() for p in (first,invalid,last))
            result=subprocess.run([str(self.binary),packets,'90000','continue'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('rejected=1 failed=0',result.stderr)
            sections=[bytes.fromhex(line) for line in result.stdout.splitlines()]
            self.assertEqual([int.from_bytes(s[14:18],'big') for s in sections],[42,43])
            self.assertTrue(all(crc(s)==0 for s in sections))
            result=subprocess.run([str(self.binary),packets,'90000','strict'],capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn('rejected=1 failed=1',result.stderr)
            self.assertEqual(len(result.stdout.splitlines()),1)

    def test_live_news_two_splice_returns_in_one_mom(self):
        packet=bytes.fromhex('08ffff00300000e900000000020101000e0300289a80000013bf00000000000101000e0300289a77000013bf0000000000')
        sections=self.run_packets([packet],pts=2216250)
        self.assertEqual(len(sections),2)
        self.assertEqual([int.from_bytes(s[14:18],'big') for s in sections],[2660992,2660983])
        for s in sections:
            self.assertEqual(s[13],5)
            self.assertFalse(s[19]&0x80) # return to network
            self.assertFalse(s[19]&0x10) # scheduled, not immediate
            self.assertEqual(int.from_bytes(s[20:25],'big')&((1<<33)-1),2671200)
            self.assertEqual(crc(s),0)
        self.assertEqual(len(self.run_packets([packet,packet])),2)

    def test_multiple_commands_scope_descriptors_and_validate_atomically(self):
        descriptor=b'\x00\x08CUEI\x00\x00\x00\x01'
        ops=[(0x101,splice(event=42)),(0x108,b'\x01'+descriptor),(0x101,splice(event=43))]
        def packet(items):
            body=b''.join(struct.pack('>HH',op,len(data))+data for op,data in items)
            return b'\x08\xff\xff'+struct.pack('>H',12+len(body))+bytes([0,0,1,0,0,0,0,len(items)])+body
        sections=self.run_packets([packet(ops)])
        self.assertIn(descriptor,sections[0]);self.assertNotIn(descriptor,sections[1])
        self.run_packets([packet([(0x108,b'\x01'+descriptor),(0x101,splice())])],ok=False)
        bad=packet([(0x101,splice(event=42)),(0x777,b'')])
        good=packet([(0x101,splice(event=42))])
        result=subprocess.run([str(self.binary),bad.hex()+','+good.hex(),'90000','continue'],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('rejected=1 failed=0',result.stderr)
        self.assertEqual(len(result.stdout.splitlines()),1) # bad MOM neither emitted nor poisoned dedupe
