import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Pipeline from './pages/Pipeline';
import RequestDetail from './pages/RequestDetail';
import ReviewQueue from './pages/ReviewQueue';
import EmailDrafts from './pages/EmailDrafts';
import Settings from './pages/Settings';
import Reports from './pages/Reports';
import Zendesk from './pages/Zendesk';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/pipeline" replace />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="/requests/:id" element={<RequestDetail />} />
        <Route path="/reviews" element={<ReviewQueue />} />
        <Route path="/email-drafts" element={<EmailDrafts />} />
        <Route path="/zendesk" element={<Zendesk />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/reports" element={<Reports />} />
      </Route>
    </Routes>
  );
}
