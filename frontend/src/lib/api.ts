const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const config: RequestInit = {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let message = `HTTP error! status: ${response.status}`;
      try {
        const err = await response.json();
        if (err?.detail) {
          message = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
        } else if (err?.error) {
          message = typeof err.error === 'string' ? err.error : JSON.stringify(err.error);
        }
      } catch {
        try {
          const text = await response.text();
          if (text) message = text;
        } catch {}
      }
      throw new ApiError(response.status, message);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      0,
      `Network error: ${error instanceof Error ? error.message : 'Unknown error'}`
    );
  }
}

// Auth token management
let authToken: string | null = null;

export const setAuthToken = (token: string | null) => {
  authToken = token;
  if (typeof window !== "undefined") {
    if (token) {
      localStorage.setItem("auth_token", token);
    } else {
      localStorage.removeItem("auth_token");
    }
  }
};

export const getAuthToken = (): string | null => {
  if (authToken) return authToken;
  if (typeof window !== "undefined") {
    authToken = localStorage.getItem("auth_token");
  }
  return authToken;
};

// Enhanced API request with auth
async function authenticatedRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return apiRequest<T>(endpoint, {
    ...options,
    headers,
  });
}

export const api = {
  // Health check
  healthCheck: () =>
    apiRequest<{ status: string; message: string }>("/api/health"),

  // Authentication
  login: (email: string, password: string) =>
    apiRequest<{ access_token: string; token_type: string; user: any }>(
      "/api/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }
    ),

  signup: (name: string, email: string, password: string) =>
    apiRequest<{ access_token: string; token_type: string; user: any }>(
      "/api/auth/signup",
      {
        method: "POST",
        body: JSON.stringify({ name, email, password }),
      }
    ),

  getCurrentUser: () => authenticatedRequest<any>("/api/auth/me"),

  logout: () =>
    authenticatedRequest<{ message: string }>("/api/auth/logout", {
      method: "POST",
    }),

  // Question Banks (now with authentication)
  getQuestionBanks: () => authenticatedRequest<any[]>("/api/question-banks"),

  uploadQuestionBank: (
    file: File,
    metadata: { name: string; description?: string }
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", metadata.name);
    if (metadata.description) {
      formData.append("description", metadata.description);
    }

    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return apiRequest<any>("/api/question-banks/upload", {
      method: "POST",
      headers,
      body: formData,
    });
  },

  getQuestionBank: (id: string) =>
    authenticatedRequest<any>(`/api/question-banks/${id}`),

  getQuestions: (
    questionBankId: string,
    filters?: {
      category?: string;
      difficulty?: string;
      skip?: number;
      limit?: number;
    }
  ) => {
    const params = new URLSearchParams();
    if (filters?.category) params.append("category", filters.category);
    if (filters?.difficulty) params.append("difficulty", filters.difficulty);
    if (filters?.skip) params.append("skip", filters.skip.toString());
    if (filters?.limit) params.append("limit", filters.limit.toString());

    const queryString = params.toString();
    const url = `/api/question-banks/${questionBankId}/questions${
      queryString ? `?${queryString}` : ""
    }`;

    return authenticatedRequest<any[]>(url);
  },

  deleteQuestionBank: (id: string) =>
    authenticatedRequest(`/api/question-banks/${id}`, { method: "DELETE" }),
  updateQuestionBank: (
    id: string,
    update: { name?: string; description?: string }
  ) =>
    authenticatedRequest<any>(`/api/question-banks/${id}`, {
      method: "PUT",
      body: JSON.stringify(update),
    }),

  // Test Management
  createTest: (testData: {
    title: string;
    description?: string;
    // Backward compat: allow either single or multiple question banks
    question_bank_id?: string;
    question_bank_ids?: string[];
    num_questions: number;
    time_limit_minutes?: number;
    difficulty_filter?: string;
    category_filter?: string;
    is_public?: boolean;
    scheduled_start?: string;
    scheduled_end?: string;
    max_attempts?: number;
    pass_threshold?: number;
  }) =>
    authenticatedRequest<any>("/api/tests", {
      method: "POST",
      body: JSON.stringify(testData),
    }),

  getTests: (filters?: {
    skip?: number;
    limit?: number;
    question_bank_id?: string;
    is_active?: boolean;
    created_by_me?: boolean;
  }) => {
    const params = new URLSearchParams();
    if (filters?.skip) params.append("skip", filters.skip.toString());
    if (filters?.limit) params.append("limit", filters.limit.toString());
    if (filters?.question_bank_id)
      params.append("question_bank_id", filters.question_bank_id);
    if (filters?.is_active !== undefined)
      params.append("is_active", filters.is_active.toString());
    if (filters?.created_by_me) params.append("created_by_me", "true");

    const queryString = params.toString();
    const url = `/api/tests${queryString ? `?${queryString}` : ""}`;

    return authenticatedRequest<any[]>(url);
  },

  getTestDetails: (testId: string) => authenticatedRequest<any>(`/api/tests/${testId}`), // Includes auth when available; still works for public tests

  updateTest: (testId: string, updateData: any) =>
    authenticatedRequest<any>(`/api/tests/${testId}`, {
      method: "PUT",
      body: JSON.stringify(updateData),
    }),

  deleteTest: (testId: string) =>
    authenticatedRequest(`/api/tests/${testId}`, { method: "DELETE" }),

  submitTest: (
    testId: string,
    submission: {
      participant_name: string;
      participant_email?: string;
      answers: Array<{ question_id: string; selected_answer: string }>;
      time_taken_minutes?: number;
    }
  ) =>
    authenticatedRequest<any>(`/api/tests/${testId}/submit`, {
      method: "POST",
      body: JSON.stringify(submission),
    }),

  getTestAnalytics: (testId: string) =>
    authenticatedRequest<any>(`/api/tests/${testId}/analytics`),

  getTestSubmissions: (
    testId: string,
    filters?: { skip?: number; limit?: number; start_date?: string; end_date?: string; user?: string }
  ) => {
    const params = new URLSearchParams();
    if (filters?.skip) params.append("skip", filters.skip.toString());
    if (filters?.limit) params.append("limit", filters.limit.toString());
    if (filters?.start_date) params.append("start_date", filters.start_date);
    if (filters?.end_date) params.append("end_date", filters.end_date);
    if (filters?.user) params.append("user", filters.user);

    const queryString = params.toString();
    const url = `/api/tests/${testId}/submissions${
      queryString ? `?${queryString}` : ""
    }`;

    return authenticatedRequest<any[]>(url);
  },

  // Analytics
  getDashboardStats: () =>
    authenticatedRequest<any>("/api/analytics/dashboard"),

  getLeaderboard: (limit?: number) => {
    const params = new URLSearchParams();
    if (limit) params.append("limit", limit.toString());

    const queryString = params.toString();
    const url = `/api/analytics/leaderboard${
      queryString ? `?${queryString}` : ""
    }`;

    return authenticatedRequest<any[]>(url);
  },

  getRecentActivity: (filters?: { limit?: number; test_id?: string }) => {
    const params = new URLSearchParams();
    if (filters?.limit) params.append("limit", filters.limit.toString());
    if (filters?.test_id) params.append("test_id", filters.test_id);

    const queryString = params.toString();
    const url = `/api/analytics/recent-activity${
      queryString ? `?${queryString}` : ""
    }`;

    return authenticatedRequest<any[]>(url);
  },

  getUserPerformance: () =>
    authenticatedRequest<any[]>("/api/analytics/user-performance"),

  // Test Sharing
  generateShareLink: (testId: string) =>
    authenticatedRequest<any>(`/api/tests/${testId}/share`, { method: "POST" }),

  getSharedTest: (token: string) => apiRequest<any>(`/api/tests/share/${token}`),

  submitViaShareToken: (
    token: string,
    payload: {
      participant_name: string
      participant_email?: string
      answers: Array<{ question_id: string; selected_answer: string }>
      time_taken_minutes?: number
    }
  ) =>
    apiRequest<any>(`/api/tests/share/${token}/submit`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getTestLeaderboardForTest: (testId: string, limit?: number) => {
    const params = new URLSearchParams();
    if (limit) params.append("limit", limit.toString());
    const qs = params.toString();
    return authenticatedRequest<any[]>(`/api/tests/${testId}/leaderboard${qs ? `?${qs}` : ""}`)
  },

  downloadTestResultsCsv: async (testId: string): Promise<Blob> => {
    const token = getAuthToken();
    const res = await fetch(`${API_BASE_URL}/api/tests/${testId}/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      throw new ApiError(res.status, `Failed to download CSV: ${res.status}`)
    }
    return await res.blob();
  },

  // Test Taking Flow
  startTestSession: (
    testId: string,
    sessionData: {
      participant_name: string;
      participant_email?: string;
      invite_token?: string;
    }
  ) =>
    authenticatedRequest<any>(`/api/test-taking/${testId}/start`, {
      method: "POST",
      body: JSON.stringify(sessionData),
    }),

  getTestQuestions: (testId: string, sessionToken: string) => {
    const params = new URLSearchParams();
    params.append("session_token", sessionToken);

    return authenticatedRequest<any[]>(`/api/test-taking/${testId}/questions?${params}`); // Session token + auth when available
  },

  getSessionStatus: (sessionToken: string) =>
    authenticatedRequest<any>(`/api/test-taking/session/${sessionToken}/status`), // Session token + auth when available

  saveAnswer: (
    sessionToken: string,
    answerData: {
      question_id: string;
      selected_answer: string;
      question_number: number;
    }
  ) =>
    authenticatedRequest<any>(`/api/test-taking/session/${sessionToken}/save-answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(answerData),
    }), // Session token provides auth

  submitTestSession: (sessionToken: string) =>
    authenticatedRequest<any>(`/api/test-taking/session/${sessionToken}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }), // Session token provides auth

  getSubmissionResult: (submissionId: string) =>
    authenticatedRequest<any>(`/api/test-taking/submission/${submissionId}`),

  getResultByEmail: (testId: string, email: string) =>
    apiRequest<any>(`/api/test-taking/results/${testId}/${email}`),

  getPublicTestDetails: (token: string) =>
    apiRequest<any>(`/api/test-sharing/public/${token}`),

  getUserAttempts: () =>
    authenticatedRequest<any[]>("/api/test-taking/user/attempts"),

  cancelTestSession: (sessionToken: string) =>
    authenticatedRequest(`/api/test-taking/session/${sessionToken}`, {
      method: "DELETE",
    }),
};
