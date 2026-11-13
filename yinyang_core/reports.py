"""Dienst für den wöchentlichen Technik-Update-Bericht (aufrufbar; von diesem Starter NICHT zeitgesteuert).

Später planen: WeeklyReportService.generate() per Cron/systemd-Timer oder
Aufgabenplaner aufrufen. Es wird nichts automatisch installiert oder geändert.
"""
import json
from datetime import datetime, timezone
from typing import Callable, Dict, List, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_BYTES = 100_000


def parse_sources(entries: Sequence[str]) -> List[Dict[str, str]]:
    out = []
    for e in entries:
        name, sep, url = e.partition("=")
        if not sep or urlparse(url).scheme != "https":
            raise ValueError(f"ungültige Berichtsquelle '{name}': erwartet name=https://...")
        out.append({"name": name.strip(), "url": url.strip()})
    return out


def http_fetch(url: str) -> str:
    if urlparse(url).scheme != "https":
        raise ValueError("nur https-Quellen sind erlaubt")
    with urlopen(Request(url, headers={"User-Agent": "yinyang-core"}), timeout=10) as r:  # noqa: S310
        return r.read(MAX_BYTES).decode("utf-8", "replace")


class WeeklyReportService:
    def __init__(self, store, audit, sources: Sequence[Dict[str, str]], fetch: Callable[[str], str] = http_fetch):
        self._store, self._audit, self._sources, self._fetch = store, audit, list(sources), fetch

    def generate(self) -> dict:
        items = []
        for s in self._sources:
            retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                text = self._fetch(s["url"])
                items.append({"source": s["name"], "url": s["url"], "retrieved_at": retrieved,
                              "excerpt": text[:300], "error": None})
            except Exception as exc:  # Fehler je Quelle melden, weitermachen
                items.append({"source": s["name"], "url": s["url"], "retrieved_at": retrieved,
                              "excerpt": "", "error": type(exc).__name__})
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "items": items,
            "note": "Nur zur Information. Es wurde nichts installiert oder geändert." if items
                    else "Keine Quellen konfiguriert (YY_REPORT_SOURCES setzen).",
        }
        report["id"] = self._store.save_report("weekly_tech_update", json.dumps(report, ensure_ascii=False))
        self._audit.write("weekly_report_generated", id=report["id"], sources=len(items))
        return report
