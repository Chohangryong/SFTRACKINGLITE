import axios from 'axios'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Descriptions, Modal, Progress, Space, Table, Tag, Typography, Upload, message } from 'antd'
import type { UploadProps } from 'antd'
import { useEffect, useMemo, useState } from 'react'

import { analyzeLiteUpload, createLiteRunJob, downloadLiteRunResult, getLiteRunJob } from '../api'
import { statusMeta } from '../lib/status'
import type { LiteAnalyzeResponse, LiteRunJobResponse, LiteRunResponse } from '../types'

const ACTIVE_JOB_STORAGE_KEY = 'sf-lite-active-job-id'
const COMPLETED_NOTICE_STORAGE_KEY = 'sf-lite-completed-job-id'

type NoticeModalState = {
  type: 'completed' | 'expired'
  title: string
  content: string
  reloadOnOk?: boolean
}

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

function getStoredJobId() {
  if (typeof window === 'undefined') {
    return null
  }
  return window.sessionStorage.getItem(ACTIVE_JOB_STORAGE_KEY)
}

function clearStoredJobState() {
  if (typeof window === 'undefined') {
    return
  }
  window.sessionStorage.removeItem(ACTIVE_JOB_STORAGE_KEY)
  window.sessionStorage.removeItem(COMPLETED_NOTICE_STORAGE_KEY)
}

function markCompletionNoticeShown(jobId: string) {
  if (typeof window === 'undefined') {
    return
  }
  window.sessionStorage.setItem(COMPLETED_NOTICE_STORAGE_KEY, jobId)
}

function isCompletionNoticeShown(jobId: string) {
  if (typeof window === 'undefined') {
    return false
  }
  return window.sessionStorage.getItem(COMPLETED_NOTICE_STORAGE_KEY) === jobId
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return '-'
  }

  const normalizedValue =
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !value.includes('T') ? value : `${value}Z`
  const date = new Date(normalizedValue)
  if (Number.isNaN(date.getTime())) {
    return '-'
  }
  const formatter = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return formatter.format(date).replace(' ', ' ')
}

