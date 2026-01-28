import { useEffect, useState } from 'react'
import { TabBar, Toast, SpinLoading } from 'antd-mobile'
import {
  AppOutline,
  FileOutline,
  UnorderedListOutline,
} from 'antd-mobile-icons'
import { authWithTelegram } from './api/client'
import { useTelegram } from './hooks/useTelegram'
import { TelegramUser } from './api/types'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import Attendance from './pages/Attendance'

type TabType = 'dashboard' | 'documents' | 'attendance'

const tabs = [
  { key: 'dashboard', title: 'Головна', icon: <AppOutline /> },
  { key: 'documents', title: 'Документи', icon: <FileOutline /> },
  { key: 'attendance', title: 'Відвідування', icon: <UnorderedListOutline /> },
]

function App() {
  const { webApp, isReady, BackButton } = useTelegram()
  const [activeTab, setActiveTab] = useState<TabType>('dashboard')
  const [user, setUser] = useState<TelegramUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [authenticated, setAuthenticated] = useState(false)

  useEffect(() => {
    if (!isReady) return

    const initApp = async () => {
      try {
        setLoading(true)

        // Auth with Telegram
        const authData = await authWithTelegram()
        setUser(authData.user)
        setAuthenticated(true)
      } catch (error) {
        Toast.show({
          content: 'Помилка автентифікації. Спробуйте пізніше.',
          icon: 'fail',
        })
        if (webApp) {
          webApp.close()
        }
      } finally {
        setLoading(false)
      }
    }

    initApp()
  }, [isReady, webApp])

  // Setup back button
  useEffect(() => {
    if (activeTab !== 'dashboard') {
      BackButton.show()
      BackButton.onClick(() => setActiveTab('dashboard'))
    } else {
      BackButton.hide()
    }
  }, [activeTab, BackButton])

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: '#f5f5f5',
      }}>
        <SpinLoading color="primary" />
        <p style={{ marginTop: '16px', color: '#999' }}>Завантаження...</p>
      </div>
    )
  }

  if (!authenticated || !user) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: '#f5f5f5',
        padding: '16px',
        textAlign: 'center',
      }}>
        <p style={{ color: '#999' }}>Помилка автентифікації</p>
      </div>
    )
  }

  return (
    <div style={{ paddingBottom: '50px' }}>
      {activeTab === 'dashboard' && <Dashboard user={user} />}
      {activeTab === 'documents' && <Documents user={user} />}
      {activeTab === 'attendance' && <Attendance user={user} />}

      <TabBar
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as TabType)}
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 999,
        }}
      >
        {tabs.map(tab => (
          <TabBar.Item key={tab.key} icon={tab.icon} title={tab.title} />
        ))}
      </TabBar>
    </div>
  )
}

export default App
