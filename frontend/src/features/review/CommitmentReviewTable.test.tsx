import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { CommitmentReviewTable, REVIEW_FIELDS } from './CommitmentReviewTable';

afterEach(cleanup);

function record(): any {
  return {
    commitment_record_id: 'review-record', form_id: 'doc_page_0', source_page: 1,
    relationship_status: 'inferred', final_review_token: 'current-token', final_review_confirmed: false,
    ...Object.fromEntries(REVIEW_FIELDS.map(name => [name, {
      raw_value: name === 'central_numbers' ? ['00121', '00122'] : name === 'commitment_number' ? '00031' : 'Example',
      review_state: 'auto_accepted', extraction_state: 'found', validation_issues: [],
      candidates: name === 'commitment_number' ? [{ value: '00032', reason: 'multiple_commitments_on_page', status: 'pending' }] : [],
    }])),
  };
}

it('shows and edits all seven clean fields, preserving extra numbers, and requires a separate record action', () => {
  const onEdit = vi.fn(), onConfirmReview = vi.fn();
  const data = record();
  render(<CommitmentReviewTable records={[data]} onEdit={onEdit} onConfirmReview={onConfirmReview} onViewSource={vi.fn()} onRejectCandidate={vi.fn()} />);
  expect(screen.getAllByText('זוהה אוטומטית')).toHaveLength(7);
  expect(screen.queryByText('מאושר')).toBeNull();
  const edits = screen.getAllByRole('button', { name: /עריכת/ });
  expect(edits).toHaveLength(7);
  edits.forEach(button => fireEvent.click(button));
  expect(onEdit.mock.calls.map(call => call[1])).toEqual([...REVIEW_FIELDS]);
  expect(onEdit.mock.calls[5][2]).toEqual(['00121', '00122']);
  expect(onEdit.mock.calls[6][2]).toEqual(['00031', '00032']);
  expect(onConfirmReview).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'אישור בדיקת הרשומה, עמוד 1' }));
  expect(onConfirmReview).toHaveBeenCalledWith(data);
});

it('keeps specific Hebrew warnings visible and disables record confirmation while unresolved', () => {
  const data = record();
  data.patient_first_name = { raw_value: null, extraction_state: 'missing', review_state: 'needs_review',
    review_reasons_he: ['השם הפרטי לא זוהה במסמך.'] };
  render(<CommitmentReviewTable records={[data]} onEdit={vi.fn()} onConfirmReview={vi.fn()} onViewSource={vi.fn()} onRejectCandidate={vi.fn()} />);
  expect(screen.getByText('השם הפרטי לא זוהה במסמך.')).toBeTruthy();
  expect((screen.getByRole('button', { name: 'אישור בדיקת הרשומה, עמוד 1' }) as HTMLButtonElement).disabled).toBe(true);
});

it('reopens a confirmed record without demanding another click or labeling AI fields human verified', () => {
  const data = { ...record(), final_review_confirmed: true };
  render(<CommitmentReviewTable records={[data]} onEdit={vi.fn()} onConfirmReview={vi.fn()} onViewSource={vi.fn()} onRejectCandidate={vi.fn()} />);
  expect(screen.getByRole('status').textContent).toContain('בדיקת הרשומה אושרה');
  expect(screen.queryByRole('button', { name: 'אישור בדיקת הרשומה, עמוד 1' })).toBeNull();
  expect(screen.getAllByText('זוהה אוטומטית')).toHaveLength(7);
  expect(screen.getAllByRole('button', { name: /עריכת/ })).toHaveLength(7);
});
