import { useQuery } from '@tanstack/react-query';
import { BookOpenCheck, Languages, MessageCircle, Search } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiMode, search } from '../api/client';
import type { SearchRequest } from '../api/types';
import { AnswerPanel } from '../components/AnswerPanel';
import { ArticleDrawer } from '../components/ArticleDrawer';
import { Results } from '../components/Results';
import { SearchForm } from '../components/SearchForm';
import { Button } from '../components/ui/button';

export default function SearchPage() {
  const { t } = useTranslation();
  const [request, setRequest] = useState<SearchRequest | null>(null);
  const [articleId, setArticleId] = useState<string | null>(null);
  const results = useQuery({
    queryKey: ['search', request],
    queryFn: ({ signal }) => search(request!, signal),
    enabled: !!request,
    retry: false,
  });
  return (
    <>
      <section className={`hero ${request ? 'hero-searched' : ''}`}>
        <div className="hero-stamp">
          <span />
          {t('eyebrow')}
        </div>
        <h1>
          {t('title')}
          <br />
          <em>{t('titleAccent')}</em>
        </h1>
        <p className="hero-subtitle">{t('subtitle')}</p>
        <SearchForm onSearch={setRequest} busy={results.isFetching} />
      </section>
      {!request && (
        <section className="features" aria-label={t('project')}>
          {[MessageCircle, BookOpenCheck, Languages].map((Icon, index) => (
            <article key={index}>
              <div className="feature-icon">
                <Icon size={22} />
              </div>
              <span className="feature-number">0{index + 1}</span>
              <h2>{t(`feature${index + 1}`)}</h2>
              <p>{t(`feature${index + 1}Text`)}</p>
            </article>
          ))}
        </section>
      )}
      {request && (
        <section className="search-results" aria-busy={results.isFetching}>
          <div className="section-heading">
            <h2>
              <Search size={19} />
              {t('sources')}
            </h2>
            <span>
              {results.data
                ? t('resultCount', { count: results.data.results.length })
                : t('searching')}
            </span>
          </div>
          {results.isError && (
            <div role="alert" className="error-box">
              <h3>{t('failed')}</h3>
              <p>{results.error.message}</p>
              <Button onClick={() => void results.refetch()}>{t('retry')}</Button>
            </div>
          )}
          {results.isFetching && (
            <div className="results-layout">
              <div className="skeleton-block" />
              <div className="skeleton-block" />
            </div>
          )}
          {results.data && !results.isFetching && (
            <>
              {!!results.data.degraded?.length && (
                <div role="status" className="notice">
                  {t('degraded', { stages: results.data.degraded?.join(', ') })}
                </div>
              )}
              <div className="results-layout">
                <Results results={results.data.results} onOpen={setArticleId} />
                {results.data.results.length > 0 && (
                  <AnswerPanel
                    key={results.data.query_id}
                    request={request}
                    onOpen={setArticleId}
                  />
                )}
              </div>
              <p className="pipeline-note">
                {apiMode === 'mock'
                  ? t('mockPipeline')
                  : `${t('pipeline')}: ${results.data.pipeline_version}${results.data.timing_ms.total !== undefined ? ` · ${t('elapsed', { ms: results.data.timing_ms.total })}` : ''}`}
              </p>
            </>
          )}
        </section>
      )}
      <ArticleDrawer id={articleId} onChange={setArticleId} />
    </>
  );
}
