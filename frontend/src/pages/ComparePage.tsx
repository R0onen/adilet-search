import { useQuery } from '@tanstack/react-query';
import { ArrowLeftRight } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiMode, search } from '../api/client';
import type { SearchRequest } from '../api/types';
import { ArticleDrawer } from '../components/ArticleDrawer';
import { Results } from '../components/Results';
import { SearchForm } from '../components/SearchForm';
import { Button } from '../components/ui/button';

export default function ComparePage() {
  const { t } = useTranslation();
  const [request, setRequest] = useState<SearchRequest | null>(null);
  const [articleId, setArticleId] = useState<string | null>(null);
  const comparison = useQuery({
    queryKey: ['compare', request],
    queryFn: ({ signal }) =>
      Promise.all([
        search({ ...request!, mode: 'keyword' }, signal),
        search({ ...request!, mode: 'hybrid' }, signal),
      ]),
    enabled: !!request,
    retry: false,
  });
  return (
    <section className="compare-page">
      <div className="page-intro">
        <span className="hero-stamp">
          <ArrowLeftRight size={16} />
          {t('compare')}
        </span>
        <h1>{t('compareTitle')}</h1>
        <p>{t(apiMode === 'mock' ? 'compareText' : 'compareLive')}</p>
      </div>
      <SearchForm compact onSearch={setRequest} busy={comparison.isFetching} />
      {!request && (
        <div className="empty">
          <ArrowLeftRight size={28} />
          <p>{t('noComparison')}</p>
        </div>
      )}
      {comparison.isFetching && (
        <div className="compare-grid">
          <div className="skeleton-block" />
          <div className="skeleton-block" />
        </div>
      )}
      {comparison.isError && (
        <div role="alert" className="error-box">
          <p>
            {t('failed')}: {comparison.error.message}
          </p>
          <Button onClick={() => void comparison.refetch()}>{t('retry')}</Button>
        </div>
      )}
      {comparison.data && !comparison.isFetching && (
        <div className="compare-grid">
          {comparison.data.map((response, index) => (
            <section key={index} className={index ? 'smart-column' : ''}>
              <div className="section-heading">
                <h2>{t(index ? 'semantic' : 'keyword')}</h2>
                <span>{t('resultCount', { count: response.results.length })}</span>
              </div>
              {!!response.degraded?.length && (
                <p className="notice">{t('degraded', { stages: response.degraded?.join(', ') })}</p>
              )}
              <Results results={response.results} onOpen={setArticleId} />
            </section>
          ))}
        </div>
      )}
      <ArticleDrawer id={articleId} onChange={setArticleId} />
    </section>
  );
}
