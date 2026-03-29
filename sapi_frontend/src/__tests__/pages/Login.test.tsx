import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '@/pages/Login';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn();
const mockLogin = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...(actual as object), useNavigate: () => mockNavigate };
});

vi.mock('@/contexts/auth-context', () => ({
  useAuthStore: vi.fn().mockImplementation((selector: (s: any) => any) =>
    selector({ login: mockLogin })
  ),
}));

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LoginPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renderiza el formulario de login con campos usuario y contraseña', () => {
    renderLogin();
    expect(screen.getByLabelText('Usuario')).toBeInTheDocument();
    expect(screen.getByLabelText('Contraseña')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Iniciar Sesión/ })).toBeInTheDocument();
  });

  it('muestra las credenciales de prueba', () => {
    renderLogin();
    expect(screen.getByText(/Credenciales de prueba/)).toBeInTheDocument();
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('admin123')).toBeInTheDocument();
  });

  it('actualiza los campos al escribir', () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText('Usuario'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'admin123' } });
    expect(screen.getByLabelText('Usuario')).toHaveValue('admin');
    expect(screen.getByLabelText('Contraseña')).toHaveValue('admin123');
  });

  it('llama a login y navega a / en caso de éxito', async () => {
    mockLogin.mockResolvedValue(undefined);
    renderLogin();
    fireEvent.change(screen.getByLabelText('Usuario'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'admin123' } });
    fireEvent.submit(screen.getByRole('button', { name: /Iniciar Sesión/ }).closest('form')!);
    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith('admin', 'admin123'));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/'));
  });

  it('muestra mensaje de error cuando el login falla', async () => {
    mockLogin.mockRejectedValue({
      response: { data: { detail: 'Credenciales inválidas' } },
    });
    renderLogin();
    fireEvent.change(screen.getByLabelText('Usuario'), { target: { value: 'wrong' } });
    fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'wrong' } });
    fireEvent.submit(screen.getByRole('button', { name: /Iniciar Sesión/ }).closest('form')!);
    await waitFor(() =>
      expect(screen.getByText('Credenciales inválidas')).toBeInTheDocument()
    );
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('muestra mensaje genérico de error cuando no hay detail en la respuesta', async () => {
    mockLogin.mockRejectedValue(new Error('Network error'));
    renderLogin();
    fireEvent.submit(screen.getByRole('button', { name: /Iniciar Sesión/ }).closest('form')!);
    await waitFor(() =>
      expect(screen.getByText('Error de autenticación')).toBeInTheDocument()
    );
  });
});
