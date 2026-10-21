/**
 * API client for backend communication
 * 
 * Integration Package 1: Complete Frontend-Backend connection
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create axios instance with base configuration
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for processing (Gemini API can be slow)
  headers: {
    'Content-Type': 'application/json',
  },
});

// Existing callers may log request errors; never include demo credentials there.
apiClient.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401) {
    delete apiClient.defaults.auth;
    window.dispatchEvent(new Event('api-auth-required'));
  }
  if (error.config) {
    delete error.config.auth;
    delete error.config.headers?.Authorization;
  }
  return Promise.reject(error);
});

// Types - Domain Models
export interface FieldValue<T = any> {
  raw_value: T | null;
  normalized_value: T | null;
  reviewed_value: T | null;
  extraction_state: 'found' | 'missing' | 'uncertain' | 'conflicting' | 'invalid';
  review_state: 'pending' | 'needs_review' | 'human_verified' | 'rejected';
  validation_issues: ValidationIssue[];
  extractor_id?: string;
  extraction_attempt_id?: string;
  candidates?: { value: string; source_label?: string | null; reason: string; status?: string }[];
  extraction_notes?: string[];
}

export interface ValidationIssue {
  field_name: string;
  severity: 'error' | 'warning';
  message: string;
  suggested_fix?: string;
}

export interface TestRecord {
  test_id: string;
  document_id: string;
  page_indices: number[];
  patient_first_name: FieldValue<string>;
  patient_last_name: FieldValue<string>;
  patient_full_name_raw?: FieldValue<string>; // Stage 1.5: Full name before splitting
  patient_id_number: FieldValue<string>;
  sender: FieldValue<string>;
  received_date: FieldValue<string>;
  central_numbers: FieldValue<string[]>;
  commitment_ids: string[];
}

/**
 * NEW: Multi-page form entity (MVP 8-hour contract)
 */
export interface LogicalForm {
  form_id: string;
  document_id: string;
  page_indices: number[];  // e.g. [4, 5] for 2-page form
  
  // Segmentation metadata
  segmentation_confidence: number;  // 0.0-1.0
  segmentation_method: 'page_notation' | 'heuristic' | 'single_page';
  
  // Patient/Sample fields (from TestRecord)
  patient_first_name: FieldValue<string>;
  patient_last_name: FieldValue<string>;
  patient_id_number: FieldValue<string>;
  sender: FieldValue<string>;
  
  // References
  sample_ids: string[];
  commitment_ids: string[];
}

/**
 * NEW: Sample = (central_number, received_date) pair
 */
export interface Sample {
  sample_id: string;
  form_id: string;
  central_number: FieldValue<string>;
  received_date: FieldValue<string>;
}

export interface CommitmentRecord {
  patient_first_name?: FieldValue<string>;
  patient_last_name?: FieldValue<string>;
  patient_id_number?: FieldValue<string>;
  sender?: FieldValue<string>;
  received_date?: FieldValue<string>;
  central_numbers?: FieldValue<string[]>;
  commitment_record_id: string;
  test_id: string;  // DEPRECATED: will be replaced by form_id
  form_id?: string;  // NEW: link to LogicalForm
  commitment_number: FieldValue<string>;
  central_number_refs: string[];  // KEEP for backward compatibility
  sample_ids?: string[];  // NEW: explicit links to Sample[]
  relation_status: 'clear' | 'ambiguous' | 'manual';  // LEGACY: read-only mapping
  relationship_status?: 'explicit' | 'inferred' | 'unresolved_relationship' | 'none';  // NEW: per Decision D2
  page_warnings?: string[];  // short, de-duplicated extraction warnings for the page
}

export interface ProcessingError {
  document_id: string;
  page_index?: number;
  error: string;
  error_code?: string;
  retry_after_seconds?: number | null;
}

// API Response Types
export interface HealthResponse {
  requires_auth?: boolean;
  status: string;
  service: string;
  version: string;
  model: string;
  demo_mode?: boolean;
  environment?: string;
  extractor?: string;
}

export interface DocumentInfo {
  document_id: string;
  filename: string;
  size_bytes: number;
  page_count?: number;
}

export interface ProcessingProgress {
  current: number;
  total: number;
  current_file: string | null;
  page_current?: number;
  page_total?: number;
  pages_succeeded?: number;
  pages_failed?: number;
  last_error_code?: string | null;
}

export interface BatchResponse {
  batch_id: string;
  documents: DocumentInfo[];
}

