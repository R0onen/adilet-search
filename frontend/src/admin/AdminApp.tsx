import { useState } from 'react';
import type { FormEvent } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { BarChart3, ListFilter, LogOut, ServerCog } from 'lucide-react';
import { AdminError } from '../api/admin';
import { Button } from '../components/ui/button';
import { AuthProvider, RequireAuth, useAuth } from './auth';
import Dashboard from './Dashboard';
import Queries from './Queries';
import System from './System';
import './admin.css';

function Login() {
  const { authenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from || '/admin';
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  if (authenticated) return <Navigate to={from} replace />;
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError('Введите логин и пароль');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await login(username.trim(), password);
      void navigate(from, { replace: true });
    } catch (caught) {
      if (caught instanceof AdminError && caught.status === 401)
        setError('Неверный логин или пароль');
      else if (caught instanceof AdminError && caught.status === 429)
        setError(`Слишком много попыток. Повторите через ${caught.retryAfter ?? 60} с`);
      else setError('Не удалось войти: сервер недоступен');
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="admin-login">
      <h1>Вход для администратора</h1>
      <form onSubmit={(event) => void submit(event)} noValidate>
        <label>
          Логин
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            autoFocus
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>
        {error && (
          <p role="alert" className="admin-form-error">
            {error}
          </p>
        )}
        <Button type="submit" className="full-width" disabled={busy}>
          {busy ? 'Входим…' : 'Войти'}
        </Button>
      </form>
    </section>
  );
}

function Layout() {
  const { logout } = useAuth();
  return (
    <section className="admin-page">
      <nav className="admin-nav" aria-label="Разделы панели администратора">
        <NavLink to="/admin" end>
          <BarChart3 size={16} /> Статистика
        </NavLink>
        <NavLink to="/admin/queries">
          <ListFilter size={16} /> Журнал запросов
        </NavLink>
        <NavLink to="/admin/system">
          <ServerCog size={16} /> Система
        </NavLink>
        <button className="text-button admin-logout" onClick={logout}>
          <LogOut size={15} /> Выйти
        </button>
      </nav>
      <Routes>
        <Route index element={<Dashboard />} />
        <Route path="queries" element={<Queries />} />
        <Route path="system" element={<System />} />
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </section>
  );
}

/** Mounted lazily at /admin/*: none of this is in the public bundle. */
export default function AdminApp() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="login" element={<Login />} />
        <Route
          path="*"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        />
      </Routes>
    </AuthProvider>
  );
}
