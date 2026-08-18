import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { request } from './client'
import type {
  Document,
  DocumentCreate,
  LivenessResponse,
  Page,
  ReadinessResponse,
  SourceType,
} from './types'

export const queryKeys = {
  health: ['health'] as const,
  readiness: ['health', 'ready'] as const,
  documents: (filters: DocumentFilters) => ['documents', filters] as const,
}

export interface DocumentFilters {
  source_type?: SourceType | undefined
  limit?: number
  offset?: number
}

export function useLiveness() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => request<LivenessResponse>('/health/live'),
    staleTime: 30_000,
  })
}

export function useReadiness() {
  return useQuery({
    queryKey: queryKeys.readiness,
    queryFn: () => request<ReadinessResponse>('/health/ready'),
    // A 503 here is meaningful state to display, not a transient failure worth
    // hammering the backend over.
    retry: false,
    refetchInterval: 15_000,
  })
}

export function useDocuments(filters: DocumentFilters = {}) {
  return useQuery({
    queryKey: queryKeys.documents(filters),
    queryFn: () =>
      request<Page<Document>>('/documents', {
        params: {
          source_type: filters.source_type,
          limit: filters.limit ?? 50,
          offset: filters.offset ?? 0,
        },
      }),
  })
}

export function useRegisterDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: DocumentCreate) =>
      request<Document>('/documents', { method: 'POST', json: payload }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}
