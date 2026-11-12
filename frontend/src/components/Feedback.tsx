import { useState } from 'react';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { feedback } from '../api/client';

/** 👍 / 👎 for one search result or for the generated answer. A repeat overwrites the earlier vote. */
export function Feedback({
  queryId,
  target,
  articleId,
}: {
  queryId: string;
  target: 'result' | 'answer';
  articleId?: string;
}) {
  const { t } = useTranslation();
  const [rating, setRating] = useState<1 | -1 | null>(null);
  const [failed, setFailed] = useState(false);
  async function vote(value: 1 | -1) {
    const previous = rating;
    setRating(value); // optimistic: the vote shows at once and is rolled back on failure
    setFailed(false);
    try {
      await feedback({ query_id: queryId, target, rating: value, article_id: articleId ?? null });
    } catch {
      setRating(previous);
      setFailed(true);
    }
  }
  return (
    <span className="feedback" role="group" aria-label={t('feedbackLabel')}>
      <button
        type="button"
        className="feedback-button"
        aria-pressed={rating === 1}
        aria-label={t('feedbackUp')}
        title={t('feedbackUp')}
        onClick={() => void vote(1)}
      >
        <ThumbsUp size={14} />
      </button>
      <button
        type="button"
        className="feedback-button"
        aria-pressed={rating === -1}
        aria-label={t('feedbackDown')}
        title={t('feedbackDown')}
        onClick={() => void vote(-1)}
      >
        <ThumbsDown size={14} />
      </button>
      <span className="feedback-status" aria-live="polite">
        {failed ? t('feedbackFailed') : rating !== null ? t('feedbackThanks') : ''}
      </span>
    </span>
  );
}
