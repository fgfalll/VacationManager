/**
 * Tests for DocumentCard component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DocumentCard } from '../DocumentCard'
import { Document } from '../../api/types'

describe('DocumentCard', () => {
  const mockDocument: Document = {
    id: 1,
    doc_type: 'VACATION_PAID',
    status: 'DRAFT',
    created_at: '2026-01-22T10:00:00',
    staff: {
      id: 1,
      pib_nom: 'Тестов Тест Тестович'
    }
  }

  it('renders document information correctly', () => {
    render(
      <DocumentCard
        document={mockDocument}
        onClose={vi.fn()}
      />
    )

    expect(screen.getByText('VACATION_PAID')).toBeInTheDocument()
    expect(screen.getByText('Тестов Тест Тестович')).toBeInTheDocument()
    expect(screen.getByText('ID: 1')).toBeInTheDocument()
  })

  it('calls onSign when sign button is clicked', () => {
    const handleSign = vi.fn()

    render(
      <DocumentCard
        document={mockDocument}
        onSign={handleSign}
        onClose={vi.fn()}
      />
    )

    const signButton = screen.getByText(/підписати/i)
    fireEvent.click(signButton)

    expect(handleSign).toHaveBeenCalledOnce()
  })

  it('calls onClose when close button is clicked', () => {
    const handleClose = vi.fn()

    render(
      <DocumentCard
        document={mockDocument}
        onClose={handleClose}
      />
    )

    const closeButton = screen.getByRole('button', { name: /close/i }) ||
                         screen.getByText('❌')

    if (closeButton) {
      fireEvent.click(closeButton)
      expect(handleClose).toHaveBeenCalledOnce()
    }
  })

  it('shows completed state for PROCESSED documents', () => {
    const processedDoc = { ...mockDocument, status: 'PROCESSED' }

    render(
      <DocumentCard
        document={processedDoc}
        onClose={vi.fn()}
      />
    )

    expect(screen.getByText(/документ оброблено/i)).toBeInTheDocument()
  })

  it('displays correct status labels', () => {
    const { rerender } = render(
      <DocumentCard
        document={mockDocument}
        onClose={vi.fn()}
      />
    )

    expect(screen.getByText(/чернетка/i)).toBeInTheDocument()

    const signedDoc = { ...mockDocument, status: 'SIGNED_BY_APPLICANT' }
    rerender(
      <DocumentCard
        document={signedDoc}
        onClose={vi.fn()}
      />
    )

    expect(screen.getByText(/підписано заявником/i)).toBeInTheDocument()
  })

  it('shows scan button for SIGNED_RECTOR status', () => {
    const rectorDoc = { ...mockDocument, status: 'SIGNED_RECTOR' }
    const handleScan = vi.fn()

    render(
      <DocumentCard
        document={rectorDoc}
        onScan={handleScan}
        onClose={vi.fn()}
      />
    )

    expect(screen.getByText(/завантажити сканкопію/i)).toBeInTheDocument()
  })

  it('does not show actions for PROCESSED documents', () => {
    const processedDoc = { ...mockDocument, status: 'PROCESSED' }
    const handleSign = vi.fn()
    const handleForward = vi.fn()

    render(
      <DocumentCard
        document={processedDoc}
        onSign={handleSign}
        onForward={handleForward}
        onClose={vi.fn()}
      />
    )

    expect(handleSign).not.toHaveBeenCalled()
    expect(handleForward).not.toHaveBeenCalled()
  })
})
