import axios from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Form, Input, Select, Space, Switch, Table, Tag, Typography, message } from 'antd'
import { useState } from 'react'

import {
  createApiKey,
  deleteApiKey,
  listApiKeys,
  testApiKey,
  updateApiKey,
} from '../api'
import type { ApiKeyCreatePayload, ApiKeyMasked } from '../types'

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

export function SettingsPage() {
  const [apiKeyForm] = Form.useForm<ApiKeyCreatePayload>()
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [editingId, setEditingId] = useState<number | null>(null)
  const isEditing = editingId !== null

  const apiKeysQuery = useQuery({ queryKey: ['api-keys'], queryFn: listApiKeys })

  const createKeyMutation = useMutation({
    mutationFn: createApiKey,
    onSuccess: () => {
      resetForm()
      messageApi.success('API KEY를 저장했습니다.')
      void queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error))
    },
  })

  const updateKeyMutation = useMutation({
    mutationFn: ({ apiKeyId, payload }: { apiKeyId: number; payload: Record<string, unknown> }) =>
      updateApiKey(apiKeyId, payload),
    onSuccess: () => {
      resetForm()
      messageApi.success('API KEY를 수정했습니다.')
      void queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error))
    },
  })

  const deleteKeyMutation = useMutation({
    mutationFn: deleteApiKey,
    onSuccess: (_, apiKeyId) => {
      if (editingId === apiKeyId) {
        resetForm()
      }
      void queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      messageApi.success('API KEY를 삭제했습니다.')
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error))
    },
  })

  const testKeyMutation = useMutation({
    mutationFn: testApiKey,
    onSuccess: () => {
      messageApi.success('API 연결 테스트를 요청했습니다.')
      void queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error))
    },
  })

  function resetForm() {
    setEditingId(null)
    apiKeyForm.resetFields()
    apiKeyForm.setFieldsValue({ environment: 'sandbox', is_active: true, label: '', partner_id: '', checkword: '' })
  }

  function handleEdit(record: ApiKeyMasked) {
    setEditingId(record.id)
    apiKeyForm.setFieldsValue({
      label: record.label,
      environment: record.environment as 'sandbox' | 'production',
      partner_id: '',
      checkword: '',
      is_active: record.is_active,
    })
  }

  function handleSubmit(values: ApiKeyCreatePayload) {
    if (!isEditing) {
      createKeyMutation.mutate(values)
      return
    }
    const apiKeyId = editingId
    if (apiKeyId === null) {
      return
    }
    const partnerId = (values.partner_id ?? '').trim()
    const checkword = (values.checkword ?? '').trim()
    const payload: Record<string, unknown> = {
      label: values.label,
      is_active: values.is_active,
    }
    if (partnerId) {
      payload.partner_id = partnerId
    }
    if (checkword) {
      payload.checkword = checkword
    }
    updateKeyMutation.mutate({ apiKeyId, payload })
  }

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      {contextHolder}
      <div className="page-header">
        <div>
          <Typography.Title level={1}>설정</Typography.Title>
          <Typography.Paragraph>SF Express Tracking 조회를 위한 API KEY를 관리하는 화면입니다.</Typography.Paragraph>
        </div>
      </div>

      <Card className="glass-card" title="SF Express API KEY">
        <Form
          form={apiKeyForm}
          layout="vertical"
          initialValues={{ environment: 'sandbox', is_active: true }}
          onFinish={handleSubmit}
        >
          <Space align="start" wrap>
            <Form.Item label="라벨" name="label" rules={[{ required: true, message: '라벨을 입력하세요.' }]}>
              <Input style={{ width: 180 }} />
            </Form.Item>
            <Form.Item
              label="환경"
              name="environment"
              rules={[{ required: true, message: '환경을 선택하세요.' }]}
              extra={isEditing ? '생성 후에는 환경을 변경할 수 없습니다.' : undefined}
            >
              <Select
                style={{ width: 140 }}
                disabled={isEditing}
                options={[
                  { label: '샌드박스', value: 'sandbox' },
                  { label: '운영', value: 'production' },
                ]}
              />
            </Form.Item>
            <Form.Item
              label="Partner ID"
              name="partner_id"
              rules={isEditing ? [] : [{ required: true, message: 'Partner ID를 입력하세요.' }]}
              extra={isEditing ? '비워두면 현재 Partner ID를 유지합니다.' : undefined}
            >
              <Input style={{ width: 180 }} placeholder={isEditing ? '현재 값 유지' : undefined} />
            </Form.Item>
            <Form.Item
              label="Checkword"
              name="checkword"
              rules={isEditing ? [] : [{ required: true, message: 'Checkword를 입력하세요.' }]}
              extra={isEditing ? '비워두면 현재 Checkword를 유지합니다.' : undefined}
            >
              <Input.Password style={{ width: 220 }} placeholder={isEditing ? '현재 값 유지' : undefined} />
            </Form.Item>
            <Form.Item label="사용 여부" name="is_active" valuePropName="checked">
              <Switch checkedChildren="사용" unCheckedChildren="중지" />
            </Form.Item>
            <Form.Item label=" ">
              <Space>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={createKeyMutation.isPending || updateKeyMutation.isPending}
                >
                  {isEditing ? '수정' : '저장'}
                </Button>
                {isEditing && <Button onClick={resetForm}>취소</Button>}
              </Space>
            </Form.Item>
          </Space>
        </Form>
        <Table
          rowKey="id"
          dataSource={apiKeysQuery.data ?? []}
          pagination={false}
          columns={[
            { title: '라벨', dataIndex: 'label' },
            { title: '환경', dataIndex: 'environment' },
            {
              title: '사용 여부',
              dataIndex: 'is_active',
              render: (value: boolean) => (value ? <Tag color="green">사용중</Tag> : <Tag>중지</Tag>),
            },
            {
              title: '등록 정보',
              render: (_, record) => `${record.key_fields.partner_id} / ${record.key_fields.checkword}`,
            },
            { title: '테스트 결과', dataIndex: 'test_result' },
            {
              title: '작업',
              render: (_, record) => (
                <Space>
                  <Button size="small" onClick={() => handleEdit(record)}>
                    수정
                  </Button>
                  <Button size="small" onClick={() => testKeyMutation.mutate(record.id)}>
                    테스트
                  </Button>
                  <Button danger size="small" onClick={() => deleteKeyMutation.mutate(record.id)}>
                    삭제
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  )
}

