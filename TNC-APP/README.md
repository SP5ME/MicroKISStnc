# MicroKISStnc - Terminal Node Controller

Maksymalnie prosta, modularna aplikacja do wysyłania i odbierania pakietów APRS/AX.25 poprzez **protokół KISS** (Keep It Simple Stupid).

## Koncepcja

- **Prostota przede wszystkim** - tylko KISS protocol, brak AGW
- **Audio I/O management** - użytkownik ustawia urządzenia audio, regulacja poziomu z poziomu Windows
- **Development mode** - aplikacja w fazie wczesnego developmentu

## Struktura projektu

```
TNC-APP/
├── main.py              # Punkt wejścia aplikacji
├── requirements.txt     # Zależności Python
├── config.json         # Konfiguracja aplikacji
├── tnc.log             # Logi aplikacji (tworzony przy uruchomieniu)
├── afsk_modem.py       # Modulator AFSK
├── audio_manager.py    # Zarządzanie audio I/O
├── hdlc_codec.py       # Kodek HDLC (encoding/decoding)
├── tx_pipeline.py      # Pipeline TX (HDLC + AFSK + audio)
└── src/
    ├── __init__.py      # Inicjalizacja pakietu
    ├── config.py        # Zarządzanie konfiguracją
    ├── servers.py       # Serwer KISS
    ├── parser.py        # Parser APRS/AX.25
    ├── gui.py           # Interfejs graficzny tkinter
    ├── gui_audio.py     # Audio GUI
    └── kiss_builder.py  # Budowanie ramek KISS
```

## Wymagania

- **Python 3.8+**
- **tkinter** - Framework GUI (wbudowany w Python)
- **PyAudio** - Dostęp do urządzeń audio
- **NumPy** - Przetwarzanie sygnałów
- **System operacyjny**: Windows, Linux, macOS

## Instalacja

### 1. Zainstaluj zależności

```bash
pip install -r requirements.txt
```

### 2. Konfiguracja (opcjonalnie)

Edytuj `config.json` aby zmienić port KISS lub ustawienia okna:

```json
{
  "servers": {
    "kiss": {
      "enabled": true,
      "host": "0.0.0.0",
      "port": 8001
    }
  },
  "gui": {
    "window_title": "MicroKISStnc - Development",
    "window_width": 900,
    "window_height": 600
  }
}
```

## Uruchomienie

### GUI (Development)

```bash
python main.py
```

lub bezpośrednio GUI audio:

```bash
python src/gui_audio.py
```

### Headless mode (bez GUI)

```bash
python tnc_headless.py
```

## Funkcjonalności

### ✅ Zaimplementowane

- **TX Pipeline** - KISS → HDLC Encoder → AFSK Modulator → Audio Output
  - HDLC encoding (NRZI + bit stuffing + CRC-16-CCITT)
  - AFSK modulator (Bell 202: 1200 Hz mark, 2200 Hz space)
  - PyAudio output z auto-detencją urządzenia
  
- **Serwer KISS** - Nasłuchiwanie na porcie 8001 (TCP)
  - Obsługa wieloklienta
  - Dekodowanie ramek KISS (0xC0 framing, 0xDB escaping)
  
- **GUI** - Interfejs graficzny tkinter
  - Monitor pakietów
  - Status serwera
  - Logi aplikacji
  
- **Headless mode** - Pracuje bez GUI
  - Idealne dla embedded systemów

### 📋 Planowane

- **RX Pipeline** - Audio Input → AFSK Demodulator → HDLC Decoder → KISS
- **Wybór urządzeń audio** - UI do wyboru mic/speaker
- **PTT Control** - Serial/GPIO PTT
- **APRS-IS Gateway** - Połączenie z APRS-IS network
- **Zaawansowane ustawienia** - TX power, tone levels, itp.

## Testowanie

### Test KISS server z nc (netcat):

```bash
# Otwórz drugi terminal i nawiąż połączenie
nc localhost 8001

# Wyślij KISS frame (0xC0 to FEND)
# Przykład: echo -ne '\xc0\x00\x00\xc0' | nc localhost 8001
```

### Test TX pipeline

```bash
python test_tx_pipeline.py
# Sprawdź tx_debug/*.wav files w audio analyzerze
```

### Test HDLC/AFSK

```bash
python test_hdlc_afsk.py
```

## Audio Setup

MicroKISStnc wymaga dostępu do urządzeń audio:

1. **Mikrofon** - Do odbierania sygnałów APRS (RX)
2. **Głośnik/Linia wyjściowa** - Do wysyłania sygnałów APRS (TX)

### Rekomendacja dla Windows

- Użyj CABLE Audio Virtual Audio Cable (VB-Audio) do połączenia aplikacji z radiem
- Ustaw poziomy audio w **Windows Volume Mixer** (Ustawienia → Dźwięk)

## Logi

Logi są zapisywane w `tnc.log` i wyświetlane w konsoli.

Poziom logowania: `INFO` (zmienić w `main.py` na `DEBUG` dla bardziej szczegółowych logów)

## Licencja

MIT

## Autor

MicroTNC Team

## Status

**DEVELOPMENT** - Early version, many features not yet implemented
