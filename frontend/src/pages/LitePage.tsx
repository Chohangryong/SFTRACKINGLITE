import axios from 'axios'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Descriptions, Progress, Select, Space, Table, Tag, Typography, Upload, message } from 'antd'
import type { UploadProps } from 'antd'
import { useEffect, useState } from 'react'

import { analyzeLiteUpload, createLiteRunJob, exportLiteResult, getLiteRunJob } from '../api'
import { statusMeta } from '../lib/status'
import type { LiteAnalyzeResponse, LiteRunJobResponse, LiteRunResponse } from '../types'

const mappingFields = [
  { key: 'order_number', label: 'Order Number' },
  { key: 'tracking_number', label: 'Tracking Number' },
] as const

function getErrorMessage(error: unknown) {
  if (!axios.isAxiosError(error)) {
    return 'Request failed.'
  }

  const detail = error.response?.data?.detail
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => `${item.loc?.join('.') ?? 'request'}: ${item.msg}`)
      .join('\n')
  }
  return error.message || 'Request failed.'
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export function LitePage() {
  const [file, setFile] = useState<File | null>(null)
  const [analysis, setAnalysis] = useState<LiteAnalyzeResponse | null>(null)
  const [result, setResult] = useState<LiteRunResponse | null>(null)
  const [mapping, setMapping] = useState<Record<string, string | null>>({})
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [handledJobId, setHandledJobId] = useState<string | null>(null)
  const [exportingFormat, setExportingFormat] = useState<'csv' | 'xlsx' | null>(null)

  const analyzeMutation = useMutation({
    mutationFn: (selectedFile: File) => analyzeLiteUpload(selectedFile),
    onSuccess: (data, selectedFile) => {
      setFile(selectedFile)
      setAnalysis(data)
      setResult(null)
      setActiveJobId(null)
      setHandledJobId(null)
      setMapping(data.detected_mapping)
      message.success('File analyzed.')
    },
    onError: (error) => {
      message.error(getErrorMessage(error))
    },
  })

  const runMutation = useMutation({
    mutationFn: () =>
      createLiteRunJob(file!, {
        mapping,
        sheetName: analysis?.selected_sheet ?? null,
        batchSize: 10,
        language: '0',
      }),
    onSuccess: (data) => {
      setResult(null)
      setHandledJobId(null)
      setActiveJobId(data.job_id)
      message.info('Lite tracking started.')
    },
    onError: (error) => {
      message.error(getErrorMessage(error))
    },
  })

  const jobQuery = useQuery({
    queryKey: ['lite-run-job', activeJobId],
    queryFn: () => getLiteRunJob(activeJobId!),
    enabled: Boolean(activeJobId),
    refetchInterval: (query) => {
      const data = query.state.data as LiteRunJobResponse | undefined
      if (!data) {
        return 1000
      }
      return data.status === 'queued' || data.status === 'running' ? 1000 : false
    },
  })

  useEffect(() => {
    const job = jobQuery.data
    if (!job || handledJobId === job.job_id) {
      return
    }
    if (job.status === 'completed' && job.result) {
      setResult(job.result)
      setHandledJobId(job.job_id)
      message.success('Lite tracking completed.')
      return
    }
    if (job.status === 'failed') {
      setHandledJobId(job.job_id)
      message.error(job.error_message ?? 'Lite tracking failed.')
    }
  }, [handledJobId, jobQuery.data])

  const exportMutation = useMutation({
    mutationFn: async (fileFormat: 'csv' | 'xlsx') => {
      const blob = await exportLiteResult(result!.rows, fileFormat)
      return { blob, fileFormat }
    },
    onMutate: (fileFormat) => {
      setExportingFormat(fileFormat)
    },
    onSuccess: ({ blob, fileFormat }) => {
      downloadBlob(blob, `lite-tracking-results.${fileFormat}`)
      message.success(`Downloaded ${fileFormat.toUpperCase()} file.`)
    },
    onError: (error) => {
      message.error(getErrorMessage(error))
    },
    onSettled: () => {
      setExportingFormat(null)
    },
  })

  const analyzeUploadProps: UploadProps = {
    maxCount: 1,
    beforeUpload: (selectedFile) => {
      analyzeMutation.mutate(selectedFile)
      return false
    },
    showUploadList: true,
  }

  const currentJob = jobQuery.data
  const isRunInProgress = currentJob?.status === 'queued' || currentJob?.status === 'running'

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div className="page-header">
        <div>
          <Typography.Title level={1}>Lite Tracking</Typography.Title>
          <Typography.Paragraph>
            Upload one customer file, dedupe by order and tracking, query SF in batches of 10, and return the
            latest mapped status using the 2,708-waybill analysis rules.
          </Typography.Paragraph>
        </div>
      </div>

      <div className="upload-grid">
        <Card className="glass-card" title="1. Analyze File">
          <Upload.Dragger {...analyzeUploadProps}>
            <p>Drop a CSV/XLSX/XLS file here or click to analyze it.</p>
            <p>The Lite flow only needs Order Number and Tracking Number.</p>
          </Upload.Dragger>

          {analysis && (
            <Descriptions bordered size="small" column={1} style={{ marginTop: 16 }}>
              <Descriptions.Item label="파일명">{analysis.file_name}</Descriptions.Item>
              <Descriptions.Item label="시트명">{analysis.selected_sheet ?? 'CSV'}</Descriptions.Item>
              <Descriptions.Item label="전체 ROW 수">{analysis.total_rows}</Descriptions.Item>
              <Descriptions.Item label="중복 제거 후 ROW 수">{analysis.deduped_rows}</Descriptions.Item>
              <Descriptions.Item label="조회대상 수">{analysis.query_target_count}</Descriptions.Item>
              <Descriptions.Item label="Tracking No 없음">{analysis.no_tracking_rows}</Descriptions.Item>
            </Descriptions>
          )}
        </Card>

        <Card className="glass-card" title="2. Mapping And Run">
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {mappingFields.map((field) => (
              <div key={field.key}>
                <Typography.Text strong>{field.label}</Typography.Text>
                <Select
                  allowClear
                  style={{ width: '100%', marginTop: 8 }}
                  value={mapping[field.key] ?? undefined}
                  options={(analysis?.columns ?? []).map((column) => ({
                    label: column,
                    value: column,
                  }))}
                  onChange={(value) => {
                    setMapping((current) => ({ ...current, [field.key]: value ?? null }))
                    setResult(null)
                    setActiveJobId(null)
                    setHandledJobId(null)
                  }}
                />
              </div>
            ))}

            <Space wrap>
              <Button
                type="primary"
                disabled={!file || isRunInProgress}
                loading={runMutation.isPending}
                onClick={() => runMutation.mutate()}
              >
                Run Lite Tracking
              </Button>
              <Button
                disabled={!result || exportMutation.isPending || isRunInProgress}
                loading={exportMutation.isPending && exportingFormat === 'xlsx'}
                onClick={() => exportMutation.mutate('xlsx')}
              >
                Download XLSX
              </Button>
              <Button
                disabled={!result || exportMutation.isPending || isRunInProgress}
                loading={exportMutation.isPending && exportingFormat === 'csv'}
                onClick={() => exportMutation.mutate('csv')}
              >
                Download CSV
              </Button>
            </Space>

            {currentJob && currentJob.status !== 'completed' && (
              <div>
                <Progress percent={currentJob.progress_percent} status={currentJob.status === 'failed' ? 'exception' : undefined} />
                <Typography.Text type="secondary">
                  {currentJob.status === 'queued'
                    ? '조회 준비 중'
                    : currentJob.status === 'failed'
                      ? currentJob.error_message ?? '조회 실패'
                      : `요청됨 ${currentJob.completed_targets}/${currentJob.query_target_count} · 남음 ${currentJob.remaining_targets}`}
                </Typography.Text>
              </div>
            )}
          </Space>
        </Card>
      </div>

      {result && (
        <Card className="glass-card" title="3. 조회 결과 요약">
          <Descriptions bordered size="small" column={1} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="조회 Tracking No 건수">{result.summary.query_target_count}</Descriptions.Item>
          </Descriptions>

          <Table
            rowKey="status"
            pagination={false}
            dataSource={Object.entries(result.summary.status_counts).map(([status, count]) => ({
              key: status,
              status,
              count,
            }))}
            columns={[
              {
                title: '상태',
                dataIndex: 'status',
                render: (status: string) => {
                  const meta = statusMeta(status)
                  return <Tag color={meta.color}>{meta.label}</Tag>
                },
              },
              {
                title: '건수',
                dataIndex: 'count',
              },
            ]}
          />
        </Card>
      )}
    </Space>
  )
}
