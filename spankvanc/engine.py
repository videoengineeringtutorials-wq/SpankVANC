"""Validated route plans and a local FFmpeg process supervisor.

Capability gates are deliberate: a successful A/V encode is not evidence of
SCTE or ANC preservation. Unsupported metadata paths never start silently.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
from collections import deque
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .captions import SourceMonitor
from .ffmpeg_compat import discover as ffmpeg_discover, option_names


YOUTUBE_FILTERS = {"yadif", "scale", "pad", "setsar", "fps", "setfield", "sidedata"}
YOUTUBE_VIDEO_FILTER = ("yadif=mode=send_frame:parity=auto:deint=interlaced,"
    "scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2:out_color_matrix=bt709:out_range=tv,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,setfield=prog")

YOUTUBE_SERVER = "rtmps://a.rtmps.youtube.com:443/live2"

DEFAULT = {
    "name": "Main program",
    "input": {"kind": "decklink", "address": "", "realtime": True, "format_code": "", "scte_error_policy": "continue", "scte_pid": None},
    "outputs": [{"name": "Program TS", "kind": "udp", "address": "udp://127.0.0.1:5000?pkt_size=1316",
                 "captions": "pass", "scte": "convert", "video_codec": "h264", "enabled": True}],
    "whisper": {"model": "small.en", "language": "en", "delay_ms": 0, "audio_channel": 1, "device": "auto"},
    "gpo": {"enabled": False, "port": "", "baud": 115200, "channel": 1, "pulse_ms": 250},
}


class ConfigError(ValueError):
    pass


def video_codec_options(destination: str) -> dict[str, str]:
    if destination == "decklink":
        return {"uncompressed": "Uncompressed SDI"}
    if destination in ("rtmp", "youtube"):
        return {"h264": "H.264 / AVC"}
    return {"h264": "H.264 / AVC", "mpeg2video": "MPEG-2 video"}


def scte_options(source: str, destination: str) -> dict[str, str]:
    """Carriage is fixed by SDI/TS, not by a user-selectable conversion direction."""
    ts = ("udp", "srt", "file")
    if source == destination == "decklink":
        return {"pass": "Pass SCTE-104", "strip": "Strip SCTE-104"}
    if source in ts and destination in ts:
        return {"pass": "Pass SCTE-35", "strip": "Strip SCTE-35"}
    if source == "decklink" and destination in ts:
        return {"convert": "Convert 104 → 35", "strip": "Strip SCTE-104"}
    if source in ts and destination == "decklink":
        return {"convert": "Convert 35 → 104", "strip": "Strip SCTE-35"}
    return {"strip": "No SCTE carriage"}


def scte_matrix() -> dict:
    return {source: {destination: scte_options(source, destination)
                     for destination in ("decklink", "udp", "srt", "file", "rtmp", "youtube")}
            for source in ("decklink", "udp", "srt", "file", "rtmp")}


def validate(raw: dict, *, check_scte: bool = True) -> dict:
    """Return a normalized copy; reject typos, invalid endpoints and policies."""
    if not isinstance(raw, dict):
        raise ConfigError("Configuration must be an object")
    unknown = set(raw) - set(DEFAULT)
    if unknown:
        raise ConfigError("Unknown setting: " + ", ".join(sorted(unknown)))
    cfg = copy.deepcopy(DEFAULT)
    for key, value in raw.items():
        if key in ("input", "whisper", "gpo"):
            if not isinstance(value, dict) or set(value) - set(DEFAULT[key]):
                raise ConfigError(f"Invalid {key} settings")
            cfg[key].update(value)
        else:
            cfg[key] = copy.deepcopy(value)
    if not isinstance(cfg["name"], str) or not 1 <= len(cfg["name"]) <= 100:
        raise ConfigError("Route name must contain 1–100 characters")
    src = cfg["input"]
    if src["kind"] not in ("decklink", "udp", "srt", "rtmp", "file"):
        raise ConfigError("Unknown input type")
    if type(src["realtime"]) is not bool:
        raise ConfigError("Input realtime must be true or false")
    if not isinstance(src["format_code"], str) or (src["format_code"] and not re.fullmatch(r"[A-Za-z0-9 ]{4}", src["format_code"])):
        raise ConfigError("DeckLink mode must be a four-character code")
    pid=src.get("scte_pid")
    if pid in (None, ""):
        src["scte_pid"]=None
    else:
        try:
            if isinstance(pid,bool): raise ValueError()
            pid=int(pid,16 if str(pid).lower().startswith("0x") else 10) if isinstance(pid,str) else pid
            if not isinstance(pid,int) or not 16 <= pid <= 8190: raise ValueError()
        except (ValueError,TypeError): raise ConfigError("SCTE-35 PID must be 16..8190, decimal or 0x hex")
        src["scte_pid"]=pid
    if src["scte_error_policy"] not in ("continue", "stop"):
        raise ConfigError("SCTE error policy must be continue or stop")
    endpoint(src["kind"], src["address"], allow_empty=True)
    if not isinstance(cfg["outputs"], list) or not 1 <= len(cfg["outputs"]) <= 8:
        raise ConfigError("Configure between one and eight outputs")
    names = set()
    for out in cfg["outputs"]:
        required = {"name", "kind", "address", "captions", "scte", "enabled"}
        if not isinstance(out, dict) or not required <= set(out) or set(out) - required - {"video_codec", "youtube_server", "youtube_stream_key", "youtube_bitrate_mbps"}:
            raise ConfigError("Each output needs name, kind, address, captions, scte, enabled")
        if not isinstance(out["name"], str) or not 1 <= len(out["name"]) <= 100 or out["name"] in names:
            raise ConfigError("Output names must be nonempty and unique")
        names.add(out["name"])
        if out["kind"] not in ("decklink", "udp", "srt", "rtmp", "youtube", "file"):
            raise ConfigError("Unknown output type")
        # Older saved routes used H.264 implicitly; preserve that default.
        out.setdefault("video_codec", "uncompressed" if out["kind"] == "decklink" else "h264")
        if not isinstance(out["video_codec"], str) or out["video_codec"] not in video_codec_options(out["kind"]):
            raise ConfigError(f"{out['name']}: {out['kind']} does not support video codec {out['video_codec']}")
        if out["kind"] == "youtube":
            bitrate = out.setdefault("youtube_bitrate_mbps", 14)
            if type(bitrate) is not int or bitrate not in (6, 8, 10, 14):
                raise ConfigError("YouTube bitrate must be 6, 8, 10 or 14 Mbit/s")
            # Migrate saved combined destinations into the two editable fields.
            if "youtube_server" not in out and "youtube_stream_key" not in out:
                address = out["address"]
                endpoint("youtube", address, allow_empty=True)
                server, separator, key = address.rpartition("/")
                if address and separator and urlsplit(address).path.count("/") >= 2:
                    out["youtube_server"], out["youtube_stream_key"] = server, key
                else:
                    out["youtube_server"], out["youtube_stream_key"] = address or YOUTUBE_SERVER, ""
            server = out.get("youtube_server", YOUTUBE_SERVER)
            key = out.get("youtube_stream_key", "")
            if not isinstance(server, str):
                raise ConfigError("YouTube RTMPS server must be a URL")
            server = server.strip().rstrip("/")
            endpoint("youtube", server)
            parsed = urlsplit(server)
            if parsed.query or parsed.username or parsed.password or not parsed.path.strip("/"):
                raise ConfigError("YouTube RTMPS server must include an application path and exclude credentials or query parameters")
            if not isinstance(key, str) or len(key) > 1024 or any(c.isspace() or c in "/?#:" or ord(c) < 32 for c in key):
                raise ConfigError("Paste only the YouTube stream key, without a URL or spaces")
            out["youtube_server"], out["youtube_stream_key"] = server, key
            out["address"] = server + "/" + key if key else ""
        else:
            out.pop("youtube_server", None); out.pop("youtube_stream_key", None); out.pop("youtube_bitrate_mbps", None)
        endpoint(out["kind"], out["address"], allow_empty=True)
        if out["kind"] == "udp" and out["address"]:
            parsed = urlsplit(out["address"])
            query = parse_qsl(parsed.query, keep_blank_values=True)
            sizes = [value for key,value in query if key == "pkt_size"]
            if not sizes:
                query.append(("pkt_size", "1316"))
            elif len(sizes) != 1 or not sizes[0].isdigit() or int(sizes[0]) not in range(188,1317,188):
                raise ConfigError("UDP output pkt_size must be a multiple of 188 between 188 and 1316; use 1316")
            out["address"] = urlunsplit(parsed._replace(query=urlencode(query)))
        if out["captions"] not in ("pass", "strip", "recaption"):
            raise ConfigError("Caption policy must be pass, strip or recaption")
        if out["scte"] not in ("pass", "strip", "convert"):
            raise ConfigError("SCTE policy must be pass, strip or convert")
        allowed = scte_options(src["kind"], out["kind"])
        if check_scte and out["scte"] not in allowed:
            raise ConfigError(f"{out['name']}: {src['kind']} → {out['kind']} allows only "
                              + " or ".join(allowed.values()))
        if type(out["enabled"]) is not bool:
            raise ConfigError("Output enabled must be true or false")
    whisper = cfg["whisper"]
    if whisper["model"] not in ("tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "medium.en", "large-v3", "turbo"):
        raise ConfigError("Unknown Whisper model")
    if not isinstance(whisper["language"], str) or not re.fullmatch(r"[a-z]{2,3}", whisper["language"]):
        raise ConfigError("Whisper language must be a two or three letter code")
    integer(whisper["delay_ms"], 0, 60000, "Whisper delay")
    integer(whisper["audio_channel"], 1, 2, "Whisper audio channel")
    if whisper["device"] not in ("auto", "cpu", "cuda"):
        raise ConfigError("Whisper device must be auto, cpu or cuda")
    gpo = cfg["gpo"]
    if type(gpo["enabled"]) is not bool or not isinstance(gpo["port"], str):
        raise ConfigError("Invalid GPO settings")
    if gpo["baud"] != 115200:
        raise ConfigError("Firmware currently uses 115200 baud")
    integer(gpo["channel"], 1, 4, "GPO channel")
    integer(gpo["pulse_ms"], 10, 10000, "GPO pulse")
    return cfg


def integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ConfigError(f"{label} must be an integer between {minimum} and {maximum}")


def endpoint(kind, address, allow_empty=False):
    if not isinstance(address, str) or len(address) > 4096 or any(ord(c) < 32 for c in address):
        raise ConfigError("Invalid endpoint address")
    if not address:
        if allow_empty:
            return
        raise ConfigError("An endpoint address is required")
    if kind in ("file", "decklink"):
        if address.startswith("-"):
            raise ConfigError("Endpoint cannot begin with '-' ")
        if kind == "file" and "://" in address:
            raise ConfigError("File endpoint must be a local path")
        return
    parsed = urlsplit(address)
    schemes = {"udp": ("udp",), "srt": ("srt",), "rtmp": ("rtmp", "rtmps"), "youtube": ("rtmps",)}
    try:
        port = parsed.port
    except ValueError as exc:
        raise ConfigError("Invalid endpoint port") from exc
    if parsed.scheme not in schemes[kind] or not parsed.hostname:
        raise ConfigError(f"{kind} requires a {schemes[kind]} URL with a host")
    if kind in ("udp", "srt") and port is None:
        raise ConfigError(f"{kind} requires an explicit port")
    if parsed.fragment:
        raise ConfigError("Endpoint URLs cannot contain fragments")


def scrub(text: str) -> str:
    """Hide entire media URLs, including RTMP stream keys and SRT passphrases."""
    return re.sub(r"(?:rtmps?|srt|udp)://[^\s\"']+", "[media endpoint]", text)


def executable(decklink=False) -> str:
    if decklink:
        custom = os.environ.get("SPANKVANC_DECKLINK_FFMPEG")
        bundled = Path(__file__).resolve().parent.parent / "build/ffmpeg-decklink/bin/ffmpeg"
        if custom:
            return custom
        if bundled.is_file():
            return str(bundled)
    return os.environ.get("SPANKVANC_FFMPEG", "ffmpeg")


def decklink_devices() -> tuple[list, str]:
    diagnostic = os.environ.get("SPANKVANC_DECKLINK_DIAGNOSTIC",
        str(Path(__file__).resolve().parent.parent / "build/native/spankvanc-decklink"))
    if not Path(diagnostic).is_file():
        return [], "Build the native DeckLink diagnostic to enumerate devices and modes"
    try:
        result = subprocess.run([diagnostic, "--list"], capture_output=True, text=True, timeout=12)
        if result.returncode:
            return [], scrub(result.stderr.strip())
        devices = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        return devices, ""
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return [], scrub(str(exc))


def doctor() -> dict:
    binary = executable()
    result = {"ffmpeg": shutil.which(binary), "decklink_input": False, "decklink_output": False,
              "srt": False, "rtmp": False, "libx264": False, "mpeg2video": False, "aac": False, "tsp": shutil.which("tsp"),
              "platform": os.name, "decklink_devices": [], "native_anc": False,
              "recaption_runtime": False, "scte_runtime": False, "source_monitor": False, "scte_recovery": False}
    if not result["ffmpeg"]:
        return result
    def query(*args):
        p = subprocess.run([binary, "-hide_banner", *args], capture_output=True, text=True, timeout=12)
        return p.stdout + p.stderr
    devices = query("-devices")
    for line in devices.splitlines():
        if "decklink" in line:
            flags = line.split()[0]
            result["decklink_input"] = "D" in flags
            result["decklink_output"] = "E" in flags
    protocols = query("-protocols").split()
    result["srt"] = "srt" in protocols
    result["rtmp"] = "rtmp" in protocols
    encoders = {parts[1] for line in query("-encoders").splitlines()
                if len(parts := line.split()) >= 2}
    for codec in ("libx264", "mpeg2video", "aac"):
        result[codec] = codec in encoders
    result["version"] = query("-version").splitlines()[0]
    result["decklink_devices"], result["decklink_error"] = decklink_devices()
    result["native_anc"] = bool(result["decklink_devices"])
    result["decklink_discovery"] = "sdk" if result["native_anc"] else "unavailable"
    deck_binary = executable(True)
    result["decklink_ffmpeg"] = shutil.which(deck_binary)
    if result["decklink_ffmpeg"]:
        try:
            probe = subprocess.run([deck_binary, "-hide_banner", "-devices"], capture_output=True, text=True, timeout=12)
            result["decklink_output"] = any("decklink" in line and "E" in line.split()[0]
                for line in (probe.stdout + probe.stderr).splitlines() if line.split())
            result["decklink_input"] = any("decklink" in line and "D" in line.split()[0]
                for line in (probe.stdout + probe.stderr).splitlines() if line.split())
        except (OSError, subprocess.TimeoutExpired):
            result["decklink_input"] = False
    if result.get("decklink_output"):
        try:
            probe = subprocess.run([deck_binary, "-hide_banner", "-h", "muxer=decklink"], capture_output=True, text=True, timeout=12)
            result["decklink_caption_output"] = "spankvanc_caption_output" in probe.stdout + probe.stderr
            result["decklink_scte_output"] = "spankvanc_scte_output" in probe.stdout + probe.stderr
            from .ffmpeg_compat import discover_outputs
            result["decklink_outputs"], result["decklink_output_error"] = discover_outputs(deck_binary)
        except (OSError, subprocess.TimeoutExpired):
            pass
    if result.get("decklink_input"):
        try:
            probe = subprocess.run([deck_binary, "-hide_banner", "-h", "demuxer=decklink"], capture_output=True, text=True, timeout=12)
            options = probe.stdout + probe.stderr
            result["decklink_options"] = option_names(options)
            result["source_monitor"] = "spankvanc_anc" in options
            result["scte_runtime"] = "spankvanc_scte35" in options
            result["scte_recovery"] = "spankvanc_scte_strict" in options
        except (OSError, subprocess.TimeoutExpired):
            pass
    if result.get("decklink_input") and not result["decklink_devices"]:
        result["decklink_devices"], result["decklink_error"] = ffmpeg_discover(deck_binary)
        if result["decklink_devices"]:
            result["decklink_discovery"] = "ffmpeg"
    if os.name == "nt" and (result.get("decklink_input") or result.get("decklink_output")):
        from .decklink_windows import discover_attributes, enrich_devices
        attributes, result["decklink_attribute_error"] = discover_attributes()
        enrich_devices(result, attributes)
    if result.get("decklink_input"):
        result["decklink_profile"] = "extended" if result.get("source_monitor") else "compatibility"
        if result["decklink_profile"] == "compatibility":
            result["caption_encoders"] = {}
            for codec,encoder in (("h264","libx264"),("mpeg2video","mpeg2video")):
                try:
                    p = subprocess.run([deck_binary,"-hide_banner","-h","encoder="+encoder],capture_output=True,text=True,errors="replace",timeout=12)
                    result["caption_encoders"][codec] = "a53cc" in option_names(p.stdout+p.stderr)
                except (OSError,subprocess.TimeoutExpired):
                    result["caption_encoders"][codec] = False
            try:
                p = subprocess.run([deck_binary,"-hide_banner","-h","filter=sidedata"],capture_output=True,text=True,errors="replace",timeout=12)
                result["caption_strip_filter"] = "A53_CC" in p.stdout+p.stderr
            except (OSError,subprocess.TimeoutExpired):
                result["caption_strip_filter"] = False
    from .whisper_runtime import probe as whisper_probe
    result["whisper"] = whisper_probe()
    for label, selected in (("general",binary),("decklink",deck_binary)):
        try:
            p=subprocess.run([selected,"-hide_banner","-h","filter=spankvanc_cc"],capture_output=True,text=True,timeout=12)
            result["recaption_"+label] = "UTF-8 journal" in p.stdout+p.stderr and "continuous field-slotted" in p.stdout+p.stderr
            if result["recaption_"+label]:
                mux=subprocess.run([selected,"-hide_banner","-muxers"],capture_output=True,text=True,timeout=12)
                result["recaption_"+label] = bool(re.search(r"\bf32le\b",mux.stdout+mux.stderr))
        except (OSError,subprocess.TimeoutExpired):
            result["recaption_"+label] = False
    result["recaption_runtime"] = result["whisper"].get("available",False) and result.get("recaption_decklink",False)
    result["youtube_profiles"] = {}
    for label, selected in (("general", binary), ("decklink", deck_binary)):
        try:
            def selected_query(*args):
                p = subprocess.run([selected, "-hide_banner", *args], capture_output=True, text=True, errors="replace", timeout=12)
                return p.stdout + p.stderr
            filters = {parts[1] for line in selected_query("-filters").splitlines() if len(parts := line.split()) >= 2}
            result["youtube_profiles"][label] = YOUTUBE_FILTERS <= filters and "rtmps" in selected_query("-protocols").split()
        except (OSError, subprocess.TimeoutExpired):
            result["youtube_profiles"][label] = False
    return result


def plan(raw: dict, capabilities: dict | None = None) -> dict:
    cfg = validate(raw, check_scte=False)
    cap = capabilities if capabilities is not None else doctor()
    blockers, notes, outputs = [], [], []
    src = cfg["input"]
    if not src["address"]:
        blockers.append("Set an input device or address")
    if not cap.get("ffmpeg"):
        blockers.append("FFmpeg is not installed")
    if src["kind"] == "decklink":
        if not cap.get("decklink_input"):
            blockers.append("Install the SpankVANC DeckLink-enabled FFmpeg build for live SDI capture")
        if cap.get("decklink_profile") == "compatibility":
            options = cap.get("decklink_options", [])
            if "format_code" not in options:
                blockers.append("This FFmpeg is too old to select DeckLink modes by format_code")
            if "raw_format" not in options and "bm_v210" not in options:
                blockers.append("This FFmpeg cannot select 10-bit DeckLink capture needed for caption extraction")
            notes.append("Existing FFmpeg compatibility mode: CPU A/V capture and its available caption handling only. Live source monitoring and SCTE conversion need the SpankVANC FFmpeg extensions. Check caption reception with a known source.")
        selected = next((d for d in cap.get("decklink_devices", []) if d.get("name") == src["address"] and d.get("input")), None)
        if not selected:
            blockers.append("Choose a detected DeckLink input device")
        if not src["format_code"]:
            blockers.append("Choose the SDI input video mode")
        elif selected and src["format_code"] not in {m["code"] for m in selected.get("modes", [])}:
            blockers.append("Selected video mode is not supported by this DeckLink device")
    if src["kind"] == "srt" and not cap.get("srt"):
        blockers.append("FFmpeg needs SRT support")
    if src["kind"] == "rtmp" and not cap.get("rtmp"):
        blockers.append("FFmpeg needs RTMP support")
    if cfg["gpo"]["enabled"]:
        blockers.append("Live SCTE-to-serial dispatch is not integrated yet; firmware and protocol are provided for bench testing")
    active = [o for o in cfg["outputs"] if o["enabled"]]
    if not active:
        blockers.append("Enable at least one output")
    destinations = set()
    for out in active:
        label = out["name"]
        kind = out["kind"]
        codec = out["video_codec"]
        if kind != "decklink":
            encoder = "libx264" if codec == "h264" else "mpeg2video"
            if not cap.get(encoder):
                blockers.append(f"{label}: FFmpeg needs the {encoder} encoder")
            if not cap.get("aac"):
                blockers.append(f"{label}: FFmpeg needs the AAC encoder")
        allowed = scte_options(src["kind"], kind)
        if out["scte"] not in allowed:
            blockers.append(f"{label}: {src['kind']} → {kind} allows only " + " or ".join(allowed.values()))
        if not out["address"]:
            blockers.append(f"{label}: paste a YouTube stream key" if kind == "youtube" else f"{label}: set a destination")
        if out["address"] in destinations:
            blockers.append(f"{label}: duplicate output destination")
        destinations.add(out["address"])
        if src["kind"] == kind == "file" and Path(src["address"]).resolve() == Path(out["address"]).resolve():
            blockers.append(f"{label}: output would overwrite the input")
        if kind == "decklink":
            if not cap.get("decklink_output"):
                blockers.append(f"{label}: selected FFmpeg needs DeckLink output support")
            ports = cap.get("decklink_outputs", [d for d in cap.get("decklink_devices", []) if d.get("output")])
            if not any(d["name"] == out["address"] for d in ports):
                blockers.append(f"{label}: choose an available DeckLink output port")
            if src["kind"] == "decklink" and src["address"] == out["address"]:
                # A DeckLink name identifies a subdevice, not necessarily one
                # physical socket. Full-duplex devices have separate IN/OUT.
                devices = cap.get("decklink_devices", []) + ports
                duplex = {d.get("duplex") for d in devices if d.get("name") == out["address"]} - {None, "unknown"}
                if duplex & {"half", "simplex", "inactive"}:
                    blockers.append(f"{label}: this DeckLink subdevice cannot capture and play out simultaneously in its active profile; choose another connector or configure Desktop Video Setup")
                elif "full" not in duplex:
                    notes.append(f"{label}: input and output share a DeckLink subdevice name. Separate IN/OUT sockets can operate together; duplex capability is unreported, so Desktop Video will validate availability when the route starts. For Duo 2 independent connectors, select different subdevices.")
            if out["captions"] in ("pass", "recaption") and not cap.get("decklink_caption_output"):
                blockers.append(f"{label}: caption passthrough needs the extended VANC playout build")
            if out["captions"] == "strip" and not cap.get("caption_strip_filter", cap.get("source_monitor", False)):
                blockers.append(f"{label}: this FFmpeg lacks the A/53 caption stripping filter")
        if kind == "srt" and not cap.get("srt"):
            blockers.append(f"{label}: FFmpeg needs SRT support")
        if kind in ("rtmp", "youtube") and not cap.get("rtmp"):
            blockers.append(f"{label}: FFmpeg needs RTMP support")
        if out["scte"] != "strip":
            if kind in ("rtmp", "youtube"):
                blockers.append(f"{label}: this RTMP profile has no SCTE carriage; select Strip")
            elif kind == "decklink":
                if not cap.get("decklink_scte_output"):
                    blockers.append(f"{label}: SCTE output needs the updated SCTE-104 playout engine")
                elif out["scte"] == "pass" and "spankvanc_scte104" not in cap.get("decklink_options", []):
                    blockers.append(f"{label}: SCTE-104 passthrough needs the updated ANC capture engine")
            elif not (src["kind"] == "decklink" and kind in ("udp", "srt", "file") and out["scte"] == "convert" and cap.get("scte_runtime")):
                blockers.append(f"{label}: SCTE preservation/conversion needs the native ANC/TS adapter")
        if kind != "decklink" and cap.get("decklink_profile") == "compatibility":
            if out["captions"] == "pass" and not cap.get("caption_encoders", {}).get(codec):
                blockers.append(f"{label}: this FFmpeg encoder does not expose A/53 caption pass; choose another encoder or Strip")
            if out["captions"] == "strip" and not cap.get("caption_strip_filter"):
                blockers.append(f"{label}: this FFmpeg lacks the A/53 caption stripping filter")
        if src["kind"] == "decklink" and out["scte"] == "convert" and src["scte_error_policy"] == "continue" and cap.get("scte_runtime") and not cap.get("scte_recovery"):
            blockers.append(f"{label}: capture FFmpeg needs the cue-recovery update for Continue A/V; choose Stop on rejected cue with an older build")
        if out["captions"] == "recaption":
            w=cap.get("whisper",{})
            if not w.get("available"):
                blockers.append(f"{label}: configure a Python installation with Whisper, PyTorch and NumPy")
            if not cap.get("recaption_decklink"):
                blockers.append(f"{label}: rebuild the selected engine with the live 608 replacement filter")
            if cfg["whisper"]["device"]=="cuda" and not w.get("cuda"):
                blockers.append(f"{label}: CUDA requested but unavailable in Whisper Python")
            if w.get("models") and cfg["whisper"]["model"] not in w["models"]:
                blockers.append(f"{label}: model unavailable in installed Whisper; choose a supported model")
            if src["kind"]=="file" and not src["realtime"]:
                blockers.append(f"{label}: live Whisper requires reading files at program speed")
            notes.append(f"{label}: live CC1 two-row roll-up from routed audio channel {cfg['whisper']['audio_channel']}. Recognition and 608 transmission add latency; A/V is not delayed. Source captions are replaced only on this output.")
        video_label = video_codec_options(kind)[codec]
        outputs.append({"name": label, "transport": kind, "video_codec": codec,
                        "audio_codec": "pcm" if kind == "decklink" else "aac",
                        "audio_framing": "ADTS" if kind in ("udp", "srt", "file") else None,
                        "container": "SDI / uncompressed / PCM / ANC" if kind == "decklink" else "FLV / H.264 / AAC-LC" if kind in ("rtmp", "youtube") else f"MPEG-TS / {video_label} / AAC-LC (ADTS)",
                        "captions": out["captions"], "scte": out["scte"],
                        "scte_label": allowed.get(out["scte"], "Unsupported SCTE policy")})
        if kind == "youtube":
            if not cap.get("youtube_profiles", {}).get("decklink" if src["kind"] == "decklink" else "general"):
                blockers.append(f"{label}: YouTube requires RTMPS and the progressive-profile filters; update your selected FFmpeg")
            notes.append(f"{label}: YouTube SDR preset: 1920×1080 progressive, 30 fps, H.264 High, {out['youtube_bitrate_mbps']} Mbit/s CBR, two-second GOP, square pixels, AAC stereo 44.1 kHz / 128 kbit/s. Interlaced inputs are deinterlaced. Use an SDR Rec.709 source; HDR tone mapping is not implemented.")
            notes.append(f"{label}: enable Embedded 608/708 in YouTube Studio; one caption track")
    notes.append("TS and generic RTMP outputs use AAC-LC at 48 kHz / 192 kbit/s; YouTube uses stereo AAC-LC at 44.1 kHz / 128 kbit/s when source audio exists. TS carries AAC in ADTS; RTMP uses FLV AAC framing. SDI uses uncompressed video and PCM audio.")
    if any(o["kind"] == "decklink" and o["scte"] != "strip" for o in active):
        notes.append("SDI SCTE-104 pass preserves primary-stream packet bytes, frame association and VANC line, including fragments. TS → SDI conversion supports unencrypted program splice start/end/cancel, time_signal, splice_null and opaque descriptors. Select the SCTE-35 PID when it is not the first data stream. PTS is retained; pre-roll is rounded to milliseconds. Break duration must fit 0.1-second units and pre-roll must fit 65535 ms. Unsupported, late, encrypted, component and non-default-tier cues follow Continue/Stop policy. Conversion emits ST 2010 starting on VANC line 13 (following lines for fragments).")
    notes.append("Caption pass retains decoded A/53 608/708 data in the selected video codec; verify each source codec and receiving player.")
    notes.append("Strip removes embedded A/53 captions and excludes separate subtitle/data streams. Burned-in text remains part of the picture.")
    notes.append("SCTE Strip excludes separate data streams, including SCTE-35 PIDs. DeckLink → TS conversion supports program splice start/end/cancel, durations, auto-return, time_signal and raw descriptors with time_type 0. Rejected SCTE messages follow the selected continue/stop policy; arbitrary ANC routing is unavailable.")
    if src["kind"] == "decklink" and any(o["scte"] == "convert" for o in active):
        notes.append("Rejected or unsupported SCTE messages are discarded with a visible warning and saved diagnostic; A/V and later supported cues continue." if src["scte_error_policy"] == "continue" else "Strict SCTE mode stops the route on any rejected message.")
    return {"ready": not blockers, "blockers": list(dict.fromkeys(blockers)), "notes": notes,
            "outputs": outputs, "command": [scrub(arg) for arg in command(cfg, cap, "WHISPER_JOURNAL_AT_START")] if not blockers else []}


def input_command(cfg: dict, *, monitor=False, capabilities=None) -> list[str]:
    src = cfg["input"]
    args = [executable(src["kind"] == "decklink" or any(o["enabled"] and (o["kind"] == "decklink" or o["captions"] == "recaption") for o in cfg["outputs"])), "-hide_banner", "-nostdin", "-n", "-loglevel", "info"]
    if src["kind"] == "file" and src["realtime"]:
        args += ["-re"]
    if src["kind"] == "decklink":
        cap = capabilities or {}
        legacy = cap.get("decklink_profile") == "compatibility"
        options = cap.get("decklink_options", [])
        args += ["-copyts"]
        if legacy:
            args += ["-vsync", "0"]
        args += ["-f", "decklink"]
        if not legacy:
            args += ["-spankvanc_anc", "1"]
        args += ["-video_input", "sdi", "-audio_input", "embedded", "-channels", "2"]
        args += ["-bm_v210", "1"] if legacy and "raw_format" not in options else ["-raw_format", "yuv422p10"]
        args += ["-format_code", src["format_code"]]
        if "signal_loss_action" in options or (not options and capabilities is None):
            args += ["-signal_loss_action", "none"]
        elif "draw_bars" in options:
            args += ["-draw_bars", "0"]
        if not monitor and any(o["enabled"] and o["scte"] == "convert" for o in cfg["outputs"]):
            args += ["-spankvanc_scte35", "1", "-xerror"]
            if "spankvanc_scte_strict" in options or capabilities is None:
                args += ["-spankvanc_scte_strict", "1" if src["scte_error_policy"] == "stop" else "0"]
    if src["kind"] == "decklink" and not monitor and any(o["enabled"] and o["kind"] == "decklink" and o["scte"] == "pass" for o in cfg["outputs"]):
        args += ["-spankvanc_scte104", "1"]
    if src["kind"] in ("udp", "srt", "file") and any(o["enabled"] and o["kind"] == "decklink" and o["scte"] == "convert" for o in cfg["outputs"]):
        args += ["-copyts"]
    args += ["-i", src["address"]]
    return args


def command(cfg: dict, capabilities=None, caption_journal=None) -> list[str]:
    src = cfg["input"]
    cap = capabilities or {}
    legacy = cap.get("decklink_profile") == "compatibility"
    args = input_command(cfg, capabilities=cap)
    def replacement_filter():
        if caption_journal is None:
            raise ConfigError("Whisper output requires a running caption worker")
        return "spankvanc_cc=journal="+str(Path(caption_journal).resolve()).encode("utf-8").hex()
    for out in cfg["outputs"]:
        if not out["enabled"]:
            continue
        if out["kind"] == "decklink":
            args += ["-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1", "-map_chapters", "-1",
                     "-c:v", "v210", "-pix_fmt", "yuv422p10le", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]
            if src["kind"] == "decklink" and src["format_code"] in ("Hi50", "Hi59", "Hi60", "ntsc", "pal "):
                args += ["-field_order", "tt"]
            if out["captions"] == "strip":
                args += ["-vf", "sidedata=mode=delete:type=A53_CC"]
            if out["captions"] == "recaption":
                args += ["-vf", replacement_filter()]
            if out["scte"] != "strip":
                args += ["-fps_mode:v", "passthrough"]
                args += ["-spankvanc_scte_output", "1" if out["scte"] == "pass" else "2"]
                if out["scte"] == "convert":
                    mapping=f"0:i:{src['scte_pid']}" if src.get("scte_pid") is not None else "0:d:0?"
                    args += ["-map", mapping, "-c:d", "copy", "-avoid_negative_ts", "disabled",
                             "-spankvanc_scte_output_strict", "1" if src["scte_error_policy"] == "stop" else "0"]
            if out["captions"] in ("pass", "recaption"):
                args += ["-spankvanc_caption_output", "1"]
            args += ["-f", "decklink", out["address"]]
            continue
        args += ["-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1", "-map_chapters", "-1",
                 "-c:v", "mpeg2video" if out.get("video_codec") == "mpeg2video" else "libx264", "-threads:v", "4"]
        if src["kind"] == "decklink" and out["scte"] == "convert":
            args += ["-map", "0:d:0", "-c:d", "copy", "-avoid_negative_ts", "disabled"]
        youtube = out["kind"] == "youtube"
        if youtube:
            bitrate = out.get("youtube_bitrate_mbps", 14)
            # fps=30 already establishes the clock before caption insertion.
            # A second CFR synchronizer can duplicate caption-bearing frames.
            video_sync = (["-fps_mode:v", "passthrough"] if out["captions"]=="recaption" else
                          ["-r:v", "30", "-fps_mode:v", "cfr"])
            args += ["-preset", "veryfast", "-profile:v", "high", "-level:v", "4.1",
                     "-b:v", f"{bitrate}M", "-minrate:v", f"{bitrate}M", "-maxrate:v", f"{bitrate}M", "-bufsize:v", f"{bitrate * 2}M",
                     "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-bf", "2", "-refs", "1",
                     "-x264-params", "nal-hrd=cbr:force-cfr=1:cabac=1", *video_sync,
                     "-enc_time_base:v", "1:30", "-field_order", "progressive",
                     "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]
        elif out.get("video_codec") == "mpeg2video":
            args += ["-q:v", "3", "-g", "15", "-bf", "2"]
        else:
            args += ["-preset", "veryfast", "-crf", "20"]
        if src["kind"] == "decklink" and not legacy and not youtube:
            args += ["-fps_mode:v", "passthrough"]
            if out.get("video_codec") != "mpeg2video":
                args += ["-enc_time_base:v", "demux"]
        if not youtube and src["kind"] == "decklink" and src["format_code"] in ("Hi50", "Hi59", "Hi60", "ntsc", "pal "):
            args += ["-flags:v", "+ilme+ildct", "-field_order", "tt"]
            if out.get("video_codec") != "mpeg2video":
                args += ["-x264-params", "tff=1"]
        args += ["-pix_fmt", "yuv420p"]
        if not legacy or cap.get("caption_encoders", {}).get(out.get("video_codec", "h264"), False):
            args += ["-a53cc", "0" if out["captions"] == "strip" else "1"]
        args += ["-c:a", "aac", "-profile:a", "aac_low", "-b:a", "128k" if youtube else "192k", "-ar", "44100" if youtube else "48000"]
        if youtube:
            args += ["-ac", "2"]
        # Filtering is specific to A/53 captions; never discard all H.264 SEI.
        filters = [YOUTUBE_VIDEO_FILTER] if youtube else []
        if out["captions"] == "strip":
            filters.append("sidedata=mode=delete:type=A53_CC")
        if out["captions"] == "recaption":
            filters.append(replacement_filter())
        if filters:
            args += ["-vf", ",".join(filters)]
        if out["kind"] in ("rtmp", "youtube"):
            args += ["-f", "flv", "-flvflags", "no_duration_filesize"]
        else:
            args += ["-f", "mpegts", "-mpegts_flags", "-latm"]
        args += [out["address"]]
    if any(o["enabled"] and o["captions"]=="recaption" for o in cfg["outputs"]):
        channel=cfg["whisper"]["audio_channel"]-1
        args += ["-map","0:a:0","-vn","-af",f"channelmap=map={channel}:channel_layout=mono","-ar","16000",
                 "-c:a","pcm_f32le","-f","f32le","pipe:1"]
    return args



def process_group_options():
    return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}


def terminate_process(process):
    if os.name == "nt":
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            return
        except OSError:
            pass
    process.terminate()


class Engine:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.config_path = state_dir / "route.json"
        self.lock = threading.RLock()
        self.logs = deque(maxlen=200)
        self.process = None
        self.monitor_process = None
        self.whisper_process = None
        self.source_monitor = SourceMonitor()
        self.last_exit = None
        self.stop_requested = False
        self.config = copy.deepcopy(DEFAULT)
        if self.config_path.exists():
            # Preserve older saved settings for review; invalid carriage is
            # blocked by preflight and cannot be saved or started unchanged.
            self.config = validate(json.loads(self.config_path.read_text()), check_scte=False)
        self.capabilities = doctor()

    def monitor_state(self):
        with self.lock:
            running = bool(self.process and self.process.poll() is None)
            monitoring = bool(self.monitor_process and self.monitor_process.poll() is None)
            return {"monitor": self.source_monitor.state(running or monitoring),
                    "running": running, "monitor_running": monitoring}

    def monitor_start(self, raw):
        with self.lock:
            if self.process and self.process.poll() is None:
                raise ConfigError("The running route already supplies the source monitor")
            if not self.capabilities.get("source_monitor"):
                raise ConfigError("Build the source-monitor-enabled DeckLink FFmpeg first")
            cfg = validate(raw, check_scte=False)
            if cfg["input"]["kind"] != "decklink":
                raise ConfigError("Standalone source monitoring currently supports DeckLink SDI input")
            check = copy.deepcopy(DEFAULT)
            check["input"] = cfg["input"]
            check["outputs"][0].update(kind="file", address="monitor-only.ts", captions="strip", scte="strip")
            readiness = plan(check, self.capabilities)
            if not readiness["ready"]:
                raise ConfigError("; ".join(readiness["blockers"]))
            if self.monitor_process and self.monitor_process.poll() is None:
                raise ConfigError("Stop the source monitor before changing its input")
            self.source_monitor = SourceMonitor({"name":cfg["input"]["address"],"mode":cfg["input"]["format_code"]})
            args = input_command(cfg, monitor=True, capabilities=self.capabilities) + ["-map", "0:v:0", "-c:v", "copy", "-f", "null", "-"]
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, errors="replace", stdin=subprocess.DEVNULL, **process_group_options())
            self.monitor_process = process
            threading.Thread(target=self._read, args=(process, True), daemon=True).start()
        return self.state()

    def monitor_stop(self):
        with self.lock:
            process = self.monitor_process
        if process and process.poll() is None:
            terminate_process(process)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
        with self.lock:
            if self.monitor_process is process:
                self.monitor_process = None
        return self.state()

    def refresh_devices(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                raise ConfigError("Stop the route before refreshing devices")
            if self.monitor_process and self.monitor_process.poll() is None:
                raise ConfigError("Stop the source monitor before refreshing devices")
            self.capabilities = doctor()
        return self.state()

    def save(self, raw):
        cfg = validate(raw)
        with self.lock:
            if self.process and self.process.poll() is None:
                raise ConfigError("Stop the route before changing its configuration")
            self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = self.config_path.with_suffix(".tmp")
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                json.dump(cfg, stream, indent=2)
            temporary.replace(self.config_path)
            self.config = cfg
        return cfg

    def state(self):
        with self.lock:
            readiness = plan(self.config, self.capabilities)
            running = bool(self.process and self.process.poll() is None)
            return {"config": copy.deepcopy(self.config), "capabilities": self.capabilities,
                    "running": running, "last_exit": self.last_exit, "stopped_by_user": self.stop_requested, "logs": list(self.logs),
                    "plan": readiness, "scte_options": scte_matrix(),
                    "monitor_running": bool(self.monitor_process and self.monitor_process.poll() is None),
                    "source_monitor": self.source_monitor.state(running or bool(self.monitor_process and self.monitor_process.poll() is None)),
                    "video_codec_options": {kind: video_codec_options(kind)
                                            for kind in ("decklink", "udp", "srt", "file", "rtmp", "youtube")}}

    def start(self, raw):
        with self.lock:
            cfg = validate(raw)
            result = plan(cfg, self.capabilities)
            if not result["ready"]:
                raise ConfigError("; ".join(result["blockers"]))
            self.monitor_stop()
            self.source_monitor = SourceMonitor({"name":cfg["input"]["address"] if cfg["input"]["kind"] == "decklink" else cfg["input"]["kind"],"mode":cfg["input"]["format_code"]})
            self.save(cfg)
            self.logs.clear()
            self.last_exit = None
            self.stop_requested = False
            worker=None;journal=None
            if any(o["enabled"] and o["captions"]=="recaption" for o in cfg["outputs"]):
                from .whisper_runtime import prepare
                try:
                    worker,journal=prepare(self.state_dir,cfg,self.logs.append,process_group_options())
                except (OSError,RuntimeError) as exc:raise ConfigError(str(exc)) from exc
            self.whisper_process=worker
            try:
                process = subprocess.Popen(command(cfg, self.capabilities,journal), stdout=worker.stdin if worker else subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       text=True, errors="replace", stdin=subprocess.DEVNULL, **process_group_options())
            except Exception:
                if worker:worker.kill();worker.wait()
                raise
            if worker:
                worker.stdin.close()
            process._spank_whisper = worker
            self.process = process
            if worker:
                threading.Thread(target=self._watch_whisper,args=(worker,process),daemon=True).start()
            threading.Thread(target=self._read, args=(process,), daemon=True).start()
        return self.state()

    def _watch_whisper(self,worker,route):
        code=worker.wait()
        if self.process is route and not self.stop_requested and (code != 0 or route.poll() is None):
            self.logs.append(f"Whisper worker exited ({code}); stopping route to avoid silent caption loss")
            if route.poll() is None:
                terminate_process(route)

    def _save_rejection(self, record):
        # Bound persistent diagnostics to two 1 MiB files; never include route URLs.
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = self.state_dir / "scte-rejections.ndjson"
            if path.exists() and path.stat().st_size >= 1024 * 1024:
                path.replace(path.with_suffix(".ndjson.1"))
            fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")
        except OSError as exc:
            self.logs.append("Could not save SCTE rejection diagnostic: " + scrub(str(exc)))

    def _read(self, process, monitor=False):
        with process.stderr:
            for line in process.stderr:
                with self.lock:
                    if "SPANKVANC_SCTE_REJECT {" in line:
                        try:
                            record=json.loads(line.split("SPANKVANC_SCTE_REJECT ",1)[1])
                            self.source_monitor.rejected += 1
                            record["total"]=self.source_monitor.rejected
                            self.source_monitor.rejections.append(record)
                            self._save_rejection(record)
                            self.logs.append("SCTE-35 → 104 cue rejected: " + scrub(record["reason"]))
                        except (ValueError,TypeError,KeyError): self.logs.append("Invalid SCTE output rejection diagnostic")
                    elif "SPANKVANC {" in line:
                        if process is (self.monitor_process if monitor else self.process):
                            try:
                                event = json.loads(line[line.index("SPANKVANC ")+10:])
                                previous = self.source_monitor.rejected
                                self.source_monitor.feed(event)
                                if self.source_monitor.rejected > previous:
                                    record = self.source_monitor.rejections[-1]
                                    self._save_rejection(record)
                                    self.logs.append("SCTE-104 cue rejected: " + scrub(record["reason"]) + "; source_pts90k=" + str(record["source_pts90k"]))
                            except (ValueError, TypeError, KeyError) as exc:
                                self.logs.append("Invalid source telemetry: " + str(exc))
                    else:
                        self.logs.append(scrub(line.rstrip()))
        code = process.wait()
        worker=getattr(process,"_spank_whisper",None)
        if not monitor and worker and worker.poll() is None:
            try:worker.wait(timeout=3)
            except subprocess.TimeoutExpired:
                worker.kill();worker.wait()
        with self.lock:
            if monitor:
                self.logs.append(f"Source monitor exited with status {code}")
            elif self.process is process:
                self.last_exit = code
                self.logs.append(f"Route exited with status {code}")

    def stop(self):
        with self.lock:
            process = self.process
        if process and process.poll() is None:
            with self.lock:
                self.stop_requested = True
            terminate_process(process)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        return self.state()
