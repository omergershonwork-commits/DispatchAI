import sys
import subprocess
try:
    from docx import Document
    from docx.shared import Pt
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
    from docx import Document
    from docx.shared import Pt

import re
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# Helpers from hebrew-document-generator skill
_HEB = re.compile(r'[\u0590-\u05FF\uFB1D-\uFB4F]')
_LIST_MARKER = re.compile(r'^\d{1,2}\.$')

def _strong(ch):
    if _HEB.match(ch): return True
    if ch.isascii() and ch.isalnum(): return False
    return None

def _split_by_script(text):
    default_rtl = next((s for s in (_strong(c) for c in text) if s is not None), True)
    segments, buf, buf_rtl = [], '', None
    for ch in text:
        s = _strong(ch)
        kind = s if s is not None else (buf_rtl if buf_rtl is not None else default_rtl)
        if buf_rtl is None or kind == buf_rtl:
            buf, buf_rtl = buf + ch, kind
        else:
            segments.append((buf, buf_rtl))
            buf, buf_rtl = ch, kind
    if buf: segments.append((buf, buf_rtl))
    return segments

def _shift_boundary_spaces(segments):
    out = [[seg, rtl] for seg, rtl in segments]
    for i in range(len(out) - 1):
        seg, rtl = out[i]
        nseg, nrtl = out[i + 1]
        if rtl is False and nrtl is True and seg.endswith(' '):
            stripped = seg.rstrip(' ')
            out[i][0] = stripped
            out[i + 1][0] = seg[len(stripped):] + nseg
    return [(s, r) for s, r in out if s]

def _merge_list_marker(segments):
    if (len(segments) >= 2 and segments[0][1] is False
            and _LIST_MARKER.match(segments[0][0].strip())
            and segments[1][1] is True):
        return [(segments[0][0] + segments[1][0], True)] + list(segments[2:])
    return list(segments)

def _para_is_rtl(text):
    if _HEB.search(text): return True
    if any(ch.isascii() and ch.isalnum() for ch in text): return False
    return True

def add_rtl_paragraph(doc, text, font='David', size=12, bold=False, italic=False, heading_level=None):
    p = doc.add_heading(level=heading_level) if heading_level else doc.add_paragraph()
    base_rtl = _para_is_rtl(text)
    pPr = p._p.get_or_add_pPr()
    if base_rtl:
        pPr.append(pPr.makeelement(qn('w:bidi'), {}))
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if base_rtl else WD_ALIGN_PARAGRAPH.LEFT
    para_has_latin = any(ch.isascii() and ch.isalpha() for ch in text)
    for segment, is_rtl in _shift_boundary_spaces(_merge_list_marker(_split_by_script(text))):
        run = p.add_run(segment)
        rPr = run._r.get_or_add_rPr()
        rPr.append(rPr.makeelement(qn('w:rFonts'), {
            qn('w:ascii'): font, qn('w:hAnsi'): font, qn('w:cs'): font}))
        if bold:
            rPr.append(rPr.makeelement(qn('w:b'), {}))
            rPr.append(rPr.makeelement(qn('w:bCs'), {}))
        if italic:
            rPr.append(rPr.makeelement(qn('w:i'), {}))
            rPr.append(rPr.makeelement(qn('w:iCs'), {}))
        rPr.append(rPr.makeelement(qn('w:sz'),   {qn('w:val'): str(size * 2)}))
        rPr.append(rPr.makeelement(qn('w:szCs'), {qn('w:val'): str(size * 2)}))
        if is_rtl and not para_has_latin:
            rPr.append(rPr.makeelement(qn('w:rtl'), {}))
    return p

doc = Document()
doc.styles['Normal'].font.name = 'David'
doc.styles['Normal'].font.size = Pt(12)

# Content Generation
add_rtl_paragraph(doc, 'מדריך מקיף: מסלול LLM במערכת AI-Rescue Connect', size=22, bold=True, heading_level=1)
add_rtl_paragraph(doc, 'מסמך זה נועד להעניק לך הבנה עמוקה, שלב אחר שלב, של מה אנחנו בונים במסלול ה-LLM, למה אנחנו בונים את זה ככה, ואיך הכל מתחבר.', size=12)

