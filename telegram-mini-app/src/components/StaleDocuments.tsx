import { useState } from 'react'
import { Button, Toast, Modal, TextArea } from 'antd-mobile'
import { ExclamationCircleOutlined, MessageOutlined, DeleteOutlined, CheckOutlined } from '@ant-design/icons'
import { Document } from '../api/types'
import { documentApi } from '../api/client'
import { useTelegram } from '../hooks/useTelegram'
import { DOCUMENT_TYPE_LABELS, STATUS_LABELS, normalizeStatus, normalizeDocType } from '../api/constants'

interface StaleDocumentsProps {
  documents: Document[]
  loading?: boolean
  onRefresh?: () => void
}

export const StaleDocuments: React.FC<StaleDocumentsProps> = ({
  documents,
  loading: _externalLoading = false,
  onRefresh,
}) => {
  const { HapticFeedback } = useTelegram()
  const [explainModal, setExplainModal] = useState<{ visible: boolean; documentId: number | null }>({
    visible: false,
    documentId: null,
  })
  const [explanation, setExplanation] = useState('')
  const [loading, setLoading] = useState(false)

  const handleResolve = async (documentId: number) => {
    setLoading(true)
    try {
      HapticFeedback.impactOccurred('medium')
      await documentApi.resolveStale(documentId, { action: 'resolve' })
      HapticFeedback.notificationOccurred('success')
      Toast.show({
        content: 'Документ позначено як вирішений',
        icon: 'success',
      })
      onRefresh?.()
    } catch (error) {
      HapticFeedback.notificationOccurred('error')
      Toast.show({
        content: 'Не вдалося вирішити документ',
        icon: 'fail',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (documentId: number) => {
    Modal.confirm({
      content: 'Ви впевнені, що хочете видалити цей документ?',
      onConfirm: async () => {
        setLoading(true)
        try {
          HapticFeedback.impactOccurred('heavy')
          await documentApi.delete(documentId)
          HapticFeedback.notificationOccurred('success')
          Toast.show({
            content: 'Документ видалено',
            icon: 'success',
          })
          onRefresh?.()
        } catch (error) {
          HapticFeedback.notificationOccurred('error')
          Toast.show({
            content: 'Не вдалося видалити документ',
            icon: 'fail',
          })
        } finally {
          setLoading(false)
        }
      },
    })
  }

  const handleExplain = (documentId: number) => {
    setExplainModal({ visible: true, documentId })
  }

  const submitExplanation = async () => {
    if (!explainModal.documentId) return

    setLoading(true)
    try {
      HapticFeedback.impactOccurred('medium')
      await documentApi.resolveStale(explainModal.documentId, {
        action: 'explain',
        reason: explanation,
      })
      HapticFeedback.notificationOccurred('success')
      Toast.show({
        content: 'Пояснення додано',
        icon: 'success',
      })
      setExplainModal({ visible: false, documentId: null })
      setExplanation('')
      onRefresh?.()
    } catch (error) {
      HapticFeedback.notificationOccurred('error')
      Toast.show({
        content: 'Не вдалося додати пояснення',
        icon: 'fail',
      })
    } finally {
      setLoading(false)
    }
  }

  const getDaysStale = (createdAt: string) => {
    const days = Math.floor((Date.now() - new Date(createdAt).getTime()) / (1000 * 60 * 60 * 24))
    return days
  }

  if (documents.length === 0) {
    return (
      <div style={{ padding: '40px 16px', textAlign: 'center' }}>
        <CheckOutlined style={{ fontSize: '48px', color: '#52c41a', marginBottom: '16px' }} />
        <h3>Відмінно!</h3>
        <p style={{ color: '#999' }}>Застарілих документів немає</p>
      </div>
    )
  }

  return (
    <div style={{ padding: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
        <ExclamationCircleOutlined style={{ fontSize: '24px', color: '#faad14', marginRight: '8px' }} />
        <h3 style={{ margin: 0 }}>Проблемні документи</h3>
      </div>

      {documents.map((doc) => {
        const daysStale = getDaysStale(doc.created_at)
        return (
          <div
            key={doc.id}
            style={{
              backgroundColor: daysStale > 3 ? '#fff2e8' : '#f5f5f5',
              borderRadius: '8px',
              padding: '12px',
              marginBottom: '12px',
              border: daysStale > 3 ? '1px solid #ffbb96' : '1px solid #d9d9d9',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontWeight: 600, fontSize: '14px' }}>
                {DOCUMENT_TYPE_LABELS[normalizeDocType(doc.doc_type)] || doc.title || doc.doc_type}
              </span>
              <span style={{
                fontSize: '11px',
                padding: '2px 6px',
                borderRadius: '4px',
                backgroundColor: daysStale > 3 ? '#ff4d4f' : '#faad14',
                color: '#fff',
              }}>
                {daysStale} дн.
              </span>
            </div>

            <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
              Співробітник: {doc.staff.pib_nom}
            </div>

            <div style={{ fontSize: '11px', color: '#999', marginBottom: '12px' }}>
              Статус: {STATUS_LABELS[normalizeStatus(doc.status)] || doc.status}
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <Button
                size="small"
                color="primary"
                onClick={() => handleExplain(doc.id)}
                disabled={loading}
              >
                <MessageOutlined style={{ marginRight: '4px' }} />
                Пояснити
              </Button>
              <Button
                size="small"
                color="success"
                onClick={() => handleResolve(doc.id)}
                disabled={loading}
              >
                <CheckOutlined style={{ marginRight: '4px' }} />
                Вирішено
              </Button>
              <Button
                size="small"
                color="danger"
                onClick={() => handleDelete(doc.id)}
                disabled={loading}
              >
                <DeleteOutlined style={{ marginRight: '4px' }} />
                Видалити
              </Button>
            </div>
          </div>
        )
      })}

      {/* Explain Modal */}
      <Modal
        visible={explainModal.visible}
        title="Пояснити затримку"
        content={
          <TextArea
            placeholder="Опишіть причину затримки документа..."
            value={explanation}
            onChange={setExplanation}
            rows={4}
            maxLength={500}
            showCount
          />
        }
        actions={[
          {
            key: 'cancel',
            text: 'Скасувати',
            onClick: () => {
              setExplainModal({ visible: false, documentId: null })
              setExplanation('')
            },
          },
          {
            key: 'confirm',
            text: 'Надіслати',
            primary: true,
            onClick: submitExplanation,
          },
        ]}
      />
    </div>
  )
}

export default StaleDocuments
