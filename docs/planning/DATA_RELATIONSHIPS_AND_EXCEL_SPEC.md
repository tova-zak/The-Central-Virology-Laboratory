# DATA RELATIONSHIPS AND EXCEL SPEC

> **Version:** 1.0  
> **Date:** 2026-10-19  
> **Purpose:** מפרט לוגיקה עסקית, מבנה נתונים וקשרי רשומות למערכת חילוץ התחייבויות  
> **Scope:** תכנון בלבד — ללא שינויים בקוד  
> **Status:** FOR REVIEW

---

## תקציר מנהלים

מסמך זה מנתח את מודל הנתונים הקיים, מזהה פערים ותרחישי קצה, ומציע המלצות לשיפור טיפול בקשרים בין רשומות ובייצוא Excel. המסמך **לא מציע שינויי קוד** אלא מתעד את המצב הקיים ומציג שאלות עסקיות פתוחות הדורשות הכרעה.

**ממצאים עיקריים:**
1. המודל הקיים תומך ב-N:M אך ההטמעה חלקית
2. קיימות החלטות עסקיות פתוחות (D-04, D-05, D-13) שחוסמות ייצוא סופי
3. מדיניות `relation_status="ambiguous"` כברירת מחדל יוצרת רוויה של אזהרות
4. חוסר בדרישות עסקיות ברורות למקרי קצה (התחייבויות יתומות, טפסים מרובי עמודים)

---

## 1. מודל הנתונים הקיים — ניתוח

### 1.1 הישויות המרכזיות

```
UploadBatch (1) ──┬──> SourceDocument (N)
                  │
TestRecord (1) ───┼──> CommitmentRecord (N)
      ↑           │
      └───────────┘
```

#### TestRecord (Test/Patient Level)

**ייצוג:** טופס בדיקה יחיד, עם נתוני מטופל

**שדות עיקריים:**
- `test_id`: מזהה ייחודי
- `patient_first_name`, `patient_last_name`, `patient_id_number`: זיהוי מטופל
- `sender`, `received_date`: מקור וזמן
- `central_numbers`: **רשימה** של מספרים מרכזיים (FieldValue\[list\[str\]\])
- `commitment_ids`: **רשימה** של מזהי התחייבויות (list\[str\])

**ייחודיות:** `test_id` ייחודי, אך שדות מטופל זהים לא חייבים לייצג אותו אדם (דגימות חוזרות לגיטימיות)

#### CommitmentRecord (Commitment Level)

**ייצוג:** התחייבות בודדת, משוייכת לבדיקה

**שדות עיקריים:**
- `commitment_record_id`: מזהה ייחודי
- `test_id`: הפניה ל-TestRecord
- `commitment_number`: FieldValue\[str\] — המספר עצמו
- `central_number_refs`: **רשימה** של מספרים מרכזיים שקשורים להתחייבות (list\[str\])
- `relation_status`: `"related"` | `"ambiguous"` | `"unknown"`
- `review_status`: ReviewState

**קשרים מוגדרים:**
1. CommitmentRecord → TestRecord: N:1 דרך `test_id`
2. TestRecord → CommitmentRecord: 1:N דרך `commitment_ids[]`
3. CommitmentRecord → CentralNumbers: N:M דרך `central_number_refs[]`

### 1.2 FieldValue Wrapper

כל שדה עסקי עטוף ב-`FieldValue<T>`:

```python
{
  raw_value: T | None          # ערך מקורי מהמנוע
  normalized_value: T | None   # ערך מנורמל
  reviewed_value: T | None     # ערך מתוקן אנושית (גובר!)
  
  extraction_state: ExtractionState  # found|uncertain|missing|conflicting|invalid
  review_state: ReviewState          # pending|needs_review|human_verified|rejected
  
  validation_issues: list[ValidationIssue]
  evidence_refs: list[EvidenceRef]
  
  # Hybrid extensions (backward compatible)
  ocr_value: T | None
  verification_status: str | None
}
```

