import * as Dialog from '@radix-ui/react-dialog';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink, Languages, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { apiMode, article } from '../api/client';
import { Button } from './ui/button';

export function ArticleDrawer({
  id,
  onChange,
}: {
  id: string | null;
  onChange: (id: string | null) => void;
}) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ['article', id],
    queryFn: ({ signal }) => article(id!, signal),
    enabled: !!id,
  });
  const data = query.data;
  const safeSource = data && /^https?:\/\//.test(data.article.url) ? data.article.url : undefined;
  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={(open) => {
        if (!open) onChange(null);
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content className="drawer" aria-describedby="article-description">
          <div className="drawer-head">
            <span className="eyebrow">{t('fullText')}</span>
            <Dialog.Close className="icon-button" aria-label={t('close')}>
              <X size={22} />
            </Dialog.Close>
          </div>
          <Dialog.Title className="drawer-title">
            {data ? `${t('article')} ${data.article.number}. ${data.article.title}` : t('fullText')}
          </Dialog.Title>
          <Dialog.Description id="article-description">
            {data?.doc.title || t('searching')}
          </Dialog.Description>
          {query.isPending && <div className="skeleton-block" />}
          {query.isError && (
            <div role="alert" className="error-box">
              <p>{t('failed')}</p>
              <p>{query.error.message}</p>
              <Button onClick={() => void query.refetch()}>{t('retry')}</Button>
            </div>
          )}
          {data && (
            <>
              <div className="article-meta">
                <span
                  className={`status ${data.article.unit_status === 'excluded' || data.doc.status !== 'in_force' ? 'inactive' : ''}`}
                >
                  {t(data.article.unit_status === 'excluded' ? 'excluded' : data.doc.status)}
                </span>
                <span>
                  {t('revision')}: {data.doc.revision_date}
                </span>
                <span>{data.lang.toUpperCase()}</span>
              </div>
              {apiMode === 'mock' && <div className="notice">{t('synthetic')}</div>}
              <div className="law-text">{data.text}</div>
              {data.amendment_notes?.map((note) => (
                <p className="amendment" key={note}>
                  {note}
                </p>
              ))}
              <div className="drawer-actions">
                {data.parallel_article_id && (
                  <Button
                    className="secondary"
                    onClick={() => onChange(data.parallel_article_id || null)}
                  >
                    <Languages size={16} />
                    {t('switchArticle')}
                  </Button>
                )}
                {apiMode === 'live' && safeSource && (
                  <a className="button" href={safeSource} target="_blank" rel="noreferrer">
                    {t('source')}
                    <ExternalLink size={16} />
                  </a>
                )}
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
