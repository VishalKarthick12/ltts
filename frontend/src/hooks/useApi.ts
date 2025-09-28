"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, setAuthToken, getAuthToken } from "@/lib/api";

// Auth hooks
export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.login(email, password),
    onSuccess: (data) => {
      setAuthToken(data.access_token);
      queryClient.setQueryData(["current-user"], data.user);
      queryClient.invalidateQueries({ queryKey: ["question-banks"] });
    },
  });
}

export function useUpdateQuestionBank() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, update }: { id: string; update: { name?: string; description?: string } }) =>
      api.updateQuestionBank(id, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["question-banks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
}

export function useDeleteQuestionBank() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deleteQuestionBank(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["question-banks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
}

// Sharing hooks
export function useGenerateShareLink() {
  return useMutation({
    mutationFn: (testId: string) => api.generateShareLink(testId),
  });
}

export function useTestLeaderboardForTest(testId?: string, limit?: number) {
  return useQuery({
    queryKey: ["test-leaderboard", testId, limit],
    queryFn: () => api.getTestLeaderboardForTest(testId as string, limit),
    enabled: !!testId && !!getAuthToken(),
    staleTime: 30000,
  });
}

export function useSignup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      name,
      email,
      password,
    }: {
      name: string;
      email: string;
      password: string;
    }) => api.signup(name, email, password),
    onSuccess: (data) => {
      setAuthToken(data.access_token);
      queryClient.setQueryData(["current-user"], data.user);
    },
  });
}

export function useCurrentUser() {
  return useQuery({
    queryKey: ["current-user"],
    queryFn: async () => {
      try {
        return await api.getCurrentUser();
      } catch (error: any) {
        // If unauthorized, clear the token
        if (error.status === 401 || error.status === 403) {
          setAuthToken(null);
        }
        throw error;
      }
    },
    enabled: !!getAuthToken(),
    retry: (failureCount, error: any) => {
      // Don't retry on auth errors
      if (error?.status === 401 || error?.status === 403) {
        return false;
      }
      return failureCount < 3;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      setAuthToken(null);
      queryClient.clear();
    },
  });
}

// Health check hook
export function useHealthCheck() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.healthCheck,
    retry: 3,
    staleTime: 30000, // 30 seconds
  });
}

// Question banks hooks
export function useQuestionBanks() {
  return useQuery({
    queryKey: ["question-banks"],
    queryFn: api.getQuestionBanks,
  });
}

export function useUploadQuestionBank() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      file,
      metadata,
    }: {
      file: File;
      metadata: { name: string; description?: string };
    }) => api.uploadQuestionBank(file, metadata),
    onSuccess: () => {
      // Invalidate and refetch question banks
      queryClient.invalidateQueries({ queryKey: ["question-banks"] });
    },
  });
}

// Questions hooks
export function useQuestions(questionBankId: string) {
  return useQuery({
    queryKey: ["questions", questionBankId],
    queryFn: () => api.getQuestions(questionBankId),
    enabled: !!questionBankId,
  });
}

// Test Management hooks
export function useCreateTest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (testData: any) => api.createTest(testData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tests"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
}

export function useTests(filters?: any) {
  return useQuery({
    queryKey: ["tests", filters],
    queryFn: () => api.getTests(filters),
    enabled: !!getAuthToken(),
  });
}

export function useTestDetails(testId: string) {
  return useQuery({
    queryKey: ["test-details", testId],
    queryFn: () => api.getTestDetails(testId),
    enabled: !!testId,
  });
}

// Shared Test (via token) - used when accessing tests from a share link
export function useSharedTest(token?: string | null) {
  return useQuery({
    queryKey: ["shared-test", token],
    queryFn: () => api.getSharedTest(token as string),
    enabled: !!token,
    retry: false,
  });
}

export function useUpdateTest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ testId, updateData }: { testId: string; updateData: any }) =>
      api.updateTest(testId, updateData),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["tests"] });
      queryClient.invalidateQueries({
        queryKey: ["test-details", variables.testId],
      });
    },
  });
}

