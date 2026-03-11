import { RocketOutlined, SettingOutlined } from '@ant-design/icons'
import { Layout, Menu, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { APP_VERSION } from '../appVersion'

const { Header, Sider, Content } = Layout

export function LayoutShell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const selectedKey = location.pathname.startsWith('/settings') ? '/settings' : '/lite'

  return (
    <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
      <Sider
        width={280}
        breakpoint="lg"
        collapsedWidth="0"
        style={{
          display: 'flex',
          flexDirection: 'column',
          background: 'rgba(13, 35, 48, 0.92)',
          borderRight: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <div style={{ padding: '32px 24px 16px', color: 'white' }}>
          <Typography.Text style={{ color: '#8fd8f1', letterSpacing: 2 }}>SF EXPRESS</Typography.Text>
          <Typography.Title level={3} style={{ color: 'white', margin: '8px 0 0' }}>
            SF Express 송장 조회
          </Typography.Title>
          <Typography.Paragraph style={{ color: 'rgba(255,255,255,0.72)', marginTop: 12 }}>
            쇼핑몰 오더 엑셀파일을 업로드하여 송장번호가 있는 건을 대상으로 배송상태를 조회할 수 있습니다.
          </Typography.Paragraph>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          style={{ background: 'transparent', borderInlineEnd: 0, flex: 1 }}
          items={[
            { key: '/lite', icon: <RocketOutlined />, label: <Link to="/lite">SF Express 송장 조회</Link> },
            { key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">설정</Link> },
          ]}
        />
        <div style={{ padding: '16px 24px 24px' }}>
          <Typography.Text style={{ color: 'rgba(255,255,255,0.58)', fontSize: 12 }}>
            버전 v{APP_VERSION}
          </Typography.Text>
        </div>
      </Sider>
      <Layout style={{ background: 'transparent' }}>
        <Header
          style={{
            background: 'transparent',
            padding: '24px 24px 0',
            height: 'auto',
          }}
        />
        <Content style={{ padding: '0 24px 24px' }}>{children}</Content>
      </Layout>
    </Layout>
  )
}
