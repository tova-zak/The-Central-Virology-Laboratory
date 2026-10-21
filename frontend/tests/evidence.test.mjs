// Run with: npm run test:evidence   (Node >= 22.18 strips TypeScript types natively; no extra dependencies)
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  canApproveAsIs,
  exportableCommitmentCount,
  isCenturyInferredDate,
  validateEditedValue,
} from '../src/features/review/utils/evidence.ts';

const extra = (value, status) => ({ value, reason: 'multiple_commitments_on_page', status });

test('single commitment number exports one row', () => {
  assert.equal(exportableCommitmentCount({ raw_value: '730578626' }), 1);
  assert.equal(exportableCommitmentCount(null), 1);
});

test('pending candidates add one row each, even after approval', () => {
  const field = {
    raw_value: '730578626',
    review_state: 'human_verified',
    candidates: [extra('730578627', 'pending'), extra('730578628')],
  };
  assert.equal(exportableCommitmentCount(field), 3);
});

test('rejected, duplicate and unrelated candidates are not counted', () => {
  const field = {
    raw_value: '730578626',
    candidates: [
      extra('730578627', 'rejected'),
      extra('730578626', 'pending'),
      { value: '111', reason: 'ambiguous_label', status: 'pending' },
    ],
  };
  assert.equal(exportableCommitmentCount(field), 1);
});

test('reviewed value takes precedence; empty value exports a single empty row', () => {
  assert.equal(
    exportableCommitmentCount({ raw_value: '1', reviewed_value: '2', candidates: [extra('3')] }),
    2,
  );
  assert.equal(exportableCommitmentCount({ raw_value: '1', reviewed_value: '', candidates: [extra('3')] }), 1);
});

// 2000+YY policy: a two-digit year is read as 20YY, flagged as inferred, and only a human action clears the flag.
test('reviewer-typed dates: 4-digit and 2-digit years accepted, incomplete rejected', () => {
  assert.equal(validateEditedValue('received_date', '15/03/2024'), null);
  assert.equal(validateEditedValue('received_date', '15/03/24'), null);
  assert.equal(validateEditedValue('received_date', '2024-03-15'), null);
  assert.notEqual(validateEditedValue('received_date', '15/3'), null);
  assert.notEqual(validateEditedValue('received_date', '15/03/202'), null);
});

test('century-inferred detection by issue code, by message and by two-digit raw value', () => {
  assert.equal(isCenturyInferredDate({ raw_value: '15/03/2024', validation_issues: [{ code: 'century_inferred' }] }), true);
  assert.equal(
    isCenturyInferredDate({ raw_value: 'x', validation_issues: [{ message: 'Century inferred: 15/03/24 read as 15/03/2024 (20YY)' }] }),
    true,
  );
  assert.equal(isCenturyInferredDate({ raw_value: '15.03.24' }), true);
  assert.equal(isCenturyInferredDate({ raw_value: '15/03/2024' }), false);
});

test('a human-verified date is never shown as inferred', () => {
  assert.equal(
    isCenturyInferredDate({ raw_value: '15/03/24', review_state: 'human_verified', validation_issues: [{ code: 'century_inferred' }] }),
    false,
  );
});

test('approve as is: inferred date with 4-digit normalized value yes, incomplete date no', () => {
  assert.equal(canApproveAsIs('received_date', { raw_value: '15/03/24', normalized_value: '15/03/2024' }), true);
  assert.equal(canApproveAsIs('received_date', { raw_value: '15/03/24', normalized_value: '15/03/24' }), false);
  assert.equal(canApproveAsIs('received_date', { raw_value: 'abc' }), false);
  assert.equal(canApproveAsIs('sender', { raw_value: 'x' }), true);
});
