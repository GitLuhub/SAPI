import pytest
from unittest.mock import patch, MagicMock
from app.services.ai_service import GeminiAIService

@patch("app.services.ai_service.genai")
def test_gemini_service_classification(mock_genai):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = '{"tipo": "Factura de Proveedor", "confianza": 0.98}'
    mock_genai.GenerativeModel.return_value = mock_model
    
    service = GeminiAIService()
    doc_type, confidence = service.classify_document("Some invoice text")
    
    assert doc_type == "Factura de Proveedor"
    assert confidence == "0.98"

@patch("app.services.ai_service.genai")
def test_gemini_service_extract_entities(mock_genai):
    mock_model = MagicMock()
    mock_model.generate_content.return_value.text = '{"campos": [{"nombre": "numero_factura", "valor": "INV-123", "confianza": 0.95}]}'
    mock_genai.GenerativeModel.return_value = mock_model
    
    service = GeminiAIService()
    entities = service.extract_entities("Invoice content", "Factura de Proveedor")
    
    assert len(entities) == 1
    assert entities[0]["field_name"] == "numero_factura"
    assert entities[0]["ai_extracted_value"] == "INV-123"
    assert entities[0]["ai_confidence"] == "0.95"
