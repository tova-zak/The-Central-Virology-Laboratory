import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { CommitmentReviewTable, REVIEW_FIELDS } from './CommitmentReviewTable';

afterEach(cleanup);
function record(): any {
  return {commitment_record_id:'synthetic', form_id:'doc_page_0', source_page:1,
    relationship_status:'inferred', relation_status:'unknown', final_review_token:'token',
    ...Object.fromEntries(REVIEW_FIELDS.map(name => [name, {raw_value:name === 'central_numbers' ? ['00121','00122'] : '00031',
      extraction_state:'found', review_state:'auto_accepted', validation_issues:[], candidates:[]}]))};
}
function view(data: any, resolve = vi.fn()) {
  return render(<CommitmentReviewTable records={[data]} onEdit={vi.fn()} onRejectCandidate={vi.fn()}
    onViewSource={vi.fn()} onConfirmReview={vi.fn()} onResolveRelationship={resolve} />);
}
it('keeps every page warning available in the review screen without truncating its text', () => {
  const data = record();
  data.page_warnings = Array.from({length:12}, (_,i) => `Synthetic warning ${i} ${'x'.repeat(350)}`);
  view(data);
  for (const warning of data.page_warnings) expect(screen.getByText(warning)).toBeTruthy();
});
it('disables whole-record approval for legacy ambiguity and offers explicit relationship resolution', () => {
  const data = record(), resolve = vi.fn();
  data.relation_status = 'ambiguous';
  view(data, resolve);
  expect((screen.getByRole('button', {name:'אישור בדיקת הרשומה, עמוד 1'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', {name:'פתרון קשר, עמוד 1'}));
  expect(resolve).toHaveBeenCalledWith(data);
});
it('shows confirmed empty distinctly from an unreviewed missing value and preserves zeroes', () => {
  const data = record();
  data.patient_first_name = {raw_value:'Old synthetic',reviewed_value:'',review_state:'human_verified',extraction_state:'found'};
  data.patient_last_name = {raw_value:null,review_state:'needs_review',extraction_state:'missing'};
  view(data);
  expect(screen.queryByText('Old synthetic')).toBeNull();
  expect(screen.getByText('מאושר')).toBeTruthy();
  expect(screen.getByText('שם המשפחה לא זוהה במסמך.')).toBeTruthy();
  expect(screen.getByText('00121, 00122')).toBeTruthy();
});
