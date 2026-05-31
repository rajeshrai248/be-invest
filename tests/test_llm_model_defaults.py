import inspect

from fastapi.testclient import TestClient

from be_invest.api.server import app
from be_invest.llm_models import DEFAULT_CLAUDE_SONNET_MODEL
from be_invest.sources.llm_extract import extract_fee_records_via_llm


def test_default_claude_sonnet_model_is_current_shared_default():
    assert DEFAULT_CLAUDE_SONNET_MODEL == "claude-sonnet-4-6"
    assert inspect.signature(extract_fee_records_via_llm).parameters["model"].default == DEFAULT_CLAUDE_SONNET_MODEL


def test_api_openapi_uses_shared_claude_sonnet_default():
    client = TestClient(app)
    openapi = client.get("/openapi.json").json()

    parameters = openapi["paths"]["/cost-comparison-tables"]["get"]["parameters"]
    model_parameter = next(param for param in parameters if param["name"] == "model")

    assert model_parameter["schema"]["default"] == DEFAULT_CLAUDE_SONNET_MODEL
