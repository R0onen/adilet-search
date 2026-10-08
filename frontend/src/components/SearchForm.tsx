import { ArrowRight, Search, SlidersHorizontal } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { documents } from '../api/client';
import type { SearchRequest } from '../api/types';
import { Button } from './ui/button';

export function SearchForm({
  onSearch,
  busy = false,
  compact = false,
}: {
  onSearch: (request: SearchRequest) => void;
  busy?: boolean;
  compact?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState('');
  const [lang, setLang] = useState<'auto' | 'ru' | 'kk'>('auto');
  const [docId, setDocId] = useState('');
  const [inForce, setInForce] = useState(true);
  const sourceLanguage = lang === 'auto' ? (/[әғқңөұүһі]/i.test(query) ? 'kk' : 'ru') : lang;
  const docs = useQuery({
    queryKey: ['documents', sourceLanguage],
    queryFn: ({ signal }) => documents(sourceLanguage, signal),
  });
  const makeRequest = (text: string): SearchRequest => ({
    query: text.trim(),
    lang,
    mode: 'hybrid',
    top_k: 10,
    filters: {
      doc_ids: docId ? [docId] : [],
      doc_types: [],
      in_force_only: inForce,
      date_from: null,
      date_to: null,
    },
  });
  const examples =
    i18n.language === 'kk'
      ? [
          'Жалақымды төлемейді',
          'Мені қысқартуға байланысты жұмыстан шығарады',
          'Ауаны ластағаны үшін айыппұл',
        ]
      : ['Мне не платят зарплату', 'Меня увольняют по сокращению', 'Штраф за загрязнение воздуха'];
  return (
    <div className={`search-area ${compact ? 'compact' : ''}`}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (query.trim()) onSearch(makeRequest(query));
        }}
      >
        <div className="search-input-wrap">
          <Search className="search-icon" size={23} />
          <label htmlFor="question" className="sr-only">
            {t('inputLabel')}
          </label>
          <input
            id="question"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('placeholder')}
            maxLength={500}
            required
            autoComplete="off"
          />
          <Button type="submit" disabled={busy || !query.trim()}>
            {busy ? t('searching') : t(compact ? 'compareSubmit' : 'submit')}
            <ArrowRight size={18} />
          </Button>
        </div>
        <div className="search-filters">
          <SlidersHorizontal size={15} />
          <label>
            <span className="sr-only">{t('language')}</span>
            <select
              aria-label={t('language')}
              value={lang}
              onChange={(event) => setLang(event.target.value as typeof lang)}
            >
              <option value="auto">
                {t('language')}: {t('auto')}
              </option>
              <option value="ru">Русский</option>
              <option value="kk">Қазақша</option>
            </select>
          </label>
          <span className="filter-divider" />
          <label>
            <span className="sr-only">{t('allActs')}</span>
            <select
              aria-label={t('allActs')}
              value={docId}
              onChange={(event) => setDocId(event.target.value)}
            >
              <option value="">{t('allActs')}</option>
              {docs.data?.items.map((doc) => (
                <option key={doc.doc_id} value={doc.doc_id}>
                  {doc.short_title}
                </option>
              ))}
            </select>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={inForce}
              onChange={(event) => setInForce(event.target.checked)}
            />
            {t('inForce')}
          </label>
        </div>
      </form>
      <div className="examples">
        <span>{t('examples')}</span>
        <div>
          {examples.map((example, index) => (
            <button
              type="button"
              disabled={busy}
              key={example}
              onClick={() => {
                setQuery(example);
                onSearch(makeRequest(example));
              }}
            >
              {t(['exampleSalary', 'exampleDismissal', 'exampleEco'][index])}
              <ArrowRight size={13} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
