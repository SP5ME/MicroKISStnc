# Changelog

Wszystkie istotne zmiany w projekcie MicroKISStnc.

## [1.1.0] - 2026-06-04
### Added
- Lokalny serwer KISS TCP na porcie `8001`.
- Pełny tor audio dla APRS/KISS: KISS -> HDLC -> AFSK -> audio oraz audio -> AFSK -> HDLC -> KISS.
- Opcjonalny Web UI do sterowania aplikacją z poziomu przeglądarki.
- Lista dozwolonych adresów dla Web UI oraz opcjonalny token.
- Wybór urządzeń audio wejścia i wyjścia oraz mierniki poziomu sygnału.
- Testy tonu `1200 Hz`, `2200 Hz` i `Both`.
- Sterowanie PTT w trybach `RIG/CAT`, `DTR`, `RTS` i `VOX`.
- Obsługa CAT przez `Hamlib rigctld` albo bezpośrednio przez port szeregowy.
- Profile radiowe dla popularnych modeli i test połączenia CAT.
- Monitor zdarzeń z opcją zamrożenia przewijania.
- Minimalizacja do traya i przełączanie języka interfejsu.

### Changed
- Przebudowano układ interfejsu na czytelniejsze sekcje konfiguracyjne.
- Ujednolicono i uporządkowano ustawienia TX/PTT oraz CAT.
- Zaktualizowano tag wersji aplikacji do `1.1.0`.

