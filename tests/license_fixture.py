"""Explicit licensed test double for tests of media behavior, without network calls."""
from spankvanc.engine import Engine


class TestLicense:
    __test__ = False
    def __init__(self):
        self.valid = True
    def status(self):
        return {'valid': self.valid, 'message': 'Test license active.' if self.valid else 'License expired.'}
    def check(self, force=False): return self.status()
    def require(self):
        if not self.valid:
            from spankvanc.licensing import LicenseError
            raise LicenseError('License expired.')
    def due(self): return True


class LicensedEngine(Engine):
    def __init__(self, state_dir):
        super().__init__(state_dir, license_client=TestLicense())
