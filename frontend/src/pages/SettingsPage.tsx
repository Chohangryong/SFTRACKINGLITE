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
      messageApi.success('API key saved.')
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
      messageApi.success('API key updated.')
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
    },
    onError: (error) => {
      messageApi.error(getErrorMessage(error))
    },
  })

  const testKeyMutation = useMutation({
    mutationFn: testApiKey,
    onSuccess: () => {
      messageApi.success('API test request sent.')
      void queryClient.invalidateQueries({ queryKey: ['api-keys'] })
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
          <Typography.Title level={1}>Settings</Typography.Title>
          <Typography.Paragraph>Manage the SF API key used by Lite Tracking.</Typography.Paragraph>
        </div>
      </div>

      <Card className="glass-card" title="SF API Key">
        <Form
          form={apiKeyForm}
          layout="vertical"
          initialValues={{ environment: 'sandbox', is_active: true }}
          onFinish={handleSubmit}
        >
          <Space align="start" wrap>
            <Form.Item label="Label" name="label" rules={[{ required: true }]}>
              <Input style={{ width: 180 }} />
            </Form.Item>
            <Form.Item
              label="Environment"
              name="environment"
              rules={[{ required: true }]}
              extra={isEditing ? 'Environment is fixed after create.' : undefined}
            >
              <Select
                style={{ width: 140 }}
                disabled={isEditing}
                options={[
                  { label: 'Sandbox', value: 'sandbox' },
                  { label: 'Production', value: 'production' },
                ]}
              />
            </Form.Item>
            <Form.Item
              label="Partner ID"
              name="partner_id"
              rules={isEditing ? [] : [{ required: true }]}
              extra={isEditing ? 'Leave blank to keep the current Partner ID.' : undefined}
            >
              <Input style={{ width: 180 }} placeholder={isEditing ? 'Keep current value' : undefined} />
            </Form.Item>
            <Form.Item
              label="Checkword"
              name="checkword"
              rules={isEditing ? [] : [{ required: true }]}
              extra={isEditing ? 'Leave blank to keep the current Checkword.' : undefined}
            >
              <Input.Password style={{ width: 220 }} placeholder={isEditing ? 'Keep current value' : undefined} />
            </Form.Item>
            <Form.Item label="Active" name="is_active" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label=" ">
              <Space>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={createKeyMutation.isPending || updateKeyMutation.isPending}
                >
                  {isEditing ? 'Update' : 'Save'}
                </Button>
                {isEditing && (
                  <Button onClick={resetForm}>
                    Cancel
                  </Button>
                )}
              </Space>
            </Form.Item>
          </Space>
        </Form>
        <Table
          rowKey="id"
          dataSource={apiKeysQuery.data ?? []}
          pagination={false}
          columns={[
            { title: 'Label', dataIndex: 'label' },
            { title: 'Environment', dataIndex: 'environment' },
            {
              title: 'Active',
              dataIndex: 'is_active',
              render: (value: boolean) => (value ? <Tag color="green">Active</Tag> : <Tag>Inactive</Tag>),
            },
            {
              title: 'Secrets',
              render: (_, record) => `${record.key_fields.partner_id} / ${record.key_fields.checkword}`,
            },
            { title: 'Test Result', dataIndex: 'test_result' },
            {
              title: 'Actions',
              render: (_, record) => (
                <Space>
                  <Button size="small" onClick={() => handleEdit(record)}>
                    Edit
                  </Button>
                  <Button size="small" onClick={() => testKeyMutation.mutate(record.id)}>
                    Test
                  </Button>
                  <Button danger size="small" onClick={() => deleteKeyMutation.mutate(record.id)}>
                    Delete
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
