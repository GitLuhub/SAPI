import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/api';
import { useAuthStore } from '@/contexts/auth-context';
import {
  ArrowLeft,
  Save,
  Download,
  FileText,
  Loader2,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { useState } from 'react';
import toast from 'react-hot-toast';

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  
  const [editedFields, setEditedFields] = useState<Record<string, string>>({});

  const { data: document, isLoading, error } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => documentsApi.getDocumentData(documentId!),
    enabled: !!documentId,
  });

  const updateMutation = useMutation({
    mutationFn: (updates: { field_name: string; new_value: string }[]) =>
      documentsApi.updateDocumentData(documentId!, updates),
    onSuccess: () => {
      toast.success('Datos actualizados correctamente');
      queryClient.invalidateQueries({ queryKey: ['document', documentId] });
      setEditedFields({});
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Error al actualizar');
    },
  });

  const handleFieldChange = (fieldName: string, value: string) => {
    setEditedFields((prev) => ({ ...prev, [fieldName]: value }));
  };

  const handleSave = () => {
    const updates = Object.entries(editedFields).map(([field_name, new_value]) => ({
      field_name,
      new_value,
    }));
    updateMutation.mutate(updates);
  };

  const handleDownload = () => {
    if (document) {
      documentsApi.downloadDocument(document.id, document.original_filename);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-danger mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-secondary-900 mb-2">Error al cargar el documento</h2>
          <Link to="/" className="text-primary-600 hover:underline">
            Volver al dashboard
          </Link>
        </div>
      </div>
    );
  }

  const getConfidenceColor = (confidence?: string) => {
    if (!confidence) return 'text-secondary-500';
    const value = parseFloat(confidence);
    if (value >= 0.9) return 'text-success';
    if (value >= 0.7) return 'text-warning';
    return 'text-danger';
  };

  return (
    <div className="min-h-screen bg-secondary-50">
      <header className="bg-white shadow-sm border-b border-secondary-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="flex items-center gap-2 text-secondary-600 hover:text-secondary-900"
            >
              <ArrowLeft className="w-5 h-5" />
              Volver a Documentos
            </Link>
            <span className="text-secondary-300">|</span>
            <h1 className="text-lg font-semibold text-secondary-900 truncate max-w-md">
              {document.original_filename}
            </h1>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold text-secondary-900 mb-4">
              Documento Original
            </h2>
            <div className="aspect-[3/4] bg-secondary-100 rounded-lg flex items-center justify-center">
              <div className="text-center text-secondary-500">
                <FileText className="w-16 h-16 mx-auto mb-4" />
                <p>Vista previa no disponible</p>
                <p className="text-sm mt-2">{document.mime_type}</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-semibold text-secondary-900">
                Datos Extraídos
              </h2>
              {document.document_type && (
                <span className="px-3 py-1 bg-primary-100 text-primary-700 rounded-full text-sm font-medium">
                  {document.document_type.name}
                </span>
              )}
            </div>

            {document.classification_confidence && (
              <div className="mb-6 p-4 bg-secondary-50 rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-secondary-600">Confianza de Clasificación</span>
                  <span className={`font-semibold ${getConfidenceColor(document.classification_confidence)}`}>
                    {(parseFloat(document.classification_confidence) * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full bg-secondary-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      parseFloat(document.classification_confidence) >= 0.9
                        ? 'bg-success'
                        : parseFloat(document.classification_confidence) >= 0.7
                        ? 'bg-warning'
                        : 'bg-danger'
                    }`}
                    style={{ width: `${parseFloat(document.classification_confidence) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {document.executive_summary && (
              <div className="mb-6 p-4 bg-info/10 rounded-lg border border-info/20">
                <h3 className="font-semibold text-secondary-900 mb-2">Resumen Ejecutivo</h3>
                <p className="text-secondary-600 text-sm">{document.executive_summary}</p>
              </div>
            )}

            <div className="space-y-4">
              <h3 className="font-semibold text-secondary-900">Campos Extraídos</h3>
              {document.extracted_fields.map((field) => {
                const confidence = field.ai_confidence;
                const hasChanges = editedFields[field.field_name] !== undefined;
                
                return (
                  <div key={field.field_name} className="p-3 bg-secondary-50 rounded-lg">
                    <div className="flex justify-between items-start mb-1">
                      <label className="text-sm font-medium text-secondary-700">
                        {field.field_label || field.field_name}
                      </label>
                      {confidence && (
                        <span className={`text-xs ${getConfidenceColor(confidence)}`}>
                          IA: {confidence}
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={hasChanges ? editedFields[field.field_name] : field.final_value}
                      onChange={(e) => handleFieldChange(field.field_name, e.target.value)}
                      className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 ${
                        field.is_corrected ? 'border-success bg-success/5' : ''
                      } ${hasChanges ? 'border-warning bg-warning/5' : 'border-secondary-300'}`}
                    />
                    {field.is_corrected && (
                      <div className="flex items-center gap-1 mt-1 text-xs text-success">
                        <CheckCircle className="w-3 h-3" />
                        Corregido manualmente
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {document.extracted_fields.length === 0 && (
              <div className="text-center py-8 text-secondary-500">
                <Loader2 className="w-8 h-8 mx-auto mb-2 animate-spin" />
                <p>Procesando documento...</p>
              </div>
            )}

            <div className="flex gap-4 mt-6 pt-6 border-t border-secondary-200">
              <button
                onClick={handleSave}
                disabled={Object.keys(editedFields).length === 0 || updateMutation.isPending}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {updateMutation.isPending ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Save className="w-5 h-5" />
                )}
                Guardar Cambios
              </button>
              <button
                onClick={handleDownload}
                className="flex items-center justify-center gap-2 px-4 py-3 border border-secondary-300 text-secondary-700 rounded-lg hover:bg-secondary-50"
              >
                <Download className="w-5 h-5" />
                Descargar
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
