import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.feedback import FeedbackRequest
from app.schemas.search import SearchFilters, SearchRequest
from tests.conftest import make_settings


def test_cors_origins_from_comma_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://adilet.example ,")
    assert Settings(_env_file=None).cors_origins == [  # type: ignore[call-arg]
        "http://localhost:5173",
        "https://adilet.example",
    ]


def test_prod_rejects_dev_session_salt() -> None:
    with pytest.raises(ValidationError, match="SESSION_SALT"):
        make_settings(environment="prod")
    assert make_settings(environment="prod", session_salt="s3cret-from-env").environment == "prod"


def test_query_is_trimmed_and_nfc_normalised() -> None:
    # "и" + combining breve composes to "й" under NFC.
    assert SearchRequest(query="  Трудовой кодекс \n").query == "Трудовой кодекс"


def test_query_length_counts_after_trimming() -> None:
    assert len(SearchRequest(query=" " + "я" * 500 + " ").query) == 500
    with pytest.raises(ValidationError):
        SearchRequest(query="я" * 501)


def test_search_defaults_match_contract() -> None:
    request = SearchRequest(query="зарплата")
    assert (request.lang, request.mode, request.top_k) == ("auto", "hybrid", 10)
    assert request.filters == SearchFilters(
        doc_types=[], doc_ids=[], in_force_only=True, date_from=None, date_to=None
    )


def test_feedback_article_required_only_for_results() -> None:
    query_id = "5f0c2a9e-3b1d-4c8e-9a47-2d6f8e1b0c3a"
    assert FeedbackRequest(query_id=query_id, target="answer", rating=1).article_id is None  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="article_id is required"):
        FeedbackRequest(query_id=query_id, target="result", rating=1)  # type: ignore[arg-type]


def test_feedback_comment_limit() -> None:
    query_id = "5f0c2a9e-3b1d-4c8e-9a47-2d6f8e1b0c3a"
    with pytest.raises(ValidationError):
        FeedbackRequest(query_id=query_id, target="answer", rating=1, comment="x" * 1001)  # type: ignore[arg-type]


def test_article_id_format() -> None:
    query_id = "5f0c2a9e-3b1d-4c8e-9a47-2d6f8e1b0c3a"
    for bad in ("K1500000414:kz:a113", "K1500000414:ru:A113", "a113"):
        with pytest.raises(ValidationError):
            FeedbackRequest(query_id=query_id, target="result", rating=1, article_id=bad)  # type: ignore[arg-type]
