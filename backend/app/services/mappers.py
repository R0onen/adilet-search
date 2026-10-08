"""ORM rows -> contract objects."""

from app.db.models import Article, Document
from app.schemas.common import ArticleRef, DocumentRef


def document_ref(doc: Document) -> DocumentRef:
    return DocumentRef.model_validate(
        {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "short_title": doc.short_title,
            "doc_type": doc.doc_type,
            "number": doc.number,
            "adopted_date": doc.adopted_date,
            "revision_date": doc.revision_date,
            "status": doc.status,
            "url": doc.source_url,
        }
    )


def article_ref(article: Article) -> ArticleRef:
    return ArticleRef.model_validate(
        {
            "article_id": article.article_id,
            "unit_type": article.unit_type,
            "number": article.unit_number,
            "title": article.unit_title,
            "section_title": article.section_title,
            "chapter_title": article.chapter_title,
            "unit_status": article.unit_status,
            "has_amendments": article.has_amendments,
            "url": article.source_url,
        }
    )
