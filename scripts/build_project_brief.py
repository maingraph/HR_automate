from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "brief" / "images"
OUTPUT = ROOT / "output" / "pdf" / "Sourcer_Project_Brief_RU.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

FONT_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
]
regular = next(path for path in FONT_CANDIDATES if path.exists())
bold = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
if not bold.exists():
    bold = regular
pdfmetrics.registerFont(TTFont("Brief", str(regular)))
pdfmetrics.registerFont(TTFont("BriefBold", str(bold)))

W, H = A4
NAVY = colors.HexColor("#152032")
BLUE = colors.HexColor("#2D6CDF")
CYAN = colors.HexColor("#48C6D9")
MUTED = colors.HexColor("#667085")
PALE = colors.HexColor("#F3F6FA")
GREEN = colors.HexColor("#20A56B")


def footer(c: canvas.Canvas, page: int):
    c.setFillColor(colors.HexColor("#98A2B3"))
    c.setFont("Brief", 8)
    c.drawString(36, 22, "Sourcer | Pilot brief | 24 July 2026")
    c.drawRightString(W - 36, 22, str(page))


def title(c: canvas.Canvas, text: str, y: float, size: int = 24):
    c.setFillColor(NAVY)
    c.setFont("BriefBold", size)
    c.drawString(36, y, text)


def paragraph(c: canvas.Canvas, text: str, x: float, y: float, width: float, size=10, leading=14, color=NAVY):
    style = ParagraphStyle(
        "body",
        fontName="Brief",
        fontSize=size,
        leading=leading,
        textColor=color,
        alignment=TA_LEFT,
    )
    p = __import__("reportlab.platypus", fromlist=["Paragraph"]).Paragraph(text, style)
    _, height = p.wrap(width, H)
    p.drawOn(c, x, y - height)
    return y - height


