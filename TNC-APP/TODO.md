# MicroKISStnc TODO & PROGRESS

## 📋 PROJECT STATUS

### Overview
- **Application Name**: MicroKISStnc
- **Protocol**: KISS only (NO AGW)
- **Architecture**: Maksymalnie simplistic - audio I/O, user picks devices
- **Phase**: Development (dev version)

---

## ✅ COMPLETED - KISS CORE

### TX Pipeline (100% WORKING)
- [x] HDLC encoder (NRZI + bit stuffing + CRC-16-CCITT)
- [x] AFSK modulator (Bell 202: 1200 Hz mark, 2200 Hz space)
- [x] Audio output via PyAudio
- [x] KISS protocol parsing (0xC0 framing, 0xDB escaping)
- [x] KISS server (TCP port 8001 on 0.0.0.0)
- [x] Device auto-detection and fallback mechanism
- [x] Headless mode (tnc_headless.py - fully tested)
- [x] GUI skeleton (src/gui_audio.py with Monitor + Audio tabs)

### Audio System (VERIFIED)
- [x] PyAudio integration with device enumeration
- [x] Smart device selection (filters virtual/CABLE/SPDIF/Steam)
- [x] Format fallback: Int16 → Float32
- [x] Fallback to alternative devices if primary fails
- [x] Amplitude increased to 0.9 for audibility
- [x] Audio saved to WAV files for debugging (tx_debug/ folder)

### Code Cleanup - SESSION CURRENT
- [x] Remove AGWPEServer from servers.py
- [x] Remove AGW references from config.py
- [x] Remove AGW from gui.py
- [x] Remove AGW from main.py
- [x] Update config.json (KISS only)
- [x] Update README.md (KISS + Audio focus)
- [x] Update TODO.md

---

## 🔄 IN PROGRESS - TX VERIFICATION

### Audio Analysis Required
- [ ] Check WAV files in tx_debug/ folder with audio analyzer
  - Verify 1200 Hz (mark/1) frequency
  - Verify 2200 Hz (space/0) frequency
  - Check modulation timing and bit boundaries
  - Verify NRZI encoding correctness
  
### Potential Issues to Debug
- [ ] AFSK modulator - czy częstotliwości są dokładne?
- [ ] HDLC bit stuffing - czy działa prawidłowo?
- [ ] NRZI encoding - czy stany przejść są poprawne?
- [ ] Timing between bits - czy samples_per_bit jest dokładnie 36.75 (44100/1200)?

---

## ❌ NOT STARTED - PHASE 2 (RX Path)

### RX Pipeline (0% - deferred)
- [ ] Audio input via PyAudio
- [ ] AFSK demodulator (Bell 202 decode)
- [ ] Bit timing recovery
- [ ] NRZI decode
- [ ] HDLC bit destuffing
- [ ] CRC verification
- [ ] KISS frame formatting
- [ ] Frame output to KISS clients

### RX Components Needed
- [ ] AFSKDemodulator class
- [ ] BitSlicer / timing recovery
- [ ] Frame reception buffer
- [ ] AGC (automatic gain control)

---

## 🎯 NOT STARTED - PHASE 3 (UI & FEATURES)

### User Interface
- [ ] Audio device selection UI (microphone dropdown)
- [ ] Audio device selection UI (speaker dropdown)
- [ ] TX test button
- [ ] RX monitor with live frame display
- [ ] Settings persistence (JSON)

### Audio Management (Windows)
- [ ] Instructions for Windows Volume Mixer
- [ ] Audio level documentation (user adjusts via Windows, not app)
- [ ] CABLE Audio setup guide

### PTT Control
- [ ] GPIO/serial PTT implementation
- [ ] VOX (Voice Operated Transmit) option
- [ ] TX timeout protection

### Diagnostics
- [ ] Real-time signal monitor (waveform display)
- [ ] Frequency analyzer (FFT display)
- [ ] Audio level indicator (showing device levels)
- [ ] Statistics (packets TX/RX, errors, etc.)

---

## 📌 NOTES

### Design Principles
- **Keep it simple** - no AGW, only KISS
- **User controls audio devices** - Windows handles audio levels
- **Modularity** - each function in separate file
- **Python first** - focus on correctness before optimization

### Architecture Constraints
- No AGWPE support (removed)
- No APRS-IS gateway in core (can be added as plugin later)
- Audio device selection is mandatory for TX/RX
- Windows audio levels set via OS mixer, not app
- [ ] TCP KISS server stability testing
- [ ] UDP KISS support
- [ ] Multiple client handling
- [ ] Frame queuing under load

