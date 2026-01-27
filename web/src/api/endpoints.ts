export const endpoints = {
  // Auth
  auth: {
    login: '/auth/login',
    logout: '/auth/logout',
    refresh: '/auth/refresh',
    me: '/auth/me',
  },

  // Dashboard
  dashboard: {
    stats: '/dashboard/stats',
    today: '/dashboard/today',
    contractExpiring: '/dashboard/contract-expiring',
  },

  // Staff
  staff: {
    list: '/staff',
    search: '/staff/search',
    detail: (id: string | number) => `/staff/${id}`,
    documents: (id: string | number) => `/staff/${id}/documents`,
    schedule: (id: string | number) => `/staff/${id}/schedule`,
    attendance: (id: string | number) => `/staff/${id}/attendance`,
    history: (id: string | number) => `/staff/${id}/history`,
    create: '/staff',
    update: (id: string | number) => `/staff/${id}`,
    delete: (id: string | number) => `/staff/${id}`,
  },

  // Documents
  documents: {
    list: '/documents',
    stale: '/documents/stale',
    detail: (id: string | number) => `/documents/${id}`,
    types: '/documents/types',
    validate: '/documents/validate',
    create: '/documents',
    update: (id: string | number) => `/documents/${id}`,
    delete: (id: string | number) => `/documents/${id}`,
    workflow: (id: string | number, action: string) => `/documents/${id}/${action}`,
    uploadScan: (id: string | number) => `/documents/${id}/upload`,
    download: (id: string | number) => `/documents/${id}/download`,
    preview: '/documents/preview',
    blockedDays: (staffId: string | number) => `/documents/staff/${staffId}/blocked-days`,
    resolveStale: (id: string | number) => `/documents/${id}/stale/resolve`,
  },

  // Schedule
  schedule: {
    annual: '/schedule/annual',
    detail: (id: string | number) => `/schedule/${id}`,
    stats: '/schedule/stats',
    autoDistribute: '/schedule/auto-distribute',
    create: '/schedule',
    update: (id: string | number) => `/schedule/${id}`,
    delete: (id: string | number) => `/schedule/${id}`,
  },

  // Attendance
  attendance: {
    list: '/attendance/list',
    daily: '/attendance/daily',
    create: '/attendance',
    update: (id: string | number) => `/attendance/${id}`,
    delete: (id: string | number) => `/attendance/${id}`,
    correction: '/attendance/correction',
    submit: '/attendance/submit',
    tabel: '/attendance/tabel',
    tabelApprove: '/attendance/tabel/approve',
  },

  // Settings
  settings: {
    current: '/settings',
    update: '/settings',
  },

  // Tabel
  tabel: {
    generate: '/tabel/generate',
    preview: '/tabel/preview',
    archive: '/tabel/archive',
    archives: '/tabel/archives',
    archiveDetail: (filename: string) => `/tabel/archives/${filename}`,
    lockedMonths: '/tabel/locked-months',
    corrections: '/tabel/corrections',
    approve: '/tabel/approve',
    status: '/tabel/status',
  },

  // Telegram
  telegram: {
    info: '/telegram/info',
    requests: '/telegram/link-requests',
    approve: (id: string | number) => `/telegram/link-requests/${id}/approve`,
    reject: (id: string | number) => `/telegram/link-requests/${id}/reject`,
    unlink: (id: string | number) => `/telegram/link-requests/${id}/unlink`,
  },
};
