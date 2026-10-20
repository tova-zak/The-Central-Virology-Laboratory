# DECISIONS.md — תיעוד החלטות פרויקט

> **Version:** 2.0  
> **Last Updated:** 2026-10-14  
> **Purpose:** מסמך מרכזי לתיעוד כל החלטות התכנון והפיתוח  
> **Format:** ID | Decision | Rationale | Status | Date | Affected Tasks  
> **Important:** מסמך זה הוא המקור המחייב לסטטוס החלטות. אין להתחיל משימה הדורשת החלטה PENDING.

---

## 0. פרוטוקול ביצוע משימות

### כללי עבודה מחייבים

1. **משימה אחת בלבד:** לא לבצע מספר משימות במקביל
2. **אין auto-continue:** גם אם כל הבדיקות עברו, לא עוברים למשימה הבאה ללא אישור מפורש
3. **אישור לכל משימה:** בעלת הפרויקט חייבת לומר: **"מאשרת לבצע TASK-XXX בלבד"**
4. **אין קוד ללא אישור:** אסור להתחיל כתיבת קוד, התקנת תלויות או ביצוע משימת פיתוח ללא אישור מפורש
5. **תלות בהחלטות:** משימה התלויה בהחלטה PENDING חסומה עד להכרעה

### תהליך ביצוע משימה

```
TODO → [אישור מפורש] → IN_PROGRESS → IN_REVIEW → [אישור תוצאות] → DONE
```

אין לדלג על שלבי אישור.

---

## 1. החלטות מאושרות (APPROVED)

החלטות שאושרו במפורש על ידי בעלת הפרויקט ומחייבות ביצוע.

---

### D-01: שימוש בטפסי הדוגמה עם Gemini — תכנית פיתוח

**Decision:**  
מאושר שימוש בטפסי הדוגמה המצורפים (48 עמודים מ־2 קובצי PDF) לצורך פיתוח ובדיקות מול Gemini Free Tier בלבד.

**אסור:**
- מסמכים אמיתיים ממעבדה
- שליחה לשירות בתשלום
- חשיפת PII ללוגים או Git
- שימוש בתכולת הדוגמאות ל-training או telemetry

**הבהרה חשובה:**  
אישור זה הוא לתכנית הפיתוח בלבד. **אין בכך אישור פרטיות או הרשאה חיצונית שכבר אומתו.**  
כל קריאה לטפסי הדוגמה ושליחתם לספק חיצוני (Gemini) מותנית באימות:
- תנאי שימוש של Google AI
- מדיניות שמירת נתונים
- אי-שימוש במידע לאימון מודלים
- זמינות Free Tier
- התאמה לדרישות פרטיות המעבדה

**Rationale:**
- טפסי הדוגמה הם מקור הבדיקה המרכזי כפי שנקבע במסמך האתגר
- פיתוח מול נתונים אמיתיים (דוגמאות) מאפשר בדיקת דיוק אמיתית
- שימוש בשירות חינמי מונע עלויות

**Status:** APPROVED  
**Approved By:** בעלת הפרויקט  
**Date:** 2026-10-14  
**Affected Tasks:** Gemini Integration (TASK-007), Golden Dataset (TASK-008), Accuracy (TASK-009)  
**Dependencies:** D-02 (בחירת מודל חינמי)

**Implementation Gate:**  
לפני שליחה ראשונה ל-Gemini, לאמת:
1. קריאת תנאי שימוש Google AI Studio / Gemini API
2. אימות זמינות Free Tier למודל המבוקש
3. בדיקת מדיניות data retention
4. אישור שאין חיוב אוטומטי במעבר למכסה

---

### D-02: Gemini Vision Free Tier בלבד, תקציב 0 ₪ מחייב

**Decision:**  
שימוש אך ורק במודל Gemini Vision הזמין ב־Free Tier.

**דרישות:**
- תקציב: **0 ₪** ללא חריגות
- מודל חייב לתמוך ב:
  - קלט תמונה (image input)
  - structured output (JSON)
  - זמין ב־Free Tier ללא חיוב
