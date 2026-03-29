import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/api';
import toast from 'react-hot-toast';

export function useDocumentDetail(documentId: string | undefined) {
  return useQuery({
    queryKey: ['document', documentId],
    queryFn: () => documentsApi.getDocumentData(documentId!),
    enabled: !!documentId,
  });
}

export function useDocumentFieldUpdate(documentId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (updates: { field_name: string; new_value: string }[]) =>
      documentsApi.updateDocumentData(documentId!, updates),
    onSuccess: () => {
      toast.success('Datos actualizados correctamente');
      queryClient.invalidateQueries({ queryKey: ['document', documentId] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Error al actualizar');
    },
  });
}
