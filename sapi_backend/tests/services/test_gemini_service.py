import time
import pytest
from unittest.mock import patch, MagicMock
from app.services.ai_service import GeminiAIService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(mock_genai):
    """Crea una instancia con cliente mockeado."""
    return GeminiAIService()


def _set_response(mock_genai, text: str):
    """Configura el mock para devolver `text` como respuesta de generate_content."""
    mock_genai.Client.return_value.models.generate_content.return_value.text = text


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_gemini_service_classification(mock_genai):
    _set_response(mock_genai, '{"tipo": "Factura de Proveedor", "confianza": 0.98}')

    service = _make_service(mock_genai)
    doc_type, confidence = service.classify_document("Some invoice text")

    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.98"


def test_classify_document_no_client():
    """Cuando no hay API key, devuelve valor por defecto sin crashear."""
    with patch("app.services.ai_service.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = None
        service = GeminiAIService()

    doc_type, confidence = service.classify_document("some text")
    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.75"


@patch("app.services.ai_service.genai")
def test_classify_document_api_error_returns_fallback(mock_genai):
    mock_genai.Client.return_value.models.generate_content.side_effect = Exception("API unavailable")

    service = _make_service(mock_genai)
    doc_type, confidence = service.classify_document("text")

    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.50"


@patch("app.services.ai_service.genai")
def test_classify_document_confidence_above_1_normalized(mock_genai):
    """Confianza > 1 (ej: porcentaje 98) se normaliza a 0-1."""
    _set_response(mock_genai, '{"tipo": "Contrato Simple", "confianza": 98}')

    service = _make_service(mock_genai)
    _, confidence = service.classify_document("contract text")
    assert float(confidence) <= 1.0


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_gemini_service_extract_entities(mock_genai):
    _set_response(
        mock_genai,
        '{"campos": [{"nombre": "numero_factura", "valor": "INV-123", "confianza": 0.95}]}',
    )

    service = _make_service(mock_genai)
    entities = service.extract_entities("Invoice content", "Factura de Proveedor")

    assert len(entities) == 1
    assert entities[0]["field_name"] == "numero_factura"
    assert entities[0]["ai_extracted_value"] == "INV-123"
    assert entities[0]["ai_confidence"] == "0.95"


@patch("app.services.ai_service.genai")
def test_extract_entities_contrato_type(mock_genai):
    _set_response(
        mock_genai,
        '{"campos": [{"nombre": "partes_involucradas", "valor": "Empresa A y B", "confianza": 0.88}]}',
    )

    service = _make_service(mock_genai)
    entities = service.extract_entities("Contract content", "Contrato Simple")

    assert len(entities) == 1
    assert entities[0]["field_name"] == "partes_involucradas"


def test_extract_entities_no_client():
    with patch("app.services.ai_service.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = None
        service = GeminiAIService()

    result = service.extract_entities("text", "Factura de Proveedor")
    assert result == []


@patch("app.services.ai_service.genai")
def test_extract_entities_api_error_returns_empty(mock_genai):
    mock_genai.Client.return_value.models.generate_content.side_effect = Exception("timeout")

    service = _make_service(mock_genai)
    result = service.extract_entities("text", "Factura de Proveedor")
    assert result == []


# ---------------------------------------------------------------------------
# Summarize
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_summarize_document(mock_genai):
    _set_response(mock_genai, "  Este contrato establece los términos.  ")

    service = _make_service(mock_genai)
    summary = service.summarize_document("contract content")

    assert summary == "Este contrato establece los términos."


def test_summarize_document_no_client():
    with patch("app.services.ai_service.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = None
        service = GeminiAIService()

    summary = service.summarize_document("any text")
    assert "no disponible" in summary.lower()


@patch("app.services.ai_service.genai")
def test_summarize_document_api_error_returns_fallback(mock_genai):
    mock_genai.Client.return_value.models.generate_content.side_effect = Exception("error")

    service = _make_service(mock_genai)
    summary = service.summarize_document("text")
    assert "error" in summary.lower()


# ---------------------------------------------------------------------------
# _parse_json_response — markdown-wrapped JSON
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_parse_json_markdown_wrapper(mock_genai):
    _set_response(
        mock_genai,
        '```json\n{"tipo": "Factura de Proveedor", "confianza": 0.9}\n```',
    )

    service = _make_service(mock_genai)
    doc_type, confidence = service.classify_document("invoice text")
    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.9"


# ---------------------------------------------------------------------------
# _parse_json_response — JSON completamente inválido
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_parse_json_response_invalid_raises_value_error(mock_genai):
    """Ambos intentos de parseo JSON fallan → classify devuelve fallback."""
    _set_response(mock_genai, "this is definitely not json at all!!!")

    service = _make_service(mock_genai)
    doc_type, confidence = service.classify_document("text")
    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.50"


# ---------------------------------------------------------------------------
# _call_gemini — sin cliente configurado
# ---------------------------------------------------------------------------

def test_call_gemini_no_client_raises_runtime_error():
    """_call_gemini lanza RuntimeError cuando client es None."""
    with patch("app.services.ai_service.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = None
        service = GeminiAIService()

    with pytest.raises(RuntimeError, match="not configured"):
        service._call_gemini("any prompt")


# ---------------------------------------------------------------------------
# Multimodal — image bytes passed to Gemini (nueva API con types.Part)
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
@patch("app.services.ai_service.types")
def test_call_gemini_with_image_bytes(mock_types, mock_genai):
    """_call_gemini construye types.Part y lo pasa junto al prompt."""
    mock_part = MagicMock()
    mock_types.Part.from_bytes.return_value = mock_part
    mock_genai.Client.return_value.models.generate_content.return_value.text = "image response"

    service = _make_service(mock_genai)
    result = service._call_gemini("describe this", b"\x89PNG", "image/png")

    mock_types.Part.from_bytes.assert_called_once_with(data=b"\x89PNG", mime_type="image/png")
    mock_genai.Client.return_value.models.generate_content.assert_called_once_with(
        model="gemini-2.5-flash",
        contents=[mock_part, "describe this"],
    )
    assert result == "image response"


@patch("app.services.ai_service.genai")
@patch("app.services.ai_service.types")
def test_classify_document_with_image(mock_types, mock_genai):
    """classify_document pasa image_bytes a _call_gemini."""
    mock_types.Part.from_bytes.return_value = MagicMock()
    _set_response(mock_genai, '{"tipo": "Factura de Proveedor", "confianza": 0.92}')

    service = _make_service(mock_genai)
    doc_type, confidence = service.classify_document("", b"\x89PNG", "image/png")

    assert doc_type == "Factura de Proveedor"
    assert float(confidence) == 0.92
    mock_types.Part.from_bytes.assert_called_once()


@patch("app.services.ai_service.genai")
@patch("app.services.ai_service.types")
def test_extract_entities_with_image(mock_types, mock_genai):
    """extract_entities usa prompt de imagen cuando se proporcionan image_bytes."""
    mock_types.Part.from_bytes.return_value = MagicMock()
    _set_response(
        mock_genai,
        '{"campos": [{"nombre": "numero_factura", "valor": "F-001", "confianza": 0.93}]}',
    )

    service = _make_service(mock_genai)
    entities = service.extract_entities("", "Factura de Proveedor", b"\xff\xd8\xff", "image/jpeg")

    assert len(entities) == 1
    assert entities[0]["field_name"] == "numero_factura"
    assert entities[0]["ai_extracted_value"] == "F-001"
    mock_types.Part.from_bytes.assert_called_once()


@patch("app.services.ai_service.genai")
@patch("app.services.ai_service.types")
def test_summarize_document_with_image(mock_types, mock_genai):
    """summarize_document pasa image bytes a _call_gemini."""
    mock_types.Part.from_bytes.return_value = MagicMock()
    _set_response(mock_genai, "Factura de servicios de consultoría.")

    service = _make_service(mock_genai)
    summary = service.summarize_document("", b"\xff\xd8\xff", "image/jpeg")

    assert summary == "Factura de servicios de consultoría."
    mock_types.Part.from_bytes.assert_called_once()


# ---------------------------------------------------------------------------
# Circuit Breaker (I3)
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_circuit_breaker_opens_after_max_failures(mock_genai):
    """Tras 3 fallos, el circuito se abre y las llamadas se rechazan sin tocar la API."""
    mock_genai.Client.return_value.models.generate_content.side_effect = Exception("API down")

    service = _make_service(mock_genai)
    # Producir 3 fallos consecutivos
    for _ in range(3):
        try:
            service._call_gemini("test")
        except Exception:
            pass

    assert service._failure_count == 3

    # La siguiente llamada debe fallar con circuit breaker, sin llamar a la API
    api_call_count_before = mock_genai.Client.return_value.models.generate_content.call_count
    with pytest.raises(RuntimeError, match="circuit breaker"):
        service._call_gemini("test")
    assert mock_genai.Client.return_value.models.generate_content.call_count == api_call_count_before


@patch("app.services.ai_service.genai")
def test_circuit_breaker_resets_on_success(mock_genai):
    """Una llamada exitosa resetea el contador de fallos."""
    _set_response(mock_genai, '{"tipo": "Factura de Proveedor", "confianza": 0.9}')

    service = _make_service(mock_genai)
    service._failure_count = 2  # Dos fallos previos

    service._call_gemini("prompt")  # Llamada exitosa

    assert service._failure_count == 0
    assert service._last_failure_time is None


@patch("app.services.ai_service.genai")
def test_circuit_breaker_resets_after_duration(mock_genai):
    """Tras expirar la ventana de 2 minutos, el circuito se cierra automáticamente."""
    _set_response(mock_genai, "OK")

    service = _make_service(mock_genai)
    service._failure_count = 3
    service._last_failure_time = time.time() - 121  # 2 min + 1 s atrás

    # No debe lanzar circuit breaker
    result = service._call_gemini("test")
    assert result == "OK"
    assert service._failure_count == 0  # Reseteado en _is_circuit_open + éxito
