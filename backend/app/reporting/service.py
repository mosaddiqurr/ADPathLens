import base64
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
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer

LOGO_PATH = Path(__file__).with_name("logo.png")
HTML_TEMPLATE = Path(__file__).with_name("report.html").read_text(encoding="utf-8")


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


def _exposure(payload: dict[str, object]) -> str:
    findings = payload.get("findings", [])
    active = (
        [
            item
            for item in findings
            if isinstance(item, dict)
            and item.get("status") not in {"resolved", "closed", "false_positive", "accepted_risk"}
        ]
        if isinstance(findings, list)
        else []
    )
    source = payload.get("source", {})
    paths = source.get("important_paths", []) if isinstance(source, dict) else []
    for severity in ("critical", "high", "medium", "low", "informational"):
        if any(f.get("severity") == severity for f in active):
            return severity.title()
        if severity == "critical" and any(p.get("risk_score", 0) >= 85 for p in paths):
            return "Critical"
        if severity == "high" and any(p.get("risk_score", 0) >= 65 for p in paths):
            return "High"
        if severity == "medium" and any(p.get("risk_score", 0) >= 35 for p in paths):
            return "Medium"
    return (
        "Low"
        if paths
        else "No significant exposure identified"
        if isinstance(source, dict) and source.get("analysis_available")
        else "Not analyzed"
    )


def _html_bytes(payload: dict[str, object]) -> bytes:
    environment = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(default_for_string=True, default=True),
    )
    template = environment.from_string(HTML_TEMPLATE)
    return template.render(
        title="ADPathLens Directory Exposure Report",
        project=payload["project"],
        exposure=_exposure(payload),
        logo="data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii"),
        generated_at=payload["generated_at"],
        schema_version=payload["schema_version"],
        source=payload["source"],
        findings=payload["findings"],
    ).encode("utf-8")


