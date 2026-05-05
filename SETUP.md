# SETUP - MicroKISStnc v1

## 📦 Struktura Projektu

```
mikrokisstnc_dev_v1/
├── kiss_tx_rx_dev.py              ← GŁÓWNY SKRYPT (bidirectional KISS server)
├── components/                    ← Komponenty współdzielone
│   ├── __init__.py
│   ├── hdlc_codec.py              ← HDLC encoding/decoding (AX.25)
│   ├── afsk_modem.py              ← AFSK modulation (1200/2200 Hz)
│   └── audio_manager.py           ← Audio I/O wrapper
├── requirements.txt               ← Python dependencies
├── README.md                      ← Dokumentacja
└── SETUP.md                       ← Ten plik (instrukcje instalacji)

TNC-APP/
└── launch_v1.py                   ← Launcher dla MicroKISStnc v1
```

## 🔧 Instalacja

### Krok 1: Python Environment

```bash
# Sprawdź wersję Python
python --version
# Wymagane: Python 3.8+

# Zainstaluj virtualenv (opcjonalnie, ale polecane)
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate.bat  # Windows
```

### Krok 2: Zainstaluj Zależności

```bash
# Z folderu mikrokisstnc_dev_v1/
pip install -r requirements.txt

# Lub ręcznie:
pip install sounddevice numpy
```

### Krok 3: Testowanie Audio

```bash
# Sprawdź czy system audio działa
python -c "import sounddevice; print(sounddevice.query_devices())"

# Poszukaj w outputzie:
# - "CABLE Input" - VB-Audio
# - "CABLE Output" - VB-Audio
# - "USB PnP" - USB audio device
```

## 🎛️ Konfiguracja Audio

### Opcja A: Auto-Detection (Domyślnie)

Aplikacja automatycznie znajdzie urządzenia:

```python
# kiss_tx_rx_dev.py uruchamia:
OUTPUT: Device 6 (CABLE Input)
INPUT: Device 36 (CABLE Output)
```

Jeśli Device ID się zmieniają, aplikacja użyje `nth=2` fallback.

### Opcja B: Ręczna Konfiguracja

Edytuj `kiss_tx_rx_dev.py` linia ~140:

```python
def __init__(self, kiss_port=8001, output_device_id=6, input_device_id=36):
    # output_device_id = Twoje TX urządzenie
    # input_device_id = Twoje RX urządzenie
```

### Opcja C: Znalezienie Device ID

```bash
# Wyświetl wszystkie dostępne urządzenia z ID
python -c "
import sounddevice
devices = sounddevice.query_devices()
for i, dev in enumerate(devices):
    print(f'ID {i}: {dev[\"name\"]}')"

# Szukaj:
# ID 6: CABLE Input (VB-Audio Virtual Cable)
# ID 16: CABLE Output (VB-Audio Virtual Cable)
# ID 36: CABLE Output (VB-Audio Virtual Cable)
```

## 🚀 Uruchomienie

### Opcja 1: Bezpośrednio

```bash
cd mikrokisstnc_dev_v1
python kiss_tx_rx_dev.py
```

### Opcja 2: Z TNC-APP (Launcher)

```bash
cd TNC-APP
python launch_v1.py
```

Launcher automatycznie:
- Sprawdzuje czy wszystkie pliki istnieją
- Sprawdza dostępność portu 8001
- Uruchamia aplikację
- Wyświetla logi w real-time

### Opcja 3: Z Menu TNC-APP (Future)

Po integracji z GUI:

```
TNC-APP Menu
├── Standalone TX/RX (MicroKISStnc v1)
│   └── [START v1]  ← Uruchamia launcher
└── ...
```

## 📊 Testowanie Połączenia

### Test 1: Czy server słucha?

```bash
# Windows PowerShell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8001

# Linux/Mac
nc -zv 127.0.0.1 8001
```

Powinno pokazać:
```
RemoteAddress     RemotePort    TcpTestSucceeded
127.0.0.1         8001          True
```

### Test 2: Połącz KISS Client

1. Otwórz APRSIS32 (lub inny KISS client)
2. Network > KISS Server
3. Ustaw:
   - Host: 127.0.0.1
   - Port: 8001
   - (lub kissnetwork: localhost:8001)
4. Connect

### Test 3: Wyślij TX Frame

1. Z KISS client'a wyślij AX.25 frame
2. Sprawdź logi aplikacji:
   ```
   [TX] Received AX.25 frame: XX bytes
   [TX] Encoding to HDLC...
   [TX] Generated XXXX samples
   [TX] Writing to audio device...
   ```

### Test 4: Odbierz RX Frame

1. Wyślij audio do INPUT device'a
2. Sprawdź logi:
   ```
   [RX-AUDIO] Audio detected! (peak: X.XXX)
   [RX-AUDIO] Demodulated N bits
   [RX-AUDIO] ✓ Frame decoded! CRC valid: True
   [KISS] Sending RX frame: X bytes
   ```

## 🐛 Troubleshooting

### Problem: "Cannot find module X"

```
ModuleNotFoundError: No module named 'sounddevice'
```

