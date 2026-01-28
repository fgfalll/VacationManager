import { useState, useRef } from 'react'
import { Button, Steps, NavBar, Toast } from 'antd-mobile'
import { CheckOutlined, CameraOutlined, FolderOutlined } from '@ant-design/icons'
import { Document } from '../api/types'
import { documentApi } from '../api/client'
import { DOCUMENT_TYPE_LABELS, STATUS_LABELS, normalizeStatus, normalizeDocType } from '../api/constants'
import { useTelegram } from '../hooks/useTelegram'

interface DocumentCardProps {
  document: Document
  onSign?: () => void
  onForward?: () => void
  onScanComplete?: () => void
  onClose?: () => void
  loading?: boolean
}

const statusEmoji: Record<string, string> = {
  draft: '📝',
  signed_by_applicant: '✍️',
  approved_by_dispatcher: '👍',
  signed_dep_head: '👨‍💼',
  agreed: '🤝',
  signed_rector: '🎓',
  scanned: '📸',
  processed: '✅',
}

export const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  onSign,
  onForward,
  onScanComplete,
  onClose,
  loading = false,
}) => {
  const { HapticFeedback } = useTelegram()
  const [uploading, setUploading] = useState(false)
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Upload function
  const uploadScan = async (file: File) => {
    setUploading(true)
    try {
      HapticFeedback.impactOccurred('medium')

      // Upload scan for this specific document
      await documentApi.uploadScan(document.id, file)

      HapticFeedback.notificationOccurred('success')
      Toast.show({
        content: 'Сканкопію завантажено!',
        icon: 'success',
      })

      // Notify parent to refresh
      onScanComplete?.()
    } catch (error: any) {
      HapticFeedback.notificationOccurred('error')
      let errorMessage = 'Не вдалося завантажити'
      if (error.response?.data?.detail) {
        errorMessage = typeof error.response.data.detail === 'string'
          ? error.response.data.detail
          : JSON.stringify(error.response.data.detail)
      }
      Toast.show({
        content: errorMessage,
        icon: 'fail',
      })
    } finally {
      setUploading(false)
    }
  }

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    await uploadScan(file)

    // Reset input
    event.target.value = ''
  }

  const handleAction = () => {
    const status = normalizeStatus(document.status)
    if (status === 'draft' || status === 'approved_by_dispatcher' || status === 'agreed') {
      onSign?.()
    } else if (status === 'signed_by_applicant' || status === 'signed_dep_head') {
      onForward?.()
    }
  }

  const isRectorSigned = normalizeStatus(document.status) === 'signed_rector'
  const isLoading = loading || uploading

  return (
    <div style={{ padding: '16px' }}>
      {/* Header */}
      <NavBar
        onBack={onClose}
        backArrow={true}
        style={{ marginBottom: '16px', paddingLeft: 0, paddingRight: 0 }}
      >
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <span style={{ fontSize: '24px', marginRight: '8px' }}>
            {statusEmoji[normalizeStatus(document.status)] || '📄'}
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
            <span style={{ fontSize: '16px', fontWeight: 600 }}>
              {DOCUMENT_TYPE_LABELS[normalizeDocType(document.doc_type)] || document.title || document.doc_type}
            </span>
            <span style={{ fontSize: '10px', color: '#666', fontWeight: 'normal' }}>
              ID: {document.id}
            </span>
          </div>
        </div>
      </NavBar>

      {/* Document Details */}
      <div style={{ backgroundColor: '#f5f5f5', borderRadius: '12px', padding: '14px', marginBottom: '16px' }}>
        <div style={{ marginBottom: '8px' }}>
          <span style={{ fontSize: '12px', color: '#999' }}>Статус: </span>
          <span style={{ fontSize: '14px', fontWeight: 500 }}>
            {STATUS_LABELS[normalizeStatus(document.status)] || document.status}
          </span>
        </div>
        <div style={{ marginBottom: '8px' }}>
          <span style={{ fontSize: '12px', color: '#999' }}>Співробітник: </span>
          <span style={{ fontSize: '14px' }}>{document.staff.pib_nom}</span>
        </div>
        <div>
          <span style={{ fontSize: '12px', color: '#999' }}>Створено: </span>
          <span style={{ fontSize: '14px' }}>
            {new Date(document.created_at).toLocaleString('uk-UA')}
          </span>
        </div>
      </div>

      {/* Mobile-Friendly Scan Upload - shown only when rector signed */}
      {isRectorSigned && (
        <div style={{
          backgroundColor: '#e6f4ff',
          borderRadius: '16px',
          padding: '20px',
          marginBottom: '20px',
          border: '2px solid #1677ff'
        }}>
          <div style={{ textAlign: 'center', marginBottom: '16px' }}>
            <div style={{ fontSize: '32px', marginBottom: '8px' }}>📸</div>
            <h3 style={{ margin: '0 0 4px 0', fontSize: '18px', fontWeight: 600, color: '#1677ff' }}>
              Завантажте скан
            </h3>
            <p style={{ margin: 0, fontSize: '13px', color: '#666' }}>
              Документ підписано. Сфотографуйте або виберіть файл.
            </p>
          </div>

          {/* Hidden file inputs with mobile-native attributes */}
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handleFileChange}
            style={{ display: 'none' }}
            disabled={uploading}
          />
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf"
            onChange={handleFileChange}
            style={{ display: 'none' }}
            disabled={uploading}
          />

          {/* Large touch-friendly buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <Button
              block
              color="primary"
              size="large"
              style={{
                height: '56px',
                fontSize: '16px',
                borderRadius: '12px',
                fontWeight: 500
              }}
              onClick={() => cameraInputRef.current?.click()}
              loading={uploading}
              disabled={uploading}
            >
              <CameraOutlined style={{ fontSize: '20px', marginRight: '10px' }} />
              Сфотографувати
            </Button>

            <Button
              block
              size="large"
              style={{
                height: '56px',
                fontSize: '16px',
                borderRadius: '12px',
                fontWeight: 500,
                backgroundColor: '#fff',
                border: '2px solid #d9d9d9'
              }}
              onClick={() => fileInputRef.current?.click()}
              loading={uploading}
              disabled={uploading}
            >
              <FolderOutlined style={{ fontSize: '20px', marginRight: '10px' }} />
              Вибрати з галереї
            </Button>
          </div>

          <p style={{
            fontSize: '11px',
            color: '#999',
            textAlign: 'center',
            margin: '12px 0 0 0'
          }}>
            Підтримуються: JPG, PNG, PDF (до 10 МБ)
          </p>
        </div>
      )}

      {/* Signature Workflow */}
      <div style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '16px', marginBottom: '16px' }}>
        <h3 style={{ marginTop: 0, marginBottom: '16px', fontSize: '16px' }}>Етапи погодження</h3>
        <Steps direction="vertical">
          <Steps.Step
            title="Заявник"
            description={
              normalizeStatus(document.status) === 'draft' ? (
                <div style={{ marginTop: '8px' }}>
                  <Button size="small" color="primary" onClick={handleAction} loading={isLoading} disabled={isLoading}>
                    Підписати
                  </Button>
                </div>
              ) : (normalizeStatus(document.status) !== 'draft' ? 'Підписано' : 'Очікує')
            }
            status={normalizeStatus(document.status) === 'draft' ? 'process' : (normalizeStatus(document.status) !== 'draft' ? 'finish' : 'wait')}
          />
          <Steps.Step
            title="Диспетчер"
            description={
              normalizeStatus(document.status) === 'signed_by_applicant' ? (
                <div style={{ marginTop: '8px' }}>
                  <Button size="small" color="primary" onClick={handleAction} loading={isLoading} disabled={isLoading}>
                    Погодити
                  </Button>
                </div>
              ) : (['approved_by_dispatcher', 'signed_dep_head', 'agreed', 'signed_rector', 'scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'Погоджено' : 'Очікує')
            }
            status={normalizeStatus(document.status) === 'signed_by_applicant' ? 'process' : (['approved_by_dispatcher', 'signed_dep_head', 'agreed', 'signed_rector', 'scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'finish' : 'wait')}
          />
          <Steps.Step
            title="Зав. кафедри"
            description={
              normalizeStatus(document.status) === 'approved_by_dispatcher' ? (
                <div style={{ marginTop: '8px' }}>
                  <Button size="small" color="primary" onClick={handleAction} loading={isLoading} disabled={isLoading}>
                    Підписати
                  </Button>
                </div>
              ) : (['signed_dep_head', 'agreed', 'signed_rector', 'scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'Підписано' : 'Очікує')
            }
            status={normalizeStatus(document.status) === 'approved_by_dispatcher' ? 'process' : (['signed_dep_head', 'agreed', 'signed_rector', 'scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'finish' : 'wait')}
          />
          <Steps.Step
            title="Узгодження"
            description={
              normalizeStatus(document.status) === 'signed_dep_head' ? (
                <div style={{ marginTop: '8px' }}>
                  <Button size="small" color="primary" onClick={handleAction} loading={isLoading} disabled={isLoading}>
                    Погодити
                  </Button>
                </div>
              ) : (['agreed', 'signed_rector', 'scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'Узгоджено' : 'Очікує')
            }
            status={normalizeStatus(document.status) === 'signed_dep_head' ? 'process' : (['agreed', 'signed_rector', 'scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'finish' : 'wait')}
          />
          <Steps.Step
            title="Ректор"
            description={
              normalizeStatus(document.status) === 'agreed' ? (
                <div style={{ marginTop: '8px' }}>
                  <Button size="small" color="primary" onClick={handleAction} loading={isLoading} disabled={isLoading}>
                    Підписати
                  </Button>
                </div>
              ) : (['signed_rector', 'scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'Підписано' : 'Очікує')
            }
            status={normalizeStatus(document.status) === 'agreed' ? 'process' : (['signed_rector', 'scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'finish' : 'wait')}
          />
          <Steps.Step
            title="Сканкопія"
            description={
              isRectorSigned ? '⬆️ Завантажте скан вище' : (['scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'Завантажено' : 'Очікує')
            }
            status={isRectorSigned ? 'process' : (['scanned', 'processed'].includes(normalizeStatus(document.status)) ? 'finish' : 'wait')}
          />
          <Steps.Step
            title="Обробка"
            description={
              normalizeStatus(document.status) === 'processed' ? 'Оброблено' : (normalizeStatus(document.status) === 'scanned' ? 'Очікує обробки' : 'Очікує')
            }
            status={normalizeStatus(document.status) === 'processed' ? 'finish' : (normalizeStatus(document.status) === 'scanned' ? 'process' : 'wait')}
          />
        </Steps>
      </div>

      {/* Completed state badge */}
      {normalizeStatus(document.status) === 'processed' && (
        <div style={{
          textAlign: 'center',
          padding: '20px',
          backgroundColor: '#f6ffed',
          borderRadius: '12px',
          color: '#52c41a',
          marginTop: '16px'
        }}>
          <CheckOutlined style={{ fontSize: '28px', marginBottom: '8px' }} />
          <div style={{ fontWeight: 600, fontSize: '16px' }}>Процес завершено</div>
        </div>
      )}
    </div>
  )
}

export default DocumentCard
