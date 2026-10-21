// Run with: npm run test:evidence   (Node >= 22.18 strips TypeScript types natively; no extra dependencies)
import test from 'node:test';
import assert from 'node:assert/strict';
import { exportableCommitmentCount } from '../src/features/review/utils/evidence.ts';

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
