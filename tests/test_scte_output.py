import copy,shutil,struct,subprocess,tempfile,unittest
from pathlib import Path
from test_scte import mom,splice,crc
import test_decklink
from spankvanc.engine import command,validate,plan,ConfigError
ROOT=Path(__file__).resolve().parent.parent

@unittest.skipUnless(shutil.which('g++'),'C++ compiler needed')
class ScteOutputCodecTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.forward=Path(cls.tmp.name)/'forward';cls.reverse=Path(cls.tmp.name)/'reverse'
  for source,target in (('check_scte.cpp',cls.forward),('check_scte_output.cpp',cls.reverse)):
   subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',str(ROOT/'native'/source),'-o',str(target)],check=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def forward_packet(self,packets,pts):
  p=subprocess.run([str(self.forward),','.join(p.hex() for p in packets),str(pts)],capture_output=True,text=True,check=True)
  return [bytes.fromhex(line) for line in p.stdout.splitlines()]
 def reverse_section(self,section,pts,ok=True,repeat=False):
  p=subprocess.run([str(self.reverse),section.hex(),str(pts)]+(['repeat'] if repeat else []),capture_output=True,text=True)
  self.assertEqual(p.returncode,0 if ok else 1,p.stderr)
  return [bytes.fromhex(line) for line in p.stdout.splitlines()]
 def test_program_splices_roundtrip_and_late_repeat(self):
  for kind in range(1,6):
   section=self.forward_packet([b'\x08'+mom(splice(kind=kind))],90000)[0]
   packets=self.reverse_section(section,180000,repeat=True)
   result=self.forward_packet(packets,180000)[0]
   self.assertEqual(section,result)
 def test_pts_adjustment_and_wrap(self):
  section=bytearray(self.forward_packet([b'\x08'+mom(splice(preroll=2000))],(1<<33)-90000)[0])
  section[5:9]=(90000).to_bytes(4,'big');section[-4:]=crc(section[:-4]).to_bytes(4,'big')
  packets=self.reverse_section(section,(1<<33)-45000)
  result=self.forward_packet(packets,(1<<33)-45000)[0]
  self.assertEqual(int.from_bytes(result[20:25],'big')&((1<<33)-1),180000)
 def test_time_signal_descriptors_and_fragments(self):
  descriptor=b'\x02\xfa'+b'CUEI'+bytes(246)
  desc=b'\x02'+descriptor+descriptor
  extra=struct.pack('>HH',0x108,len(desc))+desc
  m=mom(b'\x0f\xa0',0x104,extra)
  fragments=[bytes([8|(2 if i else 0)|(4 if i+254<len(m) else 0)])+m[i:i+254] for i in range(0,len(m),254)]
  original=self.forward_packet(fragments,90000)[0]
  packets=self.reverse_section(original,180000)
  self.assertGreater(len(packets),1)
  self.assertEqual(self.forward_packet(packets,180000)[0],original)
 def test_reject_crc_encryption_late_component_and_unrepresentable_duration(self):
  original=self.forward_packet([b'\x08'+mom(splice())],90000)[0]
  bad=bytearray(original);bad[-1]^=1;self.reverse_section(bad,90000,ok=False)
  for index,mask in ((4,0x80),(19,0x40)):
   bad=bytearray(original);bad[index]^=mask;bad[-4:]=crc(bad[:-4]).to_bytes(4,'big');self.reverse_section(bad,90000,ok=False)
  bad=bytearray(original);bad[29]^=1;bad[-4:]=crc(bad[:-4]).to_bytes(4,'big');self.reverse_section(bad,90000,ok=False)
  self.reverse_section(original,450090,ok=False)
 def test_null_roundtrip(self):
  original=self.forward_packet([b'\x08'+mom(b'',0x102)],90000)[0]
  self.assertEqual(self.forward_packet(self.reverse_section(original,180000),180000)[0],original)

class ScteOutputRouteTests(unittest.TestCase):
 def setUp(self):
  f=test_decklink.DeckLinkOutputTests();f.setUp();self.cfg=f.cfg;self.cap=dict(f.cap,decklink_scte_output=True,decklink_options=['spankvanc_scte104'])
 def test_sdi_pass_and_strip_are_independent_of_captions(self):
  self.cfg['outputs'][0].update(captions='strip',scte='pass')
  self.assertTrue(plan(self.cfg,self.cap)['ready'])
  args=command(validate(self.cfg),self.cap)
  self.assertIn('-spankvanc_scte104',args);self.assertIn('-spankvanc_scte_output',args)
  self.assertIn('sidedata=mode=delete:type=A53_CC',args)
  self.cfg['outputs'][0].update(captions='pass',scte='strip')
  args=command(validate(self.cfg),self.cap);self.assertNotIn('-spankvanc_scte104',args);self.assertNotIn('-spankvanc_scte_output',args)
 def test_ts_convert_preserves_clock_and_selects_pid(self):
  self.cfg['input'].update(kind='file',address='source.ts',scte_pid='0x1ffe');self.cfg['outputs'][0]['scte']='convert'
  self.assertTrue(plan(self.cfg,self.cap)['ready']);args=command(validate(self.cfg),self.cap)
  self.assertIn('-copyts',args);self.assertIn('0:i:8190',args)
  self.assertEqual(args[args.index('-spankvanc_scte_output')+1],'2')
  self.cfg['input']['scte_pid']='';args=command(validate(self.cfg),self.cap);self.assertIn('0:d:0?',args)
  self.assertFalse(plan(self.cfg,dict(self.cap,decklink_scte_output=False))['ready'])
 def test_invalid_pid_rejected(self):
  for pid in (True,-1,0,8191,'junk'):
   self.cfg['input']['scte_pid']=pid
   with self.assertRaises(ConfigError):validate(self.cfg)
