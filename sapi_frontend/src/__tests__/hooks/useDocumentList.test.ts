import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';
import { useDocumentList, useDocumentTypes, useDocumentUpload } from '@/hooks/useDocumentList';

// ---------------------------------------------------------------------------
// Mock de la API
// ---------------------------------------------------------------------------
vi.mock('@/api', () => ({
  documentsApi: {
    listDocuments: vi.fn(),
    listDocumentTypes: vi.fn(),
    uploadDocument: vi.fn(),
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

// ---------------------------------------------------------------------------
// useDocumentList
// ---------------------------------------------------------------------------
describe('useDocumentList', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('llama a listDocuments con los parámetros correctos', async () => {
    const mockData = { items: [], total: 0, page: 1, size: 10, pages: 0 };
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(mockData as any);

    const { result } = renderHook(
      () => useDocumentList({ page: 1, size: 10 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(documentsApi.listDocuments).toHaveBeenCalledWith({
      page: 1,
      size: 10,
      status: undefined,
      search_query: undefined,
      document_type_id: undefined,
      date_from: undefined,
      date_to: undefined,
    });
    expect(result.current.data).toEqual(mockData);
  });

  it('pasa status filter cuando está definido', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({ items: [], total: 0, page: 1, size: 10, pages: 0 } as any);

    renderHook(
      () => useDocumentList({ page: 1, statusFilter: 'PROCESSED' }),
      { wrapper: createWrapper() }
    );

    await waitFor(() =>
      expect(documentsApi.listDocuments).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'PROCESSED' })
      )
    );
  });

  it('omite parámetros vacíos (string vacío → undefined)', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue({ items: [], total: 0, page: 1, size: 10, pages: 0 } as any);

    renderHook(
      () => useDocumentList({ page: 1, searchQuery: '' }),
      { wrapper: createWrapper() }
    );

    await waitFor(() =>
      expect(documentsApi.listDocuments).toHaveBeenCalledWith(
        expect.objectContaining({ search_query: undefined })
      )
    );
  });

  it('maneja error de la API con isError=true', async () => {
    vi.mocked(documentsApi.listDocuments).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(
      () => useDocumentList({ page: 1 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

// ---------------------------------------------------------------------------
// useDocumentTypes
// ---------------------------------------------------------------------------
describe('useDocumentTypes', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('retorna tipos de documento de la API', async () => {
    const types = [{ id: '1', name: 'Factura', is_active: true }];
    vi.mocked(documentsApi.listDocumentTypes).mockResolvedValue(types as any);

    const { result } = renderHook(useDocumentTypes, { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(types);
  });
});

// ---------------------------------------------------------------------------
// useDocumentUpload
// ---------------------------------------------------------------------------
describe('useDocumentUpload', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('llama a uploadDocument y muestra toast de éxito', async () => {
    const toast = (await import('react-hot-toast')).default;
    vi.mocked(documentsApi.uploadDocument).mockResolvedValue({ id: 'doc-1' } as any);

    const { result } = renderHook(useDocumentUpload, { wrapper: createWrapper() });

    const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });
    result.current.mutate({ file });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(documentsApi.uploadDocument).toHaveBeenCalledWith(file);
    expect(toast.success).toHaveBeenCalledWith('Documento subido correctamente');
  });

  it('muestra toast de error cuando falla el upload', async () => {
    const toast = (await import('react-hot-toast')).default;
    vi.mocked(documentsApi.uploadDocument).mockRejectedValue({
      response: { data: { detail: 'Archivo inválido' } },
    });

    const { result } = renderHook(useDocumentUpload, { wrapper: createWrapper() });

    const file = new File([''], 'bad.pdf', { type: 'application/pdf' });
    result.current.mutate({ file });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toast.error).toHaveBeenCalledWith('Archivo inválido');
  });
});
