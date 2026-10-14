/**
 * API client for backend communication
 */
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// Create axios instance with base configuration
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  model: string;
}

export interface DocumentInfo {
  document_id: string;
  filename: string;
  size_bytes: number;
}

export interface BatchResponse {
  batch_id: string;
  documents: DocumentInfo[];
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

export default apiClient;
