"""Concise memory-only reports derived from the same comparison result."""

from __future__ import annotations

import csv
import html
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.comparison import Change, ComparisonResult

FONT_LOCK = Lock()
PDF_CHANGE_LIMIT = 100


def csv_safe(value: object) -> str:
    text = str(value if value is not None else "")
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def render_json(result: ComparisonResult) -> bytes:
    payload = {"generated_at": datetime.now(UTC).isoformat(), **result.model_dump()}
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def render_csv(result: ComparisonResult) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    fields = ["principal", "resource", "action", "before", "after", "change", "severity", "why"]
    writer.writerow(fields)
    for change in result.changes:
        data = change.model_dump()
        writer.writerow([csv_safe(data[field]) for field in fields])
    return buffer.getvalue().encode("utf-8-sig")


def _font() -> str:
    with FONT_LOCK:
        if "AuthZDiff" not in pdfmetrics.getRegisteredFontNames():
            font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
            pdfmetrics.registerFont(TTFont("AuthZDiff", str(font_path)))
    return "AuthZDiff"


def _escape(value: str) -> str:
    return html.escape(value.replace("→", " -> ").replace("—", "-"), quote=True)


def render_pdf(result: ComparisonResult) -> bytes:
    buffer = io.BytesIO()
    font = _font()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            fontName=font,
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#142247"),
            spaceAfter=5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSection",
            fontName=font,
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#2455b7"),
            spaceBefore=5 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportBody",
            fontName=font,
            fontSize=9,
            leading=14,
            spaceAfter=2 * mm,
            splitLongWords=True,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSmall",
            fontName=font,
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#526079"),
            spaceAfter=2 * mm,
        )
    )
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=19 * mm,
        leftMargin=19 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="AuthZDiff authorization change report",
        author="AuthZDiff",
    )
    story: list[Any] = [
        Paragraph("AUTHZDIFF", styles["ReportSection"]),
        Paragraph("Authorization change report", styles["ReportTitle"]),
        Paragraph(
            f"{_escape(result.before.filename)} -> {_escape(result.after.filename)}",
            styles["ReportBody"],
        ),
        Paragraph(
            datetime.now(UTC).strftime("Generated %Y-%m-%d %H:%M UTC"), styles["ReportSmall"]
        ),
    ]
    summary = result.summary
    table = Table(
        [
            ["Total changes", "Gained", "Lost", "Risky"],
            [str(summary.total), str(summary.gained), str(summary.lost), str(summary.risky)],
        ],
        colWidths=[43 * mm] * 4,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, 1), 16),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#142247")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f3f9")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([Spacer(1, 3 * mm), table])
    story.append(Paragraph("Risky changes overlap gained/lost totals.", styles["ReportSmall"]))
    if summary.review:
        story.append(
            Paragraph(f"{summary.review} changes need contextual review.", styles["ReportSmall"])
        )
    selected = result.changes[:PDF_CHANGE_LIMIT]
    if len(selected) < summary.total:
        story.append(
            Paragraph(
                f"Showing the first {PDF_CHANGE_LIMIT} of {summary.total} changes, "
                "prioritized by risk. "
                "Export JSON for all changes and technical evidence.",
                styles["ReportSmall"],
            )
        )
    groups = [
        ("RISKY CHANGES", [c for c in selected if c.severity != "info"]),
        ("ACCESS GAINED", [c for c in selected if c.change == "gained" and c.severity == "info"]),
        ("ACCESS LOST", [c for c in selected if c.change == "lost" and c.severity == "info"]),
        (
            "OTHER CHANGES / REVIEW",
            [c for c in selected if c.change == "changed" and c.severity == "info"],
        ),
    ]
    if not selected:
        story.append(
            Paragraph(
                "No authorization changes found in the comparable evidence.", styles["ReportBody"]
            )
        )
    for heading, changes in groups:
        if not changes:
            continue
        story.append(Paragraph(heading, styles["ReportSection"]))
        for change in changes:
            story.extend(_change_paragraphs(change, styles))
    story.append(Paragraph("TECHNICAL NOTES", styles["ReportSection"]))
    for note in [*result.notes, "Technical evidence is included in the JSON report."]:
        story.append(Paragraph(_escape(note), styles["ReportSmall"]))
    story.append(Paragraph("LIMITATIONS", styles["ReportSection"]))
    for limitation in result.limitations:
        story.append(Paragraph(_escape(limitation), styles["ReportSmall"]))

    def footer(canvas: Canvas, _document: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#526079"))
        canvas.drawString(19 * mm, 12 * mm, "AuthZDiff | Authorization change report")
        canvas.drawRightString(191 * mm, 12 * mm, str(canvas.getPageNumber()))
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _change_paragraphs(change: Change, styles: Any) -> list[Any]:
    label = change.severity.upper() if change.severity != "info" else change.change.upper()
    evidence = f"Before: {change.before} | After: {change.after} | Action: {change.action}"
    if "response_difference" in change.evidence:
        references = []
        for side in ("before", "after"):
            item = change.evidence.get(side)
            if item:
                references.append(
                    f"{side.capitalize()} capture entry {item['entry']}: HTTP {item['status']}"
                )
        evidence += ". " + "; ".join(references)
    return [
        Paragraph(_escape(f"{label} · {change.summary}"), styles["ReportBody"]),
        Paragraph(_escape("Evidence - " + evidence), styles["ReportSmall"]),
        Paragraph(_escape(change.why), styles["ReportSmall"]),
        Paragraph(_escape("Recommendation: " + change.recommendation), styles["ReportSmall"]),
        Spacer(1, 2 * mm),
    ]
