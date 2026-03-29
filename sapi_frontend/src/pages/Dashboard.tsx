import { useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/api';
import { useAuthStore } from '@/contexts/auth-context';
import {
  FileText,
  Upload,
  Search,
  Eye,
  Loader2,
  CheckCircle,
  AlertCircle,
  Clock,
  XCircle,
  Download,
} from 'lucide-react';
import toast from 'react-hot-toast';
import type { Document, DocumentStatus, DocumentType } from '@/types';

const statusConfig: Record<DocumentStatus, { icon: typeof CheckCircle; color: string; label: string }> = {
  UPLOADED: { icon: Upload, color: 'text-info', label: 'Subido' },
  PROCESSING: { icon: Loader2, color: 'text-warning', label: 'Procesando' },
  PROCESSED: { icon: CheckCircle, color: 'text-success', label: 'Procesado' },
  REVIEW_NEEDED: { icon: AlertCircle, color: 'text-warning', label: 'Revisión' },
  ERROR: { icon: XCircle, color: 'text-danger', label: 'Error' },
};

export default function DashboardPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | ''>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [exportLoading, setExportLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();

  const { data: documentsData, isLoading } = useQuery({
    queryKey: ['documents', page, statusFilter, searchQuery],
    queryFn: () =>
      documentsApi.listDocuments({
        page,
        size: 10,
        status: statusFilter || undefined,
        search_query: searchQuery || undefined,
      }),
  });

  const { data: documentTypes } = useQuery({
    queryKey: ['documentTypes'],
    queryFn: () => documentsApi.listDocumentTypes(),
  });

  const uploadMutation = useMutation({
    mutationFn: ({ file }: { file: File }) => documentsApi.uploadDocument(file),
    onSuccess: () => {
      toast.success('Documento subido correctamente');
      setSelectedFile(null);
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Error al subir el documento');
    },
  });

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg'];
      if (!allowedTypes.includes(file.type)) {
        toast.error('Tipo de archivo no permitido');
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        toast.error('El archivo es demasiado grande (máx. 10MB)');
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleUpload = () => {
    if (selectedFile) {
      uploadMutation.mutate({ file: selectedFile });
    }
  };

  const handleExport = async (format: 'csv' | 'xlsx') => {
    setExportLoading(true);
    try {
      await documentsApi.exportDocuments({
        format,
        status: statusFilter || undefined,
      });
    } catch {
      toast.error('Error al exportar documentos');
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-secondary-50">
      <header className="bg-white shadow-sm border-b border-secondary-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-primary-600">SAPI</h1>
              <p className="text-sm text-secondary-600">Panel de Administración</p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-secondary-600">
                Bienvenido, <strong>{user?.username}</strong>
              </span>
              <Link
                to="/login"
                onClick={() => useAuthStore.getState().logout()}
                className="text-sm text-danger hover:text-danger-700"
              >
                Cerrar Sesión
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col lg:flex-row gap-8">
          <aside className="w-full lg:w-64 bg-white rounded-xl shadow-sm p-4 h-fit">
            <nav className="space-y-2">
              <Link
                to="/"
                className="flex items-center gap-3 px-4 py-2 bg-primary-50 text-primary-700 rounded-lg font-medium"
              >
                <FileText className="w-5 h-5" />
                Documentos
              </Link>
            </nav>
          </aside>

          <div className="flex-1 space-y-6">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <h2 className="text-lg font-semibold text-secondary-900 mb-4">
                Subir Nuevo Documento
              </h2>
              <div className="flex flex-col sm:flex-row gap-4">
                <input
                  type="file"
                  id="file-upload"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <label
                  htmlFor="file-upload"
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-secondary-300 rounded-lg cursor-pointer hover:border-primary-500 hover:bg-primary-50 transition-colors"
                >
                  <Upload className="w-5 h-5 text-secondary-400" />
                  <span className="text-secondary-600">
                    {selectedFile ? selectedFile.name : 'Seleccionar archivo PDF o imagen'}
                  </span>
                </label>
                <button
                  onClick={handleUpload}
                  disabled={!selectedFile || uploadMutation.isPending}
                  className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {uploadMutation.isPending ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Upload className="w-5 h-5" />
                  )}
                  Subir
                </button>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex flex-col sm:flex-row gap-4 mb-6">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
                  <input
                    type="text"
                    placeholder="Buscar documentos..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as DocumentStatus | '')}
                  className="px-4 py-2 border border-secondary-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">Todos los estados</option>
                  <option value="UPLOADED">Subido</option>
                  <option value="PROCESSING">Procesando</option>
                  <option value="PROCESSED">Procesado</option>
                  <option value="REVIEW_NEEDED">Revisión</option>
                  <option value="ERROR">Error</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 mb-4">
                <button
                  onClick={() => handleExport('csv')}
                  disabled={exportLoading}
                  className="flex items-center gap-2 px-3 py-2 text-sm border border-secondary-300 text-secondary-700 rounded-lg hover:bg-secondary-50 disabled:opacity-50"
                >
                  {exportLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                  CSV
                </button>
                <button
                  onClick={() => handleExport('xlsx')}
                  disabled={exportLoading}
                  className="flex items-center gap-2 px-3 py-2 text-sm border border-secondary-300 text-secondary-700 rounded-lg hover:bg-secondary-50 disabled:opacity-50"
                >
                  {exportLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                  Excel
                </button>
              </div>

              {isLoading ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
                </div>
              ) : documentsData?.items.length === 0 ? (
                <div className="text-center py-12 text-secondary-500">
                  <FileText className="w-12 h-12 mx-auto mb-4 text-secondary-300" />
                  <p>No hay documentos{searchQuery && ' que coincidan con la búsqueda'}.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-secondary-200">
                        <th className="text-left py-3 px-4 font-semibold text-secondary-700">Nombre</th>
                        <th className="text-left py-3 px-4 font-semibold text-secondary-700">Tipo</th>
                        <th className="text-left py-3 px-4 font-semibold text-secondary-700">Estado</th>
                        <th className="text-left py-3 px-4 font-semibold text-secondary-700">Fecha</th>
                        <th className="text-left py-3 px-4 font-semibold text-secondary-700">Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documentsData?.items.map((doc) => {
                        const status = statusConfig[doc.status];
                        const StatusIcon = status.icon;
                        return (
                          <tr key={doc.id} className="border-b border-secondary-100 hover:bg-secondary-50">
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-3">
                                <FileText className="w-5 h-5 text-secondary-400" />
                                <span className="font-medium text-secondary-900">{doc.original_filename}</span>
                              </div>
                            </td>
                            <td className="py-3 px-4 text-secondary-600">
                              {doc.document_type_name || '-'}
                            </td>
                            <td className="py-3 px-4">
                              <span className={`inline-flex items-center gap-1 ${status.color}`}>
                                <StatusIcon className={`w-4 h-4 ${doc.status === 'PROCESSING' ? 'animate-spin' : ''}`} />
                                {status.label}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-secondary-600">
                              {new Date(doc.created_at).toLocaleDateString()}
                            </td>
                            <td className="py-3 px-4">
                              <button
                                onClick={() => navigate(`/documents/${doc.id}`)}
                                className="p-2 text-secondary-600 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                              >
                                <Eye className="w-5 h-5" />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {documentsData && documentsData.pages > 1 && (
                <div className="flex justify-center gap-2 mt-6">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-4 py-2 border border-secondary-300 rounded-lg disabled:opacity-50"
                  >
                    Anterior
                  </button>
                  <span className="px-4 py-2">
                    Página {page} de {documentsData.pages}
                  </span>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page >= documentsData.pages}
                    className="px-4 py-2 border border-secondary-300 rounded-lg disabled:opacity-50"
                  >
                    Siguiente
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
