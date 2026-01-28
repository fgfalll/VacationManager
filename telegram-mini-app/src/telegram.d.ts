export { };

declare global {
    interface Window {
        Telegram?: {
            WebApp: {
                initData: string
                initDataUnsafe: {
                    user?: {
                        id: number
                        first_name: string
                        last_name?: string
                        username?: string
                        language_code?: string
                        photo_url?: string
                    }
                    [key: string]: any
                }
                version: string
                platform: string
                colorScheme: 'light' | 'dark'
                themeParams: {
                    bg_color?: string
                    text_color?: string
                    hint_color?: string
                    link_color?: string
                    button_color?: string
                    button_text_color?: string
                    secondary_bg_color?: string
                    [key: string]: string | undefined
                }
                isExpanded: boolean
                viewportHeight: number
                viewportStableHeight: number
                headerColor: string
                backgroundColor: string

                // Methods
                expand: () => void
                close: () => void
                ready: () => void

                // UI Methods
                showPopup: (params: {
                    title?: string
                    message: string
                    buttons?: Array<{ id?: string; type?: string; text: string }>
                }, callback?: (id?: string) => void) => void
                showAlert: (message: string, callback?: () => void) => void
                showConfirm: (message: string, callback?: (confirmed: boolean) => void) => void

                // Haptic Feedback
                HapticFeedback: {
                    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
                    notificationOccurred: (type: 'error' | 'success' | 'warning') => void
                    selectionChanged: () => void
                }

                // Buttons
                BackButton: {
                    isVisible: boolean
                    show: () => void
                    hide: () => void
                    onClick: (callback: () => void) => void
                    offClick: (callback: () => void) => void
                }
                MainButton: {
                    text: string
                    color: string
                    textColor: string
                    isVisible: boolean
                    isActive: boolean
                    isProgressVisible: boolean
                    setText: (text: string) => void
                    setColor: (color: string) => void
                    setTextColor: (color: string) => void
                    show: () => void
                    hide: () => void
                    enable: () => void
                    disable: () => void
                    showProgress: (leaveActive: boolean) => void
                    hideProgress: () => void
                    onClick: (callback: () => void) => void
                    offClick: (callback: () => void) => void
                }

                // Utilities
                openLink: (url: string, options?: { try_instant_view?: boolean }) => void
                openTelegramLink: (url: string) => void
                openInvoice: (url: string, callback?: (status: string) => void) => void

                // Event handling
                onEvent: (eventType: string, eventHandler: () => void) => void
                offEvent: (eventType: string, eventHandler: () => void) => void
                sendData: (data: any) => void
            }
        }
    }
}