**עקרון מפתח:** `reviewed_value` גובר על הכל; אין לדרוס ערך שאושר ידנית.

---

## 2. תרחישי נתונים מפורטים

### 2.1 תרחיש פשוט: 1 בדיקה, 1 מרכזי, 1 התחייבות

```
TestRecord {
  test_id: "T-001"
  patient_first_name: "יוסי"
  patient_id_number: "123456789"
  central_numbers: ["98765"]
  commitment_ids: ["C-001"]
}

CommitmentRecord {
  commitment_record_id: "C-001"
  test_id: "T-001"
  commitment_number: "REQ-2024-001"
  central_number_refs: ["98765"]
  relation_status: "related"  # ברור: המרכזי והתחייבות קשורים
}
```

**Excel צפוי (1 שורה):**
```
first_name | last_name | id_number | central_numbers | received_date | sender | commitment_number
יוסי       | כהן      | 123456789 | 98765           | 2024-10-15    | ...    | REQ-2024-001
```

**הערה:** בתרחיש זה, `central_number_refs = ["98765"]` תואם לנתון ב-`central_numbers`.

---

### 2.2 תרחיש: 1 בדיקה, 3 מרכזיים, 1 התחייבות

```
TestRecord {
  test_id: "T-002"
  central_numbers: ["11111", "22222", "33333"]  # 3 מדבקות בטופס
  commitment_ids: ["C-002"]
}

CommitmentRecord {
  commitment_record_id: "C-002"
  test_id: "T-002"
  commitment_number: "REQ-2024-002"
  central_number_refs: ["11111", "22222", "33333"]  # כל המרכזיים
  relation_status: "related"
}
```

**שאלות עסקיות:**
1. האם בפועל כל שלושת המרכזיים מתייחסים לאותה התחייבות?
2. האם זה לגיטימי (בדיקה אחת עם כמה צנצנות/דגימות)?
3. איך לייצג ב-Excel?

**אפשרויות Excel:**

**אפשרות A (שורה אחת, delimiter):**
```
central_numbers        | commitment_number
11111; 22222; 33333   | REQ-2024-002
```

**אפשרות B (3 שורות, שדות משוכפלים):**
```
first_name | central_numbers | commitment_number
יוסי       | 11111          | REQ-2024-002
יוסי       | 22222          | REQ-2024-002
יוסי       | 33333          | REQ-2024-002
```

**אפשרות C (עמודות נפרדות):**
```
central_1 | central_2 | central_3 | commitment_number
11111     | 22222     | 33333     | REQ-2024-002
```

**המלצה טכנית:** אפשרות A — פשוטה, נמנעת משכפול, עקבית עם `FieldValue[list]`

**החלטה נדרשת:** D-05 (ייצוג N:M ב-Excel) חייבת לאשר פורמט

---

### 2.3 תרחיש: 1 בדיקה, 2 מרכזיים, 3 התחייבויות

```
TestRecord {
  test_id: "T-003"
  central_numbers: ["AAA", "BBB"]
  commitment_ids: ["C-003", "C-004", "C-005"]
}

CommitmentRecord C-003 {
  commitment_number: "REQ-A"
  central_number_refs: ["AAA"]
  relation_status: "related"
}

CommitmentRecord C-004 {
  commitment_number: "REQ-B"
  central_number_refs: ["BBB"]
  relation_status: "related"
}

CommitmentRecord C-005 {
  commitment_number: "REQ-C"
  central_number_refs: ["AAA", "BBB"]  # שתי הדגימות?
  relation_status: "ambiguous"  # לא ברור אם זה נכון
}
```

**Excel צפוי (לפי דרישה: "שורה להתחייבות"):**
```
first_name | central_numbers | commitment_number
דוד        | AAA             | REQ-A
דוד        | BBB             | REQ-B
דוד        | AAA; BBB        | REQ-C
```

