/**
 * Hebrew display mappings (display only).
 *
 * Pure helpers that turn existing server codes / statuses / error shapes into
 * Hebrew text for the user. They never change server responses, status values
 * or error handling - callers keep using the raw values for logic.
 */
import { getFieldLabel } from '../features/review/utils/editPermissions';

export type ErrorContext =
  | 'upload'
  | 'startProcessing'
  | 'export'
  | 'loadBatch'
  | 'updateField'
  | 'assign'
  | 'resolve';

const FALLBACK_BY_CONTEXT: Record<ErrorContext, string> = {
  upload: 'ההעלאה לא הצליחה. נסו שוב.',
  startProcessing: 'לא ניתן היה להתחיל את העיבוד. נסו שוב.',
  export: 'הורדת הקובץ לא הצליחה. נסו שוב.',
  loadBatch: 'לא ניתן היה לטעון את הנתונים. רעננו את הדף ונסו שוב.',
  updateField: 'התיקון לא נשמר. נסו שוב.',
  assign: 'הפעולה לא הושלמה. נסו שוב.',
  resolve: 'הפעולה לא הושלמה. נסו שוב.',
};

const NO_CONNECTION = 'אין חיבור לשרת. בדקו שהשרת פועל ונסו שוב.';
const BATCH_NOT_FOUND = 'קבוצת המסמכים לא נמצאה או שטרם עובדה.';

/** Extract a plain string from a FastAPI `detail` (string | {message} | array). */
function detailToText(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const msg = (detail as { message?: unknown }).message;
    if (typeof msg === 'string') return msg;
  }
  return '';
}

/**
 * Hebrew message for a failed request, keyed on HTTP status and known detail text.
 * Unknown cases fall back to a generic Hebrew message (no guessing of the cause).
 */
export function getErrorMessage(err: any, context: ErrorContext): string {
  const fallback = FALLBACK_BY_CONTEXT[context];
  const response = err?.response;

  if (!response) {
    if (err?.code === 'ECONNABORTED' || err?.code === 'ERR_NETWORK' || err?.message === 'Network Error') {
      return NO_CONNECTION;
    }
    return fallback;
  }

  const status: number = response.status;
  const rawDetail = response.data?.detail;
  const text = detailToText(rawDetail);

  if (context === 'upload') {
    if (status === 413 || /too large/i.test(text)) {
      const name = text.match(/File (.+?) too large/i)?.[1];
      const max = text.match(/Maximum:\s*(\d+)\s*MB/i)?.[1];
      if (name && max) return `הקובץ ${name} גדול מדי. הגודל המרבי הוא ${max}MB.`;
      return 'אחד הקבצים גדול מדי. בדקו את הגודל המרבי המותר ונסו שוב.';
    }
    if (/too many files/i.test(text)) {
      const max = text.match(/Maximum:\s*(\d+)/i)?.[1];
      return max
        ? `נבחרו יותר מדי קבצים. אפשר להעלות עד ${max} קבצים בכל פעם.`
        : 'נבחרו יותר מדי קבצים. הקטינו את מספר הקבצים ונסו שוב.';
    }
    if (/invalid file type/i.test(text)) {
      return 'סוג הקובץ אינו נתמך. אפשר להעלות PDF, PNG או JPEG.';
    }
    if (/does not match declared type/i.test(text)) {
      const name = text.match(/File (.+?) content/i)?.[1];
      return name
        ? `תוכן הקובץ ${name} אינו תואם לסוג שלו. בדקו שהקובץ תקין.`
        : 'תוכן אחד הקבצים אינו תואם לסוג שלו. בדקו שהקבצים תקינים.';
    }
    return fallback;
  }

  if (context === 'startProcessing') {
    if (status === 409) return 'העיבוד של קבוצת מסמכים זו כבר מתבצע.';
    if (status === 404) return 'קבוצת המסמכים לא נמצאה. חזרו להעלאת מסמכים.';
    return fallback;
  }

  if (context === 'export') {
    if (status === 400 && /export blocked/i.test(text)) {
      let message = 'הייצוא חסום: יש שדות שדורשים בדיקה.';
      const records = rawDetail && typeof rawDetail === 'object' ? (rawDetail as any).problematic_records : null;
      if (Array.isArray(records) && records.length > 0) {
        const lines = records.map((r: any) => {
          const fields = Array.isArray(r?.issues) ? r.issues.map((f: string) => getFieldLabel(f)).join(', ') : '';
          return `טופס ${r?.test_id ?? ''}: ${fields}`;
        });
        message += '\n' + lines.join('\n');
      }
      return message;
    }
    if (status === 400) return 'הייצוא חסום: יש פריטים שדורשים טיפול לפני ההורדה.';
    if (status === 404) return BATCH_NOT_FOUND;
    return fallback;
  }

  if (context === 'updateField') {
    if (status === 403) return 'אי אפשר לתקן שדה שלא זוהתה בו בעיה.';
    if (status === 400) {
      if (/cannot be set to empty/i.test(text)) return 'שדה חובה. לא ניתן להשאיר אותו ריק.';
      if (/cannot be confirmed empty/i.test(text)) return 'לא ניתן לאשר שדה זה כריק.';
      if (/does not exist/i.test(text)) return 'השדה אינו קיים.';
      return fallback;
    }
    if (status === 404) {
      if (/test record/i.test(text)) return 'הטופס לא נמצא.';
      return BATCH_NOT_FOUND;
    }
    return fallback;
  }

  if (context === 'loadBatch') {
    if (status === 404) return 'קבוצת המסמכים לא נמצאה.';
    return fallback;
  }

  // assign / resolve
  if (status === 404) return 'ההתחייבות, הטופס או קבוצת המסמכים לא נמצאו.';
  return fallback;
}

