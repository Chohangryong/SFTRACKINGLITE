export interface ApiKeyMasked {
  id: number
  service: string
  label: string
  environment: string
  is_active: boolean
  key_fields: Record<string, string>
  last_tested_at?: string | null
  test_result?: string | null
}

export interface ApiKeyCreatePayload {
  service?: string
  label: string
  environment: 'sandbox' | 'production'
  partner_id: string
  checkword: string
  is_active: boolean
}

export interface ApiKeyUpdatePayload {
  label?: string
  partner_id?: string
  checkword?: string
  is_active?: boolean
}

export interface LitePreviewRow {
  order_number: string
  tracking_number?: string | null
}

export interface LiteAnalyzeResponse {
  file_name: string
  selected_sheet?: string | null
  columns: string[]
  detected_mapping: Record<string, string | null>
  total_rows: number
  missing_order_rows: number
  duplicate_pairs_removed: number
  deduped_rows: number
  query_target_count: number
  no_tracking_rows: number
  preview_rows: LitePreviewRow[]
}

export interface LiteResultRow {
  order_number: string
  tracking_number?: string | null
  status: string
  sf_express_code?: string | null
  sf_express_remark?: string | null
  last_event_time?: string | null
  latest_event?: Record<string, unknown> | null
}

export interface LiteRunSummary {
  total_rows: number
  missing_order_rows: number
  duplicate_pairs_removed: number
  deduped_rows: number
  query_target_count: number
  no_tracking_rows: number
  status_counts: Record<string, number>
}

export interface LiteRunResponse {
  file_name: string
  selected_sheet?: string | null
  detected_mapping: Record<string, string | null>
  summary: LiteRunSummary
  rows: LiteResultRow[]
}

export interface LiteRunJobCreateResponse {
  job_id: string
}

export interface LiteRunJobResponse {
  job_id: string
  file_name: string
  status: string
  selected_sheet?: string | null
  total_rows: number
  deduped_rows: number
  query_target_count: number
  no_tracking_rows: number
  completed_targets: number
  remaining_targets: number
  progress_percent: number
  error_message?: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  result?: LiteRunResponse | null
}