- אין billing
- אין paid tier
- אין fallback בתשלום
- אין שימוש במודל אחר (גם חינמי) ללא אישור חדש

**מגבלות שיש לבדוק בפועל:**
- מגבלת requests/minute
- מגבלת requests/day
- זמן timeout
- גודל תמונה מקסימלי
- אורך prompt/response מקסימלי

**חסימה אוטומטית:**
- אם המכסה נגמרה → הצגת הודעה למשתמש ועצירת עיבוד
- אין להמשיך עם מודל אחר או שירות בתשלום

**הבהרה חשובה:**  
**זמינות מודל Gemini מתאים, מכסות Free Tier ותנאי השימוש חייבים להיבדק בפועל.**  
אין להניח מראש שהמכסה תספיק. יש לתכנן:
- מדידת שימוש (request counter)
- התראה כשמתקרבים לגבול
- התנהגות ברורה כשמגיעים למגבלה

**הבהרה על מעבר ל-Enterprise:**  
בשלב ההאקתון נשתמש ב-Gemini API החינמי בלבד, בתקציב 0 ₪.  
במוצר אמיתי המעבדה תוכל להחליף אותו במנוע Enterprise ארגוני.  
לכן יש להקפיד על **הפרדת מנוע ה-AI באמצעות Extractor Interface**, אך אין צורך לממש כעת Enterprise או מנוע נוסף.

**Rationale:**
- דרישה מחייבת: תקציב הפרויקט הוא 0 ₪
- Gemini Vision מספק יכולות נדרשות במסלול חינמי
- מניעת עלויות בלתי צפויות
- הדגמת proof-of-concept ללא השקעה כספית
- ארכיטקטורה מודולרית מאפשרת החלפת מנוע בעתיד

**Status:** APPROVED  
**Approved By:** בעלת הפרויקט  
**Date:** 2026-10-14  
**Affected Tasks:** API Verification (TASK-002), Gemini Integration (TASK-007), Processing (TASK-013)  
**Dependencies:** אין

**Architecture Requirement:**  
כל קריאה ל-Gemini חייבת לעבור דרך `Extractor` interface מופשט.  
זה יאפשר החלפה קלה ל-Enterprise או מנוע אחר בעתיד.

**Implementation Notes:**
- TASK-002 תאמת זמינות ותתעד מגבלות בדיוק
- לתעד בקוד: model name, version, tier
- להוסיף rate limiting בצד Client
- להציג quota usage אם API מספק

---

### D-07: מדיניות סימון שדות ובקרת ייצוא

**Decision:**  
רק שדות בעייתיים/חסרים/לא ודאיים מסומנים לבדיקה.  
שדות שחולצו ללא בעיה ידועה אינם מסומנים ואינם מחייבים אישור.  
המזכירה מטפלת **רק בכל השדות המסומנים**.  
ייצוא אצווה שלמה **חסום** עד להשלמת טיפול בכל השדות המסומנים.

**כללי סימון:**
- שדה תקין ללא בעיה → לא מסומן, לא דורש אישור
- שדה לא ודאי → צבע כתום, `needs_review`
- שדה נדרש חסר / שגוי / סותר → צבע אדום, חובה לטפל
- שדה שאושר/תוקן → חזרה למצב רגיל, לא מסומן

**חסימת ייצוא:**
- כפתור "ייצוא לExcel" **disabled** כל עוד `unresolved_count > 0`
- גם ניסיון API ישיר נדחה (409 Conflict)
- אין ייצוא חלקי
- אין עקיפה (bypass)

**הבהרה קריטית:**  
**המערכת אינה יכולה להבטיח שכל שגיאה תזוהה.**  
שדה שלא סומן אינו מהווה הוכחה שהוא נכון — רק שהמערכת לא זיהתה בו בעיה.  
סימון הוא התראה על חשד, לא הבטחה שהשאר מדויק.

יש להציג למשתמש:
- כמה שדות דורשים טיפול
- קישור ישיר לשדות המסומנים
- אזהרה: "שדות שלא סומנו עדיין עלולים להכיל שגיאות"