add_rtl_paragraph(doc, 'מבוא: מה אנחנו מנסים להשיג?', size=16, bold=True, heading_level=2)
add_rtl_paragraph(doc, 'בעולם ה-AI המודרני, מודלי שפה (LLMs) הם לא רק צ\'אטבוטים שאפשר לדבר איתם. הם "מנועי חשיבה" שאפשר לשלב בתוך קוד. המטרה שלנו היא לקחת את מודל ה-Qwen, שיש לו ידע כללי רחב, ולהפוך אותו ל"מוקדן אוטומטי". המוקדן הזה ידע לקרוא הודעות וואטסאפ היסטריות, לחלץ מהן מידע קריטי (מיקום וחומרה), להחליט איזה מתנדב לשלוח, ולנסח הודעת הרגעה למדווח.', size=12)

add_rtl_paragraph(doc, 'שלב 1: חיבור למודל המקומי (vLLM ו-OpenAI SDK)', size=16, bold=True, heading_level=2)
add_rtl_paragraph(doc, 'התיאוריה:', size=12, bold=True)
add_rtl_paragraph(doc, 'כדי שפייתון ידבר עם המודל, המודל צריך להיות זמין כ"שרת". המערכת שנקראת vLLM (שמגיעה מותקנת בשרתי AMD שלנו) לוקחת את המודל Qwen והופכת אותו לשרת אינטרנט מקומי. הגאונות של vLLM היא שהיא מעמידה פנים שהיא השרתים של חברת OpenAI (החברה של ChatGPT). זה אומר שאנחנו יכולים להשתמש בספריית הפייתון הרשמית של openai, שכולם מכירים ויש לה אלפי מדריכים, אבל פשוט לכוון אותה לכתובת המקומית שלנו.', size=12)
add_rtl_paragraph(doc, 'מה צריך לעשות:', size=12, bold=True)
add_rtl_paragraph(doc, '1. מריצים את שרת ה-vLLM בטרמינל.', size=12)
add_rtl_paragraph(doc, '2. כותבים סקריפט פייתון שמשתמש ב-openai.AsyncOpenAI, אבל מגדירים את ה-base_url להיות http://localhost:8000/v1.', size=12)

add_rtl_paragraph(doc, 'שלב 2: Prompt Engineering וחילוץ מידע מובנה (JSON)', size=16, bold=True, heading_level=2)
add_rtl_paragraph(doc, 'התיאוריה:', size=12, bold=True)
add_rtl_paragraph(doc, 'כשאתה מדבר עם מודל שפה, הוא מחזיר טקסט חופשי ("בטח, הנה התשובה..."). אבל קוד לא יודע לקרוא טקסט חופשי, קוד צריך אובייקטים (כמו מילונים - Dictionaries בפייתון). כדי לפתור את זה, אנחנו חייבים להשתמש בטכניקה של חילוץ מידע מובנה. אנחנו כותבים System Prompt (הוראות מערכת מוסתרות שניתנות למודל לפני שאלת המשתמש) שאומר למודל: "אתה מכונה לחילוץ נתונים. אתה לעולם לא מסביר. אתה מחזיר רק JSON".', size=12)
add_rtl_paragraph(doc, 'מה צריך לעשות:', size=12, bold=True)
add_rtl_paragraph(doc, 'נכתוב הוראה מדויקת שמכריחה את המודל להוציא פורמט כזה: {"location": "דיזנגוף 50", "severity": "High"}. נלמד להשתמש בפרמטר response_format={"type": "json_object"} (אם vLLM תומך בו בגרסה שלנו) או שפשוט נהיה מאוד אגרסיביים בפרומפט שלנו.', size=12)

