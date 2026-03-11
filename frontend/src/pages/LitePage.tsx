import axios from 'axios'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Descriptions, Progress, Space, Table, Tag, Typography, Upload, message } from 'antd'
import type { UploadProps } from 'antd'
import { useEffect, useState } from 'react'

import { analyzeLiteUpload, createLiteRunJob, exportLiteResult, getLiteRunJob } from '../api'
import { statusMeta } from '../lib/status'
import type { LiteAnalyzeResponse, LiteRunJobResponse, LiteRunResponse } from '../types'

function getErrorMessage(error: unknown) {
  if (!axios.isAxiosError(error)) {
    return '요청에 실패했습니다.'
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
  return error.message || '요청에 실패했습니다.'
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
      message.success('파일 분석이 완료되었습니다.')
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
      message.info('SF Express 조회를 시작했습니다.')
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
      message.success('SF Express 조회가 완료되었습니다.')
      return
    }
    if (job.status === 'failed') {
      setHandledJobId(job.job_id)
      message.error(job.error_message ?? 'SF Express 조회에 실패했습니다.')
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
      message.success(`${fileFormat.toUpperCase()} 파일을 다운로드했습니다.`)
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
  const analysisSummary = analysis
    ? [
        { label: '파일명', value: analysis.file_name },
        { label: '엑셀전체 ROW 수', value: analysis.total_rows },
        { label: '중복 ROW 제거 수', value: analysis.duplicate_pairs_removed },
        { label: '송장번호 없음', value: analysis.no_tracking_rows },
        { label: '총 조회대상 건수', value: analysis.query_target_count },
      ]
    : []

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div className="page-header">
        <div>
          <Typography.Title level={1}>SF Express 송장 조회</Typography.Title>
          <Typography.Paragraph>
            쇼핑몰 주문 엑셀을 업로드해 송장번호 기준으로 SF Express 배송 상태를 조회합니다.
          </Typography.Paragraph>
        </div>
      </div>

      <div className="upload-grid">
        <Card className="glass-card" title="1. 오더 정보 엑셀 업로드">
          <Upload.Dragger {...analyzeUploadProps}>
            <p>CSV/XLSX/XLS 파일을 여기에 끌어놓거나 클릭해서 업로드하세요.</p>
          </Upload.Dragger>

          {analysis && (
            <Descriptions bordered size="small" column={1} style={{ marginTop: 16 }}>
              {analysisSummary.map((item) => (
                <Descriptions.Item key={item.label} label={item.label}>
                  {item.value}
                </Descriptions.Item>
              ))}
            </Descriptions>
          )}
        </Card>

        <Card className="glass-card" title="2. SF Express 조회">
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Space wrap>
              <Button
                type="primary"
                disabled={!file || isRunInProgress}
                loading={runMutation.isPending}
                onClick={() => runMutation.mutate()}
              >
                조회 요청
              </Button>
              <Button
                disabled={!result || exportMutation.isPending || isRunInProgress}
                loading={exportMutation.isPending && exportingFormat === 'xlsx'}
                onClick={() => exportMutation.mutate('xlsx')}
              >
                XLSX 다운로드
              </Button>
              <Button
                disabled={!result || exportMutation.isPending || isRunInProgress}
                loading={exportMutation.isPending && exportingFormat === 'csv'}
                onClick={() => exportMutation.mutate('csv')}
              >
                CSV 다운로드
              </Button>
            </Space>

            {currentJob && currentJob.status !== 'completed' && (
              <div>
                <Progress
                  percent={currentJob.progress_percent}
                  status={currentJob.status === 'failed' ? 'exception' : undefined}
                />
                <Typography.Text type="secondary">
                  {currentJob.status === 'queued'
                    ? '조회 준비 중'
                    : currentJob.status === 'failed'
                      ? currentJob.error_message ?? '조회 실패'
                      : `요청됨 ${currentJob.completed_targets}/${currentJob.query_target_count}건, 남음 ${currentJob.remaining_targets}건`}
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
