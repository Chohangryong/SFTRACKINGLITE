import axios from 'axios'

import type {
  ApiKeyCreatePayload,
  ApiKeyMasked,
  ApiKeyUpdatePayload,
  LiteAnalyzeResponse,
  LiteRunJobCreateResponse,
  LiteRunJobResponse,
  RuntimeSessionHeartbeatResponse,
  RuntimeSessionStartResponse,
} from './types'

const client = axios.create({
  baseURL: '/api',
})

export async function listApiKeys() {
  const response = await client.get<ApiKeyMasked[]>('/settings/api-keys')
  return response.data
}

export async function createApiKey(payload: ApiKeyCreatePayload) {
  const response = await client.post<ApiKeyMasked>('/settings/api-keys', payload)
  return response.data
}

export async function updateApiKey(apiKeyId: number, payload: ApiKeyUpdatePayload) {
  const response = await client.put<ApiKeyMasked>(`/settings/api-keys/${apiKeyId}`, payload)
  return response.data
}

export async function deleteApiKey(apiKeyId: number) {
  await client.delete(`/settings/api-keys/${apiKeyId}`)
}

export async function testApiKey(apiKeyId: number) {
  const response = await client.post(`/settings/api-keys/${apiKeyId}/test`)
  return response.data
}

function appendLiteFormData(
  formData: FormData,
  payload?: {
    mapping?: Record<string, string | null>
    sheetName?: string | null
    batchSize?: number
    delaySeconds?: number
    language?: string
  },
) {
  if (!payload) {
    return
  }
  if (payload.mapping) {
    formData.append('mapping_json', JSON.stringify(payload.mapping))
  }
  if (payload.sheetName) {
    formData.append('sheet_name', payload.sheetName)
  }
  if (payload.batchSize !== undefined) {
    formData.append('batch_size', String(payload.batchSize))
  }
  if (payload.delaySeconds !== undefined) {
    formData.append('delay_seconds', String(payload.delaySeconds))
  }
  if (payload.language) {
    formData.append('language', payload.language)
  }
}

export async function analyzeLiteUpload(
  file: File,
  payload?: {
    mapping?: Record<string, string | null>
    sheetName?: string | null
  },
) {
  const formData = new FormData()
  formData.append('file', file)
  appendLiteFormData(formData, payload)
  const response = await client.post<LiteAnalyzeResponse>('/lite/analyze', formData)
  return response.data
}

export async function createLiteRunJob(
  file: File,
  payload?: {
    mapping?: Record<string, string | null>
    sheetName?: string | null
    batchSize?: number
    delaySeconds?: number
    language?: string
  },
) {
  const formData = new FormData()
  formData.append('file', file)
  appendLiteFormData(formData, payload)
  const response = await client.post<LiteRunJobCreateResponse>('/lite/jobs', formData)
  return response.data
}

export async function getLiteRunJob(jobId: string) {
  const response = await client.get<LiteRunJobResponse>(`/lite/jobs/${jobId}`)
  return response.data
}

export async function downloadLiteRunResult(
  jobId: string,
  fileFormat: 'csv' | 'xlsx',
) {
  const response = await client.get(`/lite/jobs/${jobId}/download`, {
    params: { file_format: fileFormat },
    responseType: 'blob',
  })
  return response.data as Blob
}

export async function startRuntimeSession() {
  const response = await client.post<RuntimeSessionStartResponse>('/runtime/session/start')
  return response.data
}

export async function heartbeatRuntimeSession(sessionId: string) {
  const response = await client.post<RuntimeSessionHeartbeatResponse>('/runtime/session/heartbeat', {
    session_id: sessionId,
  })
  return response.data
}

export async function endRuntimeSession(sessionId: string) {
  await client.post('/runtime/session/end', { session_id: sessionId })
}