export function useDeleteTest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (testId: string) => api.deleteTest(testId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tests"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
}

export function useSubmitTest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ testId, submission }: { testId: string; submission: any }) =>
      api.submitTest(testId, submission),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["test-analytics", variables.testId],
      });
      queryClient.invalidateQueries({
        queryKey: ["test-submissions", variables.testId],
      });
      queryClient.invalidateQueries({ queryKey: ["user-performance"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
}

// Analytics hooks
export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: api.getDashboardStats,
    enabled: !!getAuthToken(),
    staleTime: 30000, // 30 seconds
  });
}

export function useTestAnalytics(testId: string) {
  return useQuery({
    queryKey: ["test-analytics", testId],
    queryFn: () => api.getTestAnalytics(testId),
    enabled: !!testId && !!getAuthToken(),
  });
}

export function useTestSubmissions(testId: string, filters?: any) {
  return useQuery({
    queryKey: ["test-submissions", testId, filters],
    queryFn: () => api.getTestSubmissions(testId, filters),
    enabled: !!testId && !!getAuthToken(),
  });
}

export function useLeaderboard(limit?: number) {
  return useQuery({
    queryKey: ["leaderboard", limit],
    queryFn: () => api.getLeaderboard(limit),
    enabled: !!getAuthToken(),
    staleTime: 60000, // 1 minute
  });
}

export function useRecentActivity(filters?: any) {
  return useQuery({
    queryKey: ["recent-activity", filters],
    queryFn: () => api.getRecentActivity(filters),
    enabled: !!getAuthToken(),
    staleTime: 30000, // 30 seconds
  });
}

export function useUserPerformance() {
  return useQuery({
    queryKey: ["user-performance"],
    queryFn: api.getUserPerformance,
    enabled: !!getAuthToken(),
  });
}

// Test Taking Flow hooks
export function useStartTestSession() {
  return useMutation({
    mutationFn: ({
      testId,
      sessionData,
    }: {
      testId: string;
      sessionData: any;
    }) => api.startTestSession(testId, sessionData),
  });
}

export function useTestQuestions(testId: string, sessionToken: string) {
  return useQuery({
    queryKey: ["test-questions", testId, sessionToken],
    queryFn: () => api.getTestQuestions(testId, sessionToken),
    enabled: !!testId && !!sessionToken,
    staleTime: Infinity, // Questions don't change during test
  });
}

export function useSessionStatus(sessionToken: string) {
  return useQuery({
    queryKey: ["session-status", sessionToken],
    queryFn: () => api.getSessionStatus(sessionToken),
    enabled: !!sessionToken,
    refetchInterval: 30000, // Check every 30 seconds
  });
}

export function useSaveAnswer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      sessionToken,
      answerData,
    }: {
      sessionToken: string;
      answerData: any;
    }) => api.saveAnswer(sessionToken, answerData),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["session-status", variables.sessionToken],
      });
    },
  });
}

export function useSubmitTestSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sessionToken: string) => api.submitTestSession(sessionToken),
    onSuccess: (data: any) => {
      // Invalidate analytics tied to the specific test
      if (data?.test_id) {
        queryClient.invalidateQueries({ queryKey: ["test-submissions", data.test_id] });
        queryClient.invalidateQueries({ queryKey: ["test-analytics", data.test_id] });
        queryClient.invalidateQueries({ queryKey: ["test-leaderboard", data.test_id] });
      }
      queryClient.invalidateQueries({ queryKey: ["user-attempts"] });
      queryClient.invalidateQueries({ queryKey: ["user-performance"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
}

export function useSubmissionResult(submissionId: string) {
  return useQuery({
    queryKey: ["submission-result", submissionId],
    queryFn: () => api.getSubmissionResult(submissionId),
    enabled: !!submissionId,
  });
}

export function useUserAttempts() {
  return useQuery({
    queryKey: ["user-attempts"],
    queryFn: api.getUserAttempts,
    enabled: !!getAuthToken(),
  });
}

export function useCancelTestSession() {
  return useMutation({
    mutationFn: (sessionToken: string) => api.cancelTestSession(sessionToken),
  });
}