**Rationale:**
- הפחתת עומס על המזכירה (לא לבדוק כל שדה)
- מניעת שגיאות שקטות (שדה שגוי שלא סומן) על ידי חסימת ייצוא
- אכיפת בקרת איכות לפני ייצוא
- שקיפות: רק מה שבעייתי דורש טיפול ידני

**Status:** APPROVED  
**Approved By:** בעלת הפרויקט  
**Date:** 2026-10-14  
**Affected Tasks:** Review UI (TASK-014), Manual Correction (TASK-015), Export Blocking (TASK-019)  
**Dependencies:** אין

**Implementation Details:**
- `GET /api/batches/{id}/export-status` → `{can_export: bool, unresolved_count: int}`
- `POST /api/batches/{id}/export` → 409 אם `can_export === false`
- Frontend: כפתור disabled + הצגת מונה
- UI: צבעים + טקסט הסבר (לא רק צבע)

**Security Focus for MVP:**  
התמקדות באבטחת המוצר עצמו:
- העלאת קבצים מאובטחת (MIME validation, size limits)
- Backend API (authentication, input validation)
- אחסון זמני מוגן
- מפתחות API (environment variables, .gitignore)
- בדיקות קלט (SQL injection, path traversal)
- ייצוא Excel בטוח (formula injection prevention)

אין צורך להרחיב לנושאי אבטחת Enterprise עתידיים (SSO, audit logs מתקדמים, encryption at rest).  
יש לשמור על תנאי השימוש והאישורים הבסיסיים לפני שליחת נתונים לשירות חיצוני.

---

## 2. הנחות ברירת מחדל (DEFAULT)

הנחות שנבחרו כברירת מחדל סבירה ל-MVP. ניתן לשנות בעתיד לפי צורך.

---

### D-03: סביבת הרצה — localhost בלבד

**Decision:**  
המערכת תרוץ על `127.0.0.1` בלבד.  
אין חשיפה ברשת, אין פריסה ציבורית, אין שרת ייצור.

**Rationale:**
- MVP להדגמה מקומית
- הפחתת סיכוני אבטחה
- single user
- אין צורך בתשתית cloud

**Status:** DEFAULT  
**Date:** 2026-10-14  
**Affected Tasks:** Backend, Frontend  
**Can Change:** כן, אם נדרשת הדגמה מרחוק

---

### D-08: שמירה ומחיקה — זמני, TTL

**Decision:**
- אחסון זמני (קבצים מקומיים או זיכרון)
- TTL מוגדר (המלצה: 24 שעות)
- ניקוי אוטומטי לאחר TTL
- אין DB קבוע ב־MVP

**Rationale:**
- פשטות מימוש
- הפחתת סיכוני פרטיות
- מתאים ל־single user demo

**Status:** DEFAULT  
**Date:** 2026-10-14  
**Affected Tasks:** Storage, Upload

---

### D-09: מספר משתמשים — single user

**Decision:**  
מפעילה אחת, ללא תמיכה במשתמשים מרובים.  
אין authentication, אין authorization, אין ניהול הרשאות.

**Rationale:**
- MVP להדגמה
- הפחתת complexity
- אין צורך באימות/הרשאות

**Status:** DEFAULT  
**Date:** 2026-10-14  
**Affected Tasks:** כל המשימות

---

### D-10: טיפול בטפסים לא מוכרים

**Decision:**
- best effort
- טופס לא מוכר → `unknown` sender/form_type
- לא לדחות את המסמך
- סימון לבדיקה ידנית

**Rationale:**
- גמישות
- אין רשימה סגורה של טפסים
- שקיפות

**Status:** DEFAULT  
**Date:** 2026-10-14  
**Affected Tasks:** Extraction, Form Classification

---

### D-11: מיפוי גורמים שולחים

**Decision:**
- רשימה ניתנת לעדכון (config/JSON)
- `unknown` ללא ראיה ברורה
- לא לבחור גורם "קרוב" או לנחש

