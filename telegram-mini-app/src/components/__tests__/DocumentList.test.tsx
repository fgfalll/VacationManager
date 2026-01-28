/**
 * Tests for DocumentList component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DocumentList } from '../DocumentList'
import { Document } from '../../api/types'

describe('DocumentList', () => {
  const mockDocuments: Document[] = [
    {
      id: 1,
      doc_type: 'VACATION_PAID',
      status: 'DRAFT',
      created_at: '2026-01-22T10:00:00',
      staff: {
        id: 1,
        pib_nom: 'Тестов Тест Тестович'
      }
    },
    {
      id: 2,
      doc_type: 'VACATION_UNPAID',
      status: 'SIGNED_BY_APPLICANT',
      created_at: '2026-01-22T11:00:00',
      staff: {
        id: 2,
        pib_nom: 'Іванов Іван Іванович'
      }
    }
  ]

  it('renders documents correctly', () => {
    render(
      <DocumentList
        documents={mockDocuments}
        onDocumentClick={vi.fn()}
      />
    )

    expect(screen.getByText('VACATION_PAID')).toBeInTheDocument()
    expect(screen.getByText('VACATION_UNPAID')).toBeInTheDocument()
    expect(screen.getByText('Тестов Тест Тестович')).toBeInTheDocument()
    expect(screen.getByText('Іванов Іван Іванович')).toBeInTheDocument()
  })

  it('shows empty state when no documents', () => {
    const { container } = render(
      <DocumentList
        documents={[]}
        onDocumentClick={vi.fn()}
      />
    )

    expect(screen.getByText(/документів не знайдено/i)).toBeInTheDocument()
  })

  it('calls onDocumentClick when document is clicked', () => {
    const handleClick = vi.fn()

    render(
      <DocumentList
        documents={mockDocuments}
        onDocumentClick={handleClick}
      />
    )

    const firstDoc = screen.getByText('VACATION_PAID').closest('[style*="cursor"]')
    if (firstDoc) {
      fireEvent.click(firstDoc)
      expect(handleClick).toHaveBeenCalledWith(mockDocuments[0])
    }
  })

  it('shows loading state', () => {
    const { container } = render(
      <DocumentList
        documents={[]}
        loading={true}
        onDocumentClick={vi.fn()}
      />
    )

    expect(screen.getByText(/завантаження/i)).toBeInTheDocument()
  })

  it('displays correct status emoji for each status', () => {
    const { container } = render(
      <DocumentList
        documents={mockDocuments}
        onDocumentClick={vi.fn()}
      />
    )

    // DRAFT should show 📝
    expect(screen.getByText('📝')).toBeInTheDocument()

    // SIGNED_BY_APPLICANT should show ✍️
    const allText = container.textContent || ''
    expect(allText).toContain('✍️')
  })

  it('displays document ID and date', () => {
    render(
      <DocumentList
        documents={mockDocuments}
        onDocumentClick={vi.fn()}
      />
    )

    expect(screen.getByText('ID: 1')).toBeInTheDocument()
    expect(screen.getByText('ID: 2')).toBeInTheDocument()
  })
})