**בעיה מזוהה:**
- אם `relation_status="ambiguous"` וחסם export, איך המזכירה תתקן?
- האם צריך UI לעריכת `central_number_refs` באופן ידני?

**מימוש נוכחי:**
- קיים endpoint `/batches/{id}/commitments/{cid}/resolve` (process.py:721)
- מאפשר עדכון `central_number_refs` ו-`relation_status`
- **לא מיושם ב-UI**

**פער מזוהה:** אין ממשק משתמש לפתרון קשרים מעורפלים

---

### 2.4 תרחיש: קשר לא ידוע (ambiguous)

```
TestRecord {
  test_id: "T-004"
  central_numbers: ["X1", "X2"]
  commitment_ids: ["C-006", "C-007"]
}

CommitmentRecord C-006 {
  commitment_number: "REQ-X"
  central_number_refs: []  # לא ברור לאיזה מרכזי
  relation_status: "ambiguous"
}

CommitmentRecord C-007 {
  commitment_number: "REQ-Y"
  central_number_refs: []
  relation_status: "ambiguous"
}
```

**התנהגות נוכחית:**
1. מנוע החילוץ (Gemini) יוצר **כל** CommitmentRecords עם `relation_status="ambiguous"` (process.py:459)
2. Classifier מסמן רשומה כ-"warnings" אם יש `relation_status="ambiguous"` (classifier.py:140)
3. Export **חסום** כל עוד `relation_status="ambiguous"` (process.py:632)

**בעיה עסקית:**
- אם **כל** ההתחייבויות נוצרות כ-ambiguous, **כל** הרשומות נחסמות
- זוהי **רוויה של false positives**

**החלטה טכנית מתועדת:** D-16 (ReviewScreen Three-Table Redesign)
- סיווג (Classification) **מדלג** על בדיקת `relation_status="ambiguous"`
- כיוון שזו ברירת מחדל, לא מקרה חריג

**המלצה:** לשקול אחת מהאפשרויות:
1. שנה ברירת מחדל ל-`"related"` כשיש ראיה (קרבה במסמך, אותו ברקוד)
2. צור `relation_status="unknown"` לנפרד מ-`"ambiguous"` (חוסם export)
3. אפשר export עם `ambiguous` אך הוסף עמודת אזהרה

---

### 2.5 תרחיש: התחייבות יתומה (orphaned commitment)

```
CommitmentRecord {
  commitment_record_id: "C-ORPHAN"
  test_id: "T-999"  # לא קיים!
  commitment_number: "REQ-LOST"
  relation_status: "unknown"
}
```

**מקורות אפשריים:**
- שגיאה בעיבוד (טופס נכשל אחרי יצירת התחייבות)
- מחיקת TestRecord ללא ניקוי CommitmentRecords
- שיוך שגוי במנוע

**התנהגות נוכחית:**
- Frontend: `relationships.ts` מזהה orphans ומדפיס console.warn, אבל **לא מציג** (D-18)
- Backend: export blocker בודק orphans (process.py:636)

**שאלה עסקית:**
- האם להציג orphans ב-UI כשגיאות?
- האם לאפשר שיוך ידני ל-TestRecord קיים?
- האם להתעלם (סימון בלוג בלבד)?

**Endpoint קיים אך לא מיושם ב-UI:**
- `POST /batches/{id}/commitments/{cid}/assign/{test_id}` (process.py:655)

---

### 2.6 תרחיש: טופס רב-עמודי

```
Document: form_multi_page.pdf (3 pages)
```

**מקרה 1: שלושה טפסים נפרדים**
```
Page 1 → TestRecord T-A (patient: רחל)
Page 2 → TestRecord T-B (patient: משה)
Page 3 → TestRecord T-C (patient: שרה)
```

