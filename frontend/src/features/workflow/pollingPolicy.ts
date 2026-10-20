/**
 * Pure polling policy for the processing screen.
 *
 * Every wait must end in something the user can see: results, or a clear error.
 * Kept free of React so it can be unit-tested with plain Node (see frontend/tests).
 */

export const POLL_INTERVAL_MS = 2500;
/** The backend hard batch deadline is 30 min (EXTRACTION_BATCH_DEADLINE_SECONDS); allow a margin. */
export const MAX_POLL_DURATION_MS = 35 * 60 * 1000;
export const MAX_CONSECUTIVE_POLL_ERRORS = 6;

export interface PollError {
  error?: string;
  error_code?: string;
  page_index?: number;
}

export interface PollSnapshot {
  status?: string;
  errors?: PollError[];
}

export interface PollContext {
  startedAt: number;
  now: number;
  consecutiveErrors: number;
}

export type PollDecision =
  | { action: 'continue' }
  | { action: 'review' }
  | { action: 'fail'; message: string; goToReview: boolean };

/** Human-readable reason built from the first persisted extraction error. */
export function describeBatchFailure(errors: PollError[] | undefined, fallback: string): string {
  const first = errors && errors.length > 0 ? errors[0] : undefined;
  if (!first || (!first.error && !first.error_code)) {
    return fallback;
  }
  const code = first.error_code ? `${first.error_code}: ` : '';
  const page = first.page_index !== undefined ? ` (page ${first.page_index + 1})` : '';
  const more = errors && errors.length > 1 ? ` [+${errors.length - 1} more]` : '';
  return `${fallback} ${code}${first.error ?? ''}${page}${more}`.trim();
}

/**
 * Decide what the poller should do after one attempt.
 * `snapshot` is null when the request itself failed (network/server error).
 */
export function decidePoll(snapshot: PollSnapshot | null, ctx: PollContext): PollDecision {
  if (snapshot === null) {
    if (ctx.consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) {
      return {
        action: 'fail',
        goToReview: false,
        message:
          'Lost contact with the server while waiting for processing. The batch may still be running; reload the page to check its status.',
      };
    }
  } else {
    switch (snapshot.status) {
      case 'completed':
      case 'completed_with_errors':
        return { action: 'review' };
      case 'failed':
        return { action: 'fail', goToReview: true, message: describeBatchFailure(snapshot.errors, 'Processing failed.') };
      case 'quota_exhausted':
        return { action: 'fail', goToReview: true, message: describeBatchFailure(snapshot.errors, 'Gemini quota exhausted.') };
      default:
        break;
    }
  }
  if (ctx.now - ctx.startedAt > MAX_POLL_DURATION_MS) {
    return {
      action: 'fail',
      goToReview: false,
      message:
        'Processing is taking longer than the allowed maximum. The server may be unavailable; reload the page to check the batch status, or upload again.',
    };
  }
  return { action: 'continue' };
}
