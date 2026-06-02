#!/usr/bin/env python3
"""
Live RX pipeline adapted from aprs_live_tnc2_dsp_bp.py.

Audio -> DSP soft symbols -> NRZI/HDLC -> AX.25 parsed frame callback.
"""

import logging
import time
from collections import deque
from typing import Callable, Optional, Tuple

import numpy as np
from scipy.signal import butter, resample_poly, sosfiltfilt

logger = logging.getLogger(__name__)


INPUT_FS_DEFAULT = 48000
DSP_FS = 9600
BAUD = 1200
SPS = DSP_FS // BAUD
MARK_HZ = 1200
SPACE_HZ = 2200
FLAG_BITS = "01111110"


def bandpass_audio(audio, fs, low=700.0, high=2700.0, order=4):
    """Bandpass filter around Bell 202 tones."""
    if len(audio) < 64:
        return audio

    nyquist = fs / 2.0
    low = max(1.0, float(low))
    high = min(float(high), nyquist - 1.0)

    if low >= high:
        return audio

    sos = butter(order, [low, high], btype="bandpass", fs=fs, output="sos")

    try:
        return sosfiltfilt(sos, audio)
    except ValueError:
        return audio


def moving_average_complex(x, n):
    if n <= 1:
        return x

    kernel = np.ones(n, dtype=np.float64) / n
    real = np.convolve(np.real(x), kernel, mode="same")
    imag = np.convolve(np.imag(x), kernel, mode="same")
    return real + 1j * imag


def moving_average_real(x, n):
    if n <= 1:
        return x

    kernel = np.ones(n, dtype=np.float64) / n
    return np.convolve(x, kernel, mode="same")


