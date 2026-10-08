"""`POST /feedback` (contracts/api.md §3)."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import ArticleId, ContractModel

FeedbackTarget = Literal["result", "answer"]


class FeedbackRequest(ContractModel):
    query_id: UUID
    target: FeedbackTarget
    article_id: ArticleId | None = Field(default=None, description="Required when target=result")
    rating: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _article_required_for_result(self) -> "FeedbackRequest":
        if self.target == "result" and not self.article_id:
            raise ValueError("article_id is required when target is 'result'")
        return self