export function LitePage() {
  const [file, setFile] = useState<File | null>(null)
  const [analysis, setAnalysis] = useState<LiteAnalyzeResponse | null>(null)
  const [result, setResult] = useState<LiteRunResponse | null>(null)
  const [mapping, setMapping] = useState<Record<string, string | null>>({})
  const [activeJobId, setActiveJobId] = useState<string | null>(() => getStoredJobId())
  const [handledJobId, setHandledJobId] = useState<string | null>(null)
  const [exportingFormat, setExportingFormat] = useState<'csv' | 'xlsx' | null>(null)
  const [expiredNoticeJobId, setExpiredNoticeJobId] = useState<string | null>(null)
  const [noticeModal, setNoticeModal] = useState<NoticeModalState | null>(null)

  const resetJobState = () => {
    setResult(null)
    setActiveJobId(null)
    setHandledJobId(null)
    setExpiredNoticeJobId(null)
    clearStoredJobState()
  }

  const showExpiredModal = () => {
    const jobId = activeJobId ?? 'expired'
    if (expiredNoticeJobId === jobId) {
      return
    }
    setExpiredNoticeJobId(jobId)
    setResult(null)
    setHandledJobId(null)
    setActiveJobId(null)
    clearStoredJobState()
    setNoticeModal({
      type: 'expired',
      title: '결과 초기화',
      content: '조회된 결과가 초기화되었습니다. 다시 조회해 주세요.',
      reloadOnOk: true,
    })
  }

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    if (activeJobId) {
      window.sessionStorage.setItem(ACTIVE_JOB_STORAGE_KEY, activeJobId)
      return
    }
    window.sessionStorage.removeItem(ACTIVE_JOB_STORAGE_KEY)
  }, [activeJobId])

  const analyzeMutation = useMutation({
    mutationFn: (selectedFile: File) => analyzeLiteUpload(selectedFile),
    onSuccess: (data, selectedFile) => {
      setFile(selectedFile)
      setAnalysis(data)
      setMapping(data.detected_mapping)
      resetJobState()
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
      setExpiredNoticeJobId(null)
      setActiveJobId(data.job_id)
      if (typeof window !== 'undefined') {
        window.sessionStorage.removeItem(COMPLETED_NOTICE_STORAGE_KEY)
      }
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
    retry: false,
  })

  const currentJob = activeJobId ? jobQuery.data : undefined
  const isRunInProgress = currentJob?.status === 'queued' || currentJob?.status === 'running'
  const canDownload = Boolean(activeJobId && result && currentJob?.status === 'completed')

  useEffect(() => {
    if (!jobQuery.error || !axios.isAxiosError(jobQuery.error)) {
      return
    }
    if (jobQuery.error.response?.status === 404) {
      resetJobState()
    }
  }, [jobQuery.error])

  useEffect(() => {
    // Run 버튼은 job 생성만 하므로 실제 완료/만료 반영은 polling 결과로 처리한다.
    const job = currentJob
    if (!job) {
      return
    }

    if (job.status === 'expired') {
      showExpiredModal()
      return
    }

    if (job.status === 'completed' && job.result) {
      setResult(job.result)
      setHandledJobId(job.job_id)
      if (!isCompletionNoticeShown(job.job_id)) {
        markCompletionNoticeShown(job.job_id)
        setNoticeModal({
          type: 'completed',
          title: '조회 완료',
          content: '조회가 완료되었습니다. 10분간 결과를 확인하고 파일을 다운로드할 수 있습니다.',
          reloadOnOk: false,
        })
      }
      return
    }

    if (job.status === 'failed' && handledJobId !== job.job_id) {
      setHandledJobId(job.job_id)
      message.error(job.error_message ?? 'SF Express 조회에 실패했습니다.')
    }
  }, [activeJobId, currentJob, expiredNoticeJobId, handledJobId])

  useEffect(() => {
    const expiresAt = currentJob?.expires_at
    if (!expiresAt || currentJob?.status !== 'completed') {
      return
    }

    const remainingMs = new Date(expiresAt).getTime() - Date.now()
    if (remainingMs <= 0) {
      showExpiredModal()
      return
    }

    const timeoutId = window.setTimeout(() => {
      showExpiredModal()
    }, remainingMs)

    return () => window.clearTimeout(timeoutId)
  }, [activeJobId, currentJob, expiredNoticeJobId])

  const exportMutation = useMutation({
    mutationFn: async (fileFormat: 'csv' | 'xlsx') => {
      const blob = await downloadLiteRunResult(activeJobId!, fileFormat)
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
      if (axios.isAxiosError(error) && error.response?.status === 410) {
        showExpiredModal()
        return
      }
      message.error(getErrorMessage(error))
    },
    onSettled: () => {
      setExportingFormat(null)
    },
  })

  const analyzeUploadProps: UploadProps = {
    maxCount: 1,
    beforeUpload: (selectedFile) => {
      // 업로드 직후 analyze만 수행하고, 실제 브라우저 업로드는 막는다.
      analyzeMutation.mutate(selectedFile)
      return false
    },
    showUploadList: true,
  }

  const analysisSummary = analysis
    ? [
        { label: '파일명', value: analysis.file_name },
        { label: '엑셀전체 ROW 수', value: analysis.total_rows },
        { label: '중복 ROW 제거 수', value: analysis.duplicate_pairs_removed },
        { label: '송장번호 없음', value: analysis.no_tracking_rows },
        { label: '총 조회대상 건수', value: analysis.query_target_count },
      ]
    : []

  const statusRows = useMemo(
    () =>
      result
        ? Object.entries(result.summary.status_counts).map(([status, count]) => ({
            key: status,
            status,
            count,
          }))
        : [],
    [result],
  )
  const queriedAt = formatDateTime(currentJob?.finished_at)

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <Modal
        open={Boolean(noticeModal)}
        title={noticeModal?.title}
        onOk={() => {
          const reloadOnOk = Boolean(noticeModal?.reloadOnOk)
          setNoticeModal(null)
          if (reloadOnOk) {
            window.location.reload()
          }
        }}
        onCancel={() => {
          const reloadOnOk = Boolean(noticeModal?.reloadOnOk)
          setNoticeModal(null)
          if (reloadOnOk) {
            window.location.reload()
          }
        }}
        okText="확인"
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        <Typography.Paragraph style={{ marginBottom: 0 }}>{noticeModal?.content}</Typography.Paragraph>
      </Modal>

      <div className="page-header">
        <div>
          <Typography.Title level={1}>SF Express 송장 조회</Typography.Title>
          <Typography.Paragraph>
            쇼핑몰 주문 엑셀을 업로드해 송장번호 기준으로 SF Express 배송 상태를 조회합니다.
          </Typography.Paragraph>
        </div>
      </div>

      <div className="upload-grid">
        <Card className="glass-card" title="1. 오더 정보 엑셀 업로드" style={{ height: '100%' }}>
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

        <Card className="glass-card" title="2. SF Express 조회" style={{ height: '100%' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%', height: '100%' }}>
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
                disabled={!canDownload || exportMutation.isPending || isRunInProgress}
                loading={exportMutation.isPending && exportingFormat === 'xlsx'}
                onClick={() => exportMutation.mutate('xlsx')}
              >
                XLSX 다운로드
              </Button>
              <Button
                disabled={!canDownload || exportMutation.isPending || isRunInProgress}
                loading={exportMutation.isPending && exportingFormat === 'csv'}
                onClick={() => exportMutation.mutate('csv')}
              >
                CSV 다운로드
              </Button>
            </Space>

            {currentJob && currentJob.status !== 'completed' && currentJob.status !== 'expired' && (
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

            {result && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                  <Typography.Title level={5} style={{ margin: 0 }}>
                    조회 결과 요약
                  </Typography.Title>
                  <Typography.Text type="secondary">조회일시 {queriedAt}</Typography.Text>
                </div>
                <Descriptions bordered size="small" column={1} style={{ marginBottom: 16 }}>
                  <Descriptions.Item label="조회 Tracking No 건수">{result.summary.query_target_count}</Descriptions.Item>
                </Descriptions>

                <div className="summary-table-wrap">
                  <Table
                    className="compact-summary-table"
                    rowKey="status"
                    pagination={false}
                    size="small"
                    sticky
                    dataSource={statusRows}
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
                </div>
              </>
            )}
          </div>
        </Card>
      </div>
    </Space>
  )
}
