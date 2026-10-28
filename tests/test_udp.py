"""TS-over-UDP destinations must preserve complete 188-byte packets."""
import unittest
from spankvanc.engine import validate,ConfigError,command
from test_core import route,CAP

class UDPTests(unittest.TestCase):
    def config(self,address):
        cfg=route();cfg['outputs'][0].update(kind='udp',address=address);return cfg

    def test_default_packet_size_and_existing_parameters(self):
        cfg=validate(self.config('udp://127.0.0.1:5000?ttl=4&buffer_size=1048576'))
        address=cfg['outputs'][0]['address']
        self.assertIn('pkt_size=1316',address);self.assertIn('ttl=4',address)
        self.assertIn(address,command(cfg,CAP));self.assertEqual(validate(cfg),cfg)
        self.assertEqual(validate(self.config('udp://127.0.0.1:5000?pkt_size=188'))['outputs'][0]['address'],'udp://127.0.0.1:5000?pkt_size=188')

    def test_rejects_unaligned_or_oversized_datagrams(self):
        for value in ('1472','1315','0','-188','188&pkt_size=376','abc',''):
            with self.assertRaises(ConfigError):validate(self.config('udp://127.0.0.1:5000?pkt_size='+value))