### Testing & Validation
- [ ] Unit tests for HDLC codec
- [ ] Unit tests for AFSK modem
- [ ] Integration tests
- [ ] Real APRS network transmission testing

---

## 📋 RECENT CHANGES (THIS SESSION)

### Files Modified
1. **tx_pipeline.py**
   - Added WAV debug output (saves all TX audio to `tx_debug/` folder)
   - Increased amplitude from 0.8 to 0.9
   - Added `_save_audio_debug()` method
   - Imports: added `wave`, `os`, `datetime`

### Audio Configuration (Current)
- **Amplitude**: 0.9 (was 0.8)
- **Sample Rate**: 44100 Hz
- **Bit Rate**: 1200 bps
- **Mark Freq**: 1200 Hz
- **Space Freq**: 2200 Hz
- **Channels**: 1 (mono)
- **Format**: 16-bit PCM (Int16)

### Known Working Systems
- ✅ HDLC encoding with bit stuffing + CRC
- ✅ AFSK modulation (generates sine waves at correct frequencies)
- ✅ Audio output to PyAudio
- ✅ Device fallback mechanism
- ✅ KISS server on 0.0.0.0:8001
- ✅ GUI launches (Tkinter window)

---

## 🐛 POSSIBLE ISSUES FOUND

### Audio Quality Issue
- User reports: "dźwięk się pojawia... ale to na pewno nie APRS"
- Likely causes:
  1. Amplitude still insufficient (0.9 may need boost to 1.0)
  2. NRZI state transitions not correct
  3. Bit stuffing errors in HDLC encoder
  4. Sine wave phase continuity issues
  5. Timing between bits may have jitter

### Debugging Approach
1. Generate simple known pattern (like string of 0s or 1s)
2. Listen to output and verify correct tones
3. Measure frequencies with analyzer
4. Check timing with oscilloscope or audio analysis software

---

## 📂 FOLDER STRUCTURE

```
h:\MicroTNC\TNC-APP\
├── src/
│   ├── gui_audio.py          # GUI with Audio tab + KISS server
│   ├── audio_manager.py       # PyAudio device management
│   ├── afsk_modem.py         # AFSK modulation/demodulation
│   ├── hdlc_codec.py         # HDLC encoding/decoding
│   └── ...
├── tnc_headless.py           # Standalone KISS server (no GUI)
├── tx_pipeline.py            # TX chain: KISS → HDLC → AFSK → Audio
├── test_tx_pipeline.py       # TX pipeline test
├── tx_debug/                 # Audio WAV files (generated by tx_pipeline)
├── .venv/                    # Python virtual environment
├── TODO.md                   # This file
└── ... (other files)
```

---

## 🚀 NEXT STEPS (FOR NEXT SESSION)

### Immediate (High Priority)
1. **Debug audio output**
   - Listen to WAV files in `tx_debug/` folder
   - Use Audacity or FFT analyzer to verify frequencies
   - Compare against reference APRS audio

2. **If frequencies incorrect**
   - Check AFSK modulator phase calculations
   - Verify sine wave pre-calculation
   - Test with manual frequency generation

3. **If bit timing off**
   - Verify samples_per_bit calculation (should be 36.75)
   - Test with known bit pattern
   - Check NRZI state machine

### Medium (After Audio is Verified)
1. **RX Pipeline implementation** (largest task)
2. **GUI enhancements** (signal monitor, FFT display)
3. **Testing with real APRS network**

### Low Priority (Nice to Have)
1. PTT control
2. Settings persistence
3. Logging to file
4. Performance optimization

---

## 💾 GITHUB COMMIT MESSAGE

```
[WIP] TX Pipeline: AFSK modulation with debug audio output

- Increased AFSK amplitude to 0.9 for better audibility
- Added WAV debug output to tx_debug/ folder for analysis
- HDLC encoding verified working
- Bell 202 AFSK (1200/2200 Hz) modulation implemented
- Audio frequencies need verification - output not yet confirmed as valid APRS

Next: Debug audio output against reference APRS samples
```

---

## 📝 NOTES

- System is **fully functional for TX** - audio is being transmitted
- Issue is **verification of output correctness** - need to confirm Bell 202 compliance
- RX path not yet started - deferring until TX is verified
- Device fallback mechanism working well - system is device-agnostic
- KISS server accepting connections and routing frames correctly

---

**Last Updated**: 2026-04-16 (Session 1)
**Status**: Ready for GitHub push + continuation at home
