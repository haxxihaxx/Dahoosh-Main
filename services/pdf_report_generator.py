import os
from typing import Dict
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from io import BytesIO
import arabic_reshaper
from bidi.algorithm import get_display
from datetime import datetime


class PDFReportGenerator:
    def __init__(self):
        self.setup_fonts()

    def setup_fonts(self):
        fonts_dir = os.path.join(os.path.dirname(__file__), '..', 'fonts')
        os.makedirs(fonts_dir, exist_ok=True)
        self.has_persian_font = False
        font_path = os.path.join(fonts_dir, 'NotoSansArabic-Regular.ttf')

        if not os.path.exists(font_path):
            self._download_font(font_path)

        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('Persian', font_path))
                self.has_persian_font = True
            except Exception:
                self.has_persian_font = False

    def _download_font(self, font_path: str):
        import urllib.request
        # Multiple fallback URLs — the Google Fonts GitHub repo restructured
        urls = [
            "https://github.com/notofonts/arabic/releases/download/NotoSansArabic-v2.013/NotoSansArabic-Regular.ttf",
            "https://raw.githubusercontent.com/notofonts/arabic/main/fonts/NotoSansArabic/unhinted/ttf/NotoSansArabic-Regular.ttf",
            "https://raw.githubusercontent.com/hotosm/HDM-CartoCSS/master/fonts/NotoSansArabic-Regular.ttf",
        ]
        for url in urls:
            try:
                print(f"Downloading Persian font from {url} ...")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                # Sanity check: a real TTF starts with bytes 0x00 0x01 0x00 0x00
                # or 'OTTO' for OTF; reject tiny/corrupt files
                if len(data) < 50_000:
                    print(f"  File too small ({len(data)} bytes), skipping.")
                    continue
                with open(font_path, 'wb') as f:
                    f.write(data)
                print("Persian font downloaded successfully.")
                return
            except Exception as e:
                print(f"  Failed ({e}), trying next URL...")

        print(
            "\n⚠️  Could not auto-download Persian font.\n"
            "Manual fix (run once in your terminal):\n"
            "  pip install requests\n"
            "  python - <<'EOF'\n"
            "import requests, os\n"
            "url = 'https://github.com/notofonts/arabic/releases/download/"
            "NotoSansArabic-v2.013/NotoSansArabic-Regular.ttf'\n"
            "os.makedirs('fonts', exist_ok=True)\n"
            "open('fonts/NotoSansArabic-Regular.ttf','wb').write(requests.get(url).content)\n"
            "EOF\n"
        )

    def _p(self, text: str) -> str:
        if not text:
            return ""
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception:
            return str(text)

    def _esc(self, text: str) -> str:
        if not text:
            return ""
        text = str(text)
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return text

    def _is_persian(self, text: str) -> bool:
        if not text:
            return False
        persian_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F')
        total = sum(1 for c in text if c.strip())
        return total > 0 and (persian_chars / total) > 0.3

    def _render(self, text: str) -> str:
        if not text:
            return ""
        if self._is_persian(str(text)):
            return self._p(str(text))
        return self._esc(str(text))

    def _styles(self):
        base = getSampleStyleSheet()
        fn      = 'Persian' if self.has_persian_font else 'Helvetica'
        fn_bold = 'Persian' if self.has_persian_font else 'Helvetica-Bold'

        styles = {
            'title':     ParagraphStyle('FaTitle',    parent=base['Title'],  fontName=fn_bold, fontSize=20,
                                         alignment=TA_CENTER, textColor=colors.HexColor('#1a1a2e'), spaceAfter=4),
            'subtitle':  ParagraphStyle('FaSub',      parent=base['Normal'], fontName=fn,      fontSize=11,
                                         alignment=TA_CENTER, textColor=colors.HexColor('#555577'), spaceAfter=2),
            'section':   ParagraphStyle('FaSection',  parent=base['Normal'], fontName=fn_bold, fontSize=13,
                                         alignment=TA_RIGHT, textColor=colors.HexColor('#2d2d6b'),
                                         spaceBefore=14, spaceAfter=6),
            'body':      ParagraphStyle('FaBody',     parent=base['Normal'], fontName=fn,      fontSize=10,
                                         alignment=TA_RIGHT, textColor=colors.HexColor('#333344'), leading=16, spaceAfter=4),
            'label':     ParagraphStyle('FaLabel',    parent=base['Normal'], fontName=fn_bold, fontSize=9,
                                         alignment=TA_RIGHT, textColor=colors.HexColor('#666688')),
            'small':     ParagraphStyle('FaSmall',    parent=base['Normal'], fontName=fn,      fontSize=8,
                                         alignment=TA_RIGHT, textColor=colors.HexColor('#888899')),
            'score_big': ParagraphStyle('FaScore',    parent=base['Normal'], fontName=fn_bold, fontSize=36,
                                         alignment=TA_CENTER, textColor=colors.HexColor('#2d2d6b')),
            'score_sub': ParagraphStyle('FaScoreSub', parent=base['Normal'], fontName=fn,      fontSize=12,
                                         alignment=TA_CENTER, textColor=colors.HexColor('#888899')),
            'grade_l':   ParagraphStyle('FaGrade',    parent=base['Normal'], fontName=fn_bold, fontSize=28,
                                         alignment=TA_CENTER, textColor=colors.HexColor('#c9a84c')),
            'bullet':    ParagraphStyle('FaBullet',   parent=base['Normal'], fontName=fn,      fontSize=10,
                                         alignment=TA_RIGHT, textColor=colors.HexColor('#444455'), leading=15, leftIndent=10),
        }
        return styles

    def _header_table(self, data: Dict, st: dict):
        score_20   = data.get('score_20', data.get('total_score', 0))
        max_score  = data.get('max_score', 20.0)
        percentage = data.get('percentage', 0)
        grade      = data.get('grade_letter', 'N/A')
        student_id = data.get('student_id', 'N/A')
        test_id    = data.get('test_id', 'N/A')
        timestamp  = data.get('timestamp', '')
        try:
            dt = datetime.fromisoformat(timestamp)
            date_str = dt.strftime('%Y/%m/%d')
        except Exception:
            date_str = timestamp[:10] if timestamp else 'N/A'

        color_score = colors.HexColor('#4ade80') if percentage >= 85 \
            else colors.HexColor('#C9A84C') if percentage >= 60 \
            else colors.HexColor('#f87171')

        score_cell = [
            Paragraph(self._p('نمره'), st['label']),
            Spacer(1, 4),
            Paragraph(f"{score_20:.1f}", st['score_big']),
            Paragraph(self._p(f"از {max_score:.0f}"), st['score_sub']),
            Spacer(1, 8),
            Paragraph(grade, st['grade_l']),
        ]

        rows = [
            [self._p('شناسه آزمون'),      self._render(test_id)],
            [self._p('شناسه دانش‌آموز'), self._render(student_id)],
            [self._p('تاريخ'),            self._render(date_str)],
            [self._p('درصد'),             f"{percentage:.1f}%"],
        ]
        fn      = 'Persian' if self.has_persian_font else 'Helvetica'
        fn_bold = 'Persian' if self.has_persian_font else 'Helvetica-Bold'

        info_table = Table(rows, colWidths=[3.5*cm, 6*cm])
        info_table.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (-1, -1), fn),
            ('FONTNAME',      (0, 0), (0, -1),  fn_bold),
            ('FONTSIZE',      (0, 0), (-1, -1),  9),
            ('ALIGN',         (0, 0), (-1, -1),  'RIGHT'),
            ('VALIGN',        (0, 0), (-1, -1),  'MIDDLE'),
            ('TEXTCOLOR',     (0, 0), (0, -1),   colors.HexColor('#888899')),
            ('TEXTCOLOR',     (1, 0), (1, -1),   colors.HexColor('#222233')),
            ('ROWBACKGROUNDS',(0, 0), (-1, -1),  [colors.HexColor('#f7f7fc'), colors.white]),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  7),
            ('TOPPADDING',    (0, 0), (-1, -1),  7),
            ('LEFTPADDING',   (0, 0), (-1, -1),  8),
            ('RIGHTPADDING',  (0, 0), (-1, -1),  8),
        ]))

        outer = Table([[score_cell, info_table]], colWidths=[4.5*cm, 10*cm])
        outer.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',         (0, 0), (0, 0),   'CENTER'),
            ('BACKGROUND',    (0, 0), (0, 0),   colors.HexColor('#f0f0fa')),
            ('BOTTOMPADDING', (0, 0), (0, 0),   14),
            ('TOPPADDING',    (0, 0), (0, 0),   14),
            ('LEFTPADDING',   (0, 0), (0, 0),   10),
            ('RIGHTPADDING',  (0, 0), (0, 0),   10),
            ('BOX',           (0, 0), (0, 0),   2,   color_score),
            ('BOX',           (0, 0), (-1, -1), 0.5, colors.HexColor('#ccccdd')),
        ]))
        return outer

    def _question_block(self, i: int, q: Dict, st: dict) -> list:
        fn      = 'Persian' if self.has_persian_font else 'Helvetica'
        fn_bold = 'Persian' if self.has_persian_font else 'Helvetica-Bold'

        num      = q.get('question_number', i)
        awarded  = q.get('points_awarded', 0)
        max_pts  = q.get('max_points', 0)
        correct  = q.get('is_correct', False)
        status_color = colors.HexColor('#4ade80') if correct else colors.HexColor('#f87171')
        status_text  = self._p('صحيح ✓') if correct else self._p('ناقص / نادرست ✗')

        header_rows = [[self._p(f'سوال {num}'), f"{awarded:.1f} / {max_pts:.1f}", status_text]]
        header_tbl = Table(header_rows, colWidths=[5*cm, 4*cm, 5.5*cm])
        header_tbl.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (-1, -1), fn_bold),
            ('FONTSIZE',      (0, 0), (-1, -1), 10),
            ('ALIGN',         (0, 0), (0, 0),   'RIGHT'),
            ('ALIGN',         (1, 0), (1, 0),   'CENTER'),
            ('ALIGN',         (2, 0), (2, 0),   'LEFT'),
            ('TEXTCOLOR',     (0, 0), (0, 0),   colors.HexColor('#2d2d6b')),
            ('TEXTCOLOR',     (2, 0), (2, 0),   status_color),
            ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#eeeef8')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ]))

        detail_rows = [
            [self._p('سوال'),            Paragraph(self._render(q.get('question_text', '')),  st['body'])],
            [self._p('پاسخ صحيح'),       Paragraph(self._render(q.get('correct_answer', '')), st['body'])],
            [self._p('پاسخ دانش‌آموز'), Paragraph(self._render(q.get('student_answer', '')), st['body'])],
        ]
        detail_tbl = Table(detail_rows, colWidths=[3.5*cm, 11*cm])
        detail_tbl.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (0, -1),  fn_bold),
            ('FONTNAME',      (1, 0), (1, -1),  fn),
            ('FONTSIZE',      (0, 0), (-1, -1),  9),
            ('ALIGN',         (0, 0), (-1, -1),  'RIGHT'),
            ('VALIGN',        (0, 0), (-1, -1),  'TOP'),
            ('TEXTCOLOR',     (0, 0), (0, -1),   colors.HexColor('#666688')),
            ('ROWBACKGROUNDS',(0, 0), (-1, -1),  [colors.HexColor('#fafafa'), colors.white]),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  7),
            ('TOPPADDING',    (0, 0), (-1, -1),  7),
            ('LEFTPADDING',   (0, 0), (-1, -1),  8),
            ('RIGHTPADDING',  (0, 0), (-1, -1),  8),
            ('GRID',          (0, 0), (-1, -1),  0.3, colors.HexColor('#ddddee')),
        ]))

        items = [header_tbl, detail_tbl]

        feedback = q.get('feedback_persian') or q.get('feedback', '')
        if feedback:
            items.append(Spacer(1, 3))
            items.append(Paragraph(
                f"<b>{self._p('بازخورد: ')}</b>{self._render(feedback)}", st['body']
            ))

        strengths = q.get('strengths', [])
        if strengths:
            items.append(Paragraph(self._p('نقاط قوت:'), st['label']))
            for s_item in strengths:
                items.append(Paragraph(f"• {self._render(s_item)}", st['bullet']))

        improvements = q.get('improvements', [])
        if improvements:
            items.append(Paragraph(self._p('نقاط قابل بهبود:'), st['label']))
            for imp in improvements:
                items.append(Paragraph(f"• {self._render(imp)}", st['bullet']))

        items.append(Spacer(1, 6))
        items.append(HRFlowable(width='100%', thickness=0.5,
                                color=colors.HexColor('#ccccdd'), spaceAfter=4))
        return [KeepTogether(items)]

    def generatePDF(self, reportData: Dict) -> bytes:
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
            title='گزارش تصحيح داهوش',
            author='داهوش'
        )
        st    = self._styles()
        story = []

        story.append(Paragraph(self._p('گزارش تصحيح آزمون'), st['title']))
        story.append(Paragraph(self._p('سامانه هوشمند داهوش'), st['subtitle']))
        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(width='100%', thickness=1.5,
                                color=colors.HexColor('#2d2d6b'), spaceAfter=8))

        story.append(self._header_table(reportData, st))
        story.append(Spacer(1, 0.6*cm))

        questions = reportData.get('questions', [])
        if questions:
            story.append(Paragraph(self._p('جزئيات سوالات'), st['section']))
            story.append(Spacer(1, 0.2*cm))
            for i, q in enumerate(questions, 1):
                story.extend(self._question_block(i, q, st))

        overall = reportData.get('overall_feedback_persian') or reportData.get('overall_feedback', '')
        if overall:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph(self._p('بازخورد كلي'), st['section']))
            story.append(Paragraph(self._render(overall), st['body']))

        story.append(Spacer(1, 1*cm))
        story.append(HRFlowable(width='100%', thickness=0.5,
                                color=colors.HexColor('#ccccdd'), spaceAfter=4))
        story.append(Paragraph(
            self._p('اين گزارش توسط سامانه داهوش به‌صورت خودكار توليد شده است.'),
            st['small']
        ))

        doc.build(story)
        pdf = buf.getvalue()
        buf.close()
        return pdf

    def addScoreSection(self, score: float, totalScore: float) -> None:
        pass

    def downloadPDF(self, pdfBytes: bytes, filename: str) -> bool:
        try:
            with open(filename, 'wb') as f:
                f.write(pdfBytes)
            return True
        except Exception as e:
            print(f"Failed to save PDF: {e}")
            return False