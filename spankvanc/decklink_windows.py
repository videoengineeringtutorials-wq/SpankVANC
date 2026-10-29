"""Read-only Desktop Video COM attributes; never opens streams or sets profiles.

Run the COM query in a bounded child process so driver failures cannot crash or
hang the web server. Method slots and IDs follow DeckLink SDK 12.8 interfaces.
"""
import json
import os
from pathlib import Path
import subprocess
import sys


def discover_attributes():
    if os.name != 'nt':
        return [], ''
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve())],
                                capture_output=True, text=True, timeout=12)
        if result.returncode:
            return [], result.stderr.strip() or 'Desktop Video attribute query failed'
        devices = json.loads(result.stdout)
        if not isinstance(devices, list):
            raise ValueError('Invalid Desktop Video attribute response')
        return devices, ''
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return [], str(exc)


def enrich_devices(cap, devices):
    """Match SDK display names exactly; preserve FFmpeg names and mode lists."""
    by_name = {d['name']: d for d in devices}
    for key in ('decklink_devices', 'decklink_outputs'):
        for device in cap.get(key, []):
            attrs = by_name.get(device['name'])
            if attrs:
                device.update({k: v for k, v in attrs.items() if k != 'name'})


def query():
    import ctypes as c
    import uuid

    pointer = c.c_void_p
    hresult = c.c_long
    ole = c.OleDLL('ole32')
    automation = c.OleDLL('oleaut32')
    ole.CoInitializeEx.argtypes = [pointer, c.c_ulong]
    ole.CoCreateInstance.argtypes = [pointer, pointer, c.c_ulong, pointer, c.POINTER(pointer)]
    automation.SysFreeString.argtypes = [pointer]

    def guid(value):
        return c.create_string_buffer(uuid.UUID(value).bytes_le)

    def call(obj, slot, types, *args):
        table = c.cast(obj, c.POINTER(c.POINTER(pointer))).contents
        return c.WINFUNCTYPE(hresult, pointer, *types)(table[slot])(obj, *args)

    def release(obj):
        if obj:
            call(obj, 2, [])

    def interface(obj, iid):
        out = pointer()
        hr = call(obj, 0, [pointer, c.POINTER(pointer)], guid(iid), c.byref(out))
        return out if hr == 0 else pointer()

    def string(obj, slot):
        out = pointer()
        hr = call(obj, slot, [c.POINTER(pointer)], c.byref(out))
        try:
            return c.wstring_at(out) if hr == 0 and out else ''
        finally:
            if out:
                automation.SysFreeString(out)

    def integer(obj, key):
        out = c.c_longlong()
        hr = call(obj, 4, [c.c_uint32, c.POINTER(c.c_longlong)], key, c.byref(out))
        return out.value if hr == 0 else None

    # A fresh child owns this COM apartment and all acquired references.
    ole.CoInitializeEx(None, 0)
    iterator = pointer()
    devices = []
    try:
        ole.CoCreateInstance(guid('ba6c6f44-6da5-4dce-94aa-ee2d1372a676'), None, 23,
                             guid('50fb36cd-3063-4b73-bdbb-958087f2d8ba'), c.byref(iterator))
        for _ in range(64):
            device = pointer()
            if call(iterator, 3, [c.POINTER(pointer)], c.byref(device)) != 0:
                break
            attrs = pointer()
            try:
                item = {'name': string(device, 4), 'model': string(device, 3)}
                attrs = interface(device, '17d4bf8e-4911-473a-80a0-731cf6ff345b')
                if attrs:
                    value = integer(attrs, 0x64757078)  # BMDDeckLinkDuplex
                    item['duplex'] = {0x64786675: 'full', 0x64786861: 'half',
                                      0x64787370: 'simplex', 0x6478696e: 'inactive'}.get(value, 'unknown')
                    for key, ident in (('subdevice_index', 0x73756269),
                                       ('subdevice_count', 0x6e736264), ('profile_id', 0x70726964)):
                        value = integer(attrs, ident)
                        if value is not None:
                            item[key] = value
                if item['name']:
                    devices.append(item)
            finally:
                release(attrs)
                release(device)
        return devices
    finally:
        release(iterator)
        ole.CoUninitialize()


if __name__ == '__main__':
    try:
        print(json.dumps(query()))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
