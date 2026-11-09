"""Builds the companion PowerPoint deck and Excel tracker for the Rabigh security plan.

    python build_extras.py <output folder>
"""
import sys
from pathlib import Path

from build_plan import INITIATIVES

NAVY, GOLD, ICE, WHITE, INK = "0B2A4A", "C9A227", "EEF3F8", "FFFFFF", "1A2433"
TITLE = "خطة تطوير الأمن والحماية وقطاعات الدفاع الجوي"

AXES = [
    ("الأمن المادي وحماية المنشآت", ["مسح أمني شامل وتصنيف المواقع", "تحكم ذكي بالدخول والخروج",
                                     "تحديث المراقبة وغرفة عمليات أمنية مركزية", "تحسين الإنارة والأسوار والدوريات"]),
    ("أمن المعلومات والأمن السيبراني", ["تصنيف المعلومات وتداولها", "مصادقة متعددة العوامل وأقل صلاحية",
                                        "عزل الشبكات الحساسة ومراقبتها", "نسخ احتياطي واستجابة للحوادث"]),
    ("أمن الأفراد والتوعية", ["تحقق أمني للمنسوبين والمتعاقدين", "توعية ربع سنوية",
                              "ضبط الزوار والمرافقة", "قناة سرية للإبلاغ"]),
    ("تطوير قطاعات الدفاع الجوي", ["تحديث الإجراءات وتقييم الجاهزية", "خطة تدريب سنوية ومحاكاة",
                                   "صيانة وقائية ونظام إدارة أصول", "اتصالات احتياطية وتنسيق مشترك"]),
    ("الطوارئ واستمرارية العمل", ["خطط طوارئ لكل موقع", "فرق استجابة وسلسلة قيادة",
                                  "خطة استمرارية للوظائف الحرجة", "تمارين نصف سنوية ودروس مستفادة"]),
    ("السلامة المهنية", ["تقييم مخاطر مواقع العمل", "معدات الوقاية والإطفاء",
                         "تدريب الإسعافات الأولية", "الإبلاغ عن الحوادث وشبه الحوادث"]),
]

KPIS = [
    ("نسبة المواقع المكتمل تقييمها أمنيًا", "100%", "ربع سنوي"),
    ("نسبة المنسوبين المكملين للتوعية", "≥ 95%", "ربع سنوي"),
    ("نسبة إنجاز خطة التدريب التخصصي", "≥ 90%", "ربع سنوي"),
    ("نسبة الجاهزية الفنية للأنظمة", "تحسن مستمر", "شهري"),
    ("متوسط زمن الإصلاح", "انخفاض 25%", "شهري"),
    ("الحوادث الأمنية والسيبرانية", "انخفاض مستمر", "شهري"),
    ("زمن الاستجابة للطوارئ", "ضمن المعيار", "نصف سنوي"),
    ("إصابات العمل", "انخفاض 30%", "ربع سنوي"),
]


