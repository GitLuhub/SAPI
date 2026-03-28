import pytest
from unittest.mock import patch, MagicMock
from app.services.ai_service import GeminiAIService


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_gemini_service_classification(mock_genai):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = '{"tipo": "Factura de Proveedor", "confianza": 0.98}'
    mock_genai.GenerativeModel.return_value = mock_model

    service = GeminiAIService()
    doc_type, confidence = service.classify_document("Some invoice text")

    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.98"


def test_classify_document_no_client():
    """When client is None (no API key), returns a default value without crashing."""
    with patch("app.services.ai_service.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = None
        service = GeminiAIService()

    doc_type, confidence = service.classify_document("some text")
    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.75"


@patch("app.services.ai_service.genai")
def test_classify_document_api_error_returns_fallback(mock_genai):
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("API unavailable")
    mock_genai.GenerativeModel.return_value = mock_model

    service = GeminiAIService()
    doc_type, confidence = service.classify_document("text")

    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.50"


@patch("app.services.ai_service.genai")
def test_classify_document_confidence_above_1_normalized(mock_genai):
    """Confidence > 1 (e.g. percentage 98) should be normalised to 0-1."""
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = '{"tipo": "Contrato Simple", "confianza": 98}'
    mock_genai.GenerativeModel.return_value = mock_model

    service = GeminiAIService()
    _, confidence = service.classify_document("contract text")
    assert float(confidence) <= 1.0


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_gemini_service_extract_entities(mock_genai):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = (
        '{"campos": [{"nombre": "numero_factura", "valor": "INV-123", "confianza": 0.95}]}'
    )
    mock_genai.GenerativeModel.return_value = mock_model

    service = GeminiAIService()
    entities = service.extract_entities("Invoice content", "Factura de Proveedor")

    assert len(entities) == 1
    assert entities[0]["field_name"] == "numero_factura"
    assert entities[0]["ai_extracted_value"] == "INV-123"
    assert entities[0]["ai_confidence"] == "0.95"


@patch("app.services.ai_service.genai")
def test_extract_entities_contrato_type(mock_genai):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = (
        '{"campos": [{"nombre": "partes_involucradas", "valor": "Empresa A y B", "confianza": 0.88}]}'
    )
    mock_genai.GenerativeModel.return_value = mock_model

    service = GeminiAIService()
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
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("timeout")
    mock_genai.GenerativeModel.return_value = mock_model

    service = GeminiAIService()
    result = service.extract_entities("text", "Factura de Proveedor")
    assert result == []


# ---------------------------------------------------------------------------
# Summarize
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_summarize_document(mock_genai):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = "  Este contrato establece los términos.  "
    mock_genai.GenerativeModel.return_value = mock_model

    service = GeminiAIService()
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
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("error")
    mock_genai.GenerativeModel.return_value = mock_model

    service = GeminiAIService()
    summary = service.summarize_document("text")
    assert "error" in summary.lower()


# ---------------------------------------------------------------------------
# _parse_json_response — markdown-wrapped JSON
# ---------------------------------------------------------------------------

@patch("app.services.ai_service.genai")
def test_parse_json_markdown_wrapper(mock_genai):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = (
        "```json\n{\"tipo\": \"Factura de Proveedor\", \"confianza\": 0.9}\n```"
    )
    mock_genai.GenerativeModel.return_value = mock_model

    service = GeminiAIService()
    doc_type, confidence = service.classify_document("invoice text")
    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.9"