def afsk_soft_symbols(
    audio_in,
    input_fs=INPUT_FS_DEFAULT,
    dsp_fs=DSP_FS,
    use_bandpass=False,
    bp_low=700.0,
    bp_high=2700.0,
    bp_order=4,
    mark_filter_len=SPS,
    soft_filter_len=None,
):
    """Generate soft symbols where >0 is MARK and <0 is SPACE."""
    audio = audio_in.astype(np.float64)

    if len(audio) == 0:
        return np.array([], dtype=np.float64)

    audio = audio - np.mean(audio)

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    if input_fs != dsp_fs:
        audio = resample_poly(audio, dsp_fs, input_fs)

    if len(audio) == 0:
        return np.array([], dtype=np.float64)

    audio = audio - np.mean(audio)

    if use_bandpass:
        audio = bandpass_audio(audio, dsp_fs, low=bp_low, high=bp_high, order=bp_order)

    n = len(audio)
    t = np.arange(n, dtype=np.float64) / dsp_fs

    mark_osc = np.exp(-1j * 2.0 * np.pi * MARK_HZ * t)
    space_osc = np.exp(-1j * 2.0 * np.pi * SPACE_HZ * t)

    mixed_mark = audio * mark_osc
    mixed_space = audio * space_osc

    mark_lp = moving_average_complex(mixed_mark, mark_filter_len)
    space_lp = moving_average_complex(mixed_space, mark_filter_len)

    mark_power = np.abs(mark_lp) ** 2
    space_power = np.abs(space_lp) ** 2

    soft = mark_power - space_power

    if soft_filter_len is None:
        soft_filter_len = max(2, SPS // 2)

    soft = moving_average_real(soft, soft_filter_len)
    return soft


def nrzi_decode(symbols):
    bits = []
    for i in range(1, len(symbols)):
        bits.append(1 if symbols[i] == symbols[i - 1] else 0)
    return bits


def bits_to_string(bits):
    return "".join("1" if b else "0" for b in bits)


def find_flags(bit_string):
    positions = []
    start = 0

    while True:
        pos = bit_string.find(FLAG_BITS, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1

    return positions


def destuff_bits(bits):
    out = []
    ones = 0

    for b in bits:
        if b == 1:
            out.append(b)
            ones += 1
        else:
            if ones == 5:
                ones = 0
                continue
            out.append(b)
            ones = 0

    return out


def bits_lsb_to_bytes(bits):
    result = []

    for i in range(0, len(bits) - 7, 8):
        value = 0
        for bit_index in range(8):
            value |= bits[i + bit_index] << bit_index
        result.append(value)

    return bytes(result)


def ax25_fcs_ok(frame_bytes):
    crc = 0xFFFF

    for byte in frame_bytes:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
            crc &= 0xFFFF

    return crc == 0xF0B8, crc


def decode_ax25_address(addr_bytes):
    if len(addr_bytes) != 7:
        return None

    chars = []
    for b in addr_bytes[:6]:
        c = (b >> 1) & 0x7F
        chars.append(chr(c))

    callsign = "".join(chars).rstrip()
    if not callsign:
        return None

    ssid_byte = addr_bytes[6]
    ssid = (ssid_byte >> 1) & 0x0F
    repeated = bool(ssid_byte & 0x80)
    last = bool(ssid_byte & 0x01)

    full = f"{callsign}-{ssid}" if ssid else callsign

    return {
        "callsign": callsign,
        "ssid": ssid,
        "full": full,
        "repeated": repeated,
        "last": last,
        "raw": addr_bytes,
    }


def address_chars_are_plausible(addr):
    for b in addr[:6]:
        c = (b >> 1) & 0x7F
        if c == 0x20:
            continue
        if 0x30 <= c <= 0x39:
            continue
        if 0x41 <= c <= 0x5A:
            continue
        return False
    return True


def parse_ax25_frame(frame_bytes):
    if len(frame_bytes) < 16:
        return None

    body = frame_bytes[:-2]
    fcs = frame_bytes[-2:]

    offset = 0
    addresses = []

    while offset + 7 <= len(body):
        addr_raw = body[offset:offset + 7]

        if not address_chars_are_plausible(addr_raw):
            return None

        addr = decode_ax25_address(addr_raw)
        if addr is None:
            return None

        addresses.append(addr)
        offset += 7

        if addr["last"]:
            break

        if len(addresses) > 10:
            return None

    if len(addresses) < 2:
        return None
    if not addresses[-1]["last"]:
        return None
    if offset + 2 > len(body):
        return None

    control = body[offset]
    pid = body[offset + 1]
    payload = body[offset + 2:]

    fcs_ok, fcs_crc = ax25_fcs_ok(frame_bytes)

    return {
        "addresses": addresses,
        "destination": addresses[0],
        "source": addresses[1],
        "path": addresses[2:],
        "control": control,
        "pid": pid,
        "payload": payload,
        "fcs": fcs,
        "fcs_ok": fcs_ok,
        "fcs_crc": fcs_crc,
        "raw": frame_bytes,
    }


def is_aprs_ui_frame(parsed):
    if parsed is None:
        return False
    return parsed["control"] == 0x03 and parsed["pid"] == 0xF0


def printable_ratio(payload):
    if not payload:
        return 0.0

    printable = sum(1 for b in payload if b == 9 or b == 10 or b == 13 or 32 <= b <= 126)
    return printable / len(payload)


def score_candidate(parsed):
    if parsed is None:
        return -1000

    score = 0

    if is_aprs_ui_frame(parsed):
        score += 500

    if parsed["fcs_ok"]:
        score += 1000

    payload = parsed["payload"]
    if payload:
        if payload[0] in b"!/=@>:;)_?`'T":
            score += 150

        ratio = printable_ratio(payload)
        if ratio > 0.95:
            score += 200
        elif ratio > 0.80:
            score += 80
        else:
            score -= 200

        if len(payload) >= 10:
            score += 50
        if len(payload) >= 30:
            score += 50

    if 20 <= len(parsed["raw"]) <= 330:
        score += 50

    return score


def extract_candidates_from_bit_string(bit_string, phase):
    flags = find_flags(bit_string)
    candidates = []

    if len(flags) < 2:
        return flags, candidates

    for i in range(len(flags) - 1):
        start = flags[i] + len(FLAG_BITS)
        end = flags[i + 1]

        if end <= start:
            continue

        frame_bits_str = bit_string[start:end]
        if not frame_bits_str:
            continue

        frame_bits = [1 if c == "1" else 0 for c in frame_bits_str]
        destuffed = destuff_bits(frame_bits)
        frame_bytes = bits_lsb_to_bytes(destuffed)

        parsed = parse_ax25_frame(frame_bytes)
        score = score_candidate(parsed)

        candidates.append({
            "phase": phase,
            "score": score,
            "flags": (flags[i], flags[i + 1]),
            "bytes": frame_bytes,
            "parsed": parsed,
        })

    return flags, candidates


def decode_soft_to_candidates(soft):
    all_candidates = []
    total_flags = 0
    total_ax25 = 0
    total_ui = 0

    for phase in range(SPS):
        sampled = soft[phase::SPS]
        if len(sampled) < 10:
            continue

        symbols = (sampled >= 0).astype(np.uint8).tolist()
        bits = nrzi_decode(symbols)
        bit_string = bits_to_string(bits)

        flags, candidates = extract_candidates_from_bit_string(bit_string, phase)
        total_flags += len(flags)

        for c in candidates:
            parsed = c["parsed"]
            if parsed is None:
                continue
            total_ax25 += 1
            if is_aprs_ui_frame(parsed):
                total_ui += 1
            all_candidates.append(c)

    all_candidates.sort(key=lambda x: x["score"], reverse=True)

    stats = {
        "flags": total_flags,
        "ax25": total_ax25,
        "ui": total_ui,
        "candidates": len(all_candidates),
        "best": all_candidates[0]["score"] if all_candidates else None,
    }

    return all_candidates, stats


class RXPipelineLiveDSP:
    """Stateful live scanner compatible with MicroKISStnc callbacks."""

    def __init__(
        self,
        sample_rate: int = INPUT_FS_DEFAULT,
        on_frame_decoded: Optional[Callable] = None,
        buffer_seconds: float = 4.0,
        scan_interval: float = 0.4,
        require_fcs: bool = True,
        dedupe_seconds: float = 2.0,
        clear_buffer_after_decode: bool = True,
        rms_gate: float = 0.005,
        use_bandpass: bool = False,
        bp_low: float = 700.0,
        bp_high: float = 2700.0,
        bp_order: int = 4,
        min_score_no_fcs: int = 1200,
    ):
        self.input_sample_rate = int(sample_rate)
        self.sample_rate = int(sample_rate)  # compatibility alias
        self.on_frame_decoded = on_frame_decoded

        self.buffer_size = int(buffer_seconds * self.input_sample_rate)
        self.scan_interval_samples = int(scan_interval * self.input_sample_rate)
        self.require_fcs = require_fcs
        self.dedupe_seconds = dedupe_seconds
        self.clear_buffer_after_decode = clear_buffer_after_decode
        self.rms_gate = rms_gate

        self.use_bandpass = use_bandpass
        self.bp_low = bp_low
        self.bp_high = bp_high
        self.bp_order = bp_order
        self.min_score_no_fcs = int(min_score_no_fcs)

        self.samples = deque(maxlen=self.buffer_size)
        self.samples_since_scan = 0
        self.seen = {}
        self.frame_count = 0
        self.scan_count = 0
        self.no_frame_scan_count = 0

        logger.info(
            "[RX-DSP] Initialized @ %d Hz (buffer=%.1fs, scan=%.1fs, fcs=%s)",
            self.input_sample_rate,
            buffer_seconds,
            scan_interval,
            "ON" if self.require_fcs else "OFF",
        )

    def _cleanup_seen(self):
        now = time.time()
        expired = [k for k, ts in self.seen.items() if now - ts > self.dedupe_seconds]
        for k in expired:
            del self.seen[k]

    def _filter_candidates(self, candidates):
        self._cleanup_seen()
        frames = []
        now = time.time()

        for c in candidates:
            parsed = c["parsed"]
            raw_bytes = c.get("bytes", b"")

            # Some real-world frames can have parser metadata failure while FCS is still valid.
            # In that case we still forward AX.25 payload to KISS clients.
            if parsed is None:
                if len(raw_bytes) < 16:
                    continue
                raw_fcs_ok, _ = ax25_fcs_ok(raw_bytes)
                if not raw_fcs_ok:
                    continue

                key = raw_bytes.hex()
                if key in self.seen:
                    continue

                self.seen[key] = now
                frames.append({
                    "parsed": None,
                    "bytes": raw_bytes,
                    "score": c.get("score", 0),
                    "fcs_ok": True,
                })
                continue

            if self.require_fcs and not parsed["fcs_ok"]:
                # Fallback for weak/noisy RX: allow only very strong candidates.
                if c.get("score", -9999) < self.min_score_no_fcs:
                    continue

            key = parsed["raw"].hex()
            if key in self.seen:
                continue

            self.seen[key] = now
            frames.append(c)

        return frames

    def process_audio(self, audio_samples: np.ndarray):
        """Feed live mono audio blocks to decoder."""
        if audio_samples is None or len(audio_samples) == 0:
            return

        block = audio_samples.astype(np.float64)
        if len(block) > 0:
            block = block - np.mean(block)

        self.samples.extend(block.tolist())
        self.samples_since_scan += len(block)

        if self.samples_since_scan < self.scan_interval_samples:
            return

        self.samples_since_scan = 0

        if len(self.samples) < int(0.8 * self.input_sample_rate):
            return

        data = np.array(self.samples, dtype=np.float64)

        rms = float(np.sqrt(np.mean(data * data)))
        if rms < self.rms_gate:
            return

        self.scan_count += 1
        t0 = time.perf_counter()

        soft = afsk_soft_symbols(
            data,
            input_fs=self.input_sample_rate,
            dsp_fs=DSP_FS,
            use_bandpass=self.use_bandpass,
            bp_low=self.bp_low,
            bp_high=self.bp_high,
            bp_order=self.bp_order,
        )

        candidates, stats = decode_soft_to_candidates(soft)
        frames = self._filter_candidates(candidates)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if frames:
            self.no_frame_scan_count = 0
            logger.info(
                "[RX-DSP] scan_ms=%.1f flags=%d ax25=%d ui=%d frames=%d best=%s",
                elapsed_ms,
                stats["flags"],
                stats["ax25"],
                stats["ui"],
                len(frames),
                stats["best"],
            )
        else:
            self.no_frame_scan_count += 1
            if self.no_frame_scan_count % 10 == 0:
                logger.info(
                    "[RX-DSP] no-frame scans=%d rms=%.5f scan_ms=%.1f flags=%d ax25=%d ui=%d best=%s",
                    self.no_frame_scan_count,
                    rms,
                    elapsed_ms,
                    stats["flags"],
                    stats["ax25"],
                    stats["ui"],
                    stats["best"],
                )

        for frame in frames:
            parsed = frame["parsed"]
            self.frame_count += 1
            if self.on_frame_decoded:
                # KISS apps expect AX.25 frame without FCS bytes.
                if parsed and parsed.get("raw"):
                    raw_with_fcs = parsed["raw"]
                else:
                    raw_with_fcs = frame.get("bytes", b"")
                ax25_no_fcs = raw_with_fcs[:-2] if len(raw_with_fcs) >= 2 else raw_with_fcs
                self.on_frame_decoded(ax25_no_fcs, parsed)

        if frames and self.clear_buffer_after_decode:
            self.samples.clear()
            self.samples_since_scan = 0
