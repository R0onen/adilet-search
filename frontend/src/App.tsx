import { Component, Suspense, lazy } from 'react';
import type { ReactNode } from 'react';
import { ArrowUpRight, Scale } from 'lucide-react';
import { NavLink, Route, Routes, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiMode } from './api/client';
import SearchPage from './pages/SearchPage';
import i18n from './i18n';

const ComparePage = lazy(() => import('./pages/ComparePage'));
class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div role="alert" className="empty">
        <h1>{i18n.t('failed')}</h1>
        <a href="/">{i18n.t('back')}</a>
      </div>
    ) : (
      this.props.children
    );
  }
}
function About() {
  const { t } = useTranslation();
  return (
    <section className="about-page">
      <span className="eyebrow">ADILET SEARCH / AI ESSENTIALS</span>
      <h1>{t('aboutTitle')}</h1>
      <p>{t('aboutText')}</p>
      <div className="notice">{t(apiMode === 'mock' ? 'aboutDemo' : 'aboutLive')}</div>
      <p>{t('disclaimer')}</p>
      <Link className="button" to="/">
        {t('back')}
      </Link>
    </section>
  );
}
export default function App() {
  const { t, i18n } = useTranslation();
  return (
    <ErrorBoundary>
      <div className="app-shell">
        <header className="site-header">
          <Link to="/" className="brand" aria-label="Adilet Search">
            <span className="brand-mark">
              <Scale size={23} />
            </span>
            <span>
              <strong>
                adilet<span className="brand-dot">.</span>
              </strong>
              <small>{t('tagline')}</small>
            </span>
          </Link>
          <nav aria-label={t('search')}>
            <NavLink to="/" end>
              {t('search')}
            </NavLink>
            <NavLink to="/compare">{t('compare')}</NavLink>
            <NavLink to="/about">
              {t('project')}
              <ArrowUpRight size={13} />
            </NavLink>
          </nav>
          <div className="header-right">
            <span className={`mode-badge ${apiMode}`}>
              <span />
              {t(apiMode === 'mock' ? 'demo' : 'live')}
            </span>
            <div className="language-switch" aria-label="UI language">
              {['ru', 'kk', 'en'].map((lang) => (
                <button
                  key={lang}
                  aria-pressed={i18n.language === lang}
                  onClick={() => void i18n.changeLanguage(lang)}
                >
                  {lang === 'kk' ? 'ҚАЗ' : lang.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </header>
        {apiMode === 'mock' && (
          <section aria-label={t('demo')} className="demo-banner">
            {t('demoNotice')}
          </section>
        )}
        <main>
          <Suspense fallback={<div className="skeleton-block" />}>
            <Routes>
              <Route path="/" element={<SearchPage />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/about" element={<About />} />
              <Route
                path="*"
                element={
                  <div className="empty">
                    <h1>{t('notFound')}</h1>
                    <Link to="/">{t('back')}</Link>
                  </div>
                }
              />
            </Routes>
          </Suspense>
        </main>
        <footer className="site-footer">
          <span className="footer-brand">
            <Scale size={15} /> adilet.
          </span>
          <span>{t('footer')}</span>
          <span>{t('sourceFooter')}</span>
        </footer>
      </div>
    </ErrorBoundary>
  );
}