export interface BatchStatusResponse {
  batch_id: string;
  status: 'uploaded' | 'queued' | 'processing' | 'completed' | 'completed_with_errors' | 'failed' | 'quota_exhausted';
  test_records: TestRecord[];  // KEEP for backward compatibility
  commitment_records: CommitmentRecord[];  // MODIFIED
  forms?: LogicalForm[];  // NEW
  samples?: Sample[];  // NEW
  statistics?: {  // NEW
    total_pages: number;
    total_forms: number;
    total_commitments: number;
    unresolved_relationships: number;
  };
  errors?: ProcessingError[];
  processed_count?: number;
  error_count?: number;
  message?: string;
  progress?: ProcessingProgress;
}

export interface FieldUpdateRequest {
  field_name: string;
  new_value: any;
}

/**
 * Health check endpoint
 */
export const healthCheck = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
};

/**
 * Upload files to create a batch
 */
export const uploadFiles = async (files: FileList): Promise<BatchResponse> => {
  const formData = new FormData();
  
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }

  const response = await apiClient.post<BatchResponse>('/api/batches', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

/**
 * Start processing a batch.
 * 
 * Returns 202 Accepted immediately. Processing runs in background.
 * Poll getBatchStatus() every 2-3 seconds to check progress.
 * 
 * @param batchId Batch identifier
 * @returns Processing job status
 */
export const processBatch = async (batchId: string): Promise<{ batch_id: string; status: string; message: string }> => {
  const response = await apiClient.post(`/api/batches/${batchId}/process`);
  return response.data;
};

/**
 * Re-run extraction only for failed/skipped pages that nobody has edited.
 * Extracted and human-reviewed pages are never overwritten. Poll getBatchStatus() afterwards.
 */
export const retryFailedPages = async (batchId: string): Promise<{ batch_id: string; status: string; message: string; pages_to_retry?: number }> => {
  const response = await apiClient.post(`/api/batches/${batchId}/retry-failed`);
  return response.data;
};

/**
 * Get batch status and results
 */
export const getBatchStatus = async (batchId: string): Promise<BatchStatusResponse> => {
  const response = await apiClient.get<BatchStatusResponse>(`/api/batches/${batchId}`);
  return response.data;
};

/**
 * Update a specific field in a test record
 */
export const updateField = async (
  batchId: string,
  testId: string,
  fieldName: string,
  newValue: any
): Promise<TestRecord> => {
  const response = await apiClient.patch<TestRecord>(
    `/api/batches/${batchId}/tests/${testId}/fields/${fieldName}`,
    { new_value: newValue }
  );
  return response.data;
};

/**
 * Reject an unconfirmed candidate. Changes only the candidate status; never sets a value or verifies a field.
 */
export const rejectFieldCandidate = async (
  batchId: string,
  testId: string,
  fieldName: string,
  value: string
): Promise<{ field: FieldValue; can_export: boolean; blockers: string[] }> => {
  const response = await apiClient.post(
    `/api/batches/${batchId}/tests/${testId}/fields/${fieldName}/candidates/reject`,
    { value }
  );
  return response.data;
};

/**
 * Mark a field as human verified
 */
export const verifyField = async (
  batchId: string,
  testId: string,
  fieldName: string
): Promise<TestRecord> => {
  const response = await apiClient.post<TestRecord>(
    `/api/batches/${batchId}/tests/${testId}/fields/${fieldName}/verify`
  );
  return response.data;
};

/**
 * Export batch to Excel
 * Returns blob for download
 */
export const exportBatch = async (batchId: string): Promise<Blob> => {
  const response = await apiClient.post(`/api/batches/${batchId}/export`, null, {
    responseType: 'blob',
  });
  return response.data;
};

/**
 * Check if batch can be exported (no blocking issues)
 */
export const checkExportEligibility = async (batchId: string): Promise<{
  can_export: boolean;
  blockers: string[];
}> => {
  const response = await apiClient.get(`/api/batches/${batchId}/export-check`);
  return response.data;
};

export default apiClient;


/**
 * Assign orphaned commitment to a test record
 */
export const assignCommitmentToTest = async (
  batchId: string,
  commitmentId: string,
  testId: string
): Promise<BatchStatusResponse> => {
  const response = await apiClient.post(
    `/batches/${batchId}/commitments/${commitmentId}/assign`,
    { test_id: testId }
  );
  return response.data;
};

/**
 * Resolve ambiguous commitment relationship
 */
export const resolveCommitmentRelationship = async (
  batchId: string,
  commitmentId: string,
  centralNumberRefs: string[],
  relationStatus: 'related' | 'unrelated'
): Promise<BatchStatusResponse> => {
  const response = await apiClient.post(
    `/batches/${batchId}/commitments/${commitmentId}/resolve`,
    {
      central_number_refs: centralNumberRefs,
      relation_status: relationStatus
    }
  );
  return response.data;
};
