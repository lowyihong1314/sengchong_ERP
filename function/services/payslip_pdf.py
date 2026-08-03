"""
Payslip PDF.

Built with reportlab rather than through AutoCount's report engine: AutoCount
has no payslip template and the payroll data is not in AutoCount at all.

Everything printed comes from the payroll item, which is a snapshot taken when
the run was built. Reprinting last quarter's payslip after somebody's raise
therefore still shows what they were actually paid.
"""
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# Employee names here are Chinese as often as not, so a Latin-only font is not
# enough -- Helvetica renders them as empty boxes.
#
# It has to be a TrueType-outline font: reportlab's TTFont cannot read the
# PostScript (CFF) outlines that Noto CJK ships with, which is exactly how the
# first attempt at this silently produced a payslip full of boxes. WenQuanYi
# is TrueType and is embedded in the file, so the PDF reads the same anywhere.
_CJK_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
BODY_FONT = None
BOLD_FONT = None


class PayslipFontError(RuntimeError):
    """No font capable of rendering employee names could be loaded."""


def _register_fonts():
    """
    Load a CJK-capable font, or refuse to build the payslip.

    Falling back to Helvetica is not an option: it produces a document that
    looks finished while the employee's name is a row of boxes, and that is
    worse than an error somebody has to read.
    """
    global BODY_FONT, BOLD_FONT
    if BODY_FONT:
        return

    tried = []
    for path in _CJK_CANDIDATES:
        if not Path(path).exists():
            tried.append(f"{path}: not installed")
            continue
        try:
            pdfmetrics.registerFont(TTFont("PayslipCJK", path, subfontIndex=0))
            BODY_FONT = BOLD_FONT = "PayslipCJK"
            return
        except Exception as error:
            tried.append(f"{path}: {error}")

    raise PayslipFontError(
        "No CJK-capable TrueType font available for payslips. Install one with "
        "`sudo apt-get install fonts-wqy-microhei`. Tried: " + "; ".join(tried)
    )


def _money(value):
    if value in (None, ""):
        return "0.00"
    return f"{Decimal(str(value)):,.2f}"


def _num(value):
    if value in (None, ""):
        return "0"
    text = f"{Decimal(str(value)):.2f}".rstrip("0").rstrip(".")
    return text or "0"


def build_payslips(run, items, *, company_label=""):
    """
    Render one PDF holding a payslip per employee, one to a page.

    `run` and `items` are the API payloads from PayrollStore, so this reads a
    snapshot and never touches the live salary setup.
    """
    _register_fonts()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Payslips {run['company']} {run['period']}",
        author="AutoCount ERP Gateway",
    )

    base = getSampleStyleSheet()["Normal"]
    styles = {
        "title": ParagraphStyle("t", parent=base, fontName=BOLD_FONT, fontSize=15, leading=19),
        "sub": ParagraphStyle("s", parent=base, fontName=BODY_FONT, fontSize=9, leading=12,
                              textColor=colors.HexColor("#475569")),
        "cell": ParagraphStyle("c", parent=base, fontName=BODY_FONT, fontSize=9, leading=12),
        "cellR": ParagraphStyle("cr", parent=base, fontName=BODY_FONT, fontSize=9, leading=12,
                                alignment=TA_RIGHT),
        "h": ParagraphStyle("h", parent=base, fontName=BOLD_FONT, fontSize=10, leading=13),
        "warn": ParagraphStyle("w", parent=base, fontName=BOLD_FONT, fontSize=9, leading=12,
                               textColor=colors.HexColor("#9a3412")),
        "foot": ParagraphStyle("f", parent=base, fontName=BODY_FONT, fontSize=7.5, leading=10,
                               textColor=colors.HexColor("#64748b"), alignment=TA_CENTER),
    }

    story = []
    for index, item in enumerate(items):
        if index:
            story.append(PageBreak())
        story.extend(_payslip(run, item, styles, company_label))

    doc.build(buffer and story, onFirstPage=_noop, onLaterPages=_noop)
    buffer.seek(0)
    return buffer.read()


def _noop(canvas, doc):
    return None