**מקרה 2: טופס אחד על 3 עמודים**
```
Page 1: patient info + central_numbers
Page 2: commitment numbers (continued)
Page 3: signatures
→ TestRecord T-MULTI
    central_numbers: [from page 1]
    commitment_ids: [from pages 1-2]
```

**מימוש נוכחי:**
- D-06 (קיבוץ עמודים) **לא הוכרעה**
- ברירת מחדל שמרנית: **כל עמוד = טופס נפרד** (PLAN.md)
- אין אלגוריתם אוטומטי לקיבוץ

**שאלות עסקיות:**
1. האם יש סימון ויזואלי מובהק שעמוד שייך לקודם? (חצים, "המשך", ברקוד זהה)
2. מה התדירות של טפסים רב-עמודיים בפועל?
3. האם קבלת 3 TestRecords במקום 1 היא תקלה או תוצאה מקובלת?

**המלצה:** אם קיבוץ נדרש, להוסיף ממשק UI לאיחוד TestRecords לאחר עיבוד

---

### 2.7 תרחיש: כמה טפסים בקובץ אחד

```
Document: batch_scan.pdf (10 pages)
```

**מצב רצוי:**
```
Page 1-2   → TestRecord T-001
Page 3     → TestRecord T-002
Page 4-5   → TestRecord T-003
Page 6     → TestRecord T-004
Page 7-10  → TestRecord T-005
```

**מצב בפועל (ברירת מחדל):**
```
Page 1   → TestRecord T-001
Page 2   → TestRecord T-002
...
Page 10  → TestRecord T-010
```

**פער:** אין הפרדה אוטומטית לטפסים

**שאלה עסקית:** האם זה תרחיש נפוץ במעבדה? אם כן, צריך פיצ'ר קיבוץ

---

## 3. מטריצת כללי עסקיים

| # | תרחיש | התנהגות נוכחית | מדיניות מוצעת | החלטה נדרשת |
|---|-------|----------------|---------------|-------------|
| **3.1** | 1 Test, 1 Central, 1 Commitment | ✅ עובד | שורה אחת ב-Excel | D-04, D-05 |
| **3.2** | 1 Test, N Centrals, 1 Commitment | ✅ יוצר רשימה | delimiter ב-Excel | D-05 |
| **3.3** | 1 Test, 1 Central, M Commitments | ✅ M שורות Excel | M שורות, central חוזר | D-04, D-05 |
| **3.4** | 1 Test, N Centrals, M Commitments | ⚠️ ambiguous ברירת מחדל | דורש פתרון ידני או חוקי שיוך | **D-05, פער UI** |
| **3.5** | Test עם central אך ללא commitment | ⚠️ לא מייצא | רשימה פנימית? גיליון נפרד? | **D-13** |
| **3.6** | Commitment עם test_id לא קיים (orphan) | ⚠️ מזוהה, לא מוצג | הצג ב-UI? שיוך ידני? | **החלטה חדשה** |
| **3.7** | relation_status="ambiguous" | 🔴 חוסם export (אך מדולג בסיווג) | לשנות ברירת מחדל? | **החלטה חדשה** |
| **3.8** | טופס רב-עמודי (multi-page form) | ⚠️ עמוד=טופס (ברירת מחדל) | קיבוץ אוטומטי? ידני? | D-06 |
| **3.9** | כמה טפסים בקובץ (multi-form file) | ⚠️ עמוד=טופס | פיצול חכם? | D-06 |
| **3.10** | ערכים חסרים בשדות חובה | ✅ סימון, חסימת export | אישור ריק = `human_verified` | D-17 (מיושם) |

---

## 4. לוגיקת סיווג (Classification)

### 4.1 שלוש טבלאות (Three-Table Design)

**Table 1 — Success (תקין)**
- כל שדות החובה קיימים
- אין אזהרות, אי-ודאויות או שגיאות
- `extraction_state=found`, `review_state=pending` או `human_verified`

