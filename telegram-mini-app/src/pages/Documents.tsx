import { useEffect, useState, useCallback } from 'react'
import { Tabs, Toast, Badge, PullToRefresh } from 'antd-mobile'
import { Document, TelegramUser } from '../api/types'
import { documentApi } from '../api/client'
import { STATUS_LABELS, normalizeStatus } from '../api/constants'
import DocumentList from '../components/DocumentList'
import DocumentCard from '../components/DocumentCard'
import StaleDocuments from '../components/StaleDocuments'
import { useTelegram } from '../hooks/useTelegram'

interface DocumentsProps {
  user: TelegramUser
}

const Documents: React.FC<DocumentsProps> = ({ user: _user }) => {
  const { HapticFeedback } = useTelegram()
  const [todayDocuments, setTodayDocuments] = useState<Document[]>([])
  const [staleDocuments, setStaleDocuments] = useState<Document[]>([])
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null)
  const [loadingToday, setLoadingToday] = useState(true)
  const [loadingStale, setLoadingStale] = useState(true)
  const [updating, setUpdating] = useState(false)

  const fetchTodayDocuments = useCallback(async () => {
    try {
      setLoadingToday(true)
      const data = await documentApi.list({ date: 'today' })
      const docs = data.data || []
      setTodayDocuments(docs.filter((d: Document) => normalizeStatus(d.status) !== 'processed'))
    } catch (error) {
      HapticFeedback.notificationOccurred('error')
      Toast.show({
        content: 'Не вдалося завантажити документи',
        icon: 'fail',
      })
    } finally {
      setLoadingToday(false)
    }
  }, [HapticFeedback])

  const fetchStaleDocuments = useCallback(async () => {
    try {
      setLoadingStale(true)
      const data = await documentApi.getStale()
      setStaleDocuments(data.data || [])
    } catch (error) {
      HapticFeedback.notificationOccurred('error')
      Toast.show({
        content: 'Не вдалося завантажити застарілі документи',
        icon: 'fail',
      })
    } finally {
      setLoadingStale(false)
    }
  }, [HapticFeedback])

  useEffect(() => {
    fetchTodayDocuments()
    fetchStaleDocuments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleDocumentClick = (document: Document) => {
    HapticFeedback.impactOccurred('light')
    setSelectedDocument(document)
  }

  const handleRefresh = async () => {
    HapticFeedback.impactOccurred('medium')
    await Promise.all([fetchTodayDocuments(), fetchStaleDocuments()])
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

      // Update document status via API
      // Update document status via API
      // Update document status via API
      const updatedDoc = await documentApi.updateStatus(selectedDocument.id, nextStatus)

      HapticFeedback.notificationOccurred('success')
      Toast.show({
        content: `Статус оновлено: ${STATUS_LABELS[normalizeStatus(nextStatus)] || nextStatus}`,
        icon: 'success',
      })
      // Update local state to keep modal open with new data
      setSelectedDocument(updatedDoc)
      // Refresh list in background
      handleRefresh()
    } catch (error: any) {
      HapticFeedback.notificationOccurred('error')
      let errorMessage = 'Не вдалося оновити статус'
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

  const handleForward = async () => {
    if (!selectedDocument || updating) return

    try {
      setUpdating(true)
      HapticFeedback.impactOccurred('medium')

      const updatedDoc = await documentApi.forward(selectedDocument.id)

      HapticFeedback.notificationOccurred('success')
      Toast.show({
        content: 'Документ відправлено далі',
        icon: 'success',
      })
      // Update local state to keep modal open with new data
      setSelectedDocument(updatedDoc)
      // Refresh list in background
      handleRefresh()
    } catch (error: any) {
      HapticFeedback.notificationOccurred('error')
      let errorMessage = 'Не вдалося відправити документ'
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

  return (
    <PullToRefresh onRefresh={handleRefresh}>
      <Tabs defaultActiveKey="today">
        <Tabs.Tab title="Сьогодні" key="today">
          <DocumentList
            documents={todayDocuments}
            loading={loadingToday}
            onDocumentClick={handleDocumentClick}
          />
        </Tabs.Tab>
        <Tabs.Tab
          title={
            <Badge content={staleDocuments.length > 0 ? staleDocuments.length : null}>
              Проблемні
            </Badge>
          }
          key="stale"
        >
          <StaleDocuments
            documents={staleDocuments}
            loading={loadingStale}
            onRefresh={handleRefresh}
          />
        </Tabs.Tab>
      </Tabs>
    </PullToRefresh>
  )
}

export default Documents

