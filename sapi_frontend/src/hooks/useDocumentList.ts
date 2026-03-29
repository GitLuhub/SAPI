import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/api';
import toast from 'react-hot-toast';
import type { DocumentStatus } from '@/types';

interface UseDocumentListOptions {
  page: number;
  size?: number;
  statusFilter?: DocumentStatus | '';
  searchQuery?: string;
  documentTypeId?: string;
  dateFrom?: string;
  dateTo?: string;
}

export function useDocumentList({
  page,
  size = 10,
  statusFilter = '',
  searchQuery = '',
  documentTypeId = '',
  dateFrom = '',
  dateTo = '',
}: UseDocumentListOptions) {
  return useQuery({
    queryKey: ['documents', page, size, statusFilter, searchQuery, documentTypeId, dateFrom, dateTo],
    queryFn: () =>
      documentsApi.listDocuments({
        page,
        size,
        status: statusFilter || undefined,
        search_query: searchQuery || undefined,
        document_type_id: documentTypeId || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
  });
}

export function useDocumentTypes() {
  return useQuery({
    queryKey: ['documentTypes'],
    queryFn: () => documentsApi.listDocumentTypes(),
  });
}

export function useDocumentUpload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file }: { file: File }) => documentsApi.uploadDocument(file),
    onSuccess: () => {
      toast.success('Documento subido correctamente');
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Error al subir el documento');
    },
  });
}
