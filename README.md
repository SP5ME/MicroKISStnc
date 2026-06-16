# MicroKISStnc v1.1.3

EXE:
[MicroKISStnc_v1.1.3.exe](https://github.com/SP5ME/MicroKISStnc/releases/download/v1.1.3/MicroKISStnc_v1.1.3.exe)

### Krotki opis aplikacji
MicroKISStnc v1.1.3 to desktopowy TNC APRS/KISS. Aplikacja zamienia ramki KISS na audio AFSK (TX) oraz audio AFSK na ramki KISS (RX), dzieki czemu moze wspolpracowac z typowymi klientami APRS.
Obsługiwane profile modemu obejmuja teraz Bell 202 / AFSK1200 oraz HF APRS 300 baud AFSK zgodny z Soundmodem (1600/1800 Hz).

Najwazniejsze porty:
- KISS Server: 127.0.0.1:8001
- Web UI (opcjonalne): 0.0.0.0:8765

### Co nowego w v1.1.3
- Web UI zostal ujednolicony z interfejsem desktopowym.
- W przegladarce dostepna jest zmiana jezyka.
- Z poziomu Web UI mozna zmieniac port KISS.
- Monitor zostal uproszczony i startuje domyslnie jako aktywna zakladka.

### Instrukcja uruchomienia

#### Windows
1. Otworz folder aplikacji.
2. Zainstaluj zaleznosci:
   - `py -3 -m pip install -r requirements.txt`
3. Uruchom aplikacje:
   - `py -3 MicroKISStnc.py`
4. W kliencie APRS ustaw polaczenie KISS na:
   - Host: 127.0.0.1
   - Port: 8001

#### macOS
1. Otworz Terminal w folderze aplikacji.
2. Zainstaluj zaleznosci:
   - `python3 -m pip install -r requirements.txt`
3. Uruchom aplikacje:
   - `python3 MicroKISStnc.py`
4. W kliencie APRS ustaw polaczenie KISS na:
   - Host: 127.0.0.1
   - Port: 8001

#### Linux z interfejsem graficznym
1. Otworz terminal w folderze aplikacji.
2. Zainstaluj zaleznosci:
   - `python3 -m pip install -r requirements.txt`
3. Uruchom aplikacje:
   - `python3 MicroKISStnc.py`
4. W kliencie APRS ustaw polaczenie KISS na:
   - Host: 127.0.0.1
   - Port: 8001

#### Linux bez srodowiska graficznego
- Obecna wersja aplikacji nie ma natywnego trybu konsolowego.
- `MicroKISStnc.py` uruchamia GUI PyQt6, wiec na systemach bez pulpitu, np. Raspberry Pi OS Lite, trzeba najpierw zapewnic sesje graficzna albo uruchomic aplikacje przez tymczasowe srodowisko X/Wayland.
- Po uruchomieniu interfejsu graficznego konfiguracja jest taka sama: `python3 MicroKISStnc.py` i port KISS `8001`.

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
- Modem profile: wybor profilu modemu dla RX/TX.
- Signal level (IN/OUT): wskaznik poziomu sygnalu.
- 1200 Hz: testowy ton MARK.
- Both: test dwoch tonow AFSK.
- 2200 Hz: testowy ton SPACE.

Sekcja: PTT / CAT
- PTT type: wybor sposobu sterowania PTT (RIG/DTR/RTS/NONE).
- Rig model: profil radia CAT/CI-V.
- PTT path (serial): port COM dla sterowania PTT.
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
MicroKISStnc v1.1.3 is a desktop APRS/KISS TNC. It converts KISS frames to AFSK audio (TX) and AFSK audio to KISS frames (RX), so it can work with standard APRS software.
Available modem profiles now include Bell 202 / AFSK1200 and HF APRS 300 baud AFSK compatible with Soundmodem (1600/1800 Hz).

Main ports:
- KISS Server: 127.0.0.1:8001
- Web UI (optional): 0.0.0.0:8765

What is new in v1.1.3:
- Web UI is aligned with the desktop interface.
- Browser language switching is available.
- KISS port can be changed from Web UI.
- Monitor view was simplified and opens by default.

### Startup instructions

#### Windows
1. Open the app folder.
2. Install dependencies:
   - `py -3 -m pip install -r requirements.txt`
3. Run the app:
   - `py -3 MicroKISStnc.py`
4. In your APRS client set KISS connection to:
   - Host: 127.0.0.1
   - Port: 8001

#### macOS
1. Open Terminal in the app folder.
2. Install dependencies:
   - `python3 -m pip install -r requirements.txt`
3. Run the app:
   - `python3 MicroKISStnc.py`
4. In your APRS client set KISS connection to:
   - Host: 127.0.0.1
   - Port: 8001

#### Linux with a graphical desktop
1. Open a terminal in the app folder.
2. Install dependencies:
   - `python3 -m pip install -r requirements.txt`
3. Run the app:
   - `python3 MicroKISStnc.py`
4. In your APRS client set KISS connection to:
   - Host: 127.0.0.1
   - Port: 8001

#### Linux without a graphical desktop
- The current build does not include a native console-only mode.
- `MicroKISStnc.py` starts a PyQt6 GUI, so on systems without a desktop, such as Raspberry Pi OS Lite, you need to provide a graphical session first or run it through a temporary X/Wayland environment.
- Once the GUI session is available, startup is the same: `python3 MicroKISStnc.py` and KISS port `8001`.

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
- Modem profile: choose the RX/TX modem profile.
- Signal level (IN/OUT): signal level meters.
- 1200 Hz: MARK test tone.
- Both: dual AFSK test tone mode.
- 2200 Hz: SPACE test tone.

Section: PTT / CAT
- PTT type: choose PTT control mode (RIG/DTR/RTS/NONE).
- Rig model: CAT/CI-V profile.
- PTT path (serial): COM port for PTT.
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
