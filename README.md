# MicroKISStnc public v1

ANG version below (wersja angielska ponizej)

## PL

To jest katalog testowy przed oficjalnym wydaniem. Aplikacja jest przygotowana jako:

- Nazwa wydania: `MicroKISStnc_public_v1`
- KISS server: port `8001` (dziala niezaleznie od Web UI)
- Web UI: port `8765` (mozna wlaczac/wylaczac bez zatrzymania KISS)
- Ikona: `Ikona-MicroKISStnc.ico` (uzywana w buildzie i runtime)

Ostatnie uwzglednione zmiany:

- Pola `Allowed addresses` sa zawsze widoczne, niezaleznie od stanu checkboxa Web UI.
- Wylaczenie Web UI nie zatrzymuje serwera KISS na porcie `8001`.
- Ujednolicona obsluga ikony aplikacji (okno, tray, taskbar) przez AppUserModelID i ladowanie ikony.

### Uruchomienie developerskie (Windows)

1. Utworz i aktywuj srodowisko `venv`.
2. Zainstaluj zaleznosci:

```powershell
pip install -r requirements.txt
```

3. Uruchom aplikacje:

```powershell
python MicroKISStnc_dev.py
```

### Build EXE (Windows onefile)

```powershell
./build_release_win.ps1
```

Wynik:

- `release/win/MicroKISStnc_public_v1.exe`

### Build AppImage (Linux)

```bash
chmod +x build_release_linux.sh
./build_release_linux.sh
```

Wynik:

- `release/package_public_v1/linux/MicroKISStnc_public_v1-x86_64.AppImage`

## EN

This is a pre-release test folder prepared before the official release. The app is packaged as:

- Release name: `MicroKISStnc_public_v1`
- KISS server: port `8001` (independent from Web UI state)
- Web UI: port `8765` (can be toggled without stopping KISS)
- Icon: `Ikona-MicroKISStnc.ico` (used in build and runtime)

Included latest changes:

- `Allowed addresses` fields are always visible, regardless of Web UI checkbox state.
- Disabling Web UI does not disable the KISS server on port `8001`.
- Unified app icon handling (window, tray, taskbar) using AppUserModelID and runtime icon loading.

### Development run (Windows)

1. Create and activate a `venv` environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
python MicroKISStnc_dev.py
```

### Build EXE (Windows onefile)

```powershell
./build_release_win.ps1
```

Output:

- `release/win/MicroKISStnc_public_v1.exe`

### Build AppImage (Linux)

```bash
chmod +x build_release_linux.sh
./build_release_linux.sh
```

Output:

- `release/package_public_v1/linux/MicroKISStnc_public_v1-x86_64.AppImage`

## 🧪 Testowanie

### Test TX

```bash
# 1. Uruchom aplikację
python kiss_tx_rx_dev.py

# 2. Połącz APRSIS32 na localhost:8001

# 3. Wyślij frame z APRSIS32
# → Sprawdź logi czy pojawił się [TX] Received AX.25 frame
# → Sprawdź czy Soundmodem słyszy audio
```

### Test RX

```bash
# 1. Uruchom aplikację
python kiss_tx_rx_dev.py

# 2. Wyślij audio z Soundmodem'a na nasz RX Device

# 3. Obserwuj logi:
# → [RX-AUDIO] Audio detected! (peak: X.XXX)
# → [RX-AUDIO] Demodulated N bits
# → [RX-AUDIO] ✓ Frame decoded! CRC valid: True
# → [KISS] Sending RX frame: X bytes
```

## 📝 Notatki Techniczne

### NRZI Encoding (Non-Return-to-Zero Inverted)

```
Raw bit:     1    1    0    1    0    0
Transition:  -    -    T    -    T    T
NRZI output: 1200 1200 2200 1200 2200 2200
             (MARK=no transition, SPACE=transition)
```

### HDLC Frame Structure

```
[FLAG] [DEST] [SOURCE] [CONTROL] [PID] [INFO] [FCS] [FLAG]
 0x7E   7b     7b       1b        1b    var   2b    0x7E

Gdzie:
- DEST/SOURCE: 7 bajty (AX.25 callsign + SSID)
- CONTROL: 1 bajt (protokół HDLC)
- PID: 1 bajt (Protocol ID)
- INFO: Payload (0-256 bajty typowo)
- FCS: CRC-16-CCITT
- Bit stuffing: Po 5x '1' wstaw '0' (usuń w decoderze)
```

## 🔗 Integracja z TNC-APP

Aplikacja `MicroKISStnc_dev.py` w `TNC-APP/` może uruchamiać ten skrypt:

```python
import subprocess
subprocess.Popen([
    sys.executable,
    r"h:\GitHub\MicroKISStnc\mikrokisstnc_dev_v1\kiss_tx_rx_dev.py"
])
```

## 📖 Referencje

- **APRS Protocol**: http://aprs.org/
- **AX.25 Standard**: http://www.n1vg.net/packet/
- **Direwolf TNC**: https://github.com/wb2osz/direwolf
- **KISS Protocol**: https://www.nada.kth.se/~maguire/KISS.html

## ⚖️ License

Bazuje na Direwolf - skompilowano dla edukacji i eksperymentów radiowych.

---

**Ostatnia aktualizacja**: 2026-04-21  
**Status**: Produkcja (TX tested, RX in development)  
**Maintainer**: GitHub User