**Table 2 — Warnings (דורש בדיקה)**
- שדות חובה קיימים
- יש אזהרות: `uncertain`, `conflicting`, `needs_review`, `validation_issues`
- ~~או `relation_status="ambiguous"`~~ (מדולג כיוון שזו ברירת מחדל, D-16)

**Table 3 — Missing (דורש השלמה)**
- לפחות שדה חובה אחד חסר או לא תקין
- `extraction_state=missing|invalid`
- **גבוה ביותר בעדיפות**

### 4.2 שדות חובה (REQUIRED_FIELDS)

```python
[
  "patient_first_name",
  "patient_last_name",
  "patient_id_number",
  "sender",
  "received_date",
  "central_numbers"
]
```

**שימו לב:** `commitment_number` **לא** בשדות חובה של TestRecord

**מדוע?**
- `commitment_number` שייך ל-CommitmentRecord, לא TestRecord
- תרחיש D-13: בדיקה ללא התחייבות לגיטימי?

**החלטה נדרשת:** D-13 — מה עושים עם Test ללא Commitment?

### 4.3 אישור שדה ריק (confirmed_empty)

**מדיניות D-17 (מיושמת):**
- `reviewed_value=""` AND `review_state="human_verified"` = **לא חסר**
- המזכירה יכולה לאשר ריק לגיטימי (שם פרטי חסר, commitment לא קיים)

**קריטריון:** `classifier.py:is_field_missing()` מחזיר `False` אם `human_verified`

**שאלה עסקית:** אילו שדות מותר לאשר כריקים?
- `patient_first_name`: אדם עם שם משפחה בלבד?
- `commitment_number`: בדיקה ללא התחייבות?
- `central_numbers`: בדיקה בלי מדבקה?

**ממתין להבהרה מהמעבדה** (PLAN.md H-3)

---

## 5. חסימת ייצוא (Export Blocking)

### 5.1 כללי Export Blocking (D-07, TASK-019)

**מדיניות מאושרת:**
- רק שדות בעייתיים מסומנים
- ייצוא אצווה **חסום עד שכל השדות המסומנים טופלו**
- אין ייצוא חלקי או עקיפה (bypass) ב-MVP

**תנאי חסימה:**
1. `review_state == needs_review` AND NOT `human_verified`
2. `extraction_state in [uncertain, conflicting, invalid]` AND NOT `human_verified`
3. ~~`relation_status == ambiguous`~~ (מדולג בסיווג, אבל **עדיין בודק בexport**, פער!)
4. Orphaned commitments
5. Documents with status `pending|processing|failed`

### 5.2 פער מזוהה: relation_status

**סתירה בין Classification לבין Export Blocking:**

**Classification (classifier.py:136-142):**
```python
# NOTE: Skipping ambiguous relation_status check (H-1 resolution)
# if commitment and commitment.relation_status == "ambiguous":
#     return True
```
→ מדולג כיוון שכל הרשומות ambiguous

**Export Blocking (process.py:632):**
```python
if commitment and commitment.get("relation_status") == "ambiguous":
    blockers.append(f"{record.test_id}: ambiguous_commitment_{commitment_id}")
```
→ **עדיין חוסם!**

**תוצאה:** אם יש CommitmentRecord עם `ambiguous`, export ייחסם, אבל הוא לא יופיע ב-Table 2

**המלצה:**
1. **להחליט:** האם `ambiguous` חוסם export או לא?
2. אם כן → צריך UI לפתרון (endpoint קיים אך לא מיושם)
3. אם לא → להסיר מExport Blocking

---

## 6. דוגמאות פלט Excel

### 6.1 פורמט זמני (Provisional, לא מאושר)

**עמודות:**
```
first_name | last_name | id_number | central_numbers | received_date | sender | commitment_number
```

**דוגמה 1: רשומה פשוטה**
```csv
יוסי,כהן,123456789,98765,2024-10-15,כללית,REQ-2024-001
```

