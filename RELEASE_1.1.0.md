# MicroKISStnc 1.1.0

## Opis aplikacji
MicroKISStnc to desktopowy TNC APRS/KISS. Aplikacja odbiera ramki KISS z lokalnych klientów APRS, zamienia je na audio AFSK do nadawania oraz dekoduje audio AFSK z powrotem do ramek KISS.

W praktyce oznacza to, że aplikacja działa jako lokalny most między klientem APRS a torem audio/radiowym.

## Co jest w tej wersji
- Wbudowany serwer KISS TCP na `127.0.0.1:8001`.
- Opcjonalny interfejs Web UI do zdalnego sterowania, domyślnie na `0.0.0.0:8765`.
- Ochrona Web UI listą dozwolonych adresów oraz opcjonalnym tokenem.
- Wybór urządzeń audio wejścia i wyjścia.
- Mierniki poziomu sygnału dla toru RX i TX.
- Testy tonu AFSK: `1200 Hz`, `2200 Hz` i `Both`.
- Sterowanie PTT w trybach `RIG/CAT`, `DTR`, `RTS` oraz `VOX`.
- Obsługa CAT przez `Hamlib rigctld` albo bezpośrednio przez port szeregowy.
- Profile radiowe dla popularnych modeli oraz test połączenia CAT.
- Dodatkowe ustawienia linii `active low`, test PTT i reset domyślnych ustawień TX/PTT.
- Monitor zdarzeń z opcją `Freeze`.
- Minimalizacja do traya i przełączanie języka interfejsu.

## Gotowy opis do GitHub Release
MicroKISStnc 1.1.0 to desktopowy TNC APRS/KISS do pracy z audio, PTT i sterowaniem siecią.

Aplikacja:
- odbiera ramki KISS od lokalnych klientów APRS,
- zamienia je na audio AFSK do nadawania,
- dekoduje audio AFSK z powrotem do ramek KISS,
- udostępnia lokalny serwer KISS na porcie `8001`,
- oferuje opcjonalny Web UI do sterowania i diagnostyki,
- pozwala wybierać urządzenia audio, sterować PTT/CAT i sprawdzać poziomy sygnału.

Najważniejsze elementy tej wersji:
- KISS TCP server
- Web UI z kontrolą dostępu
- Audio RX/TX i testy tonów
- PTT/CAT: `RIG/CAT`, `DTR`, `RTS`, `VOX`
- Hamlib `rigctld` oraz bezpośredni CAT po serialu
- Monitor, tray i przełączanie języka
