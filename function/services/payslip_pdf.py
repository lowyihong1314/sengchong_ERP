"""
Payslip PDF, laid out like the SALARY VOUCHER the office already issues.

Two bilingual columns -- EARNINGS / 收入 against DEDUCTIONS / 扣除 -- then
additions, net pay, the employer's contributions and the signature lines. The
arithmetic follows the paper form rather than the database:

    NET = GROSS - TOTAL DEDUCTIONS + TOTAL ADDITIONS

so an allowance paid on top of salary appears under additions, after the
deductions have been taken, which is where the clerk expects to find it.

Built with reportlab rather than through AutoCount's report engine: AutoCount
has no payslip template and none of this data lives there. Everything printed
comes from the payroll item, which is a snapshot taken when the run was built,
so reprinting an old payslip after a raise still shows what was actually paid.
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
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# The form is bilingual, so a Latin-only font is not enough -- Helvetica
# renders the Chinese labels as empty boxes.
#
# It has to be a TrueType-outline font: reportlab's TTFont cannot read the
# PostScript (CFF) outlines that Noto CJK ships with, which is exactly how the
# first version of this silently produced a payslip full of boxes. WenQuanYi is
# TrueType and gets embedded, so the PDF reads the same on any machine.
_CJK_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
BODY_FONT = None


class PayslipFontError(RuntimeError):
    """No font capable of rendering the bilingual labels could be loaded."""


def _register_fonts():
    """
    Load a CJK-capable font, or refuse to build the payslip.

    Falling back to Helvetica is not an option: it produces a document that
    looks finished while half the labels are boxes, and that is worse than an
    error somebody has to read.
    """
    global BODY_FONT
    if BODY_FONT:
        return

    tried = []
    for path in _CJK_CANDIDATES:
        if not Path(path).exists():
            tried.append(f"{path}: not installed")
            continue
        try:
            pdfmetrics.registerFont(TTFont("PayslipCJK", path, subfontIndex=0))
            BODY_FONT = "PayslipCJK"
            return
        except Exception as error:
            tried.append(f"{path}: {error}")

    raise PayslipFontError(
        "No CJK-capable TrueType font available for payslips. Install one with "
        "`sudo apt-get install fonts-wqy-microhei`. Tried: " + "; ".join(tried)
    )


def _d(value):
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _rm(value):
    """The form prints a dash rather than RM0.00 for anything not applicable."""
    amount = _d(value)
    return f"RM{amount:,.2f}" if amount else "-"


def _month_label(period):
    """2025-12 -> DEC 2025, the way the paper form writes it."""
    names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
             "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    try:
        year, month = (int(part) for part in str(period).split("-"))
        return f"{names[month - 1]} {year}"
    except (ValueError, IndexError):
        return str(period)


def _ic(value):
    """770110085625 -> 770110-08-5625, as printed on the form."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) == 12:
        return f"{digits[:6]}-{digits[6:8]}-{digits[8:]}"
    return str(value or "")


