# MicroKISStnc public v1

## PL

### Krotki opis aplikacji
MicroKISStnc public v1 to desktopowy TNC APRS/KISS. Aplikacja zamienia ramki KISS na audio AFSK (TX) oraz audio AFSK na ramki KISS (RX), dzieki czemu moze wspolpracowac z typowymi klientami APRS.

Najwazniejsze porty:
- KISS Server: 127.0.0.1:8001
- Web UI (opcjonalne): 0.0.0.0:8765

### Instrukcja uruchomienia
1. Przejdz do folderu aplikacji.
2. Zainstaluj zaleznosci:
   - `pip install -r requirements.txt`
3. Uruchom aplikacje:
   - `python MicroKISStnc.py`
4. W kliencie APRS ustaw polaczenie KISS na:
   - Host: 127.0.0.1
   - Port: 8001

### Opis funkcji i przyciskow

Sekcja: Header / Network
- Hide to tray: po zamknieciu okna aplikacja chowa sie do traya.
- Language: zmienia jezyk interfejsu.
- Web interface enabled: wlacza lub wylacza HTTP panel Web UI.
- Allowed addresses: lista adresow/IP/CIDR, ktore moga laczyc sie z Web UI.
- Toggle: dodaje lub usuwa wpis z listy Allowed addresses.

Sekcja: Devices / Audio
- Audio input: wybor urzadzenia wejsciowego audio (RX).
- Refresh (input): odswieza liste urzadzen input.
- Audio output: wybor urzadzenia wyjsciowego audio (TX).
- Refresh (output): odswieza liste urzadzen output.
- Signal level (IN/OUT): wskaznik poziomu sygnalu.
- 1200 Hz: testowy ton MARK.
- Both: test dwoch tonow AFSK.
- 2200 Hz: testowy ton SPACE.

Sekcja: PTT / CAT
- PTT type: wybor sposobu sterowania PTT (RIG/DTR/RTS/NONE).
- Rig model: profil radia CAT/CI-V.
- PTT path (serial): port COM dla sterowania PTT.
- ptt_share: wspoldzielenie portu PTT.
- CAT connection: tryb TCP albo SERIAL.
- Hamlib host / Port: ustawienia rigctld.
- Test: test polaczenia Hamlib/CAT.

Sekcja: Monitor
- Monitor text: log zdarzen TX/RX i systemowych.
- Freeze: zatrzymuje automatyczne przewijanie monitora.

Tray
- Restore/Show: przywraca glowne okno.
- Exit/Quit: konczy aplikacje.

### Szybka diagnostyka
- Brak dekodowania RX: sprawdz poprawny Audio input i poziom sygnalu.
- Brak nadawania TX: sprawdz Audio output, PTT type i konfiguracje CAT/PTT.
- Brak dostepu do Web UI: sprawdz checkbox Web interface enabled oraz Allowed addresses.
- Klient APRS nie laczy: sprawdz port 8001 i czy nic innego go nie zajmuje.

---

## EN

### Short app description
MicroKISStnc public v1 is a desktop APRS/KISS TNC. It converts KISS frames to AFSK audio (TX) and AFSK audio to KISS frames (RX), so it can work with standard APRS software.

Main ports:
- KISS Server: 127.0.0.1:8001
- Web UI (optional): 0.0.0.0:8765

Important:
- Disabling Web UI does not stop the KISS server.
- Allowed addresses is always visible.

### Startup instructions
1. Open the app folder (for example `github_main_ready_clean`).
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run the app:
   - `python MicroKISStnc.py`
4. In your APRS client set KISS connection to:
   - Host: 127.0.0.1
   - Port: 8001

### Functions and buttons

Section: Header / Network
- Hide to tray: closing the window sends the app to system tray.
- Language: changes UI language.
- Web interface enabled: enables or disables HTTP Web UI.
- Allowed addresses: list of IP/CIDR allowed to use Web UI.
- Toggle: adds or removes selected Allowed addresses entry.

Section: Devices / Audio
- Audio input: select input audio device (RX).
- Refresh (input): refresh input device list.
- Audio output: select output audio device (TX).
- Refresh (output): refresh output device list.
- Signal level (IN/OUT): signal level meters.
- 1200 Hz: MARK test tone.
- Both: dual AFSK test tone mode.
- 2200 Hz: SPACE test tone.

Section: PTT / CAT
- PTT type: choose PTT control mode (RIG/DTR/RTS/NONE).
- Rig model: CAT/CI-V profile.
- PTT path (serial): COM port for PTT.
- ptt_share: shared PTT port mode.
- CAT connection: TCP or SERIAL mode.
- Hamlib host / Port: rigctld settings.
- Test: Hamlib/CAT connectivity test.

Section: Monitor
- Monitor text: TX/RX/system runtime log.
- Freeze: pauses monitor auto-scroll.

Tray
- Restore/Show: restores the main window.
- Exit/Quit: closes the app.

### Quick troubleshooting
- No RX decode: verify Audio input and signal level.
- No TX output: verify Audio output, PTT type, and CAT/PTT config.
- No Web UI access: verify Web interface enabled and Allowed addresses.
- APRS client cannot connect: verify port 8001 is free and active.
