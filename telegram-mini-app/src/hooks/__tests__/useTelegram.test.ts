/**
 * Tests for useTelegram hook
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTelegram } from '../useTelegram'

// Mock window.Telegram.WebApp
const mockWebApp = {
  initData: 'test_init_data',
  initDataUnsafe: {
    user: {
      id: 123456,
      first_name: 'Test',
      last_name: 'User',
      username: 'testuser'
    }
  },
  colorScheme: 'light' as const,
  themeParams: {
    bg_color: '#ffffff',
    text_color: '#000000',
    hint_color: '#999999',
    link_color: '#2481cc',
    button_color: '#2481cc',
    button_text_color: '#ffffff',
    secondary_bg_color: '#f1f1f1'
  },
  version: '6.9',
  platform: 'ios',
  isExpanded: true,
  viewportHeight: 600,
  viewportStableHeight: 600,
  expand: vi.fn(),
  ready: vi.fn(),
  close: vi.fn(),
  showPopup: vi.fn(),
  showAlert: vi.fn(),
  showConfirm: vi.fn(),
  HapticFeedback: {
    impactOccurred: vi.fn(),
    notificationOccurred: vi.fn(),
    selectionChanged: vi.fn()
  },
  BackButton: {
    show: vi.fn(),
    hide: vi.fn(),
    onClick: vi.fn()
  },
  MainButton: {
    text: '',
    color: '',
    textColor: '',
    isVisible: false,
    isActive: true,
    isProgressVisible: false,
    setText: vi.fn(),
    setColor: vi.fn(),
    setTextColor: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
    enable: vi.fn(),
    disable: vi.fn(),
    showProgress: vi.fn(),
    hideProgress: vi.fn(),
    onClick: vi.fn()
  }
}

describe('useTelegram', () => {
  beforeEach(() => {
    // Setup mock
    ;(global as any).window = {
      Telegram: {
        WebApp: mockWebApp
      }
    }
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with Telegram WebApp data', () => {
    const { result } = renderHook(() => useTelegram())

    expect(result.current.isReady).toBe(true)
    expect(result.current.user).toEqual(mockWebApp.initDataUnsafe.user)
    expect(result.current.colorScheme).toBe('light')
    expect(result.current.version).toBe('6.9')
    expect(result.current.platform).toBe('ios')
  })

  it('calls WebApp.ready and expand on mount', () => {
    renderHook(() => useTelegram())

    expect(mockWebApp.ready).toHaveBeenCalledOnce()
    expect(mockWebApp.expand).toHaveBeenCalledOnce()
  })

  it('sets CSS variables for theme colors', () => {
    const mockStyleGetProperty = vi.fn()
    const documentGetElement = vi.fn(() => ({
      style: {
        setProperty: mockStyleGetProperty
      }
    }))

    ;(global as any).document = {
      documentElement: {
        style: {
          setProperty: mockStyleGetProperty
        }
      }
    }

    renderHook(() => useTelegram())

    expect(mockStyleGetProperty).toHaveBeenCalledWith('--tg-bg-color', '#ffffff')
    expect(mockStyleGetProperty).toHaveBeenCalledWith('--tg-text-color', '#000000')
    expect(mockStyleGetProperty).toHaveBeenCalledWith('--tg-button-color', '#2481cc')
  })

  it('showPopup calls WebApp.showPopup', () => {
    const { result } = renderHook(() => useTelegram())

    act(() => {
      result.current.showPopup('Test message', 'Test title')
    })

    expect(mockWebApp.showPopup).toHaveBeenCalledWith({
      title: 'Test title',
      message: 'Test message',
      buttons: [{ text: 'OK' }]
    })
  })

  it('showAlert calls WebApp.showAlert', () => {
    const { result } = renderHook(() => useTelegram())

    act(() => {
      result.current.showAlert('Alert message')
    })

    expect(mockWebApp.showAlert).toHaveBeenCalledWith('Alert message')
  })

  it('showConfirm calls WebApp.showConfirm', async () => {
    const { result } = renderHook(() => useTelegram())

    // Note: showConfirm in real implementation returns a Promise
    // This is a simplified test
    act(() => {
      result.current.showConfirm('Confirm message')
    })

    expect(mockWebApp.showConfirm).toHaveBeenCalledWith('Confirm message')
  })

  it('HapticFeedback methods work correctly', () => {
    const { result } = renderHook(() => useTelegram())

    act(() => {
      result.current.HapticFeedback.impactOccurred('medium')
      result.current.HapticFeedback.notificationOccurred('success')
      result.current.HapticFeedback.selectionChanged()
    })

    expect(mockWebApp.HapticFeedback.impactOccurred).toHaveBeenCalledWith('medium')
    expect(mockWebApp.HapticFeedback.notificationOccurred).toHaveBeenCalledWith('success')
    expect(mockWebApp.HapticFeedback.selectionChanged).toHaveBeenCalled()
  })

  it('BackButton methods work correctly', () => {
    const { result } = renderHook(() => useTelegram())

    act(() => {
      result.current.BackButton.show()
      result.current.BackButton.hide()
      result.current.BackButton.onClick(vi.fn())
    })

    expect(mockWebApp.BackButton.show).toHaveBeenCalled()
    expect(mockWebApp.BackButton.hide).toHaveBeenCalled()
    expect(mockWebApp.BackButton.onClick).toHaveBeenCalled()
  })

  it('MainButton methods work correctly', () => {
    const { result } = renderHook(() => useTelegram())

    act(() => {
      result.current.MainButton.setText('Test')
      result.current.MainButton.setColor('#000')
      result.current.MainButton.show()
      result.current.MainButton.enable()
    })

    expect(mockWebApp.MainButton.setText).toHaveBeenCalledWith('Test')
    expect(mockWebApp.MainButton.setColor).toHaveBeenCalledWith('#000')
    expect(mockWebApp.MainButton.show).toHaveBeenCalled()
    expect(mockWebApp.MainButton.enable).toHaveBeenCalled()
  })

  it('close calls WebApp.close', () => {
    const { result } = renderHook(() => useTelegram())

    act(() => {
      result.current.close()
    })

    expect(mockWebApp.close).toHaveBeenCalled()
  })

  it('handles missing Telegram WebApp gracefully', () => {
    // Remove Telegram from window
    delete (window as any).Telegram

    const { result } = renderHook(() => useTelegram())

    expect(result.current.isReady).toBe(false)
    expect(result.current.user).toBeNull()
    expect(result.current.webApp).toBeNull()
  })

  it('fallback to alert when WebApp not available for showPopup', () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {})
    delete (window as any).Telegram

    const { result } = renderHook(() => useTelegram())

    act(() => {
      result.current.showPopup('Test message')
    })

    expect(alertSpy).toHaveBeenCalledWith('Test message')
    alertSpy.mockRestore()
  })
})