**Rozwiązanie:**
```bash
pip install sounddevice numpy
```

### Problem: "Port 8001 already in use"

```
[ERROR] [errno 48] Address already in use
```

**Rozwiązanie:**
```bash
# Windows: Znajdź process
netstat -ano | findstr :8001
taskkill /PID <PID> /F

# Linux/Mac: Zabij proces na porcie
lsof -i :8001
kill -9 <PID>
```

### Problem: "Device X is not an output device"

```
[AUDIO] Device 2 is not an output device
```

**Rozwiązanie:**
- Zmień `output_device_id` na Device z [OUT] flagą
- Użyj listing'u aby znaleźć poprawne ID

### Problem: "No audio detected"

```
[RX-AUDIO] Audio detected! - NIGDY SIĘ NIE POKAZUJE
```

**Przyczyny & Rozwiązania:**
1. Zły INPUT device
   - Sprawdź czy Device ID jest INPUT [IN]
   - Zwiększ gain w źródle audio

2. Audio nie trafia do wejścia
   - Sprawdź routing audio systemu
   - Test z wavefile zamiast live audio

3. Próg amplitudy zbyt wysoki
   - Linia w `afsk_modem.py`: `carrier_threshold = 0.0005`
   - Spróbuj: `carrier_threshold = 0.0001`

## 📝 Konfiguracja dla Soundmodem

### Soundmodem Ustawienia

```
Sound Card:
  Output device: CABLE Input (VB-Audio Virtual Cable)
  Input device:  Mikrofon (2 — USB PnP Sound Dev)
  
  [Wysyła na Device 6 CABLE Input - nasz TX]
  [Słucha z USB - audio z radia]

Server setup:
  AGWPE Server Port: 8000
  KISS Server Port: 8100
  ☑ Enabled
```

### Nasz TNC Ustawienia

```
kiss_tx_rx_dev.py (auto-detection):
  OUTPUT: Device 6 (CABLE Input)   - Soundmodem słucha
  INPUT: Device 36 (CABLE Output) - My słuchamy Soundmodem'a
  KISS PORT: 8001
```

### Przepływ Audio

```
Radio
  ↓
USB Device (mikrofon)
  ↓
Soundmodem (RX demod)
  ↓
KISS Server (Soundmodem port 8100)
  ↓
APRSIS32 / Pinpoint / MyApp
  ↓
[Outgoing frame]
  ↓
KISS Client (localhost:8001)
  ↓
Our TNC (nasz TNC - port 8001)
  ↓
HDLC encode + AFSK modulate
  ↓
Device 6 (CABLE Input)
  ↓
Soundmodem (TX mod)
  ↓
PTT + Radio TX
```

## 🔄 Integracja z TNC-APP

### MicroKISStnc_dev.py + v1

```python
# TNC-APP/MicroKISStnc_dev.py

def launch_v1(self):
    """Uruchomi MicroKISStnc v1 standalone"""
    import subprocess
    import sys
    
    v1_launcher = Path(__file__).parent / "launch_v1.py"
    subprocess.Popen([sys.executable, str(v1_launcher)])
```

### Menu Integration (Future)

```
UI:
  ┌─ TNC Setup
  ├─ TX/RX Configuration
  ├─ KISS Server (MicroKISStnc GUI) ← TNC-APP
  │  └── [START]
  │
  └─ Standalone TX/RX v1
     └── [START v1]  ← launch_v1.py
```

## 🎓 Nauka

Aby zrozumieć jak działa:

1. **HDLC Encoding**: `components/hdlc_codec.py`
   - Bit stuffing, CRC calculation, frame detection

2. **AFSK Modulation**: `components/afsk_modem.py`
   - Tone generation, demodulation, AGC

3. **KISS Protocol**: `kiss_tx_rx_dev.py` linie ~200-280
   - Frame escaping, FEND/FESC handling

4. **Audio Routing**: `components/audio_manager.py`
   - PyAudio streams, device selection

## 📖 Przydatne Linki

- KISS Protocol: https://www.nada.kth.se/~maguire/KISS.html
- APRS Spec: http://aprs.org/
- AX.25: http://www.n1vg.net/packet/
- Direwolf GitHub: https://github.com/wb2osz/direwolf

## ✅ Checklist Przed Użyciem

- [ ] Python 3.8+ zainstalowany
- [ ] Zależności zainstalowane (`pip install -r requirements.txt`)
- [ ] VB-Audio Virtual Cable zainstalowany
- [ ] Soundmodem skonfigurowany
- [ ] APRSIS32 / Pinpoint zainstalowany
- [ ] Przejrzałeś README.md
- [ ] Znasz swoje Device ID'y
- [ ] Zanotowałeś port (8001)

## 🆘 Pomoc

Jeśli coś nie działa:

1. Sprawdź `kiss_tx_rx_dev.log`
2. Szukaj [ERROR] lub [WARNING]
3. Przejrzyj "Troubleshooting" sekcję wyżej
4. Uruchom z debugiem: `python -u kiss_tx_rx_dev.py` (unbuffered output)

---

**Ostatnia aktualizacja**: 2026-04-21
**Status**: Production Ready (TX+RX)
