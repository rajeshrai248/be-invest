from be_invest.api.i18n import (
    get_language_name,
    localize_structured_notes,
    translate_description,
)
from be_invest.api.schemas import ChatRequest, FeedbackRequest, NewsFlashRequest


def test_api_schema_models_keep_existing_shapes():
    chat = ChatRequest(question="Which broker is cheapest?", history=[{"role": "user", "content": "Hi"}])
    news = NewsFlashRequest(broker="Degiro", title="Update", summary="Summary", url="https://example.com/news")
    feedback = FeedbackRequest(trace_id="trace-1", rating="up")

    assert chat.history is not None
    assert chat.history[0].role == "user"
    assert str(news.url).startswith("https://example.com/news")
    assert feedback.comment is None


def test_i18n_helpers_localize_without_mutating_source():
    notes = {
        "Broker": [
            {
                "category": "custody",
                "label": "Custody fee",
                "description": "Free",
                "highlight": "advantage",
            }
        ]
    }

    localized = localize_structured_notes(notes, "fr-be")

    assert get_language_name("nl-be") == "Dutch (Belgian)"
    assert translate_description("Free", "nl-be") == "Gratis"
    assert localized["Broker"][0]["label"] == "Frais de garde"
    assert localized["Broker"][0]["description"] == "Gratuit"
    assert notes["Broker"][0]["label"] == "Custody fee"
