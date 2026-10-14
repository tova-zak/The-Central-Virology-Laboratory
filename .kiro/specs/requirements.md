# Requirements — דרישות מערכת חילוץ התחייבויות

> **Source:** PLAN.md v2.1, DECISIONS.md v2.0  
> **Approved:** 2026-10-14  
> **Budget:** 0 ₪  
> **Timeline:** ~7 days (MVP)

---

## 1. Business Goals

**Problem:**  
המעבדה מקבלת טפסים לא אחידים (PDF/תמונות) יחד עם דגימות, ומבצעת הזנה ידנית של נתונים ל-Excel.

**Solution:**  
מערכת חילוץ אוטומטי עם סימון אי-ודאות, תיקון ידני וייצוא מבוקר.

**Success Criteria:**
1. העלאת PDF/תמונות (בודד ואצווה) עובדת
2. חילוץ 7 שדות מדוייק ושקוף
3. סימון שדות בעייתיים בלבד
4. תיקון ידני שמור ונכבד
5. ייצוא Excel חסום עד טיפול בכל השדות המסומנים
6. דוח דיוק מדיד על דוגמאות מתויגות

---

## 2. Functional Requirements

### R-01: קליטת קבצים
- **Input:** PDF או תמונות (PNG, JPG)
- **Modes:** קובץ בודד או אצווה
- **Validation:** MIME type, magic bytes, גודל, עמודים
- **Acceptance:** קלט תקין מתקבל; קלט לא תקין נדחה בהודעה ברורה

### R-02: זיהוי סוג טופס וגורם שולח
- **Detection:** קופה/בית חולים מזוהים כשיש ראיה
- **Unknown:** `unknown` אחרת, לא לנחש
- **Acceptance:** גורם נכון מזוהה או מסומן `unknown`

### R-03: חילוץ 7 שדות
**שדות חובה:**
1. שם פרטי
2. שם משפחה
3. ת.ז
4. מספר מרכזי
5. תאריך קבלה
6. גורם שולח
7. מספר התחייבות

**Rules:**
- ערך חסר → `null` (לא נחש)
- ערך לא ודאי → סימון `uncertain`
- ערכים מרובים → שמירה כרשימה
- מספרים → שמירה כמחרוזות (אפסים מובילים)

**Acceptance:** כל שדה בסכמה, אין המצאות

### R-04: כל המספרים המרכזיים
- **Source:** מדבקה, כתב יד, מודפס
- **Multiple:** שמירת כל הערכים
- **Acceptance:** אין השמטה או יצירת מספרים מדומים

### R-05: תאריך קבלת דגימה
- **Source:** 'התקבל' או כתב יד מתחת למרכזי
- **Disambiguation:** לא לערבב עם תאריך הדפסה/בדיקה/לידה
- **Acceptance:** תאריך נכון או סימון uncertain

### R-06: מספר התחייבות
- **Aliases:** 'דרישה', 'דגימה' (בלאומית)
- **Multiple:** שמירת כל הערכים
- **Separation:** לא לערבב עם מספר מרכזי
- **Acceptance:** כל הערכים נשמרים, אין ערבוב

### R-07: טיפול באי-וודאות
- חסר → `missing` (ריק)
- לא בטוח → `uncertain` (סימון)
- לא לנחש ערכים
- **Acceptance:** מצב מתועד, אין הסתרה

### R-08: תיקון אנושי
- **Display:** טבלת תוצאות + מסמך מקור
- **Edit:** שינוי שדה שומר `reviewed_value` נפרד
- **Provenance:** `raw_value` לא נדרס
- **Acceptance:** תיקון נשמר, מופיע ב-Excel

### R-09: Excel Export
- **Format:** שורה לכל התחייבות, עמודה לכל שדה
- **Mapping:** לפי D-04, D-05 (PENDING)
- **Data Types:** מספרים כטקסט, תאריכים ISO/DD-MM-YYYY
- **Acceptance:** ספירת רשומות נכונה, אפסים נשמרים

### R-10: טפסים לא אחידים
- **Variety:** סרוק/מצולם, כתב יד, מדבקות, חותמות, סיבוב, איכות נמוכה
- **Acceptance:** כל סוג נבדק, כשלים מסומנים

### R-11: דיווח הצלחה/כשל
- **Golden Dataset:** 10-15 טפסים מתויגים ידנית
- **Metrics:** field accuracy, coverage, false extraction, unsafe acceptance, review burden
- **Acceptance:** דוח מדידה שקוף, טבלת אמת מתועדת

### R-12: פרטיות ואבטחה
- **Secrets:** API keys מחוץ ל-Git
- **PII:** לא בלוגים, לא ב-screenshots
- **Approval:** אישור לפני שליחה לשירות חיצוני
- **Acceptance:** secrets מוגנים, לוגים נקיים

---

## 3. Non-Functional Requirements

### NFR-01: שלמות נתונים
- אין מחיקת ערך/קישור בלי עקבה
- כל המידע נשמר גם אם לא ניתן למיפוי

### NFR-02: שמירת מקור
- `raw_value`, `normalized_value`, `reviewed_value` נפרדים
- נרמול לא מוחק raw

### NFR-03: מספרים כמחרוזות
- ת.ז, מרכזי, התחייבות → strings
- אפסים מובילים נשמרים
- לא float, לא scientific notation

