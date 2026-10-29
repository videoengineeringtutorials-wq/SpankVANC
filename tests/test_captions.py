import unittest
from unittest.mock import patch
from spankvanc.captions import SourceMonitor, EXTENDED


def parity(v):
    v &= 127
    return v if v.bit_count()%2 else v|128


def cc(*pairs,field=0):
    return b''.join(bytes([0xfc|field,parity(a),parity(b)]) for a,b in pairs).hex()


class CaptionMonitorTests(unittest.TestCase):
    def feed(self,m,*pairs,field=0,pts=0):
        m.feed({'signal':True,'pts90k':pts,'cc':cc(*pairs,field=field)})

    def test_pop_on_duplicate_controls_and_erase(self):
        m=SourceMonitor()
        self.feed(m,(0x14,0x20),(0x14,0x20),(ord('H'),ord('I')))
        self.assertEqual(m.state(True)['services']['CC1'],'')
        self.feed(m,(0x14,0x2f),(0x14,0x2f),pts=3003)
        self.assertEqual(m.state(True)['services']['CC1'],'HI')
        self.feed(m,(0x14,0x2c))
        self.assertEqual(m.state(True)['services']['CC1'],'')

    def test_rollup_and_field_channel_separation(self):
        m=SourceMonitor()
        self.feed(m,(0x14,0x25),(ord('O'),ord('N')),(ord('E'),0),(0x14,0x2d),(ord('T'),ord('W')),(ord('O'),0))
        self.assertEqual(m.state(True)['services']['CC1'],'ONE\nTWO')
        self.feed(m,(0x1c,0x29),(ord('C'),ord('4')),field=1)
        self.assertEqual(m.state(True)['services']['CC4'],'C4')
        self.assertEqual(m.state(True)['services']['CC3'],'')

    def test_xds_parity_digital_and_signal_loss(self):
        m=SourceMonitor()
        self.feed(m,(1,5),(ord('N'),ord('O')),(0x0f,0),field=1)
        self.assertFalse(any(m.state(True)['services'].values()))
        m.feed({'signal':True,'cc':'fc0000fe1122ff3344','pts90k':0})
        self.assertEqual(m.state(True)['digital_triplets'],2)
        self.assertEqual(m.state(True)['invalid_triplets'],1)
        self.feed(m,(0x14,0x29),(ord('Y'),ord('E')))
        m.feed({'signal':False,'pts90k':3003})
        self.assertEqual(m.state(True)['status'],'no_signal')
        self.assertFalse(m.state(True)['services']['CC1'])
        with patch('spankvanc.captions.time.monotonic',return_value=m.last_update+5):
            self.assertEqual(m.state(True)['status'],'stale')
        self.assertEqual(m.state(False)['status'],'stopped')

    def test_extended_tables_and_bounded_history(self):
        self.assertEqual([len(t) for t in EXTENDED],[32,32])
        m=SourceMonitor()
        for i in range(300):
            self.feed(m,(0x14,0x29),(0x14,0x2c),(65+i%26,66),pts=i*90000)
        self.assertLessEqual(len(m.history),100)

    def test_rejections_are_retained_bounded_and_not_recounted(self):
        m=SourceMonitor()
        event={'rejected_total':1,'last_rejection':'unsupported operation','last_rejected_hex':'087777','last_rejected_pts90k':90000}
        m.feed(event);m.feed(event);m.feed({'converted':1})
        self.assertEqual(m.rejected,1)
        self.assertEqual(m.converted,1)
        self.assertEqual(len(m.rejections),1)
        self.assertEqual(m.rejections[0]['payload_hex'],'087777')
        for i in range(2,80):m.feed(dict(event,rejected_total=i,last_rejection='x'*600,last_rejected_hex='ff'*300))
        self.assertEqual(len(m.rejections),50)
        self.assertEqual(len(m.rejections[-1]['reason']),512)
        self.assertEqual(len(m.rejections[-1]['payload_hex']),510)

    def test_engine_persists_rejection_and_activity_reason(self):
        import io,json,tempfile
        from pathlib import Path
        from unittest.mock import Mock
        from license_fixture import LicensedEngine as Engine
        with tempfile.TemporaryDirectory() as folder,patch('spankvanc.engine.doctor',return_value={}):
            engine=Engine(Path(folder))
            event={'rejected_total':1,'last_rejection':'unsupported operation 0x777','last_rejected_hex':'087777','last_rejected_pts90k':90000}
            process=Mock();process.stderr=io.StringIO('SPANKVANC '+json.dumps(event)+'\n');process.wait.return_value=1
            engine.process=process;engine._read(process)
            path=Path(folder)/'scte-rejections.ndjson'
            self.assertEqual(json.loads(path.read_text())['payload_hex'],'087777')
            self.assertTrue(any('unsupported operation 0x777' in line for line in engine.logs))
            path.write_text('x'*1048576)
            engine._save_rejection(engine.source_monitor.rejections[-1])
            self.assertTrue(path.with_suffix('.ndjson.1').exists())
            self.assertEqual(json.loads(path.read_text())['total'],1)