# ------------------------------------------------------------------ PowerPoint
def build_pptx(path: Path) -> Path:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.util import Inches, Pt

    def rgb(h):
        return RGBColor.from_string(h)

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    W, H = prs.slide_width, prs.slide_height
    blank = prs.slide_layouts[6]

    def rect(s, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
        r = s.shapes.add_shape(shape, x, y, w, h)
        r.fill.solid()
        r.fill.fore_color.rgb = rgb(color)
        r.line.fill.background()
        return r

    def text(s, x, y, w, h, lines, size=20, color=INK, bold=False, align=PP_ALIGN.RIGHT,
             anchor=MSO_ANCHOR.TOP):
        tb = s.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        for i, line in enumerate([lines] if isinstance(lines, str) else lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.space_after = Pt(8)
            p._p.get_or_add_pPr().set("rtl", "1")
            r = p.add_run()
            r.text = line
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = rgb(color)
            r.font.name = "Arial"
            rpr = r._r.get_or_add_rPr()
            cs = rpr.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}cs",
                                 {"typeface": "Arial"})
            rpr.append(cs)
        return tb

    def page(title, n):
        s = prs.slides.add_slide(blank)
        rect(s, 0, 0, W, H, "F7F9FC")
        rect(s, 0, 0, W, Inches(1.15), NAVY)
        rect(s, 0, Inches(1.15), W, Inches(0.06), GOLD)
        text(s, Inches(0.6), Inches(0.2), W - Inches(1.2), Inches(0.8), title, 30, WHITE, True,
             anchor=MSO_ANCHOR.MIDDLE)
        text(s, Inches(0.4), H - Inches(0.5), Inches(1), Inches(0.4), str(n), 12, "6B8AA3",
             align=PP_ALIGN.LEFT)
        text(s, W - Inches(6.4), H - Inches(0.5), Inches(6), Inches(0.4), "الأمن والحماية لوحدات رابغ",
             12, "6B8AA3")
        return s

    # 1 cover
    s = prs.slides.add_slide(blank)
    rect(s, 0, 0, W, H, NAVY)
    rect(s, W - Inches(0.35), 0, Inches(0.35), H, GOLD)
    text(s, Inches(0.8), Inches(2.0), W - Inches(1.8), Inches(1.8), TITLE, 44, WHITE, True)
    text(s, Inches(0.8), Inches(3.9), W - Inches(1.8), Inches(0.8), "وحدات رابغ", 32, GOLD)
    text(s, Inches(0.8), Inches(5.3), W - Inches(1.8), Inches(1), ["عرض للاعتماد", "الإصدار 1.0"], 18, "C9D6E3")

    n = 2
    # 2 summary
    s = page("الملخص التنفيذي", n); n += 1
    for i, (big, small) in enumerate((("6", "محاور رئيسية"), ("15", "مبادرة تنفيذية"),
                                      ("36", "شهرًا على 3 مراحل"), ("8", "مؤشرات أداء"))):
        x = W - Inches(0.8) - (i + 1) * Inches(3.0)
        rect(s, x, Inches(1.9), Inches(2.7), Inches(2.2), WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
        text(s, x, Inches(2.0), Inches(2.7), Inches(1.2), big, 54, NAVY, True, PP_ALIGN.CENTER)
        text(s, x, Inches(3.2), Inches(2.7), Inches(0.7), small, 18, INK, False, PP_ALIGN.CENTER)
    text(s, Inches(0.8), Inches(4.6), W - Inches(1.6), Inches(2.2),
         ["رفع مستوى حماية الأفراد والمنشآت والمعلومات.",
          "رفع الجاهزية الفنية والتدريبية لقطاعات الدفاع الجوي.",
          "تحسين الاستجابة للطوارئ وضمان استمرارية العمل."], 22)

    # 3 vision
    s = page("الرؤية والأهداف", n); n += 1
    text(s, Inches(0.8), Inches(1.6), W - Inches(1.6), Inches(1.2),
         "الرؤية: منظومة أمن وحماية ودفاع جوي متكاملة وعالية الجاهزية، بكوادر مؤهلة وتقنيات حديثة وإجراءات موحدة.",
         22, NAVY, True)
    text(s, Inches(0.8), Inches(3.0), W - Inches(1.6), Inches(4),
         ["• تعزيز الحماية المادية وضبط الدخول والخروج", "• رفع مستوى الأمن السيبراني",
          "• بناء ثقافة أمنية لدى جميع المنسوبين", "• رفع جاهزية وكفاءة قطاعات الدفاع الجوي",
          "• تطوير الصيانة والإسناد وتقليل زمن التعطل", "• تحسين الاستجابة للطوارئ",
          "• ترسيخ معايير السلامة المهنية"], 20)

    # 4-5 axes (3 per slide)
    for part in (AXES[:3], AXES[3:]):
        s = page("محاور الخطة", n); n += 1
        for i, (name, items) in enumerate(part):
            x = W - Inches(0.6) - (i + 1) * Inches(4.1)
            rect(s, x, Inches(1.6), Inches(3.9), Inches(5.2), WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
            rect(s, x, Inches(1.6), Inches(3.9), Inches(0.9), NAVY, MSO_SHAPE.ROUNDED_RECTANGLE)
            text(s, x + Inches(0.1), Inches(1.65), Inches(3.7), Inches(0.8), name, 19, WHITE, True,
                 PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
            text(s, x + Inches(0.2), Inches(2.7), Inches(3.5), Inches(4), ["• " + t for t in items], 17)

    # 6 timeline
    s = page("الخطة الزمنية", n); n += 1
    phases = [("المرحلة الأولى: التأسيس", "الشهر 1 – 6", "التقييم، السياسات، المعالجات العاجلة"),
              ("المرحلة الثانية: البناء", "الشهر 7 – 18", "الأنظمة، التدريب، الصيانة والإسناد"),
              ("المرحلة الثالثة: الاستدامة", "الشهر 19 – 36", "التمارين المشتركة، التدقيق، التحسين")]
    rect(s, Inches(0.8), Inches(3.55), W - Inches(1.6), Inches(0.08), GOLD)
    for i, (t, d, a) in enumerate(phases):
        x = W - Inches(0.8) - (i + 1) * Inches(3.95)
        rect(s, x + Inches(1.6), Inches(3.3), Inches(0.55), Inches(0.55), NAVY, MSO_SHAPE.OVAL)
        text(s, x, Inches(1.9), Inches(3.75), Inches(1.2), [t, d], 20, NAVY, True, PP_ALIGN.CENTER)
        text(s, x, Inches(4.2), Inches(3.75), Inches(1.5), a, 18, INK, False, PP_ALIGN.CENTER)

    # 7-8 initiatives
    for chunk in (INITIATIVES[:8], INITIATIVES[8:]):
        s = page("المبادرات التنفيذية", n); n += 1
        rows, cols = len(chunk) + 1, 5
        tbl = s.shapes.add_table(rows, cols, Inches(0.6), Inches(1.5), W - Inches(1.2),
                                 Inches(0.55) * rows).table
        tbl.first_row = True
        head = ["الأولوية", "المدة", "المسؤول", "المبادرة", "#"]
        widths = [1.6, 1.6, 3.0, 5.4, 0.6]
        for j, w in enumerate(widths):
            tbl.columns[j].width = Inches(w)
        data = [[r[6], f"{r[4]} – {r[5]}", r[3], r[1], r[0]] for r in chunk]
        for i, row in enumerate([head] + data):
            for j, v in enumerate(row):
                c = tbl.cell(i, j)
                c.text = v
                p = c.text_frame.paragraphs[0]
                p.alignment = PP_ALIGN.CENTER if j in (0, 1, 4) else PP_ALIGN.RIGHT
                p._p.get_or_add_pPr().set("rtl", "1")
                f = p.runs[0].font
                f.size = Pt(15)
                f.bold = i == 0
                f.color.rgb = rgb(WHITE if i == 0 else INK)
                c.fill.solid()
                c.fill.fore_color.rgb = rgb(NAVY if i == 0 else (ICE if i % 2 else WHITE))
                if i and j == 0:
                    c.fill.fore_color.rgb = rgb({"عاجلة": "F5B7B1", "عالية": "FAD7A0"}.get(v, "D5F5E3"))

    # 9 KPIs
    s = page("مؤشرات قياس الأداء", n); n += 1
    for i, (k, t, f) in enumerate(KPIS):
        col, row = i % 2, i // 2
        x = W - Inches(0.7) - (col + 1) * Inches(6.0)
        y = Inches(1.55) + row * Inches(1.35)
        rect(s, x, y, Inches(5.8), Inches(1.15), WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
        rect(s, x + Inches(5.65), y, Inches(0.15), Inches(1.15), GOLD)
        text(s, x + Inches(1.9), y + Inches(0.1), Inches(3.6), Inches(1), [k, f], 16, INK)
        text(s, x + Inches(0.1), y + Inches(0.2), Inches(1.9), Inches(0.8), t, 20, NAVY, True,
             PP_ALIGN.CENTER)

    # 10 governance
    s = page("الحوكمة والمتابعة", n); n += 1
    text(s, Inches(0.8), Inches(1.6), W - Inches(1.6), Inches(5),
         ["• لجنة إشرافية برئاسة القيادة — اجتماع ربع سنوي",
          "• فريق تنفيذي من ممثلي المحاور — اجتماع شهري",
          "• تقرير شهري مختصر وتقرير ربع سنوي بالمؤشرات",
          "• تدقيق داخلي سنوي وتحديث الخطة",
          "• مصفوفة RACI لكل مبادرة ومصفوفة مخاطر 5×5"], 24)

    # 11 decisions
    s = page("المطلوب من القيادة", n); n += 1
    text(s, Inches(0.8), Inches(1.6), W - Inches(1.6), Inches(5),
         ["1. اعتماد الخطة ومحاورها الستة", "2. اعتماد فريق العمل والصلاحيات",
          "3. اعتماد الميزانية التقديرية للمرحلة الأولى", "4. البدء بالتقييم الشامل خلال الشهر الأول"],
         26, NAVY, True)

    # 12 thanks
    s = prs.slides.add_slide(blank)
    rect(s, 0, 0, W, H, NAVY)
    rect(s, W - Inches(0.35), 0, Inches(0.35), H, GOLD)
    text(s, Inches(0.8), Inches(2.8), W - Inches(1.8), Inches(1.5), ["شكرًا لكم", "الأسئلة والنقاش"], 44,
         WHITE, True, PP_ALIGN.CENTER)

    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))
    return path


# ------------------------------------------------------------------ Excel
def build_xlsx(path: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    head_font = Font(name="Arial", bold=True, color=WHITE, size=12)
    head_fill = PatternFill("solid", fgColor=NAVY)
    body_font = Font(name="Arial", size=11)
    thin = Side(style="thin", color="B8C4D0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(horizontal="right", vertical="center", wrap_text=True, readingOrder=2)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True, readingOrder=2)

    def sheet(ws, title, headers, widths):
        ws.sheet_view.rightToLeft = True
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        ws.cell(1, 1, title).font = Font(name="Arial", bold=True, size=16, color=NAVY)
        ws.cell(1, 1).alignment = Alignment(horizontal="right", readingOrder=2)
        ws.row_dimensions[1].height = 30
        for j, (h, w) in enumerate(zip(headers, widths), 1):
            c = ws.cell(3, j, h)
            c.font, c.fill, c.alignment, c.border = head_font, head_fill, center, border
            ws.column_dimensions[c.column_letter].width = w
        ws.freeze_panes = "A4"

    def body(ws, r, c, v, centered=False, fmt=None):
        cell = ws.cell(r, c, v)
        cell.font, cell.border = body_font, border
        cell.alignment = center if centered else wrap
        if fmt:
            cell.number_format = fmt
        return cell

    wb = Workbook()

    # --- initiatives tracker
    ws = wb.active
    ws.title = "المبادرات"
    sheet(ws, "متابعة تنفيذ المبادرات — وحدات رابغ",
          ["#", "المبادرة", "المحور", "المسؤول", "من (شهر)", "إلى (شهر)", "الأولوية",
           "نسبة الإنجاز", "الحالة", "آخر تحديث", "ملاحظات"],
          [5, 42, 18, 22, 10, 10, 11, 13, 14, 13, 30])
    status = DataValidation(type="list", formula1='"لم تبدأ,جارية,متأخرة,مكتملة,متوقفة"', allow_blank=True)
    prio = DataValidation(type="list", formula1='"عاجلة,عالية,متوسطة,منخفضة"', allow_blank=True)
    pct = DataValidation(type="decimal", operator="between", formula1="0", formula2="1")
    for dv in (status, prio, pct):
        ws.add_data_validation(dv)
    for i, r in enumerate(INITIATIVES):
        row = 4 + i
        for j, v in enumerate(r[:4], 1):
            body(ws, row, j, int(v) if j == 1 else v, j == 1)
        for j, v in ((5, r[4]), (6, r[5])):
            num = v.replace("ش", "")
            body(ws, row, j, int(num) if num.isdigit() else v, True)
        body(ws, row, 7, r[6], True)
        body(ws, row, 8, 0, True, "0%")
        body(ws, row, 9, "لم تبدأ", True)
        body(ws, row, 10, None, True, "yyyy-mm-dd")
        body(ws, row, 11, None)
        prio.add(f"G{row}")
        pct.add(f"H{row}")
        status.add(f"I{row}")
        ws.row_dimensions[row].height = 32
    last = 3 + len(INITIATIVES)
    rng = f"I4:I{last}"
    for val, color in (("مكتملة", "C6EFCE"), ("جارية", "DDEBF7"), ("متأخرة", "FFC7CE"),
                       ("متوقفة", "D9D9D9"), ("لم تبدأ", "FFF2CC")):
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[f'"{val}"'],
                                                      fill=PatternFill("solid", fgColor=color)))
    ws.conditional_formatting.add(f"H4:H{last}", ColorScaleRule(start_type="num", start_value=0,
                                                                start_color="F8696B", mid_type="num",
                                                                mid_value=0.5, mid_color="FFEB84",
                                                                end_type="num", end_value=1,
                                                                end_color="63BE7B"))
    for val, color in (("عاجلة", "F5B7B1"), ("عالية", "FAD7A0")):
        ws.conditional_formatting.add(f"G4:G{last}", CellIsRule(operator="equal", formula=[f'"{val}"'],
                                                                fill=PatternFill("solid", fgColor=color)))

    # --- KPIs
    kp = wb.create_sheet("المؤشرات")
    months = ["ش1", "ش2", "ش3", "ش4", "ش5", "ش6", "ش7", "ش8", "ش9", "ش10", "ش11", "ش12"]
    sheet(kp, "مؤشرات قياس الأداء — السنة الأولى", ["المؤشر", "الدورية", "خط الأساس", "المستهدف"] + months,
          [36, 11, 12, 14] + [8] * 12)
    for i, (k, t, f) in enumerate(KPIS):
        row = 4 + i
        body(kp, row, 1, k)
        body(kp, row, 2, f, True)
        body(kp, row, 3, None, True)
        body(kp, row, 4, t, True)
        for j in range(len(months)):
            body(kp, row, 5 + j, None, True)
        kp.row_dimensions[row].height = 28

    # --- risk register
    rk = wb.create_sheet("سجل المخاطر")
    sheet(rk, "سجل المخاطر (الدرجة = الاحتمال × الأثر)",
          ["#", "وصف الخطر", "الاحتمال (1-5)", "الأثر (1-5)", "الدرجة", "المستوى", "المالك", "المعالجة", "الحالة"],
          [5, 38, 13, 12, 10, 12, 20, 38, 12])
    risks = [("نقص الميزانية أو تأخر الاعتماد", 3, 4, "ترتيب الأولويات وتنفيذ مرحلي"),
             ("نقص الكوادر المتخصصة", 3, 4, "خطط تأهيل وإحلال ونقل خبرة"),
             ("تأخر توريد الأنظمة وقطع الغيار", 3, 3, "تخطيط مبكر ومخزون احتياطي ومصادر بديلة"),
             ("مقاومة التغيير", 2, 3, "التوعية وإشراك القيادات"),
             ("تهديدات سيبرانية متطورة", 3, 5, "مراقبة مستمرة وتحديث الضوابط والتمارين")]
    one5 = DataValidation(type="whole", operator="between", formula1="1", formula2="5")
    rk.add_data_validation(one5)
    for i in range(15):
        row = 4 + i
        d = risks[i] if i < len(risks) else ("", None, None, "")
        body(rk, row, 1, i + 1, True)
        body(rk, row, 2, d[0] or None)
        body(rk, row, 3, d[1], True)
        body(rk, row, 4, d[2], True)
        body(rk, row, 5, f'=IF(AND(C{row}<>"",D{row}<>""),C{row}*D{row},"")', True)
        body(rk, row, 6, f'=IF(E{row}="","",IF(E{row}>=15,"حرج",IF(E{row}>=10,"عالٍ",IF(E{row}>=5,"متوسط","منخفض"))))', True)
        body(rk, row, 7, None)
        body(rk, row, 8, d[3] or None)
        body(rk, row, 9, "مفتوح" if d[0] else None, True)
        one5.add(f"C{row}")
        one5.add(f"D{row}")
        rk.row_dimensions[row].height = 28
    for val, color in (("حرج", "C0392B"), ("عالٍ", "E67E22"), ("متوسط", "F4D03F"), ("منخفض", "58D68D")):
        rk.conditional_formatting.add("F4:F18", CellIsRule(operator="equal", formula=[f'"{val}"'],
                                                           fill=PatternFill("solid", fgColor=color)))

    # --- dashboard
    db = wb.create_sheet("لوحة المتابعة", 0)
    db.sheet_view.rightToLeft = True
    db.column_dimensions["A"].width = 34
    db.column_dimensions["B"].width = 16
    db.merge_cells("A1:B1")
    db["A1"] = "لوحة متابعة خطة الأمن والحماية — وحدات رابغ"
    db["A1"].font = Font(name="Arial", bold=True, size=16, color=NAVY)
    db["A1"].alignment = Alignment(horizontal="right", readingOrder=2)
    rng_s = f"'المبادرات'!I4:I{last}"
    rows = [("إجمالي المبادرات", f"=COUNTA('المبادرات'!B4:B{last})", None),
            ("متوسط نسبة الإنجاز", f"=AVERAGE('المبادرات'!H4:H{last})", "0%"),
            ("مكتملة", f'=COUNTIF({rng_s},"مكتملة")', None),
            ("جارية", f'=COUNTIF({rng_s},"جارية")', None),
            ("متأخرة", f'=COUNTIF({rng_s},"متأخرة")', None),
            ("لم تبدأ", f'=COUNTIF({rng_s},"لم تبدأ")', None),
            ("متوقفة", f'=COUNTIF({rng_s},"متوقفة")', None),
            ("مخاطر حرجة", "=COUNTIF('سجل المخاطر'!F4:F18,\"حرج\")", None),
            ("مخاطر عالية", "=COUNTIF('سجل المخاطر'!F4:F18,\"عالٍ\")", None)]
    for c, h in ((1, "البند"), (2, "القيمة")):
        cell = db.cell(3, c, h)
        cell.font, cell.fill, cell.alignment, cell.border = head_font, head_fill, center, border
    for i, (k, f, fmt) in enumerate(rows):
        body(db, 4 + i, 1, k)
        cell = body(db, 4 + i, 2, f, True, fmt)
        cell.font = Font(name="Arial", size=13, bold=True, color=NAVY)
        db.row_dimensions[4 + i].height = 26
    note = db.cell(15, 1, "حدّث عمودي «نسبة الإنجاز» و«الحالة» في ورقة المبادرات، وتتحدث هذه اللوحة تلقائيًا.")
    note.font = Font(name="Arial", italic=True, color="6B8AA3")
    note.alignment = Alignment(horizontal="right", readingOrder=2)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    print(build_pptx(out / "عرض خطة الأمن والدفاع الجوي - وحدات رابغ.pptx"))
    print(build_xlsx(out / "متابعة تنفيذ الخطة - وحدات رابغ.xlsx"))
