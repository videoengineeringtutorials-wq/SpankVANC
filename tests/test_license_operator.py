"""Operator issuance keeps private and explicitly shared key policies separate."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tools.license_operator import issue


class LicenseOperatorTests(unittest.TestCase):
    def test_shared_is_opt_in_and_sql_contains_hash_only(self):
        with tempfile.TemporaryDirectory() as folder:
            for shared in (False, True):
                prefix=Path(folder)/str(shared)
                issue("Tester's trial",prefix,shared=shared)
                data=json.loads(Path(str(prefix)+'.json').read_text())
                sql=Path(str(prefix)+'.sql').read_text()
                self.assertEqual(data['shared'],shared)
                self.assertEqual(data['label'],"Tester's trial")
                self.assertEqual(data['key_hash'],hashlib.sha256(data['key'].encode()).hexdigest())
                self.assertNotIn(data['key'],sql)
                self.assertIn("N'Tester''s trial'",sql)
                self.assertTrue(sql.endswith(('1' if shared else '0')+');\n'))
                self.assertNotIn('activated_at',sql)
