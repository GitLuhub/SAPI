import apiClient from './client';
import type {
  Document,
  DocumentDetail,
  DocumentStatusResponse,
  PaginatedResponse,
  DocumentType,
  ExtractedDataUpdate,
  UploadResponse,
  DocumentStatus,
} from '@/types';

export interface DocumentFilters {
  page?: number;
  size?: number;
  status?: DocumentStatus;
  document_type_id?: string;
  search_query?: string;
  date_from?: string;
  date_to?: string;
}

export const documentsApi = {
  listDocuments: async (filters: DocumentFilters = {}): Promise<PaginatedResponse<Document>> => {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.size) params.append('size', filters.size.toString());
    if (filters.status) params.append('status', filters.status);
    if (filters.document_type_id) params.append('document_type_id', filters.document_type_id);
    if (filters.search_query) params.append('search_query', filters.search_query);
    if (filters.date_from) params.append('date_from', filters.date_from);
    if (filters.date_to) params.append('date_to', filters.date_to);

    const response = await apiClient.get<PaginatedResponse<Document>>('/documents/', { params });
    return response.data;
  },

  getDocument: async (documentId: string): Promise<Document> => {
    const response = await apiClient.get<Document>(`/documents/${documentId}`);
    return response.data;
  },

  getDocumentStatus: async (documentId: string): Promise<DocumentStatusResponse> => {
    const response = await apiClient.get<DocumentStatusResponse>(`/documents/${documentId}/status`);
    return response.data;
  },

  getDocumentData: async (documentId: string): Promise<DocumentDetail> => {
    const response = await apiClient.get<DocumentDetail>(`/documents/${documentId}/data`);
    return response.data;
  },

  updateDocumentData: async (documentId: string, updates: ExtractedDataUpdate[]): Promise<void> => {
    await apiClient.put(`/documents/${documentId}/data`, { updates });
  },

  uploadDocument: async (file: File, documentTypeId?: string): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (documentTypeId) {
      formData.append('document_type_id', documentTypeId);
    }

    const response = await apiClient.post<UploadResponse>('/documents/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  previewDocument: async (documentId: string): Promise<string> => {
    const response = await apiClient.get(`/documents/${documentId}/preview`, {
      responseType: 'blob',
    });
    return URL.createObjectURL(response.data as Blob);
  },

  downloadDocument: async (documentId: string, filename: string): Promise<void> => {
    const response = await apiClient.get(`/documents/${documentId}/download`, {
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
  },

  listDocumentTypes: async (): Promise<DocumentType[]> => {
    const response = await apiClient.get<DocumentType[]>('/documents/types/');
    return response.data;
  },

  exportDocuments: async (params: { format?: 'csv' | 'xlsx'; status?: DocumentStatus; date_from?: string; date_to?: string } = {}): Promise<void> => {
    const urlParams = new URLSearchParams();
    if (params.format) urlParams.append('format', params.format);
    if (params.status) urlParams.append('status', params.status);
    if (params.date_from) urlParams.append('date_from', params.date_from);
    if (params.date_to) urlParams.append('date_to', params.date_to);

    const response = await apiClient.get(`/documents/export?${urlParams.toString()}`, {
      responseType: 'blob',
    });

    const ext = params.format === 'xlsx' ? 'xlsx' : 'csv';
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `sapi_export.${ext}`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  reprocessDocument: async (documentId: string): Promise<DocumentStatusResponse> => {
    const response = await apiClient.post<DocumentStatusResponse>(`/documents/${documentId}/reprocess`);
    return response.data;
  },
};
