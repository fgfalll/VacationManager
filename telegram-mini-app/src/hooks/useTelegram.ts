import { useState, useEffect } from 'react'

// Telegram WebApp types are defined in telegram.d.ts

export interface TelegramUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
}

export const useTelegram = () => {
  // Extract WebApp type safely
  type WebAppType = NonNullable<Window['Telegram']>['WebApp']
  const [webApp, setWebApp] = useState<WebAppType | null>(null)
  const [user, setUser] = useState<TelegramUser | null>(null)
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp
      setWebApp(tg)
      setUser(tg.initDataUnsafe.user || null)
      setIsReady(true)

      // Initialize WebApp
      tg.ready()
      tg.expand()

      // Set theme colors
      document.documentElement.style.setProperty('--tg-bg-color', tg.themeParams.bg_color || '#ffffff')
      document.documentElement.style.setProperty('--tg-text-color', tg.themeParams.text_color || '#000000')
      document.documentElement.style.setProperty('--tg-hint-color', tg.themeParams.hint_color || '#999999')
      document.documentElement.style.setProperty('--tg-link-color', tg.themeParams.link_color || '#2481cc')
      document.documentElement.style.setProperty('--tg-button-color', tg.themeParams.button_color || '#2481cc')
      document.documentElement.style.setProperty('--tg-button-text-color', tg.themeParams.button_text_color || '#ffffff')
      document.documentElement.style.setProperty('--tg-secondary-bg-color', tg.themeParams.secondary_bg_color || '#f1f1f1')
    }
  }, [])

  const showPopup = (message: string, title?: string) => {
    if (webApp) {
      webApp.showPopup({
        title,
        message,
        buttons: [{ text: 'OK' }],
      })
    } else {
      alert(message)
    }
  }

  const showAlert = (message: string) => {
    if (webApp) {
      webApp.showAlert(message)
    } else {
      alert(message)
    }
  }

  const showConfirm = (message: string): Promise<boolean> => {
    return new Promise((resolve) => {
      if (webApp) {
        webApp.showConfirm(message)
        // Note: showConfirm in Telegram WebApp doesn't return a Promise
        // We need to handle this differently in real implementation
        resolve(true)
      } else {
        resolve(confirm(message))
      }
    })
  }

  const hapticFeedback = {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft' = 'medium') => {
      webApp?.HapticFeedback?.impactOccurred(style)
    },
    notificationOccurred: (type: 'error' | 'success' | 'warning') => {
      webApp?.HapticFeedback?.notificationOccurred(type)
    },
    selectionChanged: () => {
      webApp?.HapticFeedback?.selectionChanged()
    },
  }

  // Helper to check Telegram SDK version compatibility
  const isVersionAtLeast = (minVersion: string): boolean => {
    if (!webApp?.version) return false
    const [major, minor = 0] = webApp.version.split('.').map(Number)
    const [reqMajor, reqMinor = 0] = minVersion.split('.').map(Number)
    return major > reqMajor || (major === reqMajor && minor >= reqMinor)
  }

  const backButton = {
    show: () => {
      if (isVersionAtLeast('6.1')) webApp?.BackButton?.show()
    },
    hide: () => {
      if (isVersionAtLeast('6.1')) webApp?.BackButton?.hide()
    },
    onClick: (callback: () => void) => {
      if (isVersionAtLeast('6.1')) webApp?.BackButton?.onClick(callback)
    },
    isSupported: () => isVersionAtLeast('6.1'),
  }

  const mainButton = {
    setText: (text: string) => webApp?.MainButton?.setText(text),
    setColor: (color: string) => webApp?.MainButton?.setColor(color),
    setTextColor: (color: string) => webApp?.MainButton?.setTextColor(color),
    show: () => webApp?.MainButton?.show(),
    hide: () => webApp?.MainButton?.hide(),
    enable: () => webApp?.MainButton?.enable(),
    disable: () => webApp?.MainButton?.disable(),
    showProgress: (leaveActive = false) => webApp?.MainButton?.showProgress(leaveActive),
    hideProgress: () => webApp?.MainButton?.hideProgress(),
    onClick: (callback: () => void) => webApp?.MainButton?.onClick(callback),
  }

  const close = () => {
    webApp?.close()
  }

  return {
    webApp,
    user,
    isReady,
    colorScheme: webApp?.colorScheme || 'light',
    version: webApp?.version || '',
    platform: webApp?.platform || '',
    showPopup,
    showAlert,
    showConfirm,
    HapticFeedback: hapticFeedback,
    BackButton: backButton,
    MainButton: mainButton,
    close,
  }
}

export default useTelegram