### NFR-04: אי-המצאה
- JSON תקין ≠ הוכחה
- ערך מהמודל ≠ ראיה שהופיע במסמך

### NFR-05: בידוד כשלים
- מסמך כושל לא מבטל אחרים
- אין רשומות כפולות עקב retry

### NFR-06: שקיפות
- סטטוס בכל שדה
- מקור כשזמין
- אי-ודאות מוצגת
- סיבה לבדיקה
- יכולת תיקון

### NFR-07: מדידה
- שגיאות שקטות נמדדות בנפרד
- הבחנה בין accuracy, coverage, safety

### NFR-08: סקלביליות מדורגת
- החלפת מנוע/אחסון/תור ללא שבירת חוזים
- לא להוסיף תשתיות מיותרות מראש

### NFR-09: זמני תגובה
- מוצג מצב עיבוד
- timeout/retry/cancel או הודעת כשל
- יעדי ביצועים לאחר baseline

### NFR-10: UI
- עברית RTL
- הצגה תקינה של מזהים/אנגלית LTR
- תצוגת עמוד קריאה
- מצב שגיאה נגיש

---

## 4. Constraints & Decisions

### Approved Decisions

**D-01: Sample Data (APPROVED)**
- טפסי דוגמה (48 עמודים) בלבד
- Gemini Free Tier
- לא מסמכים אמיתיים
- תנאי שימוש ופרטיות יאומתו

**D-02: Gemini Free Tier Only (APPROVED)**
- תקציב: **0 ₪**
- מודל: Gemini Vision חינמי
- אין billing, אין paid fallback
- Extractor Interface להחלפה עתידית

**D-07: Review Policy (APPROVED)**
- רק שדות בעייתיים מסומנים
- המזכירה מטפלת בכל המסומנים
- ייצוא חסום עד השלמה
- אין ייצוא חלקי

### Default Assumptions

**D-03:** localhost only  
**D-08:** אחסון זמני, TTL  
**D-09:** single user  
**D-10:** best effort לטפסים לא מוכרים  
**D-11:** רשימת גורמים ניתנת לעדכון  
**D-14:** מגבלות: 20MB, 30 עמודים, 10 קבצים (זמני, למדידה)  
**D-15:** מינימום חשיפה טלמטרית

### Pending Decisions (BLOCKERS)

**D-04:** פורמט Excel — שמות עמודות, סדר, טיפוסי תאים  
**D-05:** ייצוג N:M — איך לייצג N מרכזיים ל-M התחייבויות  
**D-13:** בדיקה ללא התחייבות — ייצוא או הסתרה  

**D-12:** פיצול שמות — אוטומטי או ידני  
**D-06:** קיבוץ עמודים — כל עמוד נפרד או קיבוץ אוטומטי

---

## 5. Out of Scope (Not MVP)

- Authentication ארגוני
- Authorization מרובה משתמשים
- DB קבוע
- Fine-tuning מודלים
- OCR עצמאי כברירת מחדל
- מודל שני אוטומטי
- פריסה ציבורית
- אינטגרציית מעבדה
- תקנות/אישורי ייצור
- 100% דיוק מובטח

---

## 6. Acceptance Criteria (MVP)

### Must Have:
1. ✅ העלאת PDF/תמונות (בודד + אצווה)
2. ✅ **Gemini API אמיתי** מיום 2
3. ✅ חילוץ 7 שדות + validation
4. ✅ סימון שדות בעייתיים בלבד
5. ✅ תיקון ידני שמור
6. ✅ חסימת ייצוא עד טיפול
7. ✅ Excel (mapping זמני אם D-04/D-05 לא הוכרעו)
8. ✅ **Golden Dataset מוקדם** (10-15 טפסים)
9. ✅ **מדידת דיוק אמיתית** עם Gemini
10. ✅ בדיקות אבטחה (secrets, MIME, formula injection)
11. ✅ cold start + demo script
12. ✅ תיעוד מגבלות

### Should Have:
- קיבוץ רב-עמודי אוטומטי
- crop retry אוטומטי
- איתור bbox מדויק

### Could Have:
- מנוע נוסף
- תור חיצוני
- UI מתקדם

---

## 7. Quality Standards

### Testing:
- Unit tests (validation, models)
- Integration tests (API, Gemini mock)
- E2E tests (upload → review → export)
- Golden benchmark (Gemini אמיתי)
- Regression tests (כשלים ידועים)

### Security:
- API keys ב-`.env` (לא ב-Git)
- MIME + magic bytes validation
- IDOR protection
- Formula injection prevention
- לוגים נקיים מ-PII

### Documentation:
- README: installation, usage
- DECISIONS.md: choices
- LIMITATIONS.md: MVP boundaries
- PRODUCTION_READINESS.md: steps to production

---

## 8. Timeline Estimate

| Day | Goal | Gate |
|---|---|---|
| 1 | Git, API setup, תשתית | תשתית מוכנה, Gemini מאומת |
| 2 | **Gemini אמיתי** + העלאה | תוצאה אמיתית מ-Gemini |
| 3 | 7 שדות + סטטוסים | סימון אי-ודאות עובד |
| 4 | Review UI + תיקון | תיקון שמור, ייצוא חסום |
| 5 | Excel + batch | roundtrip עובד |
| 6 | **Golden Dataset + דיוק** | דוח מדידה מתועד |
| 7 | אבטחה, demo, תיעוד | cold start עובד |

---

**This requirements document is the foundation for design and implementation.**