def build_payslips(run, items, *, letterhead=None):
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
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Payslips {run['company']} {run['period']}",
        author="AutoCount ERP Gateway",
    )

    base = getSampleStyleSheet()["Normal"]
    styles = {
        "co": ParagraphStyle("co", parent=base, fontName=BODY_FONT, fontSize=13, leading=16,
                             alignment=TA_CENTER),
        "coSub": ParagraphStyle("cs", parent=base, fontName=BODY_FONT, fontSize=8.5, leading=11,
                                alignment=TA_CENTER),
        "title": ParagraphStyle("t", parent=base, fontName=BODY_FONT, fontSize=12, leading=15,
                                alignment=TA_CENTER),
        "cell": ParagraphStyle("c", parent=base, fontName=BODY_FONT, fontSize=8.5, leading=11),
        "cellR": ParagraphStyle("cr", parent=base, fontName=BODY_FONT, fontSize=8.5, leading=11,
                                alignment=TA_RIGHT),
        "warn": ParagraphStyle("w", parent=base, fontName=BODY_FONT, fontSize=7.5, leading=10,
                               textColor=colors.HexColor("#9a3412")),
        "foot": ParagraphStyle("f", parent=base, fontName=BODY_FONT, fontSize=7, leading=9,
                               textColor=colors.HexColor("#64748b"), alignment=TA_CENTER),
    }

    story = []
    for index, item in enumerate(items):
        if index:
            story.append(PageBreak())
        story.extend(_voucher(run, item, styles, letterhead or {}))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def _voucher(run, item, styles, letterhead):
    P = lambda text, style="cell": Paragraph(str(text), styles[style])
    story = []

    # --- letterhead -----------------------------------------------------
    story.append(P(letterhead.get("name") or run["company"], "co"))
    # Printed verbatim. The registration already carries SSM's own punctuation
    # -- "201903201306 (JM0910762-V)" -- so adding another pair of brackets
    # around it would nest them.
    if letterhead.get("registration"):
        story.append(P(letterhead["registration"], "coSub"))
    for line in letterhead.get("address") or []:
        story.append(P(line, "coSub"))
    story.append(Spacer(1, 6))
    story.append(P("SALARY VOUCHER", "title"))
    story.append(Spacer(1, 6))

    who = Table(
        [[P(f"MONTH: {_month_label(run['period'])}"), P(f"PAY TO: {item['name']}")],
         [P(item["employeeCode"]), P(f"IC NO: {_ic(item.get('socsoNo') or '')}")]],
        colWidths=[89 * mm, 89 * mm],
    )
    who.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(who)
    story.append(Spacer(1, 5))

    # --- earnings against deductions ------------------------------------
    # GROSS here means pay for work done. The adjustment is an addition
    # applied after deductions, further down, which is why it is excluded
    # even though the database folds it into gross_pay.
    gross = (_d(item["normalPay"]) + _d(item["otPay"])
             + _d(item["overnightPay"]) + _d(item["fixedAllowance"]))
    other_deductions = _d(item["pcb"]) + _d(item["otherDeduction"])
    total_deductions = (_d(item["epfEmployee"]) + _d(item["socsoEmployee"])
                        + _d(item["eisEmployee"]) + other_deductions)
    additions = _d(item["adjustment"])
    net = gross - total_deductions + additions

    rows = [
        [P("EARNINGS / 收入"), P(""), P("DEDUCTIONS / 扣除"), P("")],
        [P("BASIC PAY / 基本支付"), P(_rm(item["normalPay"]), "cellR"),
         P("EMPLOYEE'S EPF 雇员公积金"), P(_rm(item["epfEmployee"]), "cellR")],
        [P("OVERTIME / 超时"), P(_rm(item["otPay"]), "cellR"),
         P("EMPLOYEE'S SOCSO 雇员社会保险"), P(_rm(item["socsoEmployee"]), "cellR")],
        [P("OVERNIGHT / 通宵"), P(_rm(item["overnightPay"]), "cellR"),
         P("EMPLOYEE'S EIS 雇员就业保险"), P(_rm(item["eisEmployee"]), "cellR")],
        [P("ALLOWANCES / 津贴"), P(_rm(item["fixedAllowance"]), "cellR"),
         P(f"OTHERS / 其他 : {item.get('otherDeductionNote') or ''}"),
         P(_rm(other_deductions), "cellR")],
        [P("GROSS PAY / 总薪金"), P(_rm(gross), "cellR"),
         P("TOTAL DEDUCTIONS / 总扣除"), P(_rm(total_deductions), "cellR")],
    ]
    grid = Table(rows, colWidths=[58 * mm, 31 * mm, 58 * mm, 31 * mm])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("LINEAFTER", (1, 0), (1, -1), 0.7, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.black),
        ("LINEABOVE", (0, -1), (-1, -1), 0.7, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f8fafc")),
    ]))
    story.append(grid)

    # --- additions and net ----------------------------------------------
    net_table = Table(
        [[P("TOTAL ADDITIONS :"), P(item.get("adjustmentNote") or "-"),
          P(_rm(additions), "cellR")],
         [P("NET PAY / 净薪资"), P(""), P(_rm(net), "cellR")]],
        colWidths=[45 * mm, 102 * mm, 31 * mm],
    )
    net_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("LINEABOVE", (0, 1), (-1, 1), 0.7, colors.black),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#e2e8f0")),
    ]))
    story.append(net_table)
    story.append(Spacer(1, 5))

    # --- employer side and signatures ------------------------------------
    contribution = (_d(item["epfEmployer"]) + _d(item["socsoEmployer"])
                    + _d(item["eisEmployer"]))
    employer = Table(
        [[P("EMPLOYER'S EPF / 雇主公积金"), P(_rm(item["epfEmployer"]), "cellR"),
          P("PREPARED BY / 处理者:")],
         [P("EMPLOYER'S SOCSO / 雇主社会保险"), P(_rm(item["socsoEmployer"]), "cellR"), P("")],
         [P("EMPLOYER'S EIS / 雇主就业保险"), P(_rm(item["eisEmployer"]), "cellR"),
          P("APPROVED BY / 批准者:")],
         [P("TOTAL CONTRIBUTION / 雇主总供款"), P(_rm(contribution), "cellR"), P("")],
         [P(""), P(""), P("EMPLOYEE'S SIGNATURE / 雇员签名:")]],
        colWidths=[58 * mm, 31 * mm, 89 * mm],
        rowHeights=[None, None, None, None, 16 * mm],
    )
    employer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("LINEAFTER", (1, 0), (1, -1), 0.7, colors.black),
        ("LINEABOVE", (0, 3), (1, 3), 0.7, colors.black),
        ("SPAN", (2, 0), (2, 1)),
        ("SPAN", (2, 2), (2, 3)),
    ]))
    story.append(employer)
    story.append(Spacer(1, 5))

    # No provenance text here on purpose. Where a figure came from -- filed
    # with KWSP, derived from a contribution, copied off a voucher -- is
    # something the person reviewing the import needs, and it is shown on the
    # Payroll screen. It is not something the employee receiving the payslip
    # needs, and "your gross was reverse-engineered from your EPF" reads badly
    # on a document you hand somebody.
    #
    # The one thing the page must carry is whether it is fit to issue, and
    # that is the draft marker below.
    state = "LOCKED" if run.get("locked") else "DRAFT - not final"
    story.append(P(
        f"{state} &middot; payroll run {run['period']} &middot; "
        f"{'locked ' + run['lockedAt'] if run.get('lockedAt') else 'not yet locked'}",
        "foot",
    ))
    return story
