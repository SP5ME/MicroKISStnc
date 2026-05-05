# MicroKISStnc v4 - QUICKSTART

## Installation (5 minutes)

### 1. Download

```bash
cd f:\GitHub\MicroKISStnc\microkisstnc_dev_v4
```

### 2. Install Audio Loopback Device

**Windows**: Install VB-Cable
- Download: https://vb-audio.com/Cable/
- Run installer, restart system

### 3. Start Application

**Option A - Batch (Recommended for Windows)**
```bash
start.bat
```

**Option B - PowerShell**
```powershell
.\start.ps1
```

**Option C - Manual**
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python MicroKISStnc_dev.py
```

## First Run

1. GUI opens showing:
   - RX/TX Monitor (empty initially)
   - Input Device: Shows detected audio device
   - Output Device: Shows speaker/headphones
   - KISS Server: Listening on 127.0.0.1:8001

2. Test tone generation:
   - Click "Test Tone 1200 Hz" button
   - You should see audio level in meters
   - RX monitor should start showing decoded content

3. External software connection:
   - Open Direwolf, APRSdroid, or other TNC software
   - Configure KISS: `127.0.0.1:8001`
   - Click "Connect"
   - Frames will appear in RX monitor

## Typical Flow

```
Voice Radio (External)
    ↓
    Output to Virtual Cable Input
    ↓
MicroKISStnc RX
    (Goertzel demod, phase search, AX.25 decode)
    ↓
KISS Server (Port 8001)
    ↓
    Direwolf/APRSdroid/Other TNC Software
    ↓
    Display in APRS network
```

## Audio Configuration

### Input (RX from radio):
- Connect radio line-in to "CABLE Input"
- Set level: -30 dBm to -6 dBm (adjust in radio settings)

### Output (TX to radio):
- Connect "CABLE Output" to radio microphone input
- Level auto-adjusted by application

## Troubleshooting

### No Input Device Shown

```bash
# List available devices:
python -c "import sounddevice as sd; [print(f'{i}: {d[\"name\"]}') for i,d in enumerate(sd.query_devices())]"
```

Check VB-Cable is installed and appears in list.

### Frames Detected But Low Score

- Frame score < 300: May be corrupted signal
- Frame score 500-1000: Decent signal, validate manually
- Frame score > 1000: Perfect decode, FCS OK

### KISS Connection Refused

Port 8001 already in use:
```bash
netstat -an | findstr :8001
# Kill process or change port in MicroKISStnc_dev.py line ~50
```

## Next Steps

- **Advanced Config**: See README_V4.md for detailed settings
- **Development**: See DEVELOPMENT.md for architecture details
- **Testing**: Use test_single_frame.wav to verify RX pipeline

## Support

- APRS: https://www.aprs.org/
- VB-Cable: https://vb-audio.com/Cable/
- Amateur Radio: https://www.arrl.org/
