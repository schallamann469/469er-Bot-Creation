"""Safe weekly report generation; source data is supplied, never fetched here."""

from datetime import datetime, timezone
from urllib.parse import urlparse

from .knowledge import KnowledgeStore
from .security import contains_secret


class VisionaryReport:
    def __init__(self, store: KnowledgeStore, configured_sources: list[str] | None = None):
        self.store = store
        self.configured_sources = configured_sources or []

    def generate_weekly(self, snapshots: list[dict[str, str]] | None = None) -> dict[str, object]:
        snapshots = snapshots or []
        lines = [
            "# Visionär – wöchentlicher Update-Bericht",
            f"Erstellt: {datetime.now(timezone.utc).isoformat()}",
            "",
            "Keine Updates, Installationen oder Codeänderungen werden ausgeführt.",
            "",
            "## Quellen und Abrufzeiten",
        ]
        if snapshots:
            for snapshot in snapshots:
                if not isinstance(snapshot, dict):
                    raise ValueError("Each source snapshot must be an object.")
                source_value = snapshot.get("source", "")
                summary_value = snapshot.get("summary", "")
                retrieved_value = snapshot.get("retrieved_at", "")
                if not all(
                    isinstance(value, str)
                    for value in (source_value, summary_value, retrieved_value)
                ):
                    raise ValueError("Source, summary, and retrieved_at must be strings.")
                source = source_value.strip()
                summary = summary_value.strip()
                retrieved_at = retrieved_value.strip()
                parsed = urlparse(source)
                if parsed.scheme not in {"https", "http"} or not parsed.netloc:
                    raise ValueError("Each source must be an HTTP(S) URL.")
                if not retrieved_at or not summary:
                    raise ValueError("Each snapshot needs a retrieval time and summary.")
                try:
                    timestamp = datetime.fromisoformat(
                        retrieved_at.replace("Z", "+00:00")
                    )
                except ValueError as error:
                    raise ValueError("retrieved_at must be an ISO 8601 timestamp.") from error
                if timestamp.tzinfo is None:
                    raise ValueError("retrieved_at must include a timezone.")
                if contains_secret(source + summary):
                    raise ValueError("Source data appears to contain a secret.")
                lines.extend(
                    [f"- {source} (abgerufen: {retrieved_at})", f"  - {summary}"]
                )
        else:
            lines.append("Keine Quelldaten abgerufen.")
            if self.configured_sources:
                lines.append(
                    "Konfigurierte, aber nicht abgerufene Quellen: "
                    + ", ".join(self.configured_sources)
                )
        content = "\n".join(lines)
        report_id = self.store.save_report(content)
        return {"id": report_id, "content": content}
