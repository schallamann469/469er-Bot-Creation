# 469er Bot Creation

Kleiner, lokaler und modularer Python-Grundkern für Yin und Yang, Visionär und
das isolierte AniForge-Platzhaltemodul. Der erste Ausbau verwendet ausschließlich
die Python-Standardbibliothek.

## Installation und Start

Python 3.10 oder neuer wird benötigt. Es gibt keine zusätzlichen Abhängigkeiten:

```sh
python -m venv .venv
source .venv/bin/activate
cp .env.example .env
python -m ai_core.main
```

Die optionale `.env`-Datei wird nicht automatisch geladen. Um Werte daraus zu
verwenden, exportiere sie in deiner Shell oder setze die Variablen direkt.
Standardmäßig lauscht die API nur auf `127.0.0.1:8000`; die SQLite-Datei wird
lokal unter `data/knowledge.sqlite3` angelegt.

## API und Stopp

- `GET /health` prüft SQLite und meldet Annahmestatus sowie laufende Aufgaben.
- `POST /tasks` nimmt `{"task": "..."}` an. Aufgaben sind auf 4000 Zeichen
  begrenzt; offensichtliche Geheimnisse werden abgelehnt.
- `POST /language` nimmt `{"prompt":"..."}` an und gibt eine Textantwort des
  ausgewählten Sprachproviders zurück.
- `POST /proposals/code` nimmt `{"task":"...", "context":"..."}` an und gibt
  einen Codeentwurf als nicht angewandten Vorschlag zurück. Ein zusätzlich
  konfigurierter echter Sprachprovider kann den Entwurf erstellen; alternativ
  lässt sich ein eigener `CodeDraftProvider` in `CoreService` einsetzen.
- `POST /reports/weekly` nimmt optional explizit abgerufene Quellen an:
  `{"sources":[{"source":"https://example.org","retrieved_at":"2026-01-01T12:00:00Z","summary":"..."}]}`
  und speichert einen Bericht lokal. Die API ruft die Quellen nicht selbst ab.
- `POST /stop` nimmt keine neuen Aufgaben mehr an und wartet auf laufende Arbeit.

Zum Beenden des Prozesses `Ctrl+C` verwenden. Der Server beendet sich kontrolliert.

## Sprachprovider

Das Text-Sprachmodul ist über `ai_core/language.py` gekapselt. Ohne weitere
Konfiguration bleibt `AI_LANGUAGE_PROVIDER=mock`; dieser Modus erzeugt keine
echten Sprach- oder Codeantworten. Für einen OpenAI-kompatiblen Chat-Completions-
Endpunkt müssen `AI_LANGUAGE_PROVIDER=openai-compatible`,
`AI_LANGUAGE_EXTERNAL_ENABLED=true`, `AI_LANGUAGE_ENDPOINT`,
`AI_LANGUAGE_MODEL` und `AI_LANGUAGE_API_KEY` explizit in der Laufzeitumgebung
gesetzt sein. Der Endpunkt muss HTTPS verwenden (HTTP wird nur für localhost
akzeptiert). Zugangsdaten gehören ausschließlich in Umgebungsvariablen oder
einen Secret-Manager, niemals in Git.

Bei Aktivierung werden Prompts und nötiger Code-Kontext an den konfigurierten
Drittanbieter gesendet. Sende keine vertraulichen Inhalte; offensichtliche
Geheimnisse werden vor dem Senden zurückgewiesen. Der Provider hat Zeit- und
Antwortgrößenlimits und folgt keinen HTTP-Weiterleitungen. Die Konfiguration
lädt `.env` nicht automatisch. Dieses Modul verarbeitet Text; Audioeingabe und
Sprachausgabe sind nicht enthalten.

## Tests

```sh
python -m unittest discover -v
```

Die Tests decken API, SQLite-Wissensspeicher, Freigaben, Agententrennung,
Mock-Provider sowie Start-/Stopp-Verhalten ab.

## Architektur und Grenzen

- `ai_core/agents/roles.py`: Yin und Yang plant; Visionär liefert vergleichbare
  technische Ansätze mit Nutzen, Aufwand, Risiken und Wartbarkeit.
- `ai_core/agents/ani_forge.py`: isolierter Platzhalter ohne gemeinsame
  Erinnerung oder Produktionsaktionen.
- `ai_core/knowledge.py`: echtes lokales SQLite-Schema; Erkenntnisse,
  Entscheidungen und Feedback werden nur nach expliziter Bestätigung gespeichert.
- `ai_core/approvals.py`, `security.py` und `audit.py`: getrennte
  Freigabe-, Schutz- und Audit-Grundlagen. Änderungen werden nicht angewandt;
  ein Patch bleibt ein Vorschlag.
- `ai_core/language.py` und `ai_core/providers.py`: gekapselter Sprachdienst
  mit OpenAI-kompatiblem optionalem Provider und explizitem Mock-Standard.
  Zugangsdaten sind nicht eingebaut.
- `ai_core/code_proposals.py`: begrenzte Provider-Schnittstelle für
  Codeentwürfe; kontrolliert Eingaben und Ausgaben und gibt Vorschläge nur
  zur Prüfung zurück. Es gibt keinen Dateizugriff und keine automatische
  Codeanwendung. Im Mock-Modus wird kein echter Code generiert.
- `ai_core/reports.py`: erstellt und speichert Visionärs Wochenberichte.
  `VISIONARY_SOURCES` konfiguriert Quellen; Abruf und Verifikation von
  Quelldaten sind bewusst nicht implementiert.

Der erste Ausbau führt keine Shell-Befehle, Tests, Installationen,
Produktivänderungen, Veröffentlichungen oder kostenpflichtigen Aktionen
automatisch aus. Die Freigabeklasse unterscheidet autonome Arbeit,
isolierte ausdrücklich erlaubte Prüfungen, zustimmungspflichtige Änderungen
und dauerhaft verbotene Aktionen. Zeit- und Eingabegrenzen sind vorhanden;
eine persistente Warteschlange, echter Provider, externe Quellenabrufe und
produktive Agentenaktionen bleiben zukünftige Arbeiten.

## Annahmen und nächste Schritte

Die HTTP-Schicht verwendet nur die Standardbibliothek und ist für lokale
Entwicklung gedacht, nicht als öffentlich betriebener Produktionsserver.
Sinnvolle nächste Schritte sind Integrationstests mit dem konkret gewählten
Provider, authentifizierte Benutzerfreigaben und ein kontrollierter, isolierter
Test-Runner. Audiofunktionen sind ebenfalls nicht Teil dieses Text-Sprachmoduls.