def _payslip(run, item, styles, company_label):
    P = lambda text, style="cell": Paragraph(str(text), styles[style])
    story = []

    story.append(P(company_label or run["company"], "title"))
    story.append(P(f"Payslip &mdash; {run['period']}  ({run['periodStart']} to {run['periodEnd']})", "sub"))
    story.append(Spacer(1, 8))

    # --- who ---
    who = Table(
        [
            [P("Employee", "h"), P(f"{item['name']} ({item['employeeCode']})"),
             P("Daily Rate", "h"), P(_money(item["dailyRate"]), "cellR")],
            [P("Position", "h"), P(item["position"] or "-"),
             P("OT Rule", "h"), P(item["otRule"] or "-")],
            [P("Bank", "h"), P(f"{item['bankName']} {item['bankAccountNo']}".strip() or "-"),
             P("EPF / SOCSO No", "h"), P(f"{item['epfMemberNo'] or '-'} / {item['socsoNo'] or '-'}")],
        ],
        colWidths=[26 * mm, 62 * mm, 30 * mm, 56 * mm],
    )
    who.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(who)
    story.append(Spacer(1, 10))

    # --- what they worked, and what it earned ---
    earnings = [
        [P("Earnings", "h"), P("Worked", "h"), P("Amount (RM)", "h")],
        [P("Normal"), P(f"{_num(item['dayUnits'])} day(s)"), P(_money(item["normalPay"]), "cellR")],
        [P("Overtime"), P(f"{_num(item['otHours'])} hour(s)"), P(_money(item["otPay"]), "cellR")],
        [P("Overnight"),
         P(f"{_num(item['overnightNights'])} night(s), {_num(item['overnightHours'])} hour(s)"),
         P(_money(item["overnightPay"]), "cellR")],
        [P("Fixed allowance"), P(""), P(_money(item["fixedAllowance"]), "cellR")],
    ]
    if Decimal(str(item["adjustment"] or 0)) != 0:
        earnings.append([P("Adjustment"), P(item["adjustmentNote"] or ""),
                         P(_money(item["adjustment"]), "cellR")])
    earnings.append([P("Gross Pay", "h"), P(""), P(_money(item["grossPay"]), "cellR")])

    story.append(_grid(earnings))
    story.append(Spacer(1, 10))

    # --- deductions ---
    deductions = [
        [P("Deductions", "h"), P(""), P("Amount (RM)", "h")],
        [P("EPF (employee)"), P(""), P(_money(item["epfEmployee"]), "cellR")],
        [P("SOCSO (employee)"), P(""), P(_money(item["socsoEmployee"]), "cellR")],
        [P("EIS (employee)"), P(""), P(_money(item["eisEmployee"]), "cellR")],
        [P("PCB"), P(""), P(_money(item["pcb"]), "cellR")],
    ]
    if Decimal(str(item["otherDeduction"] or 0)) != 0:
        deductions.append([P("Other"), P(item["otherDeductionNote"] or ""),
                           P(_money(item["otherDeduction"]), "cellR")])
    total_deductions = (
        Decimal(str(item["epfEmployee"] or 0)) + Decimal(str(item["socsoEmployee"] or 0))
        + Decimal(str(item["eisEmployee"] or 0)) + Decimal(str(item["pcb"] or 0))
        + Decimal(str(item["otherDeduction"] or 0))
    )
    deductions.append([P("Total Deductions", "h"), P(""), P(_money(total_deductions), "cellR")])
    story.append(_grid(deductions))
    story.append(Spacer(1, 10))

    net = Table([[P("NET PAY (RM)", "h"), P(_money(item["netPay"]), "cellR")]],
                colWidths=[124 * mm, 50 * mm])
    net.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#94a3b8")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(net)
    story.append(Spacer(1, 8))

    # An incomplete payslip must say so on the page, not only in the UI:
    # printed paper outlives whatever warning the screen showed.
    if not run.get("statutoryConfigured"):
        warn = Table([[P(run.get("statutoryNote") or "", "warn")]], colWidths=[174 * mm])
        warn.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7ed")),
            ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#fdba74")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(KeepTogether(warn))
        story.append(Spacer(1, 6))

    state = "LOCKED" if run.get("locked") else "DRAFT - not final"
    story.append(P(
        f"{state} &middot; generated from payroll run {run['period']} &middot; "
        f"{'locked ' + run['lockedAt'] if run.get('lockedAt') else 'not yet locked'}",
        "foot",
    ))
    return story


def _grid(rows):
    table = Table(rows, colWidths=[62 * mm, 62 * mm, 50 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#94a3b8")),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.HexColor("#94a3b8")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
    ]))
    return table
