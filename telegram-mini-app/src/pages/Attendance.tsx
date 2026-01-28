import { useState, useCallback } from 'react'
import { Tabs, Toast, PullToRefresh } from 'antd-mobile'
import { TelegramUser, Attendance as AttendanceType } from '../api/types'
import { attendanceApi } from '../api/client'
import { useTelegram } from '../hooks/useTelegram'
import AttendanceForm from '../components/AttendanceForm'

interface AttendanceProps {
  user: TelegramUser
}

const Attendance: React.FC<AttendanceProps> = ({ user: _user }) => {
  const { HapticFeedback } = useTelegram()
  const [formKey, setFormKey] = useState(0)
  const [recentAttendance, setRecentAttendance] = useState<AttendanceType[]>([])
  const [submitting, setSubmitting] = useState(false)

  const handleAttendanceSubmit = useCallback(async (attendance: {
    staff_id: number
    date: string
    code: string
    notes?: string
  }) => {
    if (submitting) return

    setSubmitting(true)
    try {
      HapticFeedback.impactOccurred('medium')

      await attendanceApi.create(
        attendance.staff_id,
        attendance.date,
        attendance.code,
        attendance.notes
      )

      HapticFeedback.notificationOccurred('success')
      Toast.show({
        content: 'Відвідування додано',
        icon: 'success',
      })

      // Add to recent list (local state only)
      setRecentAttendance(prev => [{
        id: Date.now(), // temporary ID for display
        ...attendance,
      } as AttendanceType, ...prev].slice(0, 5))

      // Reset form
      setFormKey(prev => prev + 1)
    } catch (error: any) {
      HapticFeedback.notificationOccurred('error')
      let errorMessage = 'Не вдалося додати відвідування'
      if (error.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail
        } else if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail.map((e: any) => `${e.loc.join('.')}: ${e.msg}`).join('\n')
        } else if (typeof error.response.data.detail === 'object') {
          errorMessage = JSON.stringify(error.response.data.detail)
        }
      }
      Toast.show({
        content: errorMessage,
        icon: 'fail',
      })
    } finally {
      setSubmitting(false)
    }
  }, [submitting, HapticFeedback])

  const handleRefresh = async () => {
    HapticFeedback.impactOccurred('light')
    // Could fetch recent attendance from API here if needed
    setFormKey(prev => prev + 1)
  }

  return (
    <PullToRefresh onRefresh={handleRefresh}>
      <Tabs defaultActiveKey="add">
        <Tabs.Tab title="Додати" key="add">
          <AttendanceForm
            key={formKey}
            onSubmit={handleAttendanceSubmit}
            loading={submitting}
          />
        </Tabs.Tab>
        <Tabs.Tab title="Історія" key="history">
          <div style={{ padding: '16px' }}>
            {recentAttendance.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '40px 16px',
                color: '#999',
              }}>
                Ще не додано жодного відвідування
              </div>
            ) : (
              recentAttendance.map((attendance, index) => (
                <div
                  key={attendance.id || index}
                  style={{
                    backgroundColor: '#fff',
                    borderRadius: '8px',
                    padding: '12px',
                    marginBottom: '8px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                  }}
                >
                  <div style={{ fontWeight: 600 }}>
                    Код: {attendance.code}
                  </div>
                  <div style={{ fontSize: '12px', color: '#666' }}>
                    Дата: {attendance.date}
                  </div>
                  {attendance.hours && (
                    <div style={{ fontSize: '12px', color: '#666' }}>
                      Годин: {attendance.hours}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </Tabs.Tab>
      </Tabs>
    </PullToRefresh>
  )
}

export default Attendance

