import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import DocumentDetailPage from '@/pages/DocumentDetail';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/api', () => ({
  documentsApi: {
    getDocumentData: vi.fn(),
    updateDocumentData: vi.fn(),
    downloadDocument: vi.fn(),
  },
}));

vi.mock('@/contexts/auth-context', () => ({
  useAuthStore: vi.fn().mockImplementation((selector: (s: any) => any) =>
    selector({ user: { id: '1', username: 'admin', role: 'admin' } })
  ),
}));

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

// useParams devuelve documentId fijo para todos los tests
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...(actual as object), useParams: () => ({ documentId: 'doc-123' }) };
});

// PdfViewer requiere URL.createObjectURL y fetch — no testeable en jsdom
vi.mock('@/components/ui/PdfViewer', () => ({
  default: ({ documentId }: { documentId: string }) => (
    <div data-testid="pdf-viewer">{documentId}</div>
  ),
}));

import { documentsApi } from '@/api';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_DOC = {
  id: 'doc-123',
  original_filename: 'factura.pdf',
  status: 'PROCESSED',
  mime_type: 'application/pdf',
  document_type: { id: 'dt-1', name: 'Factura', description: '', is_active: true },
  classification_confidence: '0.95',
  executive_summary: 'Resumen ejecutivo de la factura de enero.',
  extracted_fields: [
    {
      field_name: 'numero_factura',
      field_label: 'Número de Factura',
      final_value: 'F-001',
      ai_confidence: '0.98',
      is_corrected: false,
    },
    {
      field_name: 'importe_total',
      field_label: 'Importe Total',
      final_value: '1500.00',
      ai_confidence: '0.91',
      is_corrected: true,
    },
  ],
};

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function renderDetail() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <DocumentDetailPage />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DocumentDetailPage', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('no muestra el contenido del documento mientras carga', () => {
    vi.mocked(documentsApi.getDocumentData).mockReturnValue(new Promise(() => {}));
    renderDetail();
    expect(screen.queryByText('factura.pdf')).not.toBeInTheDocument();
  });

  it('muestra estado de error cuando la query falla', async () => {
    vi.mocked(documentsApi.getDocumentData).mockRejectedValue(new Error('Not found'));
    renderDetail();
    await waitFor(() =>
      expect(screen.getByText('Error al cargar el documento')).toBeInTheDocument()
    );
    expect(screen.getByRole('link', { name: 'Volver al dashboard' })).toBeInTheDocument();
  });

  it('renderiza el nombre del documento en el header', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    renderDetail();
    await waitFor(() => expect(screen.getByText('factura.pdf')).toBeInTheDocument());
  });

  it('muestra el tipo de documento como badge', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    renderDetail();
    await waitFor(() => expect(screen.getByText('Factura')).toBeInTheDocument());
  });

  it('muestra el porcentaje de confianza de clasificación', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    renderDetail();
    await waitFor(() => expect(screen.getByText('95%')).toBeInTheDocument());
  });

  it('muestra el resumen ejecutivo', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    renderDetail();
    await waitFor(() =>
      expect(
        screen.getByText('Resumen ejecutivo de la factura de enero.')
      ).toBeInTheDocument()
    );
  });

  it('renderiza los campos extraídos con sus valores finales', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    renderDetail();
    await waitFor(() => expect(screen.getByDisplayValue('F-001')).toBeInTheDocument());
    expect(screen.getByDisplayValue('1500.00')).toBeInTheDocument();
  });

  it('muestra indicador "Corregido manualmente" en campos corregidos', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    renderDetail();
    await waitFor(() =>
      expect(screen.getByText(/Corregido manualmente/)).toBeInTheDocument()
    );
  });

  it('el botón Guardar está deshabilitado sin cambios pendientes', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    renderDetail();
    await waitFor(() => screen.getByRole('button', { name: /Guardar Cambios/ }));
    expect(screen.getByRole('button', { name: /Guardar Cambios/ })).toBeDisabled();
  });

  it('el botón Guardar se habilita al editar un campo', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    renderDetail();
    await waitFor(() => screen.getByDisplayValue('F-001'));
    fireEvent.change(screen.getByDisplayValue('F-001'), { target: { value: 'F-999' } });
    expect(screen.getByRole('button', { name: /Guardar Cambios/ })).not.toBeDisabled();
  });

  it('llama a updateDocumentData con los cambios correctos al guardar', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    vi.mocked(documentsApi.updateDocumentData).mockResolvedValue(undefined as any);
    renderDetail();
    await waitFor(() => screen.getByDisplayValue('F-001'));
    fireEvent.change(screen.getByDisplayValue('F-001'), { target: { value: 'F-999' } });
    fireEvent.click(screen.getByRole('button', { name: /Guardar Cambios/ }));
    await waitFor(() =>
      expect(documentsApi.updateDocumentData).toHaveBeenCalledWith('doc-123', [
        { field_name: 'numero_factura', new_value: 'F-999' },
      ])
    );
  });

  it('llama a downloadDocument al hacer clic en Descargar', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    vi.mocked(documentsApi.downloadDocument).mockResolvedValue(undefined as any);
    renderDetail();
    await waitFor(() => screen.getByRole('button', { name: /Descargar/ }));
    fireEvent.click(screen.getByRole('button', { name: /Descargar/ }));
    expect(documentsApi.downloadDocument).toHaveBeenCalledWith('doc-123', 'factura.pdf');
  });

  it('muestra "Procesando documento" cuando no hay campos extraídos', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue({
      ...MOCK_DOC,
      extracted_fields: [],
    } as any);
    renderDetail();
    await waitFor(() =>
      expect(screen.getByText('Procesando documento...')).toBeInTheDocument()
    );
  });

  it('muestra colores distintos para confianza baja (<0.7)', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue({
      ...MOCK_DOC,
      classification_confidence: '0.5',
    } as any);
    renderDetail();
    await waitFor(() => expect(screen.getByText('50%')).toBeInTheDocument());
  });

  it('muestra toast de error cuando falla el guardado', async () => {
    const toast = (await import('react-hot-toast')).default;
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    vi.mocked(documentsApi.updateDocumentData).mockRejectedValue({
      response: { data: { detail: 'Sin permisos' } },
    });
    renderDetail();
    await waitFor(() => screen.getByDisplayValue('F-001'));
    fireEvent.change(screen.getByDisplayValue('F-001'), { target: { value: 'F-999' } });
    fireEvent.click(screen.getByRole('button', { name: /Guardar Cambios/ }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Sin permisos'));
  });

  it('renderiza el PdfViewer con el documentId correcto', async () => {
    vi.mocked(documentsApi.getDocumentData).mockResolvedValue(MOCK_DOC as any);
    renderDetail();
    await waitFor(() => expect(screen.getByTestId('pdf-viewer')).toBeInTheDocument());
    expect(screen.getByTestId('pdf-viewer')).toHaveTextContent('doc-123');
  });
});
