// Types for Mini App API

export interface TelegramUser {
  id: number
  pib_nom: string
  position: string
  department: string
  telegram_username?: string
  email?: string
}

export interface Document {
  id: number
  doc_type: string
  title?: string
  status: string
  created_at: string
  updated_at: string
  staff: {
    id: number
    pib_nom: string
  }
}

export interface Attendance {
  id: number
  staff_id: number
  date: string
  code: string
  hours?: number
}

export interface Staff {
  id: number
  pib_nom: string
  position: string
  department: string
  telegram_username?: string
}

export interface AttendanceCode {
  code: string
  name: string
  description: string
}

// Note: Document status and type labels are defined in constants.ts
// Use STATUS_LABELS and DOCUMENT_TYPE_LABELS from there instead

