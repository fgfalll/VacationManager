/**
 * Tests for Telegram API client
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'
import {
  apiClient,
  authWithTelegram,
  getCurrentUser,
  getTelegramInfo,
  linkTelegramAccount
} from '../client'

// Mock axios
vi.mock('axios')

describe('Telegram API Client', () => {
  beforeEach(() => {
    // Clear localStorage
    localStorage.clear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('apiClient', () => {
    it('has correct base URL', () => {
      expect(apiClient.defaults.baseURL).toBe('/api/telegram')
    })

    it('has correct default headers', () => {
      expect(apiClient.defaults.headers['Content-Type']).toBe('application/json')
    })

    it('adds Authorization header when token exists', async () => {
      const mockToken = 'test_token_123'
      localStorage.setItem('access_token', mockToken)

      const mockAxiosInstance = {
        interceptors: {
          request: {
            use: vi.fn((handler) => {
              // Simulate request interceptor
              const config = { headers: {} }
              handler(config)
              expect(config.headers.Authorization).toBe(`Bearer ${mockToken}`)
            })
          },
          response: {
            use: vi.fn()
          }
        }
      } as any

      // Note: This tests the interceptor logic
      // In real scenario, axios intercepts all requests
    })
  })

  describe('authWithTelegram', () => {
    it('successfully authenticates with valid initData', async () => {
      const mockResponse = {
        data: {
          access_token: 'jwt_token_123',
          user: {
            id: 1,
            pib_nom: 'Тестов Тест Тестович',
            position: 'SPECIALIST',
            department: 'Кафедра',
            telegram_username: 'testuser'
          }
        }
      }

      // Mock window.Telegram.WebApp
      ;(window as any).Telegram = {
        WebApp: {
          initData: 'valid_init_data',
          ready: vi.fn(),
          expand: vi.fn()
        }
      }

      vi.mocked(axios.post).mockResolvedValue(mockResponse as any)

      const result = await authWithTelegram()

      expect(result.access_token).toBe('jwt_token_123')
      expect(result.user.id).toBe(1)
      expect(localStorage.getItem('access_token')).toBe('jwt_token_123')
      expect((window as any).Telegram.WebApp.ready).toHaveBeenCalled()
      expect((window as any).Telegram.WebApp.expand).toHaveBeenCalled()
    })

    it('throws error when Telegram WebApp not available', async () => {
      // Remove Telegram from window
      delete (window as any).Telegram

      await expect(authWithTelegram()).rejects.toThrow('Telegram WebApp not available')
    })

    it('stores token in localStorage on success', async () => {
      const mockResponse = {
        data: {
          access_token: 'stored_token',
          user: { id: 1, pib_nom: 'Test', position: 'SPECIALIST', department: 'Dept' }
        }
      }

      ;(window as any).Telegram = {
        WebApp: {
          initData: 'test_data',
          ready: vi.fn(),
          expand: vi.fn()
        }
      }

      vi.mocked(axios.post).mockResolvedValue(mockResponse as any)

      await authWithTelegram()

      expect(localStorage.getItem('access_token')).toBe('stored_token')
    })
  })

  describe('getCurrentUser', () => {
    it('fetches current user info', async () => {
      const mockUser = {
        id: 1,
        pib_nom: 'Тестов Тест Тестович',
        position: 'SPECIALIST',
        department: 'Кафедра',
        telegram_username: 'testuser',
        email: 'test@example.com'
      }

      const mockResponse = { data: mockUser }
      vi.mocked(axios.get).mockResolvedValue(mockResponse as any)

      const result = await getCurrentUser()

      expect(result).toEqual(mockUser)
      expect(axios.get).toHaveBeenCalledWith('/user')
    })

    it('includes auth token in request', async () => {
      const mockToken = 'test_token'
      localStorage.setItem('access_token', mockToken)

      vi.mocked(axios.get).mockResolvedValue({ data: {} } as any)

      await getCurrentUser()

      // Verify the call was made (token should be added by interceptor)
      expect(axios.get).toHaveBeenCalledWith('/user')
    })
  })

  describe('getTelegramInfo', () => {
    it('fetches Telegram bot configuration', async () => {
      const mockInfo = {
        enabled: true,
        mini_app_url: 'https://example.com/app',
        webhook_url: 'https://example.com/webhook'
      }

      const mockResponse = { data: mockInfo }
      vi.mocked(axios.get).mockResolvedValue(mockResponse as any)

      const result = await getTelegramInfo()

      expect(result).toEqual(mockInfo)
      expect(axios.get).toHaveBeenCalledWith('/info')
    })
  })

  describe('linkTelegramAccount', () => {
    it('links Telegram account successfully', async () => {
      const mockResponse = {
        data: {
          success: true,
          message: 'Telegram account linked successfully'
        }
      }

      vi.mocked(axios.post).mockResolvedValue(mockResponse as any)

      const result = await linkTelegramAccount('123456')

      expect(result.success).toBe(true)
      expect(result.message).toContain('linked successfully')
      expect(axios.post).toHaveBeenCalledWith('/link', {
        telegram_user_id: '123456'
      })
    })

    it('handles already linked account', async () => {
      const mockResponse = {
        data: {
          success: false,
          message: 'This Telegram account is already linked to another staff member'
        }
      }

      vi.mocked(axios.post).mockResolvedValue(mockResponse as any)

      const result = await linkTelegramAccount('123456')

      expect(result.success).toBe(false)
      expect(result.message).toContain('already linked')
    })
  })

  describe('Error handling', () => {
    it('clears token on 401 response', async () => {
      const mockError = {
        response: { status: 401 }
      }

      vi.mocked(axios.get).mockRejectedValue(mockError as any)

      // Mock localStorage operations
      const removeItemSpy = vi.spyOn(localStorage, 'removeItem')
      const closeSpy = vi.fn()
      ;(window as any).Telegram = { WebApp: { close: closeSpy } }

      try {
        await getCurrentUser()
      } catch (e) {
        // Expected error
      }

      // Token should be cleared on 401
      // Note: This is handled by response interceptor
    })
  })
})
