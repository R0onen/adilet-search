import { useEffect, useRef, useState } from 'react';
import { BookOpenCheck, Sparkles, Square } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { apiMode } from '../api/client';
import { answer } from '../api/sse';
import type { AnswerSource, SearchRequest } from '../api/types';
import { Button } from './ui/button';

export function AnswerPanel({
  request,
  onOpen,
}: {
  request: SearchRequest;
  onOpen: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const [sources, setSources] = useState<AnswerSource[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [stopped, setStopped] = useState(false);
  const [grounded, setGrounded] = useState<boolean | null>(null);
  const [degraded, setDegraded] = useState<string[]>([]);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function generate() {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setBusy(true);
    setText('');
    setSources([]);
    setError('');
    setStopped(false);
    setGrounded(null);
    setDegraded([]);
    try {
      await answer(
        request,
        {
          sources: (event) => {
            setSources(event.sources);
            setDegraded(event.degraded || []);
          },
          token: (token) => setText((previous) => previous + token),
          done: (event) => {
            setText(event.text);
            setGrounded(event.grounded);
          },
        },
        current.signal,
      );
    } catch (caught) {
      if (current.signal.aborted) setStopped(true);
      else setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      if (controller.current === current) setBusy(false);
    }
  }
  return (
    <aside className="answer-panel">
      <div className="answer-heading">
        <span className="sparkle-tile">
          <Sparkles size={20} />
        </span>
        <div>
          <h2>{t(apiMode === 'mock' ? 'mockAnswer' : 'aiAnswer')}</h2>
          <span className="answer-label">
            {apiMode === 'mock' ? 'SCRIPTED DEMO' : 'RAG · SOURCES FIRST'}
          </span>
        </div>
      </div>
      {!text && !busy && <p className="answer-intro">{t('answerIntro')}</p>}
      {text && (
        <div className="answer-text" aria-live={busy ? 'off' : 'polite'}>
          {text.split(/(\[\d+\])/g).map((part, index) => {
            const match = /^\[(\d+)\]$/.exec(part);
            if (!match) return <span key={index}>{part}</span>;
            const source = sources.find((item) => item.ref === Number(match[1]));
            return source ? (
              <button
                key={index}
                className="citation"
                aria-label={`${t('open')} ${source.article.number}`}
                onClick={() => onOpen(source.article.article_id)}
              >
                {part}
              </button>
            ) : (
              <span key={index} title={t('invalidCitation')}>
                {part}
              </span>
            );
          })}
          {busy && <span className="stream-cursor" />}
        </div>
      )}
      {busy && !text && <div className="skeleton-block" />}
      {sources.length > 0 && (
        <div className="answer-sources">
          {sources.map((source) => (
            <button key={source.ref} onClick={() => onOpen(source.article.article_id)}>
              <BookOpenCheck size={15} />
              <span>
                [{source.ref}] {source.doc.short_title} · {t('article')} {source.article.number}
              </span>
            </button>
          ))}
        </div>
      )}
      {grounded === false && (
        <p role="status" className="notice">
          {t('ungrounded')}
        </p>
      )}
      {!!degraded.length && (
        <p role="status" className="notice">
          {t('degraded', { stages: degraded.join(', ') })}
        </p>
      )}
      {error && (
        <div role="alert" className="error-box">
          <p>{t('answerUnavailable')}</p>
          <small>{error}</small>
        </div>
      )}
      {stopped && (
        <p role="status" className="notice">
          {t('stopped')}
        </p>
      )}
      <Button
        className={busy ? 'secondary full-width' : 'full-width'}
        onClick={() => (busy ? controller.current?.abort() : void generate())}
      >
        {busy ? (
          <>
            <Square size={14} />
            {t('stop')}
          </>
        ) : (
          <>
            <Sparkles size={16} />
            {t(error ? 'retry' : 'generate')}
          </>
        )}
      </Button>
      <p className="disclaimer">{t('disclaimer')}</p>
    </aside>
  );
}
