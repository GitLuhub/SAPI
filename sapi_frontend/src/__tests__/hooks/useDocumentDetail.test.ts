import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';
import { useDocumentDetail, useDocumentFieldUpdate } from '@/hooks/useDocumentDetail';

vi.mock('@/api', () => ({
  documentsApi: {
    getDocumentData: vi.fn(),
    updateDocumentData: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

import { documentsApi } from '@/api';

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
};

const mockDocument = {
  id: 'doc-123',
  original_filename: 'factura.pdf',
  status: 'PROCESSED',
  extracted_fields: [
    { field_name: 'numero_factura', final_value: 'F-001', is_corrected: false },
  ],
};

// ---------------------------------------------------------------------------
// useDocumentDetail
// ---------------------------------------------------------------------------
describe('useDocumentDetail', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('carga los datos del documento cuando hay documentId', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(mockDocument as any);

    const { result } = renderHook(
      () => useDocumentDetail('doc-123'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(documentsApi.getDocumentData).toHaveBeenCalledWith('doc-123');
    expect(result.current.data?.original_filename).toBe('factura.pdf');
  });

  it('no ejecuta la query si documentId es undefined', async () => {
    const { result } = renderHook(
      () => useDocumentDetail(undefined),
      { wrapper: createWrapper() }
    );

    // La query está deshabilitada (enabled: false)
    expect(result.current.isPending).toBe(true);
    expect(documentsApi.getDocumentData).not.toHaveBeenCalled();
  });

  it('expone isError cuando la API falla', async () => {
    vi.mocked(documentsApi.getDocumentData).mockRejectedValue(new Error('Not found'));

    const { result } = renderHook(
      () => useDocumentDetail('bad-id'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

// ---------------------------------------------------------------------------
// useDocumentFieldUpdate
// ---------------------------------------------------------------------------
describe('useDocumentFieldUpdate', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('llama a updateDocumentData y muestra toast de éxito', async () => {
    const toast = (await import('react-hot-toast')).default;
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(mockDocument as any);
    vi.mocked(documentsApi.updateDocumentData).mockResolvedValue({ updated: 1 } as any);

    const { result } = renderHook(
      () => useDocumentFieldUpdate('doc-123'),
      { wrapper: createWrapper() }
    );

    result.current.mutate([{ field_name: 'numero_factura', new_value: 'F-999' }]);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(documentsApi.updateDocumentData).toHaveBeenCalledWith('doc-123', [
      { field_name: 'numero_factura', new_value: 'F-999' },
    ]);
    expect(toast.success).toHaveBeenCalledWith('Datos actualizados correctamente');
  });

  it('muestra toast de error cuando falla la actualización', async () => {
    const toast = (await import('react-hot-toast')).default;
    vi.mocked(documentsApi.updateDocumentData).mockRejectedValue({
      response: { data: { detail: 'Sin permisos' } },
    });

    const { result } = renderHook(
      () => useDocumentFieldUpdate('doc-123'),
      { wrapper: createWrapper() }
    );

    result.current.mutate([{ field_name: 'f', new_value: 'v' }]);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toast.error).toHaveBeenCalledWith('Sin permisos');
  });
});
