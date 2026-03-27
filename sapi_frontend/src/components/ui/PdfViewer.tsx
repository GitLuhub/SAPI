import { useEffect, useState } from 'react';
import { documentsApi } from '@/api';
import { Loader2, FileText, AlertCircle } from 'lucide-react';

interface PdfViewerProps {
  documentId: string;
  mimeType: string;
}

export default function PdfViewer({ documentId, mimeType }: PdfViewerProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let url: string | null = null;

    documentsApi
      .previewDocument(documentId)
      .then((objectUrl) => {
        url = objectUrl;
        setBlobUrl(objectUrl);
      })
      .catch(() => setError(true))
      .finally(() => setIsLoading(false));

    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentId]);

  if (isLoading) {
    return (
      <div className="aspect-[3/4] bg-secondary-100 rounded-lg flex items-center justify-center">
        <Loader2 className="w-10 h-10 animate-spin text-primary-500" />
      </div>
    );
  }

  if (error || !blobUrl) {
    return (
      <div className="aspect-[3/4] bg-secondary-100 rounded-lg flex items-center justify-center">
        <div className="text-center text-secondary-500">
          <AlertCircle className="w-12 h-12 mx-auto mb-3 text-danger" />
          <p className="text-sm">No se pudo cargar la vista previa</p>
        </div>
      </div>
    );
  }

  if (mimeType === 'application/pdf') {
    return (
      <iframe
        src={blobUrl}
        title="Vista previa del documento"
        className="w-full aspect-[3/4] rounded-lg border border-secondary-200"
      />
    );
  }

  if (mimeType.startsWith('image/')) {
    return (
      <div className="aspect-[3/4] bg-secondary-100 rounded-lg overflow-hidden flex items-center justify-center">
        <img
          src={blobUrl}
          alt="Vista previa del documento"
          className="max-w-full max-h-full object-contain"
        />
      </div>
    );
  }

  return (
    <div className="aspect-[3/4] bg-secondary-100 rounded-lg flex items-center justify-center">
      <div className="text-center text-secondary-500">
        <FileText className="w-16 h-16 mx-auto mb-4" />
        <p className="text-sm">Vista previa no disponible para este tipo de archivo</p>
        <p className="text-xs mt-1">{mimeType}</p>
      </div>
    </div>
  );
}
