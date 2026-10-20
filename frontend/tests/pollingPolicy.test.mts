// Run with: node --test tests/pollingPolicy.test.mts   (Node >= 22.18 strips types natively; no extra dependencies)
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  decidePoll,
  describeBatchFailure,
  MAX_CONSECUTIVE_POLL_ERRORS,
  MAX_POLL_DURATION_MS,
} from '../src/features/workflow/pollingPolicy.ts';

const ctx = (over = {}) => ({ startedAt: 0, now: 1000, consecutiveErrors: 0, ...over });

// Shape of the real persisted batch from the incident: every page ended in HTTP 503/504.
const failedBatch = {
  status: 'failed',
  errors: [
    { document_id: 'doc_x', page_index: 0, error: 'Gemini endpoint returned HTTP 504', error_code: 'provider_unavailable' },
    { document_id: 'doc_x', page_index: 1, error: 'Gemini endpoint returned HTTP 504', error_code: 'provider_unavailable' },
  ],
};

test('keeps waiting while the batch is queued or processing', () => {
  assert.deepEqual(decidePoll({ status: 'processing' }, ctx()), { action: 'continue' });
  assert.deepEqual(decidePoll({ status: 'queued' }, ctx()), { action: 'continue' });
});

test('completed and completed_with_errors open the review screen', () => {
  assert.deepEqual(decidePoll({ status: 'completed' }, ctx()), { action: 'review' });
  assert.deepEqual(decidePoll({ status: 'completed_with_errors' }, ctx()), { action: 'review' });
});

test('a failed batch surfaces the persisted provider error instead of polling forever', () => {
  const decision = decidePoll(failedBatch, ctx());
  assert.equal(decision.action, 'fail');
  assert.ok(decision.action === 'fail' && decision.goToReview);
  assert.match((decision as { message: string }).message, /provider_unavailable: Gemini endpoint returned HTTP 504 \(page 1\) \[\+1 more\]/);
});

test('quota exhaustion is terminal', () => {
  const decision = decidePoll({ status: 'quota_exhausted', errors: [] }, ctx());
  assert.equal(decision.action, 'fail');
});

test('a batch still reported as processing is abandoned after the maximum duration', () => {
  const decision = decidePoll({ status: 'processing' }, ctx({ now: MAX_POLL_DURATION_MS + 1 }));
  assert.equal(decision.action, 'fail');
  assert.ok(decision.action === 'fail' && !decision.goToReview);
});

test('an unexpected uploaded status cannot be polled forever either', () => {
  assert.equal(decidePoll({ status: 'uploaded' }, ctx()).action, 'continue');
  assert.equal(decidePoll({ status: 'uploaded' }, ctx({ now: MAX_POLL_DURATION_MS + 1 })).action, 'fail');
});

test('tolerates a few request errors, then reports lost contact', () => {
  assert.equal(decidePoll(null, ctx({ consecutiveErrors: MAX_CONSECUTIVE_POLL_ERRORS - 1 })).action, 'continue');
  const decision = decidePoll(null, ctx({ consecutiveErrors: MAX_CONSECUTIVE_POLL_ERRORS }));
  assert.equal(decision.action, 'fail');
  assert.match((decision as { message: string }).message, /Lost contact/);
});

test('describeBatchFailure falls back when no error was persisted', () => {
  assert.equal(describeBatchFailure(undefined, 'Processing failed.'), 'Processing failed.');
  assert.equal(describeBatchFailure([], 'Processing failed.'), 'Processing failed.');
});
