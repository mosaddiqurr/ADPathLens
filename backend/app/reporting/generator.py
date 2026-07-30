from __future__ import annotations

import csv
import hashlib
import html
import io
import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def csv_safe(value: object) -> str:
    text = str(value if value is not None else "")
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


def render_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False).encode()


def render_csv(payload: dict[str, Any]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "title",
            "category",
            "severity",
            "confidence",
            "status",
            "target",
            "endpoint",
            "remediation",
        ]
    )
    for finding in payload["findings"]:
        writer.writerow(
            [
                csv_safe(finding.get("title")),
                csv_safe(finding.get("category")),
                csv_safe(finding.get("severity")),
                csv_safe(finding.get("confidence")),
                csv_safe(finding.get("status")),
                csv_safe(finding.get("target")),
                csv_safe(finding.get("endpoint")),
                csv_safe(finding.get("remediation")),
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def render_html(payload: dict[str, Any]) -> bytes:
    findings = []
    for finding in payload["findings"]:
        findings.append(
            "<article>"
            f"<h3>{html.escape(str(finding['title']))}</h3>"
            f"<p><strong>{html.escape(str(finding['severity']))}</strong> · "
            f"{html.escape(str(finding['confidence']))} confidence · "
            f"{html.escape(str(finding['status']))}</p>"
            f"<p>{html.escape(str(finding['description']))}</p>"
            f"<h4>Remediation</h4><p>{html.escape(str(finding['remediation']))}</p>"
            "</article>"
        )
    markup = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>AuthZDiff report</title>
<style>
body{{font:15px/1.55 system-ui,sans-serif;max-width:960px;margin:40px auto;color:#172033}}
h1,h2,h3{{color:#0f172a}} article{{border-top:1px solid #cbd5e1;padding:20px 0}}
.notice{{background:#fff7ed;border:1px solid #fdba74;padding:12px}}
code{{font-family:ui-monospace,monospace}}
</style></head><body>
<h1>AuthZDiff authorization comparison report</h1>
<p>Project: {html.escape(str(payload["project"]["name"]))}</p>
<p>Generated: {html.escape(str(payload["generated_at"]))}</p>
<p>Canonical evidence hash: <code>{html.escape(str(payload["content_hash"]))}</code></p>
<p class="notice">Automated differences are review aids and do not independently
prove exploitability.
Reusable credentials, cookies and authorization values are excluded.</p>
<h2>Findings</h2>{"".join(findings) or "<p>No findings were selected.</p>"}
<h2>Redaction summary</h2><p>{html.escape(str(payload["redaction_summary"]))}</p>
<h2>Limitations</h2><p>{html.escape(str(payload["limitations"]))}</p>
</body></html>"""
    return markup.encode()


def render_pdf(payload: dict[str, Any], destination: Path) -> None:
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="AuthZDiff authorization comparison report",
    )
    story = [
        Paragraph("AuthZDiff authorization comparison report", styles["Title"]),
        Spacer(1, 6 * mm),
        Paragraph(f"Project: {html.escape(str(payload['project']['name']))}", styles["Normal"]),
        Paragraph(f"Generated: {html.escape(str(payload['generated_at']))}", styles["Normal"]),
        Paragraph(
            "Automated differences are review aids and do not independently prove exploitability. "
            "Reusable credentials are excluded.",
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Finding summary", styles["Heading2"]),
    ]
    rows = [["Title", "Severity", "Confidence", "Status"]]
    rows.extend(
        [
            finding["title"],
            finding["severity"],
            finding["confidence"],
            finding["status"],
        ]
        for finding in payload["findings"]
    )
    table = Table(rows, colWidths=[90 * mm, 25 * mm, 25 * mm, 25 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172033")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(table)
    for finding in payload["findings"]:
        story.extend(
            [
                PageBreak(),
                Paragraph(html.escape(str(finding["title"])), styles["Heading1"]),
                Paragraph(
                    f"{html.escape(str(finding['severity']))} · "
                    f"{html.escape(str(finding['confidence']))} confidence",
                    styles["BodyText"],
                ),
                Paragraph("Description", styles["Heading2"]),
                Paragraph(html.escape(str(finding["description"])), styles["BodyText"]),
                Paragraph("Remediation", styles["Heading2"]),
                Paragraph(html.escape(str(finding["remediation"])), styles["BodyText"]),
            ]
        )
    document.build(story)
