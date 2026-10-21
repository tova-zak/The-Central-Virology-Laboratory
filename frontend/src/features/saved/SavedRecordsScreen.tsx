/**
 * Saved records ("מסמכים שמורים"): history + search + status filters.
 * Data comes only from the authenticated backend (never localStorage). Search uses POST so
 * patient identifiers never appear in URLs.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { searchSavedBatches } from '../../services/api';
import type { SavedBatchSearchResponse, SavedStatusFilter } from '../../services/api';
import { STATUS_FILTERS, STATUS_LABEL, formatSavedDate } from './savedStatus';
import './SavedRecordsScreen.css';

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 350;

interface Props {
  onOpenBatch: (batchId: string) => void;
}

export const SavedRecordsScreen: React.FC<Props> = ({ onOpenBatch }) => {
  const [queryInput, setQueryInput] = useState('');
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<SavedStatusFilter>('all');
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<SavedBatchSearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  // Debounce the typed query; any new query/filter returns to the first page.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(queryInput.trim());
      setOffset(0);
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [queryInput]);

  const load = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(false);
    try {
      const result = await searchSavedBatches({ query, status, limit: PAGE_SIZE, offset }, controller.signal);
      if (!controller.signal.aborted) setData(result);
    } catch {
      if (!controller.signal.aborted) setError(true);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [query, status, offset]);

  useEffect(() => {
    load();
    return () => abortRef.current?.abort();
  }, [load, reloadKey]);

  const counts = data?.status_counts;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = offset + items.length;
  const searching = query !== '' || status !== 'all';

  return (
    <section className="saved-records" aria-labelledby="saved-records-title">
      <h2 id="saved-records-title">מסמכים שמורים</h2>
      <p className="saved-hint">אצוות שנשמרו במערכת. אפשר לחפש, לסנן ולפתוח אצווה להמשך בדיקה ואישור.</p>

      <div className="saved-search">
        <label htmlFor="saved-search-input">חיפוש ברשומות שמורות</label>
        <input
          id="saved-search-input"
          type="search"
          value={queryInput}
          onChange={e => setQueryInput(e.target.value)}
          placeholder="שם מטופל, ת״ז, מספר מרכזי, מספר התחייבות, גורם שולח או מזהה אצווה"
          maxLength={100}
          autoComplete="off"
        />
      </div>

      <div className="saved-filters" role="group" aria-label="סינון לפי סטטוס">
        {STATUS_FILTERS.map(f => (
          <button
            key={f.value}
            type="button"
            className={`saved-chip${status === f.value ? ' active' : ''}`}
            aria-pressed={status === f.value}
            onClick={() => { setStatus(f.value); setOffset(0); }}
          >
            {f.label}{counts ? <> (<bdi dir="ltr">{counts[f.value]}</bdi>)</> : null}
          </button>
        ))}
      </div>

      <p className="saved-count" role="status" aria-live="polite">
        {loading ? 'טוען רשומות שמורות…' : error ? '' : total === 0 ? 'לא נמצאו תוצאות' : (
          <>מציג <bdi dir="ltr">{from}–{to}</bdi> מתוך <bdi dir="ltr">{total}</bdi> אצוות</>
        )}
      </p>

      {error && (
        <div className="error-box" role="alert">
          <p>לא ניתן לטעון את הרשומות השמורות כרגע.</p>
          <button type="button" className="button-secondary" onClick={() => setReloadKey(k => k + 1)}>נסו שוב</button>
        </div>
      )}

      {!error && !loading && total === 0 && (
        <div className="saved-empty">
          <p>{searching ? 'לא נמצאו אצוות התואמות לחיפוש או לסינון.' : 'עדיין לא נשמרו אצוות במערכת.'}</p>
        </div>
      )}

      {!error && items.length > 0 && (
        <ul className="saved-list" aria-busy={loading}>
          {items.map(item => (
            <li key={item.batch_id} className="saved-card">
              <div className="saved-card-main">
                <div className="saved-card-head">
                  <span className="saved-id"><bdi dir="ltr">{item.batch_id}</bdi></span>
                  <span className={`saved-badge saved-badge-${item.batch_status}`}>{STATUS_LABEL[item.batch_status]}</span>
                </div>
                <dl className="saved-meta">
                  <div><dt>נשמר</dt><dd><bdi dir="ltr">{formatSavedDate(item.created_at)}</bdi></dd></div>
                  <div><dt>מסמכים</dt><dd><bdi dir="ltr">{item.document_count}</bdi></dd></div>
                  <div><dt>רשומות</dt><dd><bdi dir="ltr">{item.record_count}</bdi></dd></div>
                  <div><dt>אושרו</dt><dd><bdi dir="ltr">{item.approved_count}/{item.record_count}</bdi></dd></div>
                  {item.needs_correction_count > 0 && (
                    <div><dt>דורשות תיקון</dt><dd><bdi dir="ltr">{item.needs_correction_count}</bdi></dd></div>
                  )}
                  {item.pending_count > 0 && (
                    <div><dt>ממתינות</dt><dd><bdi dir="ltr">{item.pending_count}</bdi></dd></div>
                  )}
                </dl>
                {item.senders.length > 0 && <p className="saved-senders">{item.senders.join(' · ')}</p>}
              </div>
              <button type="button" className="button-primary" onClick={() => onOpenBatch(item.batch_id)}>
                פתיחה להמשך בדיקה
              </button>
            </li>
          ))}
        </ul>
      )}

      {!error && total > PAGE_SIZE && (
        <div className="saved-pager">
          <button type="button" className="button-secondary" disabled={loading || offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>הקודם</button>
          <button type="button" className="button-secondary" disabled={loading || !data?.has_more}
            onClick={() => setOffset(offset + PAGE_SIZE)}>הבא</button>
        </div>
      )}
    </section>
  );
};
