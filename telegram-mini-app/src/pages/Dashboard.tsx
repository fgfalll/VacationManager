import { useEffect, useState, useCallback } from 'react'
import { Card, Space, PullToRefresh, SpinLoading, Toast } from 'antd-mobile'
import {
  FileOutline,
  ClockCircleOutline,
  CheckCircleOutline,
  ExclamationCircleOutline,
} from 'antd-mobile-icons'
import { Document, TelegramUser } from '../api/types'
import { documentApi } from '../api/client'
import { useTelegram } from '../hooks/useTelegram'
import { DOCUMENT_TYPE_LABELS, STATUS_LABELS, STATUS_COLORS, normalizeStatus, normalizeDocType } from '../api/constants'
import DocumentCard from '../components/DocumentCard'

interface DashboardProps {
  user: TelegramUser
}

interface Stats {
  todayCount: number
  staleCount: number
  pendingCount: number
  completedCount: number
}

const Dashboard: React.FC<DashboardProps> = ({ user }) => {
  const { HapticFeedback } = useTelegram()
  const [stats, setStats] = useState<Stats>({
    todayCount: 0,
    staleCount: 0,
    pendingCount: 0,
    completedCount: 0,
  })
  const [recentDocuments, setRecentDocuments] = useState<Document[]>([])
  const [staleDocuments, setStaleDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null)
  const [updating, setUpdating] = useState(false)

  const fetchDashboardData = useCallback(async () => {
    try {
      setLoading(true)

      // Fetch all documents (API doesn't support date filter, we filter client-side)
      const allDocsData = await documentApi.list({ limit: 100 })
      const allDocs = allDocsData.data || []

      // Get today's date for filtering (Local time)
      const now = new Date()
      const todayDocs = allDocs.filter((d: Document) => {
        const docDate = new Date(d.created_at)
        return docDate.getDate() === now.getDate() &&
          docDate.getMonth() === now.getMonth() &&
          docDate.getFullYear() === now.getFullYear()
      })

      // Fetch stale documents
      // Fetch stale documents
      const staleData = await documentApi.getStale()
      const staleDocs = staleData.data || []
      setStaleDocuments(staleDocs)

      // Calculate stats
      const pendingDocs = allDocs.filter((d: Document) =>
        !['processed', 'scanned'].includes(normalizeStatus(d.status))
      )

      setStats({
        todayCount: todayDocs.filter((d: Document) => normalizeStatus(d.status) !== 'processed').length,
        staleCount: staleDocs.length,
        pendingCount: pendingDocs.length,
        completedCount: allDocs.filter((d: Document) => {
          if (normalizeStatus(d.status) !== 'processed') return false
          const updateDate = new Date(d.updated_at)
          return updateDate.getDate() === now.getDate() &&
            updateDate.getMonth() === now.getMonth() &&
            updateDate.getFullYear() === now.getFullYear()
        }).length,
      })

      setRecentDocuments([
        ...staleDocs,
        ...allDocs.filter((d: Document) =>
          normalizeStatus(d.status) !== 'processed' &&
          !staleDocs.some((s: Document) => s.id === d.id)
        ).slice(0, 5)
      ])
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDashboardData()
  }, [fetchDashboardData])

  const handleRefresh = async () => {
    HapticFeedback.impactOccurred('medium')
    await fetchDashboardData()
  }

  const getNextStatus = (currentStatus: string): string => {
    const statusFlow: Record<string, string> = {
      'draft': 'signed_by_applicant',
      'signed_by_applicant': 'approved_by_dispatcher',
      'approved_by_dispatcher': 'signed_dep_head',
      'signed_dep_head': 'agreed',
      'agreed': 'signed_rector',
      'signed_rector': 'scanned',
      'scanned': 'processed',
    }
    return statusFlow[normalizeStatus(currentStatus)] || currentStatus
  }

  const handleDocumentClick = (document: Document) => {
    HapticFeedback.impactOccurred('light')
    setSelectedDocument(document)
  }

  const handleSign = async () => {
    if (!selectedDocument || updating) return

    const nextStatus = getNextStatus(selectedDocument.status)
    if (nextStatus === selectedDocument.status) {
      Toast.show({ content: 'Документ вже в кінцевому статусі', icon: 'fail' })
      return
    }

    try {
      setUpdating(true)
      HapticFeedback.impactOccurred('medium')

      const response = await documentApi.updateStatus(selectedDocument.id, nextStatus)

      HapticFeedback.notificationOccurred('success')
      Toast.show({
        content: `Статус оновлено: ${STATUS_LABELS[normalizeStatus(nextStatus)] || nextStatus}`,
        icon: 'success',
      })
      // Update local state to keep modal open with new data
      setSelectedDocument(response.data)
      // Refresh list in background
      handleRefresh()
    } catch (error: any) {
      HapticFeedback.notificationOccurred('error')
      let errorMessage = 'Не вдалося оновити статус'
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail
        } else if (Array.isArray(error.response.data.detail)) {
          // Pydantic validation error
          errorMessage = error.response.data.detail.map((e: any) => `${e.loc.join('.')}: ${e.msg}`).join('\n')
        } else if (typeof error.response.data.detail === 'object') {
          errorMessage = JSON.stringify(error.response.data.detail)
        }
      }
      Toast.show({
        content: errorMessage,
        icon: 'fail',
      })
    } finally {
      setUpdating(false)
    }
  }

  const handleForward = async () => {
    if (!selectedDocument || updating) return

    try {
      setUpdating(true)
      HapticFeedback.impactOccurred('medium')

      const response = await documentApi.forward(selectedDocument.id)

      HapticFeedback.notificationOccurred('success')
      Toast.show({
        content: 'Документ відправлено далі',
        icon: 'success',
      })
      // Update local state to keep modal open with new data
      setSelectedDocument(response.data)
      // Refresh list in background
      handleRefresh()
    } catch (error: any) {
      HapticFeedback.notificationOccurred('error')
      let errorMessage = 'Не вдалося погодити документ'
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail
        } else if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail.map((e: any) => `${e.loc.join('.')}: ${e.msg}`).join('\n')
        } else if (typeof error.response.data.detail === 'object') {
          errorMessage = JSON.stringify(error.response.data.detail)
        }
      }
      Toast.show({
        content: errorMessage,
        icon: 'fail',
      })
    } finally {
      setUpdating(false)
    }
  }

  const handleScanComplete = () => {
    HapticFeedback.notificationOccurred('success')
    // Refresh data after scan upload and close document view
    handleRefresh()
    setSelectedDocument(null)
  }

  if (selectedDocument) {
    return (
      <DocumentCard
        document={selectedDocument}
        onSign={handleSign}
        onForward={handleForward}
        onScanComplete={handleScanComplete}
        onClose={() => setSelectedDocument(null)}
        loading={updating}
      />
    )
  }

  if (loading) {
    return (
      <div style={{ padding: '16px', textAlign: 'center', marginTop: '40px' }}>
        <SpinLoading color="primary" />
        <p style={{ marginTop: '16px', color: '#999' }}>Завантаження...</p>
      </div>
    )
  }

  return (
    <PullToRefresh onRefresh={handleRefresh}>
      <div style={{ padding: '16px' }}>
        {/* Welcome */}
        <Card style={{ marginBottom: '16px' }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>
              Вітаємо, {user.pib_nom}! 👋
            </h4>
            <span style={{ color: '#999', fontSize: '14px' }}>
              {user.position}
            </span>
          </Space>
        </Card>

        {/* Stats Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: '12px',
          marginBottom: '16px',
        }}>
          <StatsCard
            icon={<FileOutline fontSize={24} color="#1677ff" />}
            label="Сьогодні"
            value={stats.todayCount}
          />
          <StatsCard
            icon={<ClockCircleOutline fontSize={24} color="#faad14" />}
            label="В очікуванні"
            value={stats.pendingCount}
          />
          <StatsCard
            icon={<ExclamationCircleOutline fontSize={24} color="#ff4d4f" />}
            label="Проблемні"
            value={stats.staleCount}
          />
          <StatsCard
            icon={<CheckCircleOutline fontSize={24} color="#52c41a" />}
            label="Завершені"
            value={stats.completedCount}
          />
        </div>

        {/* Recent Documents */}
        {recentDocuments.length > 0 && (
          <Card title="Останні документи">
            {recentDocuments.map((doc) => {
              const isStale = staleDocuments.some(s => s.id === doc.id)
              return (
                <div
                  key={doc.id}
                  onClick={() => handleDocumentClick(doc)}
                  style={{
                    padding: '8px 0',
                    borderBottom: '1px solid #f0f0f0',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '14px', fontWeight: 500 }}>
                      {DOCUMENT_TYPE_LABELS[normalizeDocType(doc.doc_type)] || doc.title || doc.doc_type}
                    </span>
                    {isStale && (
                      <span style={{
                        color: '#faad14',
                        fontSize: '10px',
                        display: 'flex',
                        alignItems: 'center',
                        backgroundColor: '#fffbe6',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        border: '1px solid #ffe58f'
                      }}>
                        <ExclamationCircleOutline style={{ marginRight: '4px' }} />
                        Проблема
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '12px', color: '#999', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>{doc.staff.pib_nom}</span>
                    <span style={{
                      color: STATUS_COLORS[normalizeStatus(doc.status)] || '#999',
                      border: `1px solid ${STATUS_COLORS[normalizeStatus(doc.status)] || '#d9d9d9'}`,
                      padding: '0 4px',
                      borderRadius: '4px',
                      fontSize: '10px'
                    }}>
                      {STATUS_LABELS[normalizeStatus(doc.status)] || doc.status}
                    </span>
                  </div>
                </div>
              )
            })}
          </Card>
        )}
      </div>
    </PullToRefresh>
  )
}

interface StatsCardProps {
  icon: React.ReactNode
  label: string
  value: number
}

const StatsCard: React.FC<StatsCardProps> = ({ icon, label, value }) => (
  <Card style={{ textAlign: 'center' }}>
    <div style={{ marginBottom: '8px' }}>{icon}</div>
    <div style={{ fontSize: '24px', fontWeight: 600, marginBottom: '4px' }}>
      {value}
    </div>
    <div style={{ fontSize: '12px', color: '#999' }}>{label}</div>
  </Card>
)

export default Dashboard

