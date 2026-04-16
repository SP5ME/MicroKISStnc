# TNC Application - Terminal Node Controller

Prosta, modułowa aplikacja do odbierania i dekodowania pakietów APRS/AX.25 na portach KISS i AGWPE.

## Struktura projektu

```
TNC-APP/
├── main.py              # Punkt wejścia aplikacji
├── requirements.txt     # Zależności Python
├── config.json         # Konfiguracja aplikacji
├── tnc.log             # Logi aplikacji (tworzony przy uruchomieniu)
└── src/
    ├── __init__.py      # Inicjalizacja pakietu
    ├── config.py        # Zarządzanie konfiguracją
    ├── servers.py       # Serwery KISS i AGWPE
    ├── parser.py        # Parser APRS/AX.25
    └── gui.py          # Interfejs graficzny PyQt6
```

## Wymagania

- **Python 3.8+**
- **PyQt6** - Framework GUI
- **System operacyjny**: Windows, Linux, macOS

## Instalacja

### 1. Zainstaluj zależności

```bash
pip install -r requirements.txt
```

### 2. Konfiguracja (opcjonalnie)

Edytuj `config.json` aby zmienić porty lub ustawienia:

```json
{
  "servers": {
    "kiss": {
      "enabled": true,
      "host": "0.0.0.0",
      "port": 8001
    },
    "agwpe": {
      "enabled": true,
      "host": "0.0.0.0",
      "port": 8000
    }
  },
  "gui": {
    "window_title": "TNC Application - Development Mode",
    "window_width": 1200,
    "window_height": 700
  }
}
```

## Uruchomienie

```bash
python main.py
```

Aplikacja uruchomi się z dwoma przyciskami:
- **KISS Server** - nasłuchuje na porcie 8001
- **AGWPE Server** - nasłuchuje na porcie 8000

## Wersja deweloperska

Obecna wersja jest wersją developmentową z:
- Zielonymi przyciskami statusu (ON/OFF)
- Monitorem pakietów w czytarnym formacie
- Logowaniem komunikatów serwera
- Dekodowaniem pakietów APRS/AX.25

## Funkcjonalności

### Już zaimplementowane ✅
- Serwer KISS z podstemem wieloklienta
- Serwer AGWPE (podstawowy)
- Parser AX.25
- Parser APRS
- GUI z monitorem pakietów
- Konfiguracja z pliku JSON
- Logging do pliku

### Planowane funkcjonalności 📋
- Pełna obsługa AGWPE
- Dodatkoweparsery modulacji (PSK, 9600 baud)
- Historia pakietów z filtrowaniem
- Export do pliku
- Interfejs użytkownika (UI produkcyjne)
- Obsługa modułów TNC (CM108, GPIO)
- I wiele więcej...

## Testowanie

### Test KISS server z nc (netcat):

```bash
# Otwórz drugi terminal i nawiąż połączenie
nc localhost 8001

# Wyślij KISS frame (0xC0 to FEND)
# Przykład: echo -ne '\xc0\x00\x00\xc0' | nc localhost 8001
```

### Test z klientem APRS

Użyj dowolnego klienta APRS kompatybilnego z KISS (np. APRX, Xastir, itp.)

## Logi

Logi są zapisywane w `tnc.log` i wyświetlane w konsoli.

## Licencja

MIT (Do uzupełnienia)

## Autor

TNC Developer

## Notatki

- Aplikacja jest modułowa i gotowa do rozbudowy
- Każda funkcja w osobnym module
- GUI jest przygotowane do ewolucji
- Serwery działają na wątkach w tle