**דוגמה 2: כמה מרכזיים (delimiter)**
```csv
דוד,לוי,987654321,"11111; 22222",2024-10-16,מכבי,REQ-2024-002
```

**דוגמה 3: כמה התחייבויות (שורות נפרדות)**
```csv
רחל,כהן,111222333,AAA,2024-10-17,מאוחדת,REQ-A
רחל,כהן,111222333,BBB,2024-10-17,מאוחדת,REQ-B
רחל,כהן,111222333,"AAA; BBB",2024-10-17,מאוחדת,REQ-C
```

### 6.2 טיפול באפסים מובילים

**דרישה:** מספרים נשמרים כ-**טקסט**, לא מספר

**מימוש נוכחי:**
```python
# models.py: מספרים כמחרוזות
patient_id_number: FieldValue[str]

# excel_exporter.py: cell כטקסט
ws.cell(row=idx, column=3, value=id_number)  # string, not int
```

**בדיקת roundtrip:** לקרוא Excel שנוצר ולוודא `"012345"` נשאר ולא `"12345"`

### 6.3 Formula Injection Prevention

**דרישה אבטחה:** ערך שמתחיל ב-`=`, `+`, `-`, `@` חייב להיות neutralized

**מימוש נוכחי:** לא נראה ב-`excel_exporter.py`

**המלצה:** להוסיף לפני כתיבת cell:
```python
if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
    value = "'" + value  # Prefix with single quote
```

---

## 7. פערים במימוש הנוכחי

| # | פער | חומרה | השפעה | פתרון מוצע |
|---|-----|--------|-------|------------|
| **7.1** | relation_status ברירת מחדל ambiguous | 🔴 HIGH | כל הרשומות עם אזהרה/חסימה | שנה ל-`related` או `unknown` לפי ראיות |
| **7.2** | אין UI לפתרון קשרים מעורפלים | 🟡 MEDIUM | המזכירה לא יכולה לתקן ambiguous | מימוש RelationshipEditor (endpoint קיים) |
| **7.3** | orphaned commitments לא מוצגים | 🟡 MEDIUM | נתונים אבודים ללא אזהרה ברורה | הוסף גיליון/רשימת Orphans ב-UI |
| **7.4** | Classification מדלג על ambiguous אך Export Blocking לא | 🟠 MEDIUM | סתירה לוגית, עלול לבלבל | יישור עם D-16 או שינוי מדיניות |
| **7.5** | אין קיבוץ עמודים (multi-page forms) | 🟢 LOW | טפסים מתפצלים מיותר | אלגוריתם או UI לאיחוד TestRecords |
| **7.6** | Excel Exporter ללא Formula Injection prevention | 🟠 MEDIUM | סיכון אבטחה אם ערך מכיל `=` | sanitize לפני כתיבה |
| **7.7** | אין טיפול ברשימת התחייבויות ריקה | 🟡 MEDIUM | TestRecord ללא Commitments → D-13 לא הוכרעה | החלטה עסקית: לייצא? לדלג? גיליון נפרד? |
| **7.8** | אין בדיקת roundtrip ל-Excel | 🟡 MEDIUM | אפסים מובילים עלולים להימחק | unit test: כתוב→קרא→השווה |

---

## 8. שאלות עסקיות פתוחות

### 8.1 החלטות קיימות (ממתינות לאישור)

**D-04: פורמט Excel — עמודות, סדר, טיפוסים**
- **שאלה:** האם קיימת תבנית Excel במעבדה?
- **אפשרויות:**
  1. שימוש בתבנית קיימת (מומלץ)
  2. יצירת תבנית חדשה
  3. תבנית זמנית עם סימון ברור
- **חוסם:** TASK-018 (Excel Export)
- **עדיפות:** 🔴 HIGH

