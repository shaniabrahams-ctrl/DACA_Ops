/* ------------------------------------------------------------------ */
/*  Thin fetch wrapper for the FastAPI backend at /api/v1/*            */
/* ------------------------------------------------------------------ */

const BASE_URL = '/api/v1';

/** Generic JSON fetch with error handling. */
async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      // The backend reads X-Actor-Id for audit attribution
      'X-Actor-Id': 'dashboard-user',
      ...((options.headers as Record<string, string>) ?? {}),
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}

/* ======================== DACA Requests ======================== */

import type {
  DacaRequest,
  DacaRequestListItem,
  CompliancePackage,
  Agreement,
  EmailThread,
  EmailDraft,
  HumanReview,
  AuditLog,
  OversightConfig,
  PipelineReport,
  SLAReport,
  VolumeDataPoint,
  HumanReviewReport,
  AgentPerformance,
  Borrower,
  Lender,
} from '../types';

export const dacaRequests = {
  list(params?: {
    status?: string;
    priority?: string;
    assigned_to?: string;
    limit?: number;
    offset?: number;
  }) {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.priority) qs.set('priority', params.priority);
    if (params?.assigned_to) qs.set('assigned_to', params.assigned_to);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const q = qs.toString();
    return request<DacaRequestListItem[]>(`/daca-requests${q ? `?${q}` : ''}`);
  },

  get(id: string) {
    return request<DacaRequest>(`/daca-requests/${id}`);
  },

  transition(id: string, targetStatus: string, rationale?: string) {
    return request<DacaRequest>(`/daca-requests/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify({ target_status: targetStatus, rationale }),
    });
  },

  timeline(id: string, limit = 100, offset = 0) {
    return request<AuditLog[]>(
      `/daca-requests/${id}/timeline?limit=${limit}&offset=${offset}`,
    );
  },
};

/* ======================== Borrowers / Lenders ======================== */

export const borrowers = {
  get(id: string) {
    return request<Borrower>(`/borrowers/${id}`);
  },
};

export const lenders = {
  get(id: string) {
    return request<Lender>(`/lenders/${id}`);
  },
};

/* ======================== Compliance ======================== */

export const compliance = {
  get(dacaRequestId: string) {
    return request<CompliancePackage>(`/compliance/${dacaRequestId}`);
  },
  update(packageId: string, data: Partial<CompliancePackage>) {
    return request<CompliancePackage>(`/compliance/${packageId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },
};

/* ======================== Agreements ======================== */

export const agreements = {
  getByRequest(dacaRequestId: string) {
    return request<Agreement>(`/agreements/${dacaRequestId}`);
  },
};

/* ======================== Email Threads ======================== */

export const emailThreads = {
  list(params?: { daca_request_id?: string; awaiting_response?: boolean }) {
    const qs = new URLSearchParams();
    if (params?.daca_request_id) qs.set('daca_request_id', params.daca_request_id);
    if (params?.awaiting_response !== undefined)
      qs.set('awaiting_response', String(params.awaiting_response));
    const q = qs.toString();
    return request<EmailThread[]>(`/email-threads${q ? `?${q}` : ''}`);
  },
};

/* ======================== Email Drafts ======================== */

export const emailDrafts = {
  list(params?: { daca_request_id?: string; status?: string }) {
    const qs = new URLSearchParams();
    if (params?.daca_request_id) qs.set('daca_request_id', params.daca_request_id);
    if (params?.status) qs.set('status', params.status);
    const q = qs.toString();
    return request<EmailDraft[]>(`/email-drafts${q ? `?${q}` : ''}`);
  },

  get(id: string) {
    return request<EmailDraft>(`/email-drafts/${id}`);
  },

  send(id: string) {
    return request<EmailDraft>(`/email-drafts/${id}/send`, { method: 'POST' });
  },

  update(id: string, data: Partial<EmailDraft>) {
    return request<EmailDraft>(`/email-drafts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },
};

/* ======================== Human Review ======================== */

export const reviews = {
  list(params?: { status?: string; stage?: string; limit?: number; offset?: number }) {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.stage) qs.set('stage', params.stage);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const q = qs.toString();
    return request<HumanReview[]>(`/reviews${q ? `?${q}` : ''}`);
  },

  approve(id: string, notes?: string) {
    return request<HumanReview>(`/reviews/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
  },

  reject(id: string, notes?: string) {
    return request<HumanReview>(`/reviews/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
  },

  returnForRevision(id: string, notes?: string) {
    return request<HumanReview>(`/reviews/${id}/return`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
  },
};

/* ======================== Oversight ======================== */

export const oversight = {
  getAll() {
    return request<OversightConfig[]>('/oversight/config');
  },

  updateSystem(mode: string, confidenceThreshold: number) {
    return request<OversightConfig>('/oversight/config/system', {
      method: 'PUT',
      body: JSON.stringify({ mode, confidence_threshold: confidenceThreshold }),
    });
  },

  updateStage(stage: string, mode: string, confidenceThreshold: number) {
    return request<OversightConfig>(`/oversight/config/stages/${encodeURIComponent(stage)}`, {
      method: 'PUT',
      body: JSON.stringify({ mode, confidence_threshold: confidenceThreshold }),
    });
  },
};

/* ======================== Reports ======================== */

export const reports = {
  pipeline() {
    return request<PipelineReport>('/reports/pipeline');
  },
  sla() {
    return request<SLAReport>('/reports/sla');
  },
  volume(days = 30) {
    return request<VolumeDataPoint[]>(`/reports/volume?days=${days}`);
  },
  humanReview() {
    return request<HumanReviewReport>('/reports/human-review');
  },
  agentPerformance() {
    return request<AgentPerformance[]>('/reports/agent-performance');
  },
};

/* ======================== Audit ======================== */

export const audit = {
  list(params?: { entity_type?: string; action?: string; limit?: number }) {
    const qs = new URLSearchParams();
    if (params?.entity_type) qs.set('entity_type', params.entity_type);
    if (params?.action) qs.set('action', params.action);
    if (params?.limit) qs.set('limit', String(params.limit));
    const q = qs.toString();
    return request<AuditLog[]>(`/audit${q ? `?${q}` : ''}`);
  },
};
