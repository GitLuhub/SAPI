export type DocumentStatus = 'UPLOADED' | 'PROCESSING' | 'PROCESSED' | 'REVIEW_NEEDED' | 'ERROR';

export interface DocumentType {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExtractedField {
  field_name: string;
  field_label?: string;
  ai_extracted_value?: string;
  ai_confidence?: string;
  final_value: string;
  is_corrected: boolean;
  corrected_at?: string;
}

export interface Document {
  id: string;
  original_filename: string;
  status: DocumentStatus;
  classification_confidence?: string;
  upload_user_id: string;
  document_type_id?: string;
  document_type_name?: string;
  processing_started_at?: string;
  processing_completed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentDetail extends Document {
  file_size?: string;
  mime_type?: string;
  document_type?: DocumentType;
  executive_summary?: string;
  extracted_fields: ExtractedField[];
  processing_error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface DocumentStatusResponse {
  id: string;
  status: DocumentStatus;
  message: string;
}

export interface ExtractedDataUpdate {
  field_name: string;
  new_value: string;
}

export interface UploadResponse {
  id: string;
  status: DocumentStatus;
  message: string;
}
