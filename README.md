# MicroKISStnc v1.1.3

Pobranie:
- [Latest release with installers](https://github.com/SP5ME/MicroKISStnc/releases/latest)

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

### Uruchomienie z release

#### Windows
1. Otworz [Latest release with installers](https://github.com/SP5ME/MicroKISStnc/releases/latest).
2. Pobierz paczke `MicroKISStnc-windows-x64.zip`.
3. Rozpakuj archiwum.
4. Uruchom `MicroKISStnc.exe`.
5. W kliencie APRS ustaw polaczenie KISS na:
   - Host: `127.0.0.1`
   - Port: `8001`

#### macOS
1. Otworz [Latest release with installers](https://github.com/SP5ME/MicroKISStnc/releases/latest).
2. Pobierz paczke `MicroKISStnc-macos-arm64.tar.gz`.
3. Rozpakuj archiwum.
4. Uruchom plik `MicroKISStnc`.
5. W kliencie APRS ustaw polaczenie KISS na:
   - Host: `127.0.0.1`
   - Port: `8001`

#### Linux z interfejsem graficznym
1. Otworz [Latest release with installers](https://github.com/SP5ME/MicroKISStnc/releases/latest).
2. Pobierz paczke `MicroKISStnc-linux-x64.tar.gz`.
3. Rozpakuj archiwum.
4. Uruchom plik `MicroKISStnc`.
5. W kliencie APRS ustaw polaczenie KISS na:
   - Host: `127.0.0.1`
   - Port: `8001`

#### Linux bez srodowiska graficznego
- Pobierz paczke `MicroKISStnc-linux-x64.tar.gz` z [Latest release with installers](https://github.com/SP5ME/MicroKISStnc/releases/latest).
- Rozpakuj archiwum i uruchom binarke w trybie bez okna, np.:
  - `cd /root/MicroKISStnc`
  - `QT_QPA_PLATFORM=offscreen ./MicroKISStnc`
- To jest obejscie awaryjne dla systemow bez normalnej sesji graficznej, np. Raspberry Pi OS Lite.

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

### Startup from release

#### Windows
1. Open [Latest release with installers](https://github.com/SP5ME/MicroKISStnc/releases/latest).
2. Download `MicroKISStnc-windows-x64.zip`.
3. Unpack the archive.
4. Run `MicroKISStnc.exe`.
5. In your APRS client set KISS connection to:
   - Host: `127.0.0.1`
   - Port: `8001`

#### macOS
1. Open [Latest release with installers](https://github.com/SP5ME/MicroKISStnc/releases/latest).
2. Download `MicroKISStnc-macos-arm64.tar.gz`.
3. Unpack the archive.
4. Run `MicroKISStnc`.
5. In your APRS client set KISS connection to:
   - Host: `127.0.0.1`
   - Port: `8001`

#### Linux with a graphical desktop
1. Open [Latest release with installers](https://github.com/SP5ME/MicroKISStnc/releases/latest).
2. Download `MicroKISStnc-linux-x64.tar.gz`.
3. Unpack the archive.
4. Run `MicroKISStnc`.
5. In your APRS client set KISS connection to:
   - Host: `127.0.0.1`
   - Port: `8001`

#### Linux without a graphical desktop
- Download `MicroKISStnc-linux-x64.tar.gz` from [Latest release with installers](https://github.com/SP5ME/MicroKISStnc/releases/latest).
- Unpack the archive and run the binary in headless mode, for example:
  - `cd /root/MicroKISStnc`
  - `QT_QPA_PLATFORM=offscreen ./MicroKISStnc`
- This is an emergency workaround for systems without a normal graphical session.

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
