# 469er-Bot-Creation

# Yin-und-Yang-Kern (Starter)

Kleiner, prüfbarer Python-Kern ohne externe Abhängigkeiten (Python 3.9+, nur Standardbibliothek).
Er ist **keine** fertige oder fehlerfreie Produktions-KI, sondern ein solider Grundkern zum Ausbauen.
Alle Texte, Meldungen und Kommentare sind auf Deutsch; Code-Bezeichner und JSON-Feldnamen der API bleiben englisch (stabile Schnittstelle).

## Rollen
- **Yin und Yang** – Koordinator: nimmt Aufgaben an, plant, leitet nur bei Bedarf an einen Spezialisten weiter.
- **Visionär** – technische rechte Hand/Schiedsrichter: liefert mehrere Ansätze (auch eine ungewöhnliche Option) mit Nutzen, Aufwand, Risiken, Tests und Abwägung; liefert nur Entwürfe/Patch-Vorschläge; kann nichts freigeben (Freigaben sind nur durch Menschen möglich).
- **AniForge** – isolierter, minimaler Platzhalter; keine Referenz auf Speicher, Anbieter oder andere Agenten, keine geteilten Daten.

## Aufbau (`yinyang_core/`)
`api.py` HTTP · `orchestrator.py` Routing/Zeitlimits/Wiederholungen · `agents/` · `permissions.py` Stufen + Freigaben · `knowledge.py` SQLite · `audit.py` JSONL-Log (Geheimnisse geschwärzt) · `lifecycle.py` Start/Stopp · `providers.py` Modell-Schnittstelle · `reports.py` Wochenbericht · `app.py` Verdrahtung.

## Autonomiestufen
1. Autonom: lesen/analysieren/planen/vorschlagen/berichten. 2. Begrenzte Prüfungen/Tests in Isolation. 3. Freigabe nötig: Dateiänderungen, Abhängigkeiten installieren, Konfiguration ändern, Deployment. 4. Gesperrt ohne ausdrückliche Freigabe: Löschen, Weitergabe vertraulicher Daten, Veröffentlichen, kostenpflichtige Aktionen. Unbekannte Aktionen gelten als Stufe 4. Auch mit Freigabe **führt dieser Starter nichts aus Stufe 3/4 aus** – er protokolliert nur die Entscheidung. Es werden keine Shell-Befehle ausgeführt.

## Installieren / Starten / Testen / Stoppen
```
python -m yinyang_core                          # startet http://127.0.0.1:8469 (nichts zu installieren)
python -m unittest discover -v                  # Tests
```
Stoppen mit Strg+C oder SIGTERM: neue Aufgaben werden abgelehnt (503), laufende bekommen `YY_SHUTDOWN_GRACE_S` Sekunden, danach wird der Speicher geschlossen. Konfiguration über Umgebungsvariablen (siehe `.env.example`, wird nicht automatisch geladen). Laufzeitdaten liegen in `data/` (von Git ignoriert).
Der Start prüft die Gesundheit (z. B. Datenbank) und bricht bei Fehlern kontrolliert ab.

## API
- `GET /health` – Zustand, Prüfungen, Anbieter (`is_mock`); 503, solange nicht „running“.
- `POST /tasks` `{"task": "...", "agent": optional}` – ohne `agent` plant Yin und Yang und leitet weiter.
- `GET /approvals`, `POST /approvals/{id}/decision` `{"decision":"approve|reject","decided_by":"alice","explicit":false}` – Agentennamen werden als Entscheider abgelehnt.
- `POST /reports/weekly` – Wochenbericht erzeugen und speichern.

```
curl -s localhost:8469/tasks -d '{"task":"finde den Engpass in meinem Code"}'
```

## Wochenbericht / Zeitsteuerung
`WeeklyReportService.generate()` (auch `POST /reports/weekly`) ruft Quellen aus `YY_REPORT_SOURCES` ab (`name=https://...`, nur https, begrenzte Größe/Zeit) und speichert den Bericht mit Quellen und Abrufzeitpunkten. **Es läuft noch nichts automatisch wöchentlich.** Später z. B. per Cron: `0 8 * * 1 curl -X POST localhost:8469/reports/weekly`. Es wird nie etwas installiert oder geändert.

## Übersicht: Mocks / Platzhalter / Grenzen
- Modell-Anbieter: **nur Mock** (`MockProvider`); liefert keine echten KI-Antworten. Andere Namen führen zu einem Fehler. Es werden keine API-Schlüssel gelesen.
- Visionärs Vorschläge sind feste Vorlagen, keine modellgenerierte Analyse.
- AniForge ist ein Platzhalter; das Routing von Yin und Yang arbeitet mit Stichwörtern (deutsch/englisch).
- Freigaben liegen im Speicher (nach Neustart weg); die HTTP-API hat keine Authentifizierung – nur auf localhost betreiben.
- Zeitlimits sind kooperativ: ein abgelaufener Thread wird verworfen, nicht beendet.
- Stufe 2 (isolierte Testausführung) ist definiert, aber nicht implementiert.
- Der Wissensspeicher nimmt nur ausdrücklich freigegebene Einträge an (Python-API, noch kein HTTP-Endpunkt); Geheimniserkennung ist musterbasiert und nur ein Best-Effort.
