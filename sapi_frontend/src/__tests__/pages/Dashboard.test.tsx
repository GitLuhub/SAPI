import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from '@/pages/Dashboard';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/api', () => ({
  documentsApi: {
    listDocuments: vi.fn(),
    listDocumentTypes: vi.fn(),
    uploadDocument: vi.fn(),
  },
}));

const mockLogout = vi.fn().mockResolvedValue(undefined);
vi.mock('@/contexts/auth-context', () => {
  const mockStore = vi.fn().mockImplementation((selector: (s: any) => any) =>
    selector({ user: { id: '1', username: 'admin', role: 'admin', email: 'admin@test.com' } })
  );
  Object.defineProperty(mockStore, 'getState', {
    value: () => ({ logout: mockLogout }),
    configurable: true,
  });
  return { useAuthStore: mockStore };
});

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

import { documentsApi } from '@/api';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const DOC_LIST = {
  items: [
    {
      id: 'doc-1',
      original_filename: 'factura.pdf',
      status: 'PROCESSED',
      document_type_name: 'Factura',
      created_at: '2024-01-15T10:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  size: 10,
  pages: 1,
};

const EMPTY_LIST = { items: [], total: 0, page: 1, size: 10, pages: 0 };

const MULTI_PAGE = {
  items: [
    {
      id: 'doc-2',
      original_filename: 'contrato.pdf',
      status: 'UPLOADED',
      document_type_name: null,
      created_at: '2024-01-16T10:00:00Z',
    },
  ],
  total: 25,
  page: 1,
  size: 10,
  pages: 3,
};

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function renderDashboard() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <DashboardPage />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(documentsApi.listDocumentTypes).mockResolvedValue([]);
  });

  it('muestra el nombre de usuario en el header', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(DOC_LIST as any);
    renderDashboard();
    expect(screen.getByText(/admin/)).toBeInTheDocument();
    expect(screen.getByText('Panel de Administración')).toBeInTheDocument();
  });

  it('muestra la tabla con documentos cargados', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(DOC_LIST as any);
    renderDashboard();
    await waitFor(() => expect(screen.getByText('factura.pdf')).toBeInTheDocument());
    // 'Procesado' aparece en el select y en la fila — verificamos al menos 2 ocurrencias
    expect(screen.getAllByText('Procesado').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Factura')).toBeInTheDocument();
  });

  it('muestra guión cuando el documento no tiene tipo asignado', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(MULTI_PAGE as any);
    renderDashboard();
    await waitFor(() => expect(screen.getByText('contrato.pdf')).toBeInTheDocument());
    expect(screen.getByText('-')).toBeInTheDocument();
  });

  it('muestra estado vacío cuando no hay documentos', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(EMPTY_LIST as any);
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText(/No hay documentos/)).toBeInTheDocument()
    );
  });

  it('muestra mensaje de búsqueda en estado vacío con texto de búsqueda', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(EMPTY_LIST as any);
    renderDashboard();
    await waitFor(() => screen.getByPlaceholderText('Buscar documentos...'));
    fireEvent.change(screen.getByPlaceholderText('Buscar documentos...'), {
      target: { value: 'factura' },
    });
    await waitFor(() =>
      expect(screen.getByText(/coincidan con la búsqueda/)).toBeInTheDocument()
    );
  });

  it('muestra paginación cuando hay más de una página', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(MULTI_PAGE as any);
    renderDashboard();
    await waitFor(() => expect(screen.getByText(/Página 1 de 3/)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Siguiente' })).not.toBeDisabled();
  });

  it('avanza de página al hacer clic en Siguiente', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(MULTI_PAGE as any);
    renderDashboard();
    await waitFor(() => screen.getByRole('button', { name: 'Siguiente' }));
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
    await waitFor(() =>
      expect(documentsApi.listDocuments).toHaveBeenCalledWith(
        expect.objectContaining({ page: 2 })
      )
    );
  });

  it('filtra por estado al cambiar el select', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(DOC_LIST as any);
    renderDashboard();
    await waitFor(() => screen.getByText('factura.pdf'));
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'PROCESSED' } });
    await waitFor(() =>
      expect(documentsApi.listDocuments).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'PROCESSED' })
      )
    );
  });

  it('el botón Subir está deshabilitado sin archivo seleccionado', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(DOC_LIST as any);
    renderDashboard();
    expect(screen.getByRole('button', { name: /Subir/ })).toBeDisabled();
  });

  it('rechaza archivos de tipo no permitido con toast de error', async () => {
    const toast = (await import('react-hot-toast')).default;
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(DOC_LIST as any);
    renderDashboard();
    const input = document.querySelector('#file-upload') as HTMLInputElement;
    const file = new File(['content'], 'documento.txt', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });
    expect(toast.error).toHaveBeenCalledWith('Tipo de archivo no permitido');
  });

  it('rechaza archivos mayores a 10MB', async () => {
    const toast = (await import('react-hot-toast')).default;
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(DOC_LIST as any);
    renderDashboard();
    const input = document.querySelector('#file-upload') as HTMLInputElement;
    const bigFile = new File([new ArrayBuffer(11 * 1024 * 1024)], 'huge.pdf', {
      type: 'application/pdf',
    });
    fireEvent.change(input, { target: { files: [bigFile] } });
    expect(toast.error).toHaveBeenCalledWith('El archivo es demasiado grande (máx. 10MB)');
  });

  it('acepta PDF válido, muestra nombre y habilita botón Subir', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(DOC_LIST as any);
    renderDashboard();
    const input = document.querySelector('#file-upload') as HTMLInputElement;
    const file = new File(['%PDF-1.4'], 'factura_nueva.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() =>
      expect(screen.getByText('factura_nueva.pdf')).toBeInTheDocument()
    );
    expect(screen.getByRole('button', { name: /Subir/ })).not.toBeDisabled();
  });

  it('llama a uploadDocument al hacer clic en Subir', async () => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(DOC_LIST as any);
    vi.mocked(documentsApi.uploadDocument).mockResolvedValue({ id: 'new-doc' } as any);
    renderDashboard();
    const input = document.querySelector('#file-upload') as HTMLInputElement;
    const file = new File(['%PDF-1.4'], 'invoice.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => screen.getByText('invoice.pdf'));
    fireEvent.click(screen.getByRole('button', { name: /Subir/ }));
    await waitFor(() =>
      expect(documentsApi.uploadDocument).toHaveBeenCalledWith(file)
    );
  });

  it('muestra toast de error cuando falla el upload', async () => {
    const toast = (await import('react-hot-toast')).default;
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(DOC_LIST as any);
    vi.mocked(documentsApi.uploadDocument).mockRejectedValue({
      response: { data: { detail: 'Formato no soportado' } },
    });
    renderDashboard();
    const input = document.querySelector('#file-upload') as HTMLInputElement;
    const file = new File(['%PDF-1.4'], 'bad.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => screen.getByText('bad.pdf'));
    fireEvent.click(screen.getByRole('button', { name: /Subir/ }));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('Formato no soportado')
    );
  });

  it('muestra etiquetas de status correctas para UPLOADED y ERROR', async () => {
    const mixed = {
      ...DOC_LIST,
      items: [
        { ...DOC_LIST.items[0], status: 'UPLOADED', id: 'a' },
        { ...DOC_LIST.items[0], status: 'ERROR', id: 'b', original_filename: 'err.pdf' },
      ],
    };
    vi.mocked(documentsApi.listDocuments).mockResolvedValue(mixed as any);
    renderDashboard();
    await waitFor(() => expect(screen.getByText('Subido')).toBeInTheDocument());
    expect(screen.getByText('Error')).toBeInTheDocument();
  });
});