add_rtl_paragraph(doc, 'שלב 3: תכנות אסינכרוני (Async) ושליטה בעומסים (Semaphore)', size=16, bold=True, heading_level=2)
add_rtl_paragraph(doc, 'התיאוריה:', size=12, bold=True)
add_rtl_paragraph(doc, 'בשרת אינטרנט שמקבל הודעות וואטסאפ (FastAPI), עשרות בקשות יכולות להגיע באותה השנייה. אם נעביר את כל הבקשות האלה בבת אחת לכרטיס המסך (GPU), הזיכרון שלו (VRAM) יתמלא מיד והוא יקרוס (שגיאת OOM - Out of Memory). הפתרון הוא תכנות אסינכרוני עם Semaphore. סמפור הוא כמו שומר סף במועדון - קובעים לו מקסימום של אנשים (למשל 1). כשהבקשה הראשונה נכנסת למודל, השומר חוסם את כל השאר. הבקשות לא נכשלות, הן פשוט ממתינות באלגנטיות בתור (למשך שניה או שתיים) עד שהראשונה תצא.', size=12)
add_rtl_paragraph(doc, 'מה צריך לעשות:', size=12, bold=True)
add_rtl_paragraph(doc, 'ליצור אובייקט asyncio.Semaphore(1) בפייתון, ולעטוף בעזרתו את הפונקציה שקוראת ל-vLLM בעזרת המילה השמורה async with.', size=12)

add_rtl_paragraph(doc, 'שלב 4: שרשור פרומפטים (Prompt Chaining)', size=16, bold=True, heading_level=2)
add_rtl_paragraph(doc, 'התיאוריה:', size=12, bold=True)
add_rtl_paragraph(doc, 'אי אפשר לבקש ממודל להחליט החלטה מורכבת במכה אחת ("הנה ההודעה, והנה כל המתנדבים במדינה, תבחר אחד ותענה"). זה גורם להזיות (Hallucinations) ובלבול. שרשור פרומפטים הוא פירוק הבעיה לצעדים פשוטים. צעד א: חלץ מיקום. עכשיו פייתון לוקח את המיקום, מחפש במסד הנתונים את 3 המתנדבים הקרובים, ומכניס את המידע לצעד ב. צעד ב: מי מתוך ה-3 האלה הכי מתאים? פייתון מקבל את התשובה (מזהה מתנדב), ושולח לצעד ג. צעד ג: נסח הודעת תשובה לאזרח.', size=12)
add_rtl_paragraph(doc, 'מה צריך לעשות:', size=12, bold=True)
add_rtl_paragraph(doc, 'לבנות פונקציית פייתון מרכזית שמריצה את 3 הצעדים האלה אחד אחרי השני, מעבירה את התשובה מהמודל חזרה לקוד, ומהקוד חזרה למודל לשאלה הבאה.', size=12)

add_rtl_paragraph(doc, 'שלב 5: חיבור הכל ל-FastAPI ו-Background Tasks', size=16, bold=True, heading_level=2)
add_rtl_paragraph(doc, 'התיאוריה:', size=12, bold=True)
add_rtl_paragraph(doc, 'כשמישהו שולח הודעה לוואטסאפ, חברת מטא (Meta) מצפה שהשרת שלנו יגיד "קיבלתי" (200 OK) באופן מיידי (תוך שניות בודדות), אחרת היא תחשוב שהשרת שלנו נפל ותנסה לשלוח שוב ושוב. מכיוון שהשרשור שלנו (שלב 4) יכול לקחת כמה שניות טובות, אנחנו לא יכולים לעכב את התשובה למטא. הפתרון של FastAPI הוא מנגנון BackgroundTasks.', size=12)
add_rtl_paragraph(doc, 'מה צריך לעשות:', size=12, bold=True)
add_rtl_paragraph(doc, 'נגדיר את הראוט (Route) שלנו כך שיקבל את ההודעה, יגיד מיד 200 OK ל-Meta, ו"יזרוק" את פונקציית השרשור שיצרנו לרוץ ברקע. כשהפונקציה תסיים ברקע, היא תשלח את ההודעה למתנדב באופן עצמאי.', size=12)

add_rtl_paragraph(doc, 'סיכום:', size=16, bold=True, heading_level=2)
add_rtl_paragraph(doc, 'כדי לעשות את זה מושלם, נתחיל מלכתוב במחברת ה-Jupyter רק את החיבור הבסיסי ל-vLLM בעזרת ספריית OpenAI. נתקדם צעד אחר צעד, נוודא שהמודל מחזיר JSON תקין, נוסיף את ה-Semaphore, ורק בסוף נעטוף הכל ב-FastAPI.', size=12)

doc.save(r'C:\Users\naorh\.gemini\antigravity\brain\4694b227-ecbf-476e-b160-c780e6cef4ef\LLM_Track_Guide_Hebrew.docx')
