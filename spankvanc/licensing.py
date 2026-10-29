"""Online, server-timed licensing. Credentials stay in per-user private state."""
from __future__ import annotations
import json
import http.client
import math
import os
from pathlib import Path
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

SERVER_URL = 'https://tvrewards.gear.host/spankvanc-license.ashx'
CHECK_SECONDS = 60
KEY_PATTERN = re.compile(r'SV1-[A-Za-z0-9_-]{43}\Z')


class LicenseError(ValueError):
    pass


def storage_path():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    return base / 'SpankVANC' / 'license.json'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LicenseError('License server redirected the request; contact the operator.')


class LicenseClient:
    def __init__(self, path=None, url=None, *, opener=None, monotonic=time.monotonic):
        self.path = Path(path) if path is not None else storage_path()
        self.url = url or os.environ.get('SPANKVANC_LICENSE_SERVER') or SERVER_URL
        parsed = urllib.parse.urlsplit(self.url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment):
            raise LicenseError('The license server must use a plain HTTPS endpoint URL.')
        self.opener = opener or urllib.request.build_opener(NoRedirect()).open
        self.monotonic = monotonic
        self.lock = threading.RLock()
        self.key = ''
        self.installation = secrets.token_hex(32)
        self.until = 0.0
        self.next_check = 0.0
        self.details = {'valid': False, 'message': 'Enter a license key to activate 30 days of use.'}
        try:
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(saved, dict): raise ValueError()
            if re.fullmatch(r'[0-9a-f]{64}', saved.get('installation', '')):
                self.installation = saved['installation']
            if KEY_PATTERN.fullmatch(saved.get('key', '')):
                self.key = saved['key']
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError):
            self.details['message'] = 'Saved license data could not be read. Re-enter your key or contact the operator.'

    def _save(self, key):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_name('license-' + secrets.token_hex(8) + '.tmp')
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump({'installation': self.installation, 'key': key}, stream)
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def status(self):
        with self.lock:
            result = dict(self.details)
            result['valid'] = bool(result.get('valid') and self.monotonic() < self.until)
            if self.details.get('valid') and not result['valid']:
                result['message'] = 'Online license verification is required.'
            return result

    def due(self):
        with self.lock:
            return bool(self.key and self.monotonic() >= self.next_check)

    def _request(self, action, key):
        # Only these two values leave the app: no route, stream key, audio or hostname.
        body = json.dumps({'action': action, 'key': key, 'installation': self.installation}).encode()
        request = urllib.request.Request(self.url, data=body,
            headers={'Content-Type': 'application/json', 'User-Agent': 'SpankVANC-Licensing/1'}, method='POST')
        started = self.monotonic()
        try:
            try:
                response = self.opener(request, timeout=5)
            except urllib.error.HTTPError as exc:
                if exc.code not in (400, 403, 409): raise
                response = exc
            with response:
                raw = response.read(8193)
            if len(raw) > 8192: raise ValueError()
            data = json.loads(raw)
            if not isinstance(data, dict) or type(data.get('valid')) is not bool: raise ValueError()
            if not data['valid']:
                messages = {'invalid': 'License key is invalid or revoked.',
                            'expired': 'Your 30-day license has expired. Enter a new key.',
                            'bound': 'This license is already activated for another installation.',
                            'inactive': 'Activate this key before using the app.'}
                return {'valid': False, 'message': messages.get(data.get('reason'), 'License verification failed.')}, 0
            now, activated, expires = (data[n] for n in ('server_time', 'activated_at', 'expires_at'))
            if any(type(v) is not int for v in (now, activated, expires)): raise ValueError()
            if not (0 < activated <= now < expires and expires - activated == 30 * 86400): raise ValueError()
            remaining = expires - now - (self.monotonic() - started)
            if not math.isfinite(remaining) or remaining <= 0: raise ValueError()
            return {'valid': True, 'message': 'License active.', 'activated_at': activated,
                    'expires_at': expires, 'days_remaining': math.ceil(remaining / 86400)}, min(CHECK_SECONDS, remaining)
        except (OSError, http.client.HTTPException, ValueError, TypeError, KeyError):
            # Do not echo URLs, request bodies, keys or arbitrary remote errors.
            return {'valid': False, 'message': 'Cannot verify the license online. Check Internet access and retry.'}, 0

    def check(self, force=False):
        with self.lock:
            if not self.key: return self.status()
            if not force and self.monotonic() < self.next_check: return self.status()
            self.details, lease = self._request('check', self.key)
            self.until = self.monotonic() + lease
            self.next_check = self.monotonic() + (lease or CHECK_SECONDS)
            return self.status()

    def require(self):
        result = self.check(force=True)
        if not result['valid']: raise LicenseError(result['message'])

    def activate(self, key):
        with self.lock:
            if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key.strip()):
                raise LicenseError('Enter a complete SV1 license key.')
            key = key.strip()
            # Save the installation ID before first activation so a failed response
            # or local save cannot strand the license bound to a lost identifier.
            self._save(self.key)
            details, lease = self._request('activate', key)
            if not details['valid']: raise LicenseError(details['message'])
            self._save(key)
            self.key = key
            self.details = details
            self.until = self.monotonic() + lease
            self.next_check = self.until
            return self.status()
