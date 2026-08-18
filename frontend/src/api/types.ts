/**
 * Mirrors the Pydantic schemas in src/parallax/schemas/.
 *
 * Kept by hand so the app type-checks without a running backend. To regenerate
 * from the live OpenAPI document instead: `npm run gen:api` with the API up.
 */

export type SourceType = 'sec_filing' | 'investor_deck' | 'earnings_call' | 'xbrl'

export type DocumentStatus = 'pending' | 'parsing' | 'extracting' | 'indexed' | 'failed'

export type Modality = 'text' | 'table' | 'chart' | 'audio' | 'structured'

export interface Document {
  id: string
  entity_id: string | null
  source_type: SourceType
  status: DocumentStatus
  title: string
  storage_uri: string
  checksum: string
  mime_type: string | null
  page_count: number | null
  duration_s: number | null
  fiscal_year: number | null
  fiscal_quarter: number | null
  period_start: string | null
  period_end: string | null
  published_at: string | null
  error: string | null
  doc_metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface DocumentCreate {
  entity_id?: string | null
  source_type: SourceType
  title: string
  storage_uri: string
  checksum: string
  mime_type?: string | null
  fiscal_year?: number | null
  fiscal_quarter?: number | null
  period_start?: string | null
  period_end?: string | null
  published_at?: string | null
  doc_metadata?: Record<string, unknown>
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface LivenessResponse {
  status: string
  version: string
  env: string
}

export interface ReadinessResponse {
  status: string
  version: string
  checks: Record<string, string>
}

/** The envelope produced by register_exception_handlers on the backend. */
export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details: Record<string, unknown>
  }
}

export const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  sec_filing: 'SEC Filing',
  investor_deck: 'Investor Deck',
  earnings_call: 'Earnings Call',
  xbrl: 'XBRL Facts',
}
