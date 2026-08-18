import type { ApiErrorBody } from './types'

/**
 * Empty by default: the Vite dev server and the nginx image both proxy /api to
 * FastAPI, so same-origin requests are the normal path. Set VITE_API_BASE_URL
 * only when the API lives on a different host.
 */
const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export const API_PREFIX = `${BASE_URL}/api/v1`

/** A non-2xx response, carrying the backend's error envelope when it sent one. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const { error } = value
  return typeof error === 'object' && error !== null && 'code' in error && 'message' in error
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown
  try {
    body = await response.json()
  } catch {
    return new ApiError(response.status, 'unknown', response.statusText || 'Request failed', {})
  }

  if (isApiErrorBody(body)) {
    return new ApiError(
      response.status,
      body.error.code,
      body.error.message,
      body.error.details ?? {},
    )
  }

  // FastAPI's own 422 validation errors use {detail: [...]}, not our envelope.
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const { detail } = body
    return new ApiError(response.status, 'validation_error', 'Request validation failed', {
      detail,
    })
  }

  return new ApiError(response.status, 'unknown', response.statusText || 'Request failed', {})
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** Query params; null and undefined values are dropped. */
  params?: Record<string, string | number | boolean | null | undefined>
  json?: unknown
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { params, json, headers, ...init } = options

  const url = new URL(`${API_PREFIX}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== null && value !== undefined) url.searchParams.set(key, String(value))
  }

  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    ...(json !== undefined ? { body: JSON.stringify(json) } : {}),
  })

  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T

  return (await response.json()) as T
}
