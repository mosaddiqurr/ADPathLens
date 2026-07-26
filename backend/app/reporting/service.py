import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment, select_autoescape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{{ title }}</title>
<style>
body{font-family:system-ui,sans-serif;margin:2rem;color:#14213d} h1{margin-bottom:.2rem}
.meta{color:#52606d}.finding{border:1px solid #cbd5e1;border-radius:.5rem;padding:1rem;margin:1rem 0}
.severity{font-weight:700;text-transform:uppercase}.warning{background:#fff7ed;padding:.75rem}
@media print{body{margin:12mm}.finding{break-inside:avoid}}
</style></head><body>
<h1>{{ title }}</h1><p class="meta">Generated {{ generated_at }} · schema {{ schema_version }}</p>
<p class="warning">Defensive analysis of imported, authorised data. A possible path is not evidence of compromise.</p>
{% for finding in findings %}<section class="finding">
<h2>{{ finding.title }}</h2><p class="severity">{{ finding.severity }} · {{ finding.confidence }} confidence</p>
<p>{{ finding.description }}</p><h3>Impact</h3><p>{{ finding.impact }}</p>
<h3>Remediation</h3><p>{{ finding.remediation }}</p>
<h3>Limitations</h3><p>{{ finding.limitations }}</p>
</section>{% else %}<p>No findings matched this report source.</p>{% endfor %}
</body></html>"""


def safe_csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def _canonical_payload(
    *, project: dict[str, object], source: dict[str, object], findings: list[dict[str, Any]]
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "authorized_use_notice": (
            "Use only synthetic data or information collected from systems you own "
            "or are explicitly authorized to assess."
        ),
        "limitations": "A possible path is not evidence of compromise.",
        "project": project,
        "source": source,
        "limits": {"findings": len(findings)},
        "findings": findings,
    }


def _json_bytes(payload: dict[str, object]) -> bytes:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    exported = {
        **payload,
        "report_hash": hashlib.sha256(canonical).hexdigest(),
        "report_hash_scope": "Canonical JSON payload excluding report_hash fields.",
    }
    return json.dumps(exported, indent=2, ensure_ascii=False).encode("utf-8")


def _csv_bytes(findings: list[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    fields = [
        "id",
        "title",
        "severity",
        "confidence",
        "status",
        "category",
        "description",
        "impact",
        "remediation",
        "limitations",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for finding in findings:
        writer.writerow({field: safe_csv_cell(finding.get(field, "")) for field in fields})
    return output.getvalue().encode("utf-8-sig")


def _html_bytes(payload: dict[str, object]) -> bytes:
    environment = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(default_for_string=True, default=True),
    )
    template = environment.from_string(HTML_TEMPLATE)
    return template.render(
        title="ADPathLens Defensive Findings Report",
        generated_at=payload["generated_at"],
        schema_version=payload["schema_version"],
        findings=payload["findings"],
    ).encode("utf-8")


def _pdf_bytes(payload: dict[str, object]) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        title="ADPathLens Defensive Findings Report",
        author="ADPathLens",
    )
    styles = getSampleStyleSheet()
    story: list[Any] = [
        Paragraph("ADPathLens Defensive Findings Report", styles["Title"]),
        Paragraph(escape(str(payload["generated_at"])), styles["Normal"]),
        Spacer(1, 12),
        Paragraph(
            "A possible path is not evidence of compromise. Human review is required.",
            styles["Heading3"],
        ),
        Spacer(1, 12),
    ]
    findings = payload["findings"]
    if isinstance(findings, list):
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                continue
            data = [
                ["Severity", escape(str(finding.get("severity", "")))],
                ["Confidence", escape(str(finding.get("confidence", "")))],
                ["Status", escape(str(finding.get("status", "")))],
            ]
            story.extend(
                [
                    Paragraph(escape(str(finding.get("title", ""))), styles["Heading2"]),
                    Table(
                        data,
                        colWidths=[90, 360],
                        style=TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e2e8f0")),
                                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ]
                        ),
                    ),
                    Spacer(1, 8),
                    Paragraph(escape(str(finding.get("description", ""))), styles["BodyText"]),
                    Paragraph("<b>Impact</b>", styles["BodyText"]),
                    Paragraph(escape(str(finding.get("impact", ""))), styles["BodyText"]),
                    Paragraph("<b>Remediation</b>", styles["BodyText"]),
                    Paragraph(escape(str(finding.get("remediation", ""))), styles["BodyText"]),
                    Spacer(1, 14),
                ]
            )
            if index and index % 12 == 0:
                story.append(PageBreak())
    document.build(story)
    return output.getvalue()


def generate_report(
    *,
    output_path: Path,
    output_format: str,
    project: dict[str, object],
    source: dict[str, object],
    findings: list[dict[str, Any]],
) -> tuple[str, int, str]:
    payload = _canonical_payload(project=project, source=source, findings=findings)
    generators = {
        "json": (_json_bytes, "application/json"),
        "csv": (lambda _: _csv_bytes(findings), "text/csv; charset=utf-8"),
        "html": (_html_bytes, "text/html; charset=utf-8"),
        "pdf": (_pdf_bytes, "application/pdf"),
    }
    generator, mime_type = generators[output_format]
    content = generator(payload)
    output_path.write_bytes(content)
    return hashlib.sha256(content).hexdigest(), len(content), mime_type
