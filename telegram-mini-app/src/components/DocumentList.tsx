import { Empty } from 'antd-mobile'
import { Document } from '../api/types'
import { DOCUMENT_TYPE_LABELS, STATUS_LABELS, STATUS_COLORS, normalizeStatus, normalizeDocType } from '../api/constants'

interface DocumentListProps {
  documents: Document[]
  loading?: boolean
  onDocumentClick?: (document: Document) => void
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



export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  loading = false,
  onDocumentClick,
}) => {
  if (loading) {
    return (
      <div style={{ padding: '16px', textAlign: 'center', color: '#999' }}>
        Завантаження...
      </div>
    )
  }

  if (documents.length === 0) {
    return (
      <Empty
        description="Документів не знайдено"
        style={{ padding: '40px 16px' }}
      />
    )
  }

  return (
    <div style={{ padding: '8px' }}>
      {documents.map((doc) => (
        <div
          key={doc.id}
          onClick={() => onDocumentClick?.(doc)}
          style={{
            backgroundColor: '#fff',
            borderRadius: '8px',
            padding: '12px',
            marginBottom: '8px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            cursor: onDocumentClick ? 'pointer' : 'default',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <span style={{ fontSize: '24px' }}>{statusEmoji[normalizeStatus(doc.status)] || '📄'}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                <div style={{ fontWeight: 600, fontSize: '14px' }}>
                  {DOCUMENT_TYPE_LABELS[normalizeDocType(doc.doc_type)] || doc.title || doc.doc_type}
                </div>
                <div
                  style={{
                    fontSize: '10px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    backgroundColor: STATUS_COLORS[normalizeStatus(doc.status)] || '#999',
                    color: '#fff',
                    whiteSpace: 'nowrap',
                    marginLeft: '8px',
                  }}
                >
                  {STATUS_LABELS[normalizeStatus(doc.status)] || doc.status}
                </div>
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>
                Співробітник: {doc.staff.pib_nom}
              </div>
              <div style={{ fontSize: '11px', color: '#999', marginTop: '4px' }}>
                {new Date(doc.created_at).toLocaleString('uk-UA')}
              </div>
              <div style={{ fontSize: '11px', color: '#999' }}>
                ID: {doc.id}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default DocumentList