**Rationale:**
- נרמול בסיסי
- הימנעות מנחשים
- שקיפות

**Status:** DEFAULT  
**Date:** 2026-10-14  
**Affected Tasks:** Validation, Normalization

---

### D-14: מגבלות גודל/עמודים/אצווה

**Decision (מתוקנת):**  
ספים שמרניים מוגדרי config, **מותאמים לקובצי האתגר**:

**מגבלות מוצעות:**
- **גודל קובץ בודד:** 20MB (קובצי הדוגמה: ~2-5MB)
- **עמודים ל-PDF:** 30 עמודים (קובצי הדוגמה: 22 ו-26 עמודים)
- **קבצים באצווה:** 10 קבצים (ניתן להרחבה)
- **רזולוציה מקסימלית:** 3000×3000 פיקסלים לעמוד
- **זמן עיבוד:** timeout של 60 שניות לקובץ יחיד

**הבהרה:**  
המגבלות צריכות להתאים ל:
1. קובצי האתגר (22-26 עמודים)
2. סביבת הרצה (RAM, CPU זמינים)
3. מכסות Gemini Free Tier
4. ביצועים סבירים

**אין לקבוע מספרים שרירותיים.**  
יש למדוד בפועל:
- זמן עיבוד ממוצע לעמוד
- שימוש בזיכרון
- מספר requests ל-Gemini ליחידת זמן

**Rationale:**
- הגנה מפני DoS
- שמירה על ביצועים
- התאמה למכסות Free Tier
- ניתן להרחבה לפי מדידה

**הבהרה חשובה:**  
אלו ערכי **ברירת מחדל זמניים**, שיש לאמת מול קובצי הדוגמה והביצועים בפועל.  
לא לקבוע מספרים סופיים לפני מדידה.

**Status:** DEFAULT (מחייב מדידה)  
**Date:** 2026-10-14  
**Affected Tasks:** העלאה ועיבוד קבצים  
**Action Required:** מדידת ביצועים בפועל על קובצי הדוגמה (22-26 עמודים)

---

### D-15: טלמטריה וחשיפת מסמכים

**Decision:**
- מינימום חשיפה
- לא לפתוח מסמכי אמת/דוגמאות בכלי AI חיצוני (Kiro context, screenshots, clipboard)
- אין שימוש בדוגמאות ל-telemetry
- אין העלאת תוכן טפסים לשירותי debug/monitoring חיצוניים

**Rationale:**
- פרטיות
- הפחתת סיכון דליפה
- בידוד נתונים רגישים

**Status:** DEFAULT  
**Date:** 2026-10-14  
**Affected Tasks:** כל המשימות

---

## 3. החלטות ממתינות (PENDING)

החלטות שטרם הוכרעו וחוסמות משימות ספציפיות.

---

### D-04: פורמט Excel — עמודות מדויקות ⚠️ BLOCKER

**Question:**  
מהן העמודות המדויקות בקובץ ה־Excel?  
מה סדרן? מה הפורמט של כל תא? האם קיימת תבנית Excel מוכרת במעבדה?

**Options:**
1. שימוש בתבנית קיימת מהמעבדה (מומלץ)
2. יצירת תבנית חדשה לפי דרישות המעבדה
3. תבנית זמנית להדגמה בלבד עם סימון ברור שאינה סופית

**תבנית זמנית מוצעת (לא מאושרת):**
```
first_name | last_name | id_number | central_numbers | received_date | sender | commitment_number
```

**Impact:**  
**BLOCKS Excel Export** — לא ניתן לממש ייצוא סופי ללא החלטה

**Status:** PENDING  
**Required Before:** Excel Exporter Implementation  
**Priority:** HIGH — חוסם Phase 5

**Action Items:**
- [ ] לבדוק אם קיימת תבנית Excel במעבדה
- [ ] לאשר שמות עמודות
- [ ] לאשר סדר עמודות
- [ ] לאשר פורמט תאים (text/number/date)

---

### D-05: ייצוג N מרכזיים ל־M התחייבויות ⚠️ BLOCKER