def screenshot(c: canvas.Canvas, path: Path, x: float, y_top: float, max_w: float, max_h: float):
    with Image.open(path) as img:
        iw, ih = img.size
    scale = min(max_w / iw, max_h / ih)
    width, height = iw * scale, ih * scale
    y = y_top - height
    c.setFillColor(colors.white)
    c.roundRect(x - 4, y - 4, width + 8, height + 8, 8, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#D0D5DD"))
    c.roundRect(x - 4, y - 4, width + 8, height + 8, 8, fill=0, stroke=1)
    c.drawImage(ImageReader(str(path)), x, y, width=width, height=height, preserveAspectRatio=True)
    return y


c = canvas.Canvas(str(OUTPUT), pagesize=A4)

# Page 1
c.setFillColor(NAVY)
c.rect(0, 0, W, H, fill=1, stroke=0)
c.setFillColor(CYAN)
c.circle(W - 70, H - 70, 34, fill=1, stroke=0)
c.setFillColor(colors.white)
c.setFont("BriefBold", 13)
c.drawString(36, H - 58, "SOURCER")
c.setFont("BriefBold", 32)
c.drawString(36, H - 125, "Управляемый AI sourcing")
c.setFont("Brief", 15)
c.setFillColor(colors.HexColor("#D7E3F4"))
c.drawString(36, H - 153, "Состояние продукта и проверенный demo pipeline")

stats = [("10", "исходных профилей"), ("9", "уникальных"), ("8", "AI-graded")]
for index, (value, label) in enumerate(stats):
    x = 36 + index * 174
    c.setFillColor(colors.HexColor("#20304A"))
    c.roundRect(x, H - 260, 156, 70, 10, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("BriefBold", 24)
    c.drawString(x + 14, H - 222, value)
    c.setFont("Brief", 9)
    c.setFillColor(colors.HexColor("#B7C7DB"))
    c.drawString(x + 50, H - 221, label)

c.setFillColor(colors.white)
c.setFont("BriefBold", 14)
c.drawString(36, H - 318, "Главная идея")
paragraph(
    c,
    "Каждый этап работает как самостоятельный инструмент и сохраняет собственную версию данных. "
    "Рекрутер видит процесс, может остановить его, поправить список, экспортировать результат и продолжить позже.",
    36,
    H - 340,
    W - 72,
    size=12,
    leading=18,
    color=colors.HexColor("#E5ECF5"),
)

flow = ["Sources", "Merge", "Enrich", "Rules", "Similarity", "AI Grade"]
for index, label in enumerate(flow):
    x = 36 + index * 86
    c.setFillColor(BLUE if index < 5 else GREEN)
    c.roundRect(x, 220, 72, 34, 8, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("BriefBold", 8)
    c.drawCentredString(x + 36, 232, label)
    if index < len(flow) - 1:
        c.setStrokeColor(CYAN)
        c.line(x + 72, 237, x + 84, 237)

c.setFillColor(colors.HexColor("#B7C7DB"))
c.setFont("Brief", 9)
c.drawString(36, 72, "Local single-user pilot | Docker | PostgreSQL | Playwright + noVNC | Gemini")
footer(c, 1)
c.showPage()

# Page 2
c.setFillColor(PALE)
c.rect(0, 0, W, H, fill=1, stroke=0)
title(c, "Pipeline под контролем рекрутера", H - 48, 22)
paragraph(
    c,
    "Sales Navigator открывается внутри страницы вакансии. Пользователь вручную настраивает фильтры, "
    "фиксирует поиск и может в любой момент поставить автоматизацию на паузу или забрать управление.",
    36,
    H - 72,
    W - 72,
)
screenshot(c, IMAGES / "02-pipeline-workspace.png", 36, H - 124, W - 72, 385)

y = 270
items = [
    "Независимые источники не смешиваются до явного Merge & Dedup.",
    "Continue фиксирует версию; редактирование создает дочерний датасет.",
    "Partial result остается доступным для CSV, XLSX и JSON export.",
]
for item in items:
    c.setFillColor(BLUE)
    c.circle(43, y + 2, 3, fill=1, stroke=0)
    y = paragraph(c, item, 54, y + 8, W - 90, size=10, leading=14) - 12
footer(c, 2)
c.showPage()

# Page 3
c.setFillColor(colors.white)
c.rect(0, 0, W, H, fill=1, stroke=0)
title(c, "Фактически выполненные этапы", H - 48, 22)
paragraph(
    c,
    "На demo-вакансии выполнены File Import, Merge & Dedup, Enrich Profiles, Rules Filter, "
    "Similarity и AI Grade. Все выходы сохранены как отдельные sealed datasets.",
    36,
    H - 72,
    W - 72,
)
screenshot(c, IMAGES / "03-stage-results.png", 36, H - 120, W - 72, 610)
c.setFillColor(PALE)
c.roundRect(36, 108, W - 72, 242, 10, fill=1, stroke=0)
c.setFillColor(NAVY)
c.setFont("BriefBold", 12)
c.drawString(52, 326, "Что проверено в demo run")
checks = [
    ("01", "Source datasets", "Два отдельных входа по 5 строк."),
    ("02", "Merge & Dedup", "9 уникальных профилей, дубль объединен."),
    ("03", "Rules + Similarity", "Исключение без удаления исходной версии."),
    ("04", "AI Grade", "8 оценок и финальный sealed dataset."),
]
for index, (number, label, detail) in enumerate(checks):
    column = index % 2
    row = index // 2
    x = 52 + column * 248
    y = 278 - row * 88
    c.setFillColor(BLUE if index < 3 else GREEN)
    c.circle(x + 14, y + 12, 14, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("BriefBold", 8)
    c.drawCentredString(x + 14, y + 9, number)
    c.setFillColor(NAVY)
    c.setFont("BriefBold", 10)
    c.drawString(x + 38, y + 13, label)
    paragraph(c, detail, x + 38, y + 2, 192, size=8, leading=11, color=MUTED)
footer(c, 3)
c.showPage()

# Page 4
c.setFillColor(PALE)
c.rect(0, 0, W, H, fill=1, stroke=0)
title(c, "Результат AI Grade", H - 48, 22)
paragraph(
    c,
    "В финальном датасете 8 кандидатов с оценками от 50 до 100. Список можно сортировать, "
    "исключать строки, тегировать, редактировать и выгружать без запуска outreach.",
    36,
    H - 72,
    W - 72,
)
screenshot(c, IMAGES / "04-graded-candidates.png", 36, H - 120, W - 72, 500)

c.setFillColor(colors.white)
c.roundRect(36, 76, W - 72, 112, 10, fill=1, stroke=0)
c.setFillColor(NAVY)
c.setFont("BriefBold", 12)
c.drawString(50, 166, "Следующий шаг: один реальный пилот")
paragraph(
    c,
    "Провести одну вакансию от живого Sales Navigator поиска до shortlist. Зафиксировать время, "
    "число уникальных кандидатов, качество top-10 и ручные действия рекрутера. После результата "
    "можно обсуждать подписку на рекрутера плюс оплату AI/enrichment usage.",
    50,
    150,
    W - 100,
    size=9,
    leading=13,
)
footer(c, 4)
c.save()
print(OUTPUT)
