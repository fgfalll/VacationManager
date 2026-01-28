import axios, { AxiosInstance } from 'axios'

const TELEGRAM_API_URL = '/api/telegram'
const GENERAL_API_URL = '/api'

// Telegram WebApp types are defined in telegram.d.ts

/**
 * Setup common interceptors for API clients
 */
const setupInterceptors = (client: AxiosInstance) => {
  // Request interceptor to add auth token
  client.interceptors.request.use(
    (config) => {
      const token = localStorage.getItem('access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    },
    (error) => {
      return Promise.reject(error)
    }
  )

  // Response interceptor for error handling
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        // Unauthorized - clear token and redirect to auth
        localStorage.removeItem('access_token')
        if (window.Telegram?.WebApp) {
          window.Telegram.WebApp.close()
        }
      }
      return Promise.reject(error)
    }
  )
}

// Telegram API client (for /api/telegram/*)
export const telegramApiClient = axios.create({
  baseURL: TELEGRAM_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})
setupInterceptors(telegramApiClient)

// General API client (for /api/documents, /api/attendance, /api/staff, etc.)
export const generalApiClient = axios.create({
  baseURL: GENERAL_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})
setupInterceptors(generalApiClient)

// Auth with Telegram
export const authWithTelegram = async () => {
  // Development mode: allow testing in regular browser
  const isDevelopment = import.meta.env.DEV

  if (!window.Telegram?.WebApp?.initData) {
    if (isDevelopment) {
      // Mock user for browser development/testing
      console.warn('[DEV MODE] Telegram WebApp not available, using mock user')
      const mockUser = {
        id: 1,
        telegram_id: 'dev_user',
        first_name: 'Dev',
        last_name: 'User',
        username: 'dev_user',
        staff_id: 1,
        is_active: true,
      }
      // Store a dev token
      localStorage.setItem('access_token', 'dev_token_for_testing')
      return { access_token: 'dev_token_for_testing', user: mockUser }
    }
    throw new Error('Telegram WebApp not available')
  }

  const response = await telegramApiClient.post<{ access_token: string; user: any }>('/auth', {
    init_data: window.Telegram.WebApp.initData,
  })

  // Store token
  localStorage.setItem('access_token', response.data.access_token)

  // Initialize WebApp
  window.Telegram.WebApp.ready()
  window.Telegram.WebApp.expand()

  return response.data
}

// Get current user
export const getCurrentUser = async () => {
  const response = await telegramApiClient.get('/user')
  return response.data
}

// Get Telegram info
export const getTelegramInfo = async () => {
  const response = await telegramApiClient.get('/info')
  return response.data
}

// Link Telegram account
export const linkTelegramAccount = async (telegramUserId: string) => {
  const response = await telegramApiClient.post('/link', { telegram_user_id: telegramUserId })
  return response.data
}

// ==================== Document API ====================

export const documentApi = {
  // Get documents list with optional filters
  list: async (params?: { date?: string; status?: string; skip?: number; limit?: number }) => {
    const response = await generalApiClient.get('/documents', { params })
    return response.data
  },

  // Get stale documents
  getStale: async (params?: { skip?: number; limit?: number }) => {
    const response = await generalApiClient.get('/documents/stale', { params })
    return response.data
  },

  // Get single document
  get: async (id: number) => {
    const response = await generalApiClient.get(`/documents/${id}`)
    return response.data
  },

  // Upload scan for document
  uploadScan: async (documentId: number, file: Blob) => {
    const formData = new FormData()
    formData.append('file', file, 'scan.jpg')
    const response = await generalApiClient.post(`/documents/${documentId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  // Direct scan upload (creates new archived document)
  directUpload: async (file: Blob, metadata: Record<string, any>) => {
    const formData = new FormData()
    formData.append('file', file, 'scan.jpg')
    Object.entries(metadata).forEach(([key, value]) => {
      formData.append(key, String(value))
    })
    const response = await generalApiClient.post('/documents/direct-scan-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  // Resolve stale document
  resolveStale: async (documentId: number, data: { action: string; reason?: string }) => {
    const response = await generalApiClient.post(`/documents/${documentId}/stale/resolve`, data)
    return response.data
  },

  // Update status (Sign/Approve)
  updateStatus: async (documentId: number, status: string) => {
    const response = await generalApiClient.patch(`/documents/${documentId}`, { status })
    return response.data
  },

  // Forward document (Approve/Next Step)
  forward: async (documentId: number) => {
    const response = await generalApiClient.post(`/documents/${documentId}/forward`)
    return response.data
  },

  // Delete document
  delete: async (documentId: number) => {
    await generalApiClient.delete(`/documents/${documentId}`)
  },
}

// ==================== Attendance API ====================

export const attendanceApi = {
  // Get daily attendance
  getDaily: async (date: string, department?: string) => {
    const response = await generalApiClient.get(`/attendance/daily/${date}`, {
      params: department ? { department } : undefined,
    })
    return response.data
  },

  // Create attendance record
  create: async (staffId: number, date: string, code: string, notes?: string) => {
    const response = await generalApiClient.post(`/attendance/${staffId}/${date}`, null, {
      params: { code, notes },
    })
    return response.data
  },

  // List attendance records
  list: async (params?: { staff_id?: number; month?: number; year?: number }) => {
    const response = await generalApiClient.get('/attendance/list', { params })
    return response.data
  },
}

// ==================== Staff API ====================

export const staffApi = {
  // List staff members
  list: async (params?: { department?: string; is_active?: boolean }) => {
    const response = await generalApiClient.get('/staff', { params })
    return response.data
  },

  // Get single staff member
  get: async (id: number) => {
    const response = await generalApiClient.get(`/staff/${id}`)
    return response.data
  },
}

// Legacy exports for backward compatibility
export const apiClient = telegramApiClient
export default telegramApiClient