**Question:**  
כיצד לייצג יחסי N:M ב־Excel?

**דוגמאות לבעיה:**
- התחייבות אחת עם 3 מספרים מרכזיים → שורה אחת עם delimiter?
- בדיקה עם 2 מרכזיים ו־3 התחייבויות → 6 שורות? 3 שורות? עמודות נפרדות?

**Options:**
1. שורה אחת להתחייבות, ערכים מרובים עם delimiter (`;` או `,`)
2. עמודות נוספות: `central_1`, `central_2`, `central_3`, ...
3. שורות נפרדות לכל התחייבות (המלצה)
4. גיליון נפרד לקשרים (מורכב)

**המלצה הנדסית:**  
שורה להתחייבות, `central_numbers` כטקסט עם delimiter, עמודת הערות לקשר לא ודאי

**Impact:**  
**BLOCKS Excel Export** — משפיע על לוגיקת ייצוא והמרת נתונים

**Status:** PENDING  
**Required Before:** Excel Exporter Implementation  
**Priority:** HIGH — חוסם Phase 5

---

### D-06: קיבוץ עמודים לטופס

**Question:**  
כיצד לזהות שעמוד PDF שייך לטופס/בדיקה הקודמים?

**Options:**
1. אלגוריתם שמרני: כל עמוד = טופס נפרד (המלצה ל-MVP)
2. קיבוץ לפי barcode/מספר מרכזי (דורש לוגיקה מורכבת)
3. בדיקה ידנית בממשק Review

**Impact:**  
משפיע על ספירת רשומות, מדידת דיוק, חוויית משתמש

**Status:** DEFERRED (אפשרי אחרי MVP)  
**Required Before:** Multi-page Grouping (אם נדרש קיבוץ אוטומטי)  
**Priority:** LOW — ניתן לעבוד בלי קיבוץ אוטומטי

---

### D-12: פיצול שמות

**Question:**  
האם לפצל אוטומטית `full_name` ל־`first_name` + `last_name`?

**Options:**
1. best-effort parsing (regex פשוט)
2. שמירת `full_name_raw` בלבד
3. פיצול רק אם יש ראיה (שני שדות נפרדים במקור)

**המלצה הנדסית:**  
שמירת `full_name_raw` תמיד, פיצול best-effort עם סימון `uncertain` אם לא ברור

**Status:** PENDING (החלטה אחרי Gemini Integration)  
**Required Before:** Validation Service  
**Priority:** MEDIUM

---

### D-13: בדיקה ללא מספר התחייבות ⚠️ BLOCKER

**Question:**  
מה לעשות עם בדיקה שיש לה מספר מרכזי אך אין מספר התחייבות?

**Options:**
1. לא ליצור שורת Excel (שמירה פנימית בלבד)
2. ייצוא עם `commitment_number` ריק
3. גיליון נפרד לחריגים

**Impact:**  
**BLOCKS Excel Export** — משפיע על לוגיקת ייצוא

**Status:** PENDING  
**Required Before:** Excel Exporter Implementation  
**Priority:** HIGH — חוסם Phase 5

---

## 4. סיכום חסימות

| Decision | Priority | Blocks Tasks | Action Required |
|---|---|---|---|
| D-04 | HIGH | Excel Export | אישור תבנית Excel |
| D-05 | HIGH | Excel Export | אישור ייצוג N:M |
| D-13 | HIGH | Excel Export | אישור טיפול בחסרים |
| D-12 | MEDIUM | Validation | החלטה על פיצול שמות |
| D-06 | LOW | Multi-page | אם נדרש קיבוץ אוטומטי |

**הערה:** מספרי משימות יקבעו ב-TECH_TASKS.md לאחר אישור התוכנית.  
Excel Export חסום עד ל-D-04, D-05, D-13.

---

## 5. היסטוריית שינויים

| Date | Version | Change | Reason |
|---|---|---|---|
| 2026-10-14 | 1.0 | יצירה ראשונית | תיעוד החלטות מ-PLAN.md |
| 2026-10-14 | 2.0 | תיקון מבני גדול | סקירה מול PLAN ו-TECH_TASKS |

