# מסמך מסירה לפריסה בענן (Render + Supabase) - שלב Staging

מסמך זה מיועד למי שיש לה הרשאות Render על הריפו ולא ראתה את הקוד. אין להדביק סודות במסמך זה או בצ'אט. כל הערכים להלן הם placeholders.
פירוט טכני מלא: `docs/deploy-handoff-findings.md`.

## 1. סיכום ומצב מוכנות

- `render.yaml` ב-`main`: שני השירותים (`virology-lab-staging-backend`, `virology-lab-staging-frontend`) על `branch: main`. אין חסם. (אומת: הוולידטור `python scripts\validate_render_preparation.py` עבר, אך הוא לא בודק את שם הbranch - נבדק ידנית בקובץ.)
- Backend: Docker, פלאן Free, אזור frankfurt, `healthCheckPath: /ready`, `autoDeployTrigger: "off"` (פריסה ידנית בלבד).
- Frontend: אתר סטטי, `npm ci && npm run build`, `autoDeployTrigger: "off"`.
- `DEPLOYMENT_MODE=staging-real`: דורש Gemini אמיתי (`DEMO_MODE=false`), דורש אימות Basic (`API_USERNAME` + `API_PASSWORD` באורך 16 תווים לפחות), ו-CORS מדויק. שירות שמוגדר לא נכון לא יעלה.
- בנייה של ה-frontend הצליחה מקומית. ה-Docker של ה-backend לא נבנה מקומית (Docker daemon כבוי) - הבנייה הראשונה ב-Render היא הבדיקה האמיתית.
- אין חסם קשה. נותרו אימותים שאפשריים רק אחרי פריסה (סעיף 8).
- מותר רק מסמכים סינתטיים/מעוקרים או מסמכים שאושרו כלא רגישים. אסור מטופלים אמיתיים. (המסמכים בפרויקט Supabase הקיים הם דוגמאות הדגמה מעוקרות.)

## 2. דרישות מקדימות

- גישה (דרך בעל הפרויקט) לערכי Supabase של הפרויקט הקיים `virology-lab`: `SUPABASE_URL` והמפתח הסודי של ה-backend. אין ליצור פרויקט חדש.
- מפתח Gemini ל-staging ושם מודל תקף (`GEMINI_MODEL`). וודאו מראש את מגבלות המפתח (בקשות לדקה/יום).
- הרשאות Render ליצירת Blueprint מהריפו.
- מסמכי בדיקה סינתטיים: PDF, PNG, JPEG, קובץ גדול מ-10MB, ו-4 קבצים.
- מחולל סיסמה: `API_PASSWORD` לפחות 16 תווים.

## 3. Supabase - שימוש בפרויקט הקיים (בוצע ואומת ידנית על ידי בעל הפרויקט)

הפרויקט הקיים `virology-lab` כבר מוכן ונבדק ידנית. **אין ליצור פרויקט Supabase נוסף, אין להריץ את `supabase/staging_setup.sql` על הפרויקט הקיים, ואין ליצור מחדש את הטבלה או ה-bucket.**

מצב מאומת (ידנית):
- הטבלה `public.batches` קיימת עם ארבע העמודות הצפויות (`batch_id`, `batch_data`, `created_at`, `updated_at`).
- ה-bucket הפרטי `virology-lab-uploads` קיים.
- קיים מפתח backend סודי (service/secret key).
- כל המסמכים הם דוגמאות הדגמה מעוקרות, לא רשומות מטופלים אמיתיים.

