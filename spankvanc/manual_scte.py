"""Output-only immediate splice_insert cues, queued privately per route/output."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import secrets


def crc(data):
    value = 0xffffffff
    for byte in data:
        value ^= byte << 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04c11db7 if value & 0x80000000 else 0)) & 0xffffffff
    return value


def section(event, action, duration=60):
    from .engine import ConfigError
    try:
        seconds = Decimal(str(duration))
        ticks = seconds * 10
        if not seconds.is_finite() or not 1 <= ticks <= 65535 or ticks != int(ticks):
            raise ValueError()
    except (InvalidOperation, ValueError, OverflowError):
        raise ConfigError("Break duration must be 0.1–6553.5 seconds in 0.1-second steps") from None
    start = action == "start"
    command = event.to_bytes(4, "big") + b'\x7f' + (b'\xff' if start else b'\x5f')
    if start:
        # Duration is informational; explicit End returns to program (auto_return=0).
        command += (int(ticks) * 9000 | (0x7e << 32)).to_bytes(5, "big")
    command += b'\x00\x01\x00\x00'  # unique_program_id, avail_num, avails_expected
    data = bytearray(b'\xfc\x30\x00\x00\x00\x00\x00\x00\x00\x00\xff\xf0' + bytes([len(command), 5]) + command + b'\x00\x00')
    data[1:3] = (0x3000 | (len(data) + 1)).to_bytes(2, "big")
    return bytes(data) + crc(data).to_bytes(4, "big")


def prepare_journals(state_dir, cfg):
    directory = Path(state_dir) / "manual-scte" / secrets.token_hex(12)
    journals = {}
    for index, output in enumerate(cfg['outputs']):
        if output['enabled'] and output['scte'] == 'manual':
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = directory / f'output-{index}.bin'
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            journals[index] = path
    return journals


def append_cue(path, cue):
    # Fixed records let consumers wait for a complete append across platforms.
    record = bytes([len(cue)]) + cue
    with open(path, 'ab', buffering=0) as stream:
        if stream.write(record.ljust(64, b'\x00')) != 64:
            raise OSError('Could not queue complete SCTE cue')