### שינויים בגרסה 2.0:

1. **הפרדה ברורה:** APPROVED / DEFAULT / PENDING
2. **תיקון D-01:** הבהרה שאין אישור פרטיות/הרשאה שכבר אומתו
3. **תיקון D-02:** הדגשה שזמינות Free Tier צריכה בדיקה בפועל + הבהרה על Extractor Interface
4. **תיקון D-07:** הבהרה שהמערכת לא מבטיחה זיהוי כל שגיאה + מיקוד אבטחה ב-MVP
5. **תיקון D-14:** התאמת מגבלות לקובצי האתגר (22-26 עמודים), דרישת מדידה, סימון כזמני
6. **הוספת סעיף 0:** פרוטוקול ביצוע משימות מחייב
7. **סימון BLOCKERS:** החלטות שחוסמות משימות קריטיות (הסרת מספרי משימות ספציפיים)
8. **הסרת טענות שווא:** אין להציג החלטות כאישורים שלא ניתנו

---

## 6. החלטות מיושמות (IMPLEMENTED) — ReviewScreen Three-Table Redesign

החלטות שהתקבלו במסגרת משימת ReviewScreen Three-Table Redesign (2025-01-18).

---

### D-16: relation_status MVP Limitation

**Decision:**  
במסגרת ה-MVP, כל CommitmentRecords נוצרים עם `relation_status="ambiguous"` (ברירת מחדל שמרנית).  
אין לוגיקה במנוע החילוץ שמגדירה `relation_status` כ-"clear" או "related" על בסיס ראיות.  
לכן, **בדיקת ambiguous relationships מדולגת בסיווג** (classification) כיוון שהיא הייתה מסמנת את כל הרשומות.

**Implementation:**
- Backend: `classifier.py` - פונקציה `hasWarnings()` מדלגת על בדיקת `relation_status="ambiguous"`
- Frontend: `classification.ts` - פונקציה `hasWarnings()` מדלגת על בדיקת `relation_status`
- הוערה בקוד: `// NOTE: Skipping ambiguous relation_status check (H-1 resolution)`

