from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

DOC_PATH = "decision_memo.pdf"

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "MemoTitle", parent=styles["Title"], fontSize=16, leading=19,
    spaceAfter=2, alignment=TA_LEFT,
)
subtitle_style = ParagraphStyle(
    "MemoSubtitle", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#5f5e5a"),
    spaceAfter=10,
)
heading_style = ParagraphStyle(
    "MemoHeading", parent=styles["Heading2"], fontSize=11, leading=13,
    spaceBefore=8, spaceAfter=3, textColor=colors.HexColor("#0f6e56"),
)
body_style = ParagraphStyle(
    "MemoBody", parent=styles["Normal"], fontSize=9.5, leading=13, spaceAfter=4,
)
bullet_style = ParagraphStyle(
    "MemoBullet", parent=body_style, leftIndent=12, bulletIndent=0, spaceAfter=3,
)
footer_style = ParagraphStyle(
    "MemoFooter", parent=styles["Normal"], fontSize=7.5, leading=10,
    textColor=colors.HexColor("#5f5e5a"), spaceBefore=8,
)

story = []

story.append(Paragraph("Decision memo: claims intake process redesign", title_style))
story.append(Paragraph(
    "Prepared as a data analytics / business analysis portfolio project &middot; all data synthetic",
    subtitle_style,
))
story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#d3d1c7")))
story.append(Spacer(1, 6))

story.append(Paragraph("Situation", heading_style))
story.append(Paragraph(
    "Insurance claims intake averages 12.48 days end-to-end, with wide variance by claim type. "
    "A quantified process-mining analysis of a 5,000-claim synthetic event log (57,781 events) was "
    "conducted to identify where the process loses time and what specifically should change.",
    body_style,
))

story.append(Paragraph("What was analyzed", heading_style))
story.append(Paragraph(
    "Cycle time by activity, rework loop frequency, handoff delay isolated from processing time, "
    "first-contact resolution (FCR), and cycle time by channel and claim type &mdash; computed with "
    "DuckDB directly over the event log. Full methodology, code, and analysis are in the project repo.",
    body_style,
))

story.append(Paragraph("What was found", heading_style))
findings = [
    "<b>Injury claims are the weak point on every metric</b> &mdash; 59.8% FCR, 38.4% documentation "
    "rework rate, 20.63-day average cycle time &mdash; driven by a 7.44-day average wait on "
    "third-party medical records, the single largest cycle-time driver anywhere in the process.",
    "<b>Documentation rework</b> (16.4% of all claims, 5.52-day average wait once triggered) is the "
    "second-largest driver, concentrated in Property and Injury claims.",
    "<b>Manager review is real but narrower than assumed going in.</b> Only 9.6% of claims trigger it, "
    "and the average wait (1.28 days) is misleading &mdash; the median is 0 days. The actual problem is "
    "a 4.91-day p90 tail from periodic congestion, not a permanent capacity shortfall.",
    "<b>Channel adds a smaller, consistent effect</b> &mdash; self-service (Web/Mobile) submissions run "
    "0.7&ndash;1.3 days slower than staff-assisted (Phone/Agent) ones, in every claim type.",
]
for f in findings:
    story.append(Paragraph(f"&bull; {f}", bullet_style))

story.append(Paragraph("What is recommended", heading_style))
recs = [
    "Same-day claim registration on every intake channel",
    "A document completeness check at intake, catching gaps before they reach an adjuster",
    "Medical records requested in parallel with adjuster review for Injury claims, not after it",
    "Widened, business-configurable fast-track eligibility thresholds",
    "A small overflow reviewer pool, triggered only during manager-queue congestion &mdash; not a permanent fifth manager",
]
for r in recs:
    story.append(Paragraph(f"&bull; {r}", bullet_style))

story.append(Paragraph("What it is worth", heading_style))
story.append(Paragraph(
    "Each change was implemented as actual process logic in a second simulation (same resource-queue "
    "mechanics as the as-is model) rather than estimated by hand:",
    body_style,
))

table_data = [
    ["Metric", "As-is", "To-be", "Change"],
    ["Avg cycle time (blended)", "12.48 days", "9.03 days", "-27.6%"],
    ["Injury cycle time", "20.63 days", "13.92 days", "-32.5%"],
    ["First-contact resolution", "82.8%", "94.3%", "+11.5 pts"],
    ["Documentation rework rate", "16.4%", "~5.0%", "-11.4 pts"],
    ["Manager-review p90 wait", "5.12 days", "0.0 days", "overflow absorbs tail"],
]
t = Table(table_data, colWidths=[1.9 * inch, 1.15 * inch, 1.15 * inch, 1.5 * inch])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e1f5ee")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#04342c")),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1efe8")]),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d3d1c7")),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
]))
story.append(Spacer(1, 4))
story.append(t)

story.append(Paragraph(
    "All figures are from a synthetic event log and a process simulation, not a live system. Impact "
    "figures are projections and should be re-validated against production data if implemented. Full "
    "methodology, code, BRD, user stories, requirements traceability matrix, and UAT test plan are in "
    "the accompanying repository.",
    footer_style,
))

doc = SimpleDocTemplate(
    DOC_PATH, pagesize=letter,
    topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    leftMargin=0.7 * inch, rightMargin=0.7 * inch,
)
doc.build(story)
print("built", DOC_PATH)