def _pdf_bytes(payload: dict[str, object]) -> bytes:
    project = payload["project"]
    source = payload["source"]
    findings = payload["findings"]
    if not isinstance(project, dict) or not isinstance(source, dict) or not isinstance(findings, list):
        raise ValueError("Report project, source, and findings must use the canonical structure")
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        title="ADPathLens Directory Exposure Report",
        author="ADPathLens",
    )
    styles = getSampleStyleSheet()
    for key in ("Title", "Heading2", "Heading3"):
        styles[key].textColor = colors.HexColor("#07172D")
    styles["Heading3"].keepWithNext = True
    styles["Heading3"].fontName = "Helvetica-Bold"
    styles["Heading2"].textColor = colors.HexColor("#116CCA")
    styles["BodyText"].textColor = colors.HexColor("#152238")
    styles["BodyText"].leading = 15
    styles["Normal"].textColor = colors.HexColor("#5E6B7D")
    story: list[Any] = [
        Image(str(LOGO_PATH), width=38, height=38),
        Spacer(1, 10),
        Paragraph("ADPathLens Directory Exposure Report", styles["Title"]),
        Paragraph(escape(str(project.get("name", "Environment"))), styles["Heading2"]),
        Paragraph("Exposure: " + escape(_exposure(payload)), styles["Heading3"]),
        Paragraph(escape(str(payload["generated_at"])), styles["Normal"]),
        Spacer(1, 12),
        Paragraph(
            "A possible path is not evidence of compromise. Human review is required.",
            styles["Heading3"],
        ),
        Spacer(1, 12),
        Paragraph("Environment and scope", styles["Heading2"]),
        Paragraph(escape(str(source.get("snapshot_name", "Compared directory data"))), styles["BodyText"]),
        Paragraph(
            f"{source.get('path_count', 0)} attack paths | "
            f"{len(findings)} findings | "
            f"{len(source.get('priority_fixes', []))} priority fixes",
            styles["BodyText"],
        ),
        Spacer(1, 12),
    ]
    source = payload["source"]
    if isinstance(source, dict):
        if source.get("analysis_truncated"):
            story.append(
                Paragraph(
                    "Partial results: analysis limits were reached. Additional paths may exist.", styles["BodyText"]
                )
            )
        story.append(Paragraph("Important attack paths", styles["Heading2"]))
        all_paths = source.get("important_paths", [])
        visible_paths = all_paths[:5] if source.get("report_type") == "executive" else all_paths
        if len(visible_paths) < len(all_paths):
            story.append(
                Paragraph(
                    "Showing the five highest-priority paths. JSON includes all returned paths.", styles["Normal"]
                )
            )
        for path in visible_paths:
            path_story: list[Any] = [
                Paragraph(escape(f"{path['source']} > {path['target']}"), styles["Heading3"]),
                Paragraph(escape(path["explanation"]), styles["BodyText"]),
            ]
            path_story.append(
                Paragraph(
                    escape(
                        f"{path.get('severity', 'unrated').title()} priority | Score {path['risk_score']:.0f}/100 | "
                        f"{path['confidence']} confidence"
                    ),
                    styles["BodyText"],
                )
            )
            for step in path["relationships"]:
                path_story.append(
                    Paragraph(
                        escape(f"{step['source_name']} > {step['relationship_type']} > {step['target_name']}"),
                        styles["BodyText"],
                    )
                )
                evidence = json.dumps(step.get("evidence", {}), ensure_ascii=False, sort_keys=True)
                path_story.append(Paragraph(escape("Evidence: " + evidence[:900]), styles["Normal"]))
                if len(evidence) > 900:
                    path_story.append(
                        Paragraph("Evidence abbreviated in PDF; export JSON for the complete record.", styles["Normal"])
                    )
            path_story.append(Spacer(1, 10))
            story.append(KeepTogether(path_story))
        story.append(Paragraph("Priority fixes", styles["Heading2"]))
        for fix in source.get("priority_fixes", [])[: 5 if source.get("report_type") == "executive" else None]:
            story.append(
                KeepTogether(
                    [
                        Paragraph(escape(fix["title"].replace("→", ">")), styles["Heading3"]),
                        Paragraph(escape(fix["action"]), styles["BodyText"]),
                        Paragraph(
                            f"Affects {fix['affected_paths']} returned paths. Validate before changing the directory.",
                            styles["BodyText"],
                        ),
                        Spacer(1, 8),
                    ]
                )
            )
        if source.get("metrics"):
            story.append(Paragraph("Changes", styles["Heading2"]))
            for key, value in source["metrics"].items():
                story.append(Paragraph(escape(f"{key.replace('_', ' ')}: {value}"), styles["BodyText"]))
    story.append(Paragraph("Findings", styles["Heading2"]))
    findings = payload["findings"]
    if isinstance(findings, list):
        selected_findings = (
            findings[:5] if isinstance(source, dict) and source.get("report_type") == "executive" else findings
        )
        if len(selected_findings) < len(findings):
            story.append(
                Paragraph(
                    "Showing five priority findings. Export JSON for the complete evidence record.", styles["Normal"]
                )
            )
        for finding in selected_findings:
            if not isinstance(finding, dict):
                continue
            story.append(
                KeepTogether(
                    [
                        Paragraph(escape(str(finding.get("title", ""))), styles["Heading3"]),
                        Paragraph(
                            escape(
                                f"{finding.get('severity', '').title()} priority | "
                                f"{finding.get('confidence', '')} confidence"
                            ),
                            styles["Normal"],
                        ),
                        Spacer(1, 6),
                        Paragraph(escape(str(finding.get("description", ""))), styles["BodyText"]),
                        Paragraph("<b>Impact:</b> " + escape(str(finding.get("impact", ""))), styles["BodyText"]),
                        Paragraph(
                            "<b>Remediation:</b> " + escape(str(finding.get("remediation", ""))), styles["BodyText"]
                        ),
                        Spacer(1, 14),
                    ]
                )
            )
    story.extend(
        [
            Paragraph("Methodology and limitations", styles["Heading2"]),
            Paragraph(
                "Bounded traversal and deterministic rules prioritize imported relationships for human review. "
                "Confidence reflects source evidence, not certainty of exploitation. "
                "Simulations do not change Active Directory. Retest with fresh data after applying changes.",
                styles["BodyText"],
            ),
        ]
    )

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#DEE5EC"))
        canvas.line(doc.leftMargin, 45, A4[0] - doc.rightMargin, 45)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5E6B7D"))
        canvas.drawString(doc.leftMargin, 31, "ADPathLens | Directory exposure")
        canvas.drawRightString(A4[0] - doc.rightMargin, 31, str(doc.page))
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
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
