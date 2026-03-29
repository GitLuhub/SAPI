import json
import logging
import time
from typing import Dict, List, Optional, Tuple

from google import genai
from google.genai import types

from app.core.config import settings


logger = logging.getLogger(__name__)


FACTURA_FIELDS = [
    ("numero_factura", "Número de Factura"),
    ("fecha_emision", "Fecha de Emisión"),
    ("fecha_vencimiento", "Fecha de Vencimiento"),
    ("nombre_proveedor", "Nombre del Proveedor"),
    ("nif_cif_proveedor", "NIF/CIF del Proveedor"),
    ("importe_total", "Importe Total"),
    ("importe_iva", "Importe IVA"),
]

CONTRATO_FIELDS = [
    ("partes_involucradas", "Partes Involucradas"),
    ("fecha_firma", "Fecha de Firma"),
    ("fecha_inicio", "Fecha de Inicio"),
    ("fecha_fin", "Fecha de Fin"),
    ("objeto_contrato", "Objeto del Contrato"),
    ("valor_monetario", "Valor Monetario"),
    ("clausulas_clave", "Cláusulas Clave"),
]

_MODEL = "gemini-2.5-flash"
_MAX_FAILURES = 3
_CIRCUIT_OPEN_DURATION = 120  # segundos


class GeminiAIService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not configured. AI features will be limited.")
            self.client = None
        else:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # Circuit breaker state (por instancia)
        self._failure_count: int = 0
        self._last_failure_time: Optional[float] = None

    # ------------------------------------------------------------------
    # Circuit breaker helpers
    # ------------------------------------------------------------------

    def _is_circuit_open(self) -> bool:
        """Devuelve True si el circuit breaker está abierto."""
        if self._failure_count < _MAX_FAILURES:
            return False
        elapsed = time.time() - (self._last_failure_time or 0)
        if elapsed < _CIRCUIT_OPEN_DURATION:
            return True
        # Ventana expirada → resetear
        self._failure_count = 0
        self._last_failure_time = None
        return False

    def _record_success(self) -> None:
        self._failure_count = 0
        self._last_failure_time = None

    def _record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()

    # ------------------------------------------------------------------
    # JSON parsing helper
    # ------------------------------------------------------------------

    def _parse_json_response(self, response_text: str) -> Dict:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            json_str = response_text.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Response text: {response_text[:500]}")
                raise ValueError("Invalid JSON response from AI model")

    # ------------------------------------------------------------------
    # Core API call (con circuit breaker)
    # ------------------------------------------------------------------

    def _call_gemini(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        if not self.client:
            raise RuntimeError("Gemini client not configured")

        if self._is_circuit_open():
            raise RuntimeError(
                "Gemini circuit breaker is open — service temporarily unavailable"
            )

        if image_bytes and image_mime_type:
            contents = [
                types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type),
                prompt,
            ]
        else:
            contents = [prompt]

        try:
            response = self.client.models.generate_content(
                model=_MODEL,
                contents=contents,
            )
            self._record_success()
            return response.text
        except Exception as e:
            self._record_failure()
            logger.error(f"Error calling Gemini API: {e}")
            raise

    # ------------------------------------------------------------------
    # Public service methods
    # ------------------------------------------------------------------

    def classify_document(
        self,
        text: str,
        image_bytes: Optional[bytes] = None,
        image_mime_type: Optional[str] = None,
    ) -> Tuple[str, float]:
        if not self.client:
            return "Factura de Proveedor", "0.75"

        if image_bytes:
            prompt = """Clasifica este documento como "Factura de Proveedor" o "Contrato Simple".
Responde SOLO con JSON en este formato exacto:
{"tipo": "nombre_del_tipo", "confianza": 0.95}
"""
        else:
            prompt = f"""Clasifica el siguiente documento como "Factura de Proveedor" o "Contrato Simple".

Documento:
{text[:2000]}

Responde SOLO con JSON en este formato exacto:
{{"tipo": "nombre_del_tipo", "confianza": 0.95}}
"""

        try:
            response_text = self._call_gemini(prompt, image_bytes, image_mime_type)
            result = self._parse_json_response(response_text)

            doc_type = result.get("tipo", "Factura de Proveedor")
            confidence = str(result.get("confianza", 0.75))

            if confidence.replace(".", "").isdigit():
                if float(confidence) > 1:
                    confidence = str(float(confidence) / 100)

            return doc_type, confidence
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return "Factura de Proveedor", "0.50"

    def extract_entities(
        self,
        text: str,
        doc_type: str,
        image_bytes: Optional[bytes] = None,
        image_mime_type: Optional[str] = None,
    ) -> List[Dict]:
        if not self.client:
            return []

        if "factura" in doc_type.lower():
            fields = FACTURA_FIELDS
        else:
            fields = CONTRATO_FIELDS

        fields_json = json.dumps(fields, ensure_ascii=False)

        if image_bytes:
            prompt = f"""Extrae los siguientes campos de este documento:

Campos requeridos:
{fields_json}

Responde SOLO con JSON en este formato:
{{"campos": [{{"nombre": "campo", "valor": "valor_extraido", "confianza": 0.95}}, ...]}}
"""
        else:
            prompt = f"""Extrae los siguientes campos del documento:

Campos requeridos:
{fields_json}

Documento:
{text[:3000]}

Responde SOLO con JSON en este formato:
{{"campos": [{{"nombre": "campo", "valor": "valor_extraido", "confianza": 0.95}}, ...]}}
"""

        try:
            response_text = self._call_gemini(prompt, image_bytes, image_mime_type)
            result = self._parse_json_response(response_text)

            fields_data = result.get("campos", [])
            return [
                {
                    "field_name": f.get("nombre", ""),
                    "field_label": next(
                        (label for name, label in fields if name == f.get("nombre")),
                        f.get("nombre", "")
                    ),
                    "ai_extracted_value": f.get("valor") or "",
                    "ai_confidence": str(f.get("confianza", 0.75)),
                    "final_value": f.get("valor") or "",
                }
                for f in fields_data
            ]
        except Exception as e:
            logger.error(f"Entity extraction error: {e}")
            return []

    def summarize_document(
        self,
        text: str,
        image_bytes: Optional[bytes] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        if not self.client:
            return "Resumen no disponible (AI no configurada)."

        if image_bytes:
            prompt = "Genera un resumen ejecutivo conciso de este documento (máximo 500 caracteres). Responde SOLO con el resumen, sin preamble ni explicaciones."
        else:
            prompt = f"""Genera un resumen ejecutivo conciso del siguiente documento (máximo 500 caracteres):

Documento:
{text[:3000]}

Responde SOLO con el resumen, sin preamble ni explicaciones.
"""

        try:
            response_text = self._call_gemini(prompt, image_bytes, image_mime_type)
            return response_text.strip()[:500]
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            return "Resumen no disponible debido a un error."


ai_service = GeminiAIService()