**D-05: ייצוג N מרכזיים ל-M התחייבויות**
- **שאלה:** איך לייצג יחסי N:M ב-Excel?
- **אפשרויות:**
  1. שורה אחת להתחייבות, ערכים מרובים עם `;` delimiter (המלצה)
  2. עמודות נוספות (`central_1`, `central_2`, ...)
  3. שורות נפרדות לכל צירוף (מכפלה קרטזית, **לא מומלץ**)
  4. גיליון נפרד לקשרים
- **חוסם:** TASK-018 (Excel Export)
- **עדיפות:** 🔴 HIGH

**D-13: בדיקה ללא מספר התחייבות**
- **שאלה:** מה לעשות עם TestRecord שאין לו CommitmentRecords?
- **אפשרויות:**
  1. לא ליצור שורת Excel (שמירה פנימית בלבד)
  2. ייצוא עם `commitment_number` ריק
  3. גיליון נפרד לחריגים
- **חוסם:** TASK-018 (Excel Export)
- **עדיפות:** 🔴 HIGH

**D-06: קיבוץ עמודים לטופס**
- **שאלה:** איך לזהות עמודים של אותה בדיקה?
- **אפשרויות:**
  1. אלגוריתם שמרני: כל עמוד = טופס (ברירת מחדל נוכחית)
  2. קיבוץ אוטומטי לפי barcode/מספר מרכזי
  3. UI לאיחוד ידני
- **חוסם:** Multi-page Grouping (אם נדרש)
- **עדיפות:** 🟡 MEDIUM

### 8.2 החלטות חדשות (לא מתועדות ב-DECISIONS.md)

**NEW-01: מדיניות relation_status**
- **שאלה:** מתי CommitmentRecord נחשב `related` לעומת `ambiguous` לעומת `unknown`?
- **מצב נוכחי:** הכל `ambiguous` כברירת מחדל
- **הצעה:**
  - `related`: יש ראיה חזקה (קרבה במסמך, barcode זהה, זיהוי חד-משמעי)
  - `ambiguous`: כמה אפשרויות, דורש בחירה אנושית
  - `unknown`: לא ניתן לקבוע (לא מסומן במסמך)
- **השפעה:** סיווג, export blocking, UI
- **עדיHIGH

**NEW-02: טיפול ב-orphaned commitments**
- **שאלה:** מה לעשות עם CommitmentRecord עם test_id לא קיים?
- **אפשרויות:**
  1. הצג ב-UI כשגיאה, אפשר שיוך ידני (endpoint קיים)
  2. התעלם, רק log warning
  3. חסום batch עד לפתרון
- **עדיפות:** 🟡 MEDIUM

**NEW-03: אישור שדה ריק — אילו שדות?**
- **שאלה:** אילו שדות מותר לאשר כריקים באופן לגיטימי?
- **מצב נוכחי:** כל שדה ניתן לאשר (D-17), ממתין להבהרה מהמעבדה
- **צריך החלטה:** רשימה מפורשת של שדות שמותר לאשר ריקים
- **עדיפות:** 🟡 MEDIUM

**NEW-04: Excel — טיפול ברשימות ארוכות**
- **שאלה:** מה עושים עם 10+ מספרים מרכזיים באותה בדיקה?
- **אפשרויות:**
  1. delimiter ארוך (`;` separated)
  2. truncate ברשימה + עמודת הערה
  3. שורות נפרדות (ייצוג נורמלי לא מנורמל)
- **עדי (לא נפוץ?)

**NEW-05: Excel — טיפול בשדות עם newlines/quotes**
- **שאלה:** מה קורה אם `sender` או שדה אחר מכיל `,` או `"` או `\n`?
- **פתרון טכני:** openpyxl מטפל אוטומטית, אבל צריך בדיקה
- **עדיפות:** 🟢 LOW

---

## 9. המלצות

### 9.1 המלצות טכניות (ללא שינוי קוד)

