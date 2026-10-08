import { ArrowUpRight, FileText, SearchX } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { apiMode } from '../api/client';
import type { SearchResult } from '../api/types';

export function Results({
  results,
  onOpen,
}: {
  results: SearchResult[];
  onOpen: (id: string) => void;
}) {
  const { t } = useTranslation();
  if (!results.length)
    return (
      <div className="empty">
        <SearchX size={30} />
        <h3>{t('noResults')}</h3>
        <p>{t('noResultsText')}</p>
      </div>
    );
  return (
    <div className="result-list">
      {results.map((result) => (
        <article className="result-card" key={result.article.article_id}>
          <div className="result-top">
            <span className="document-label">
              <FileText size={14} />
              {result.doc.short_title}
            </span>
            <span
              className={`status ${result.article.unit_status === 'excluded' || result.doc.status !== 'in_force' ? 'inactive' : ''}`}
            >
              {t(result.article.unit_status === 'excluded' ? 'excluded' : result.doc.status)}
            </span>
          </div>
          <button className="result-title" onClick={() => onOpen(result.article.article_id)}>
            <span>
              {t('article')} {result.article.number}. {result.article.title}
            </span>
            <ArrowUpRight size={20} />
          </button>
          <p className="snippet">{result.snippet}</p>
          <div className="result-bottom">
            <span>
              {t('revision')}: {result.doc.revision_date}
            </span>
            <button className="text-button" onClick={() => onOpen(result.article.article_id)}>
              {t('open')} <span aria-hidden="true">→</span>
            </button>
          </div>
          {apiMode === 'mock' && <span className="synthetic-note">{t('synthetic')}</span>}
        </article>
      ))}
    </div>
  );
}
