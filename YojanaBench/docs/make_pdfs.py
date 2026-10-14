"""
make_pdfs.py
------------
Renders the team documentation Markdown files to PDF using reportlab (no external
converter needed). Supports the subset of Markdown used in these docs: headings,
bullet/numbered lists, fenced code blocks, blockquotes, horizontal rules, and
inline **bold** / `code`.

Usage:
    python docs/make_pdfs.py
"""
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, Paragraph, Preformatted, SimpleDocTemplate,
    Spacer,
)

HERE = os.path.dirname(os.path.abspath(__file__))

NAVY = colors.HexColor("#0f3460")
ACCENT = colors.HexColor("#e94560")
INK = colors.HexColor("#16202f")
CODE_BG = colors.HexColor("#f2f4f8")

styles = getSampleStyleSheet()
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=10.5, leading=15, textColor=INK, spaceAfter=6,
                      alignment=TA_LEFT)
TITLE = ParagraphStyle("DocTitle", parent=BODY, fontName="Helvetica-Bold",
                       fontSize=22, leading=26, textColor=NAVY, spaceAfter=4)
H2 = ParagraphStyle("H2", parent=BODY, fontName="Helvetica-Bold", fontSize=15,
                    leading=19, textColor=NAVY, spaceBefore=14, spaceAfter=6)
H3 = ParagraphStyle("H3", parent=BODY, fontName="Helvetica-Bold", fontSize=12.5,
                    leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=4)
QUOTE = ParagraphStyle("Quote", parent=BODY, leftIndent=14, textColor=colors.HexColor("#6b7280"),
                       fontName="Helvetica-Oblique")
CODE = ParagraphStyle("Code", parent=BODY, fontName="Courier", fontSize=9,
                      leading=12.5, textColor=INK, backColor=CODE_BG,
                      leftIndent=6, rightIndent=6, spaceBefore=2, spaceAfter=2,
                      borderPadding=4)


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier" size="9">\1</font>', text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<link href="\2">\1</link>', text)
    return text


def parse(md: str):
    flow = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            flow.append(Preformatted("\n".join(block), CODE))
            flow.append(Spacer(1, 6))
            continue

        if stripped == "---":
            flow.append(Spacer(1, 6))
            flow.append(HRFlowable(width="100%", color=colors.HexColor("#e6e9f2")))
            flow.append(Spacer(1, 6))
            i += 1
            continue

        if stripped.startswith("### "):
            flow.append(Paragraph(inline(stripped[4:]), H3))
        elif stripped.startswith("## "):
            flow.append(Paragraph(inline(stripped[3:]), H2))
        elif stripped.startswith("# "):
            flow.append(Paragraph(inline(stripped[2:]), TITLE))
        elif stripped.startswith("> "):
            flow.append(Paragraph(inline(stripped[2:]), QUOTE))
        elif re.match(r"^\s*[-*] ", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*] ", lines[i]):
                items.append(ListItem(Paragraph(inline(re.sub(r"^\s*[-*] ", "", lines[i])), BODY)))
                i += 1
            flow.append(ListFlowable(items, bulletType="bullet", leftIndent=16,
                                     bulletFontSize=8, spaceAfter=4))
            continue
        elif re.match(r"^\s*\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\. ", lines[i]):
                content = re.sub(r"^\s*\d+\. ", "", lines[i])
                items.append(ListItem(Paragraph(inline(content), BODY)))
                i += 1
            flow.append(ListFlowable(items, bulletType="1", leftIndent=16,
                                     spaceAfter=4))
            continue
        elif stripped == "":
            flow.append(Spacer(1, 4))
        else:
            flow.append(Paragraph(inline(stripped), BODY))
        i += 1
    return flow


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#9aa4b8"))
    canvas.drawString(2 * cm, 1.1 * cm, "YojanaBench — team documentation")
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, "Page %d" % doc.page)
    canvas.restoreState()


def build(md_path, pdf_path):
    with open(md_path, "r", encoding="utf-8") as f:
        md = f.read()
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title=os.path.basename(pdf_path))
    doc.build(parse(md), onFirstPage=footer, onLaterPages=footer)
    print("wrote", pdf_path)


if __name__ == "__main__":
    build(os.path.join(HERE, "Project_Explained.md"),
          os.path.join(HERE, "Project_Explained.pdf"))
    build(os.path.join(HERE, "Setup_Guide.md"),
          os.path.join(HERE, "Setup_Guide.pdf"))