מה עושים ב-Render:
1. מבקשים מבעל פרויקט Supabase (בערוץ מאובטח, לא בצ'אט ציבורי ולא בקבצים) את הערכים: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (המפתח הסודי של ה-backend), ו-`SUPABASE_BUCKET_NAME` = `virology-lab-uploads`.
2. מזינים אותם ישירות בדשבורד של Render בשירות ה-backend בלבד. לעולם לא ב-frontend, לא ב-`render.yaml`, לא ב-Git.
3. לא מוסיפים policies ל-`anon`/`authenticated`. ה-backend ניגש עם המפתח הסודי בלבד.
4. אימות אחרי הפריסה: `GET /ready` חייב להחזיר 200. ה-backend בודק בעצמו שהטבלה נגישה ושה-bucket פרטי; אם ה-bucket ציבורי, `/ready` יחזיר 503 והשירות יסרב לעלות.

הערה על `supabase/staging_setup.sql`: קובץ **תיעוד בלבד** לסביבה חדשה ונקייה. **NOT FOR EXECUTION על הפרויקט הקיים.** בראש הקובץ מסומן הדבר במפורש.

## 4. שלבי Render צעד-אחר-צעד

1. Render Dashboard -> New -> Blueprint -> בחרו את הריפו, branch `main`. Render יקרא את `render.yaml`.
2. מלאו את משתני `sync:false` (טבלה בסעיף 5). עבור ה-backend: `GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET_NAME`, `API_USERNAME`, `API_PASSWORD`, `CORS_ORIGINS`.
   - `CORS_ORIGINS` חייב להיות מערך JSON, למשל `["https://<frontend-host>.onrender.com"]`. לא מחרוזת רגילה, לא מופרד בפסיקים, לא `*`, בלי `/` בסוף. פורמט שגוי מפיל את השירות באתחול.
   - בשלב הראשון, לפני שיש כתובת frontend, הזינו ערך זמני חוקי כמו `["https://placeholder.example.com"]`.
   - `SUPABASE_BUCKET_NAME` חובה למלא (ערך ריק לא יקבל את ברירת המחדל).
3. סדר פריסה (אין פריסה אוטומטית - לחצו Manual Deploy בכל שירות):
   1. Backend קודם. Manual Deploy -> Deploy latest commit. המתינו לסטטוס Live.
   2. העתיקו את כתובת ה-backend (`https://virology-lab-staging-backend.onrender.com` או הכתובת שהוקצתה).
   3. בשירות ה-frontend הגדירו `VITE_API_URL` = כתובת ה-backend המדויקת: `https://<backend-host>.onrender.com` (HTTPS, בלי נתיב, בלי `/` בסוף, בלי פרטי התחברות). זהו משתנה build-time: שינוי דורש Deploy מחדש של ה-frontend.
   4. Manual Deploy ל-frontend. העתיקו את כתובתו.
   5. חזרו ל-backend, עדכנו `CORS_ORIGINS` = `["https://<frontend-host>.onrender.com"]` (הכתובת המדויקת) ושמרו. השירות יופעל מחדש; אם לא, בצעו Manual Deploy.
4. בדיקת מוכנות: פתחו `https://<backend-host>/ready`. צפוי HTTP 200. אם 503 - ראו סעיף 9.
5. פתחו את ה-frontend והתחברו עם `API_USERNAME`/`API_PASSWORD`.
6. מומלץ: הגדירו `LOCAL_QUOTA_REQUESTS_PER_MINUTE` ו-`LOCAL_QUOTA_REQUESTS_PER_DAY` בדשבורד של ה-backend (ראו סעיף 5), אחרת ברירות המחדל (5 לדקה, 20 ליום) עלולות להיגמר באצווה אחת.
7. אל תפעילו מחדש ואל תפרסו בזמן שאצווה בעיבוד (סעיף 7).

## 5. טבלת משתני סביבה

| משתנה | שירות | חובה/אופציונלי | מקור הערך | סוד? |
|---|---|---|---|---|
| `DEPLOYMENT_MODE` = `staging-real` | backend | חובה (קבוע ב-render.yaml) | render.yaml | לא |
| `DEMO_MODE` = `false` | backend | חובה (קבוע) | render.yaml | לא |
| `GEMINI_API_KEY` = `<SET_IN_RENDER_DASHBOARD>` | backend | חובה | Google AI Studio / Cloud | כן |
| `GEMINI_MODEL` = `<SET_IN_RENDER_DASHBOARD>` | backend | חובה (לא ריק) | שם מודל תקף למפתח | לא |
| `HYBRID_ENGINE_ENABLED` = `false` | backend | קבוע | render.yaml | לא |
| `HYBRID_ENABLE_PREPROCESSING` = `false` | backend | קבוע | render.yaml | לא |
| `HYBRID_ENABLE_OCR` = `false` | backend | קבוע | render.yaml | לא |
| `HYBRID_ENABLE_HYBRID_VERIFICATION` = `false` | backend | קבוע | render.yaml | לא |
| `HYBRID_ENABLE_FOCUSED_RETRY` = `false` | backend | קבוע | render.yaml | לא |
| `MAX_FILE_SIZE_MB` = `10` | backend | קבוע | render.yaml | לא |
| `MAX_FILES_PER_BATCH` = `3` | backend | קבוע | render.yaml | לא |
| `MAX_PAGES_PER_DOCUMENT` = `10` | backend | קבוע | render.yaml | לא |
| `MAX_REQUEST_SIZE_MB` = `32` | backend | קבוע | render.yaml | לא |
| `MAX_IMAGE_PIXELS` = `12000000` | backend | קבוע | render.yaml | לא |
| `CONCURRENT_PROCESSING_BATCHES` = `1` | backend | קבוע | render.yaml | לא |
| `UPLOAD_REQUESTS_PER_MINUTE` = `6` | backend | קבוע | render.yaml | לא |
| `SUPABASE_URL` = `<SET_IN_RENDER_DASHBOARD>` | backend | חובה | Supabase -> Project Settings -> API | לא (אך לא לפרסם) |
| `SUPABASE_SERVICE_KEY` = `<SET_IN_RENDER_DASHBOARD>` | backend | חובה | Supabase service_role key | כן - קריטי |
| `SUPABASE_BUCKET_NAME` = `virology-lab-uploads` | backend | חובה | שם ה-bucket הפרטי הקיים ב-Supabase | לא |
| `API_USERNAME` = `<SET_IN_RENDER_DASHBOARD>` | backend | חובה | נבחר על ידכם | כן (מומלץ) |
| `API_PASSWORD` = `<SET_IN_RENDER_DASHBOARD>` | backend | חובה, 16+ תווים | מחולל סיסמאות | כן |
| `CORS_ORIGINS` = `["https://<frontend-host>.onrender.com"]` | backend | חובה, מערך JSON | כתובת ה-frontend המדויקת | לא |
| `LOCAL_QUOTA_REQUESTS_PER_MINUTE` = `<SET_IN_RENDER_DASHBOARD>` | backend | מומלץ (לא ב-render.yaml; ברירת מחדל 5) | מגבלת מפתח Gemini - לא מעל | לא |
| `LOCAL_QUOTA_REQUESTS_PER_DAY` = `<SET_IN_RENDER_DASHBOARD>` | backend | מומלץ (לא ב-render.yaml; ברירת מחדל 20) | מגבלת מפתח Gemini - לא מעל | לא |
| `VITE_DEPLOYMENT_MODE` = `staging` | frontend | חובה (קבוע) | render.yaml | לא |
| `VITE_API_URL` = `https://<backend-host>.onrender.com` | frontend | חובה (build-time) | כתובת ה-backend לאחר פריסה | לא |

הערות: אסור להגדיר משתני `VITE_*` נוספים (ה-build ייכשל בכוונה). מפתחות ו-service key לעולם לא ב-frontend.

## 6. תוכנית בדיקות end-to-end בענן

רק מסמכים סינתטיים. סמנו תוצאה לכל שורה.

1. `GET /ready` -> 200. `GET /api/session` בלי סיסמה -> 401.
2. אימות: ב-frontend ניסיון עם סיסמה שגויה -> חוזרים למסך כניסה. בלי Authorization כל נתיב `/api/...` -> 401.
3. PDF: העלאת PDF סינתטי (עד 10 עמודים, עד 10MB) -> עיבוד מסתיים, שדות מחולצים.
4. PNG: העלאה ועיבוד (התמונה מומרת ל-PDF בעמוד אחד).
5. JPEG: העלאה ועיבוד.
6. העלאה מרובה: 3 קבצים (`MAX_FILES_PER_BATCH`) באצווה אחת -> כולם מעובדים.
7. מגבלות: 4 קבצים -> 400; קובץ מעל 10MB -> 413; קובץ עם סיומת שאינה תואמת תוכן -> נדחה; PDF מוצפן -> נדחה.
8. מסך Review: עריכת שדה, אימות, דחיית מועמד; רעננו את הדף וודאו שהשינויים נשמרו.
9. ייצוא Excel: הורדה, פתיחה, בדיקת התאמה לנתוני ה-Review.
10. התמדה אחרי restart: בצעו Manual restart ל-backend (Render -> Manual Deploy / Restart) כשאין עיבוד פעיל. פתחו שוב את האצווה (batch id נשמר ב-localStorage): נתוני Review נשארים, תצוגת המסמך עובדת, ייצוא Excel מתבצע מחדש.
11. פרטיות bucket: ב-Supabase Dashboard העתיקו URL ציבורי של אובייקט (`https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>/<batch>/<doc>.pdf`) ופתחו בדפדפן ללא התחברות -> חייב להיכשל. בנוסף: קריאה ל-REST עם anon key ל-`/rest/v1/batches` חייבת להחזיר ריק/שגיאה.
12. מכסה: אם מתקבל "quota exhausted" - בדקו `LOCAL_QUOTA_*` ואת מגבלות המפתח.
13. זיכרון: PDF של 10 עמודים - עקבו בלוגי Render אחרי הפעלה מחדש/OOM.
14. בדיקת CORS: וידוא שהעלאה מה-frontend לא נחסמת בדפדפן.

## 7. מגבלת local_spool / filesystem זמני בפלאן Free

המערכת הקבצים ב-Render Free זמנית. מה נמצא עליה: מטמון `local_spool` (`/app/temp_storage/_verified_spool`), קובצי Excel זמניים, ותיקיית עיבוד ב-`/tmp`.

מה לא אובד (עמיד ב-Supabase): קבצי המקור שהועלו (bucket פרטי), כל נתוני האצווה, תוצאות החילוץ ועריכות ה-Review (`batches.batch_data`). ה-spool הוא מטמון בלבד; בהיעדרו הקוד מוריד מ-Supabase ומאמת SHA-256. ייצוא Excel נוצר מחדש לפי דרישה מהנתונים השמורים.

מה אובד: עבודה שרצה בזיכרון - אצווה שנמצאת בעיבוד בעת restart/פריסה/שינה (שינה של Free אחרי כ-15 דקות בלי תעבורה), מוני מכסת Gemini, ומוני rate limit. אצווה שנקטעה תישאר בסטטוס processing, ו-`process`/`retry-failed` יחזירו 409. דיווח "נקטע" מתקבל רק לאחר כ-32 דקות.

המלצה: לא לבצע restart, פריסה או שינוי משתנים בזמן עיבוד; להשאיר את הדפדפן פתוח בזמן עיבוד (ה-polling מחזיק את השירות ער); אם אצווה נקטעה - להעלות מחדש כאצווה חדשה. לעולם לא להגדיל ל-יותר ממופע אחד או יותר מ-worker אחד. זו מגבלה מקובלת ל-staging ולא חסם. לייצור נדרש עיבוד עמיד (מחוץ להיקף).

## 8. מה ניתן לאמת רק אחרי פריסה

- שה-Docker build של ה-backend עובד ב-Render (Python 3.13, חבילות apt/pip) ושהשירות עולה.
- תקפות מפתח Gemini, זמינות המודל והמכסה; חילוץ אמיתי מ-PDF/PNG/JPEG.
- מעגל Supabase מלא: העלאה, הורדה, נעילה אופטימית על `updated_at` בעמודה האמיתית, וחסימת anon ב-RLS.
- צריכת זיכרון בפלאן Free (512MB) ביעד של 10 עמודים.
- התנהגות אחרי שינה, CORS אמיתי עם Authorization, וכותרות אבטחה/HSTS בדומיינים האמיתיים.

## 9. פתרון תקלות נפוצות

| תסמין | סיבה סבירה | פעולה |
|---|---|---|
| Deploy של backend נכשל באתחול עם שגיאת הגדרה | חסר `GEMINI_API_KEY`/`GEMINI_MODEL`, `API_PASSWORD` קצר מ-16, `DEMO_MODE` לא false | בדקו משתנים בדשבורד ובלוג |
| קריסה בטעינת הגדרות (settings error) | `CORS_ORIGINS` לא מערך JSON | `["https://host"]`, בלי `/` ובלי `*` |
| `/ready` מחזיר 503 | bucket ציבורי / שם bucket שגוי / טבלת `batches` חסרה / URL או key שגויים | אל תריצו SQL על הפרויקט הקיים; וודאו מול בעל הפרויקט שה-bucket Private ושהטבלה קיימת, ובדקו `SUPABASE_*` |
| ה-frontend פונה ל-localhost:8000 | `VITE_API_URL` לא הוגדר לפני ה-build | הגדירו ובצעו Deploy מחדש ל-frontend |
| ה-build של ה-frontend נכשל | `VITE_API_URL` לא HTTPS origin מדויק, או משתנה `VITE_*` זר | תקנו את הערך |
| שגיאת CORS בדפדפן | `CORS_ORIGINS` לא תואם בדיוק את כתובת ה-frontend | עדכנו ובצעו restart |
| 401 תמידי | שם משתמש/סיסמה לא תואמים | בדקו `API_USERNAME`/`API_PASSWORD` |
| 429 בהעלאה | `UPLOAD_REQUESTS_PER_MINUTE` או קיבולת עיבוד | המתינו ונסו שוב |
| "quota exhausted" | `LOCAL_QUOTA_*` נמוך או מגבלת Gemini | התאימו למגבלות המפתח, המונים מתאפסים ב-restart/חצות UTC |
| אצווה תקועה ב-processing | restart באמצע עיבוד | העלו מחדש |
| תגובה ראשונה איטית | התעוררות משינה | המתינו כדקה |
| הפעלה מחדש בלולאה / OOM | זיכרון 512MB | קבצים קטנים יותר, או פלאן גבוה יותר |

## 10. Rollback

- אין פריסה אוטומטית, לכן שום דבר לא ישתנה בלי Manual Deploy.
- כשל בפריסה חדשה: Render לא מחליף את הגרסה הקודמת אם האתחול נכשל. אפשר גם Render -> Events/Deploys -> Rollback לפריסה קודמת.
- Frontend: Rollback לפריסה קודמת, או Deploy מחדש אחרי תיקון `VITE_API_URL`.
- שינוי משתנה שגוי: החזירו את הערך הקודם ובצעו Manual Deploy.
- חירום: Suspend לשני השירותים. נתוני Supabase נשארים; הסירו את מפתח ה-service (Rotate) אם יש חשש לחשיפה.
- אין למחוק נתונים או את ה-bucket ב-Supabase כחלק מ-rollback.