1. **יישור מדיניות relation_status:**
   - לתעד החלטה: מתי `related`, מתי `ambiguous`, מתי `unknown`
   - לשנות ברירת מחדל ב-Gemini prompt או post-processing
   - ליישר Classification ו-Export Blocking

2. **מימוש RelationshipEditor UI:**
   - Endpoint קיים: `/commitments/{cid}/resolve`
   - מאפשר עדכון `central_number_refs` ו-`relation_status`
   - חיוני לפתרון `ambiguous` commitments

3. **טיפול ב-orphaned commitments:**
   - הצג ב-UI (גיליון נפרד או אזהרה)
   - אפשר שיוך ידני (endpoint קיים: `/commitments/{cid}/assign/{test_id}`)

4. **Excel security hardening:**
   - Formula injection prevention
   - Roundtrip testing (אפסים מובילים)
   - בדיקת ערכים מיוחדים (`,`, `"`, newlines)

5. **תיעוד תרחישי קצה:**
   - הוסף דוגמאות לתיעוד המערכת
   - Golden dataset עם multi-value cases
   - בדיקות regression לכל תרחיש

### 9.2 המלצות עסקיות (דורשות אישור)

1. **לפתור D-04, D-05, D-13:**
   - בלי אלו, Excel Export לא יכול להיות סופי
   - להשתמש בתבנית זמנית רק אם המעבדה מאשרת

2. **לקבוע מדיניות relation_status:**
   - NEW-01 היא קריטית לתפקוד נכון
   - להחליט: חוסם export או לא?

3. **לבדוק תדירות multi-page forms:**
   - אם נפוץ → צריך קיבוץ
   - אם נדיר → אפשר לדחות

4. **לאמת שדות חובה עם המעבדה:**
   - האם `commitment_number` חובה? (כרגע לא)
   - אילו שדות מותר לאשר ריקים?

---

## 10. סיכום

### 10.1 המודל הקיים

**חוזקות:**
- תומך ב-N:M באופן טבעי (`central_numbers[]`, `central_number_refs[]`, `commitment_ids[]`)
- הפרדה בין raw/normalized/reviewed
- מעקב אחר extraction ו-review state
- endpoints לפתרון קשרים (קיימים אך לא מיושמים ב-UI)

**חולשות:**
- ברירת מחדל `ambiguous` יוצרת רוויה של false positives
- חסר UI לפתרון קשרים
- orphaned commitments לא מטופלים ב-UI
- החלטות עסקיות פתוחות (D-04, D-05, D-13) חוסמות ייצוא סופי

### 10.2 מה נדרש להכרעה

**קריטי (חוסם MVP):**
- D-04: פורמט Excel (עמודות, סדר)
- D-05: ייצוג N:M (delimiter? שורות? עמודות?)
- D-13: טיפול ב-Test ללא Commitment
- NEW-01: מדיניות relation_status

**חשוב (משפר איכות):**
- NEW-02: טיפול ב-orphans
- NEW-03: רשימת שדות שמותר לאשר ריקים
- D-06: קיבוץ עמודים (אם נפוץ)

**נחמד (ניתן לדחות):**
- NEW-04: רשימות ארוכות
- NEW-05: ערכים מיוחדים ב-Excel

### 10.3 צעדים הבאים

1. **סקירה עם בעלת הפרויקט:** להציג מסמך זה ולקבל החלטות על D-04, D-05, D-13, NEW-01
2. **עדכון DECISIONS.md:** לתעד החלטות חדשות
3. **תכנון משימות:** אחרי אישור החלטות, לעדכן tasks.md עם משימות מימוש
4. **מימוש פערים:** RelationshipEditor, OrphanHandler, ExcelSecurityHardening

---

**סטטוס:** FOR REVIEW  
**גרסה:** 1.0  
**תאריך:** 2026-10-19  
**מחבר:** Business Analyst, Data Architect, Healthcare Workflow Specialist (Kiro Agent)