const EXPORT_BLOCKER_FIELDS = [
  'patient_first_name',
  'patient_last_name',
  'patient_id_number',
  'sender',
  'received_date',
  'central_numbers',
];

/** Hebrew text for one export blocker string returned by `export-check`. */
export function formatExportBlocker(raw: string): string {
  const orphan = raw.match(/^orphaned_commitment:\s*(.+)$/);
  if (orphan) return `התחייבות ${orphan[1]} לא שויכה לאף טופס`;

  const ambiguous = raw.match(/^(.+?):\s*ambiguous_commitment_(.+)$/);
  if (ambiguous) return `טופס ${ambiguous[1]}: יש התחייבות שהקשר שלה לדגימות אינו ברור`;

  const fieldMatch = raw.match(/^(.+?):\s*(\w+)$/);
  if (fieldMatch && EXPORT_BLOCKER_FIELDS.includes(fieldMatch[2])) {
    return `טופס ${fieldMatch[1]}: השדה „${getFieldLabel(fieldMatch[2])}” דורש בדיקה או תיקון`;
  }

  // Unknown blocker: still shown (and still blocks) with a generic Hebrew text; the cause is not guessed.
  return 'יש פריט שחוסם את ההורדה ודורש טיפול. אם הוא לא ברור, בדקו את הטפסים והקשרים במסך הבדיקה.';
}

/** Hebrew label for a batch status (display only). */
export function getBatchStatusLabel(status: string): string {
  switch (status) {
    case 'uploaded':
      return 'הועלתה, טרם עובדה';
    case 'queued':
      return 'ממתין לעיבוד';
    case 'processing':
      return 'העיבוד מתבצע';
    case 'completed':
      return 'העיבוד הסתיים';
    case 'completed_with_errors':
      return 'העיבוד הסתיים עם שגיאות במסמכים מסוימים';
    case 'failed':
      return 'העיבוד נכשל';
    case 'quota_exhausted':
      return 'מכסת השימוש בשירות Gemini מוצתה';
    default:
      return 'מצב לא מוכר';
  }
}

/** Display label for the (already Hebrew) record_status returned by the server. */
export function getRecordStatusLabel(status: string): string {
  switch (status) {
    case 'תקין':
      return 'לא נמצאו התראות';
    case 'דורש השלמה':
      return 'דורש השלמה ידנית';
    default:
      // Server sends Hebrew statuses (e.g. "לא תקין", "דורש בדיקה"); show those as is.
      // "-" is the placeholder for a missing status. Anything else is not recognized.
      return status === '-' || /[\u0590-\u05FF]/.test(status) ? status : 'מצב לא מוכר';
  }
}

/** Hebrew label for a relationship status (explicit/inferred/unresolved_relationship/none). */
export function getRelationshipStatusLabel(status: string): string {
  if (status === 'explicit') return 'קשר מפורש';
  if (status === 'inferred') return 'קשר שנקבע אוטומטית';
  if (status === 'unresolved_relationship') return 'קשר שטרם נפתר';
  if (status === 'none') return 'לא משויכת';
  return 'קשר לא ברור';
}

/** Hebrew label for the form segmentation method. */
export function getSegmentationLabel(method: string): string {
  if (method === 'page_notation') return 'זוהה לפי סימון עמודים';
  if (method === 'heuristic') return 'זוהה אוטומטית לפי מבנה העמודים';
  return 'עמוד יחיד';
}

/** Hebrew label for server health status. */
export function getHealthStatusLabel(status: string): string {
  if (status === 'healthy') return 'תקין';
  if (status === 'unhealthy') return 'לא תקין';
  return 'מצב לא מוכר';
}