**Future Enhancement:**  
שיפור מנוע החילוץ כדי להגדיר `relation_status` על בסיס ראיות:
- "clear": יחס ברור בין commitment למספר מרכזי (בקרבה מרחבית, זיהוי barcode וכו')
- "related": סבירות גבוהה ליחס
- "ambiguous": לא ברור (ברירת מחדל)

**Rationale:**
- מניעת false positives: כל הרשומות היו מסווגות ל-Table 2 (warnings)
- pragmatic: אין נתונים זמינים להבדיל בין commitments ברורים למעורפלים
- שקיפות: תיעוד המגבלה במפורש

**Status:** IMPLEMENTED  
**Date:** 2025-01-18  
**Affected:** Classification logic (backend + frontend)  
**Documented In:** plan.md (H-1 resolution)

---

### D-17: confirmed_empty Policy

**Decision:**  
המערכת מאפשרת לאשר כל שדה כריק (confirmed empty) דרך endpoint ה-`/verify`.  
שדה עם `reviewed_value=""` AND `review_state="human_verified"` **אינו נחשב כחסר** (not missing).  
זה כולל שדות חובה (required fields).

**Implementation:**
- Backend: `classifier.py` - פונקציה `is_field_missing()` מחזירה `False` אם `review_state == "human_verified"`
- Frontend: `classification.ts` - פונקציה `isFieldMissing()` מחזירה `false` אם `review_state === 'human_verified'`

**Business Case:**  
יש מקרים לגיטימיים שבהם שדה "חובה" יכול להיות ריק:
- שם פרטי: חלק מהאנשים יש להם רק שם משפחה
- מספר התחייבות: לא תמיד קיים
- מספר מרכזי: יכול להיות חסר בנסיבות מסוימות

**Caveat:**  
זוהי מדיניות עסקית זמנית **הממתינה להבהרה מהמעבדה**.  
מומלץ לאשר עם בעלי התפקיד אילו שדות אכן מותר לאשר כריקים.

**Rationale:**
- גמישות: המזכירה יכולה לטפל במקרי קצה
- שקיפות: אישור אנושי מתועד ב-`human_verified`
- מניעת חסימות: לא לחסום ייצוא על שדה שהמזכירה אישרה שהוא ריק לגיטימי

**Status:** IMPLEMENTED (pending business policy clarification)  
**Date:** 2025-01-18  
**Affected:** Classification logic, Export eligibility  
**Documented In:** plan.md (H-3 resolution)

---

### D-18: Orphaned Commitments Handling

**Decision:**  
רשימת `commitment_ids` ב-TestRecord היא המקור המחייב.  
CommitmentRecord עם `test_id` תואם אבל שאינו ברשימת `commitment_ids` נחשב לשגיאת שלמות נתונים (orphaned commitment).

**Implementation:**
- Frontend: `relationships.ts` - פונקציה `getCommitmentNumbersForTest()`:
  - מזהה orphaned commitments (יש להם `test_id` אבל לא ב-`commitment_ids`)
  - מדפיסה אזהרה לקונסול: `console.warn(...)`
  - **לא מציגה orphaned commitments** (per H-2 resolution)
  - לא קורסת - ממשיכה לעבד רק את commitment_ids המחייבים

**Scenario:**  
במבחנים ידניים, תרחיש זה עשוי שלא להופיע כיוון שמנוע החילוץ תמיד יוצר גם TestRecord.commitment_ids וגם CommitmentRecord יחד.

**Rationale:**
- robustness: המערכת לא קורסת על שגיאת נתונים
- שקיפות: אזהרה בקונסול מסייעת לאבחון בדיקות
- pragmatic: מציגים רק מה שמתועד בצורה רשמית

**Status:** IMPLEMENTED  
**Date:** 2025-01-18  
**Affected:** Commitment display (frontend)  
**Documented In:** plan.md (H-2 resolution)

---

## 7. הנחיות שימוש

### לפני תחילת משימה:

1. בדוק אם המשימה תלויה בהחלטה PENDING
2. אם כן → המשימה BLOCKED, להמתין להכרעה
3. אם לא → ניתן להמשיך לאחר אישור מפורש

### כשנתקלים בהחלטה חסרה:

1. לתעד אותה ב-DECISIONS.md
2. להציג אפשרויות
3. לציין את ההשפעה (BLOCKS...)
4. **לא להמציא החלטה** ולא להניח ברירת מחדל בלי אישור

### כשמתגלה סתירה:

1. לתעד את הסתירה
2. להציג את המקורות הסותרים
3. להציע פתרון
4. להמתין להכרעה

---

**סטטוס מסמך:** CURRENT  
**בעלת מסמך:** בעלת הפרויקט  
**עדכון אחרון:** 2026-10-14



## Deployment preparation record - 2026-10-20

Persistence implementation checkpoint: `0f71767d62320d49b3869ca60dc7fde63b73139c`.
This is not production validation. Existing patient/review/export business rules remain unchanged.

Implemented technical boundaries authorized for this preparation:
- Protected synthetic staging is distinct from production; legacy cloud mode aliases staging.
- Production fails closed until clinical identity, tenant authorization, audit and durable processing exist.
- Supabase remains the record/original authority; no replacement database or live schema/RLS work.
- Separate production worker/private Key Value transport is a design template only, not an implemented consumer.
- Request/document/resource caps bound the demo; they do not constitute production abuse protection.

PENDING institutional decisions (not inferred or resolved): identity/SSO provider, MFA/role matrix,
organization membership/ownership, approved regions and vendor/data-handling terms, audit/retention,
backup RPO/RTO, paid resources and production release authority. The production template cannot be applied
until these decisions and implementation gates are closed. See DEPLOYMENT.md and
docs/PRODUCTION_ARCHITECTURE.md. No compliance certification is asserted.
