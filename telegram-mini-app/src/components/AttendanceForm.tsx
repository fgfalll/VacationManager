import { useState, useEffect } from 'react'
import { Form, Input, DatePicker, Selector, Button, Toast, SpinLoading } from 'antd-mobile'
import { PlusOutlined } from '@ant-design/icons'
import { Staff, AttendanceCode } from '../api/types'
import { staffApi, attendanceApi } from '../api/client'

interface AttendanceFormProps {
  onSubmit?: (attendance: Omit<Attendance, 'id'>) => void
  onCancel?: () => void
}

// Коди відвідувань згідно з наказом Мінпраці №55
const ATTENDANCE_CODES: AttendanceCode[] = [
  { code: 'Р', name: 'Робочий день', description: 'Робочий день' },
  { code: 'В', name: 'Вихідний', description: 'Вихідний день' },
  { code: 'ВД', name: 'Вихідний за графіком', description: 'Вихідний за графіком' },
  { code: 'ТН', name: 'Тимчасова непрацездатність', description: 'Лікарняний' },
  { code: 'ВР', name: 'Відпустка річна', description: 'Щорічна відпустка' },
  { code: 'ВДУ', name: 'Відпустка додаткова', description: 'Додаткова відпустка' },
  { code: 'ВН', name: 'Відпустка неоплачувана', description: 'Відпустка без збереження зарплати' },
  { code: 'ВК', name: 'Відпустка у зв\'язку з вагітністю', description: 'Декретна відпустка' },
  { code: 'ВП', name: 'Відпустка для догляду за дитиною', description: 'Відпустка по догляду за дитиною' },
  { code: 'У', name: 'Навчальна відпустка', description: 'Відпустка для навчання' },
  { code: 'ДВ', name: 'Додатковий вихідний', description: 'Додатковий вихідний день' },
  { code: 'К', name: 'Відрядження', description: 'Відрядження' },
  { code: 'Х', name: 'Відгул', description: 'Відгул' },
  { code: 'П', name: 'Прогул', description: 'Прогул без поважної причини' },
  { code: 'Б', name: 'Неявка з поважної причини', description: 'Неявка з поважної причини' },
]

export const AttendanceForm: React.FC<AttendanceFormProps> = ({
  onSubmit,
  onCancel,
}) => {
  const [staffList, setStaffList] = useState<Staff[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchStaffList()
  }, [])

  const fetchStaffList = async () => {
    setLoading(true)
    try {
      const response = await staffApi.list()
      setStaffList(response.items || [])
    } catch (error) {
      Toast.show({
        content: 'Не вдалося завантажити список співробітників',
        icon: 'fail',
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)

    try {
      // Format date as YYYY-MM-DD
      const dateStr = values.date.format('YYYY-MM-DD')

      const attendance = {
        staff_id: values.staff_id,
        date: dateStr,
        code: values.code,
        hours: values.hours || undefined,
      }

      if (onSubmit) {
        onSubmit(attendance)
      } else {
        // Submit to API using attendanceApi
        await attendanceApi.create(
          attendance.staff_id,
          attendance.date,
          attendance.code,
          attendance.hours?.toString()
        )
        Toast.show({
          content: 'Відвідування додано',
          icon: 'success',
        })
        form.resetFields()
      }
    } catch (error) {
      Toast.show({
        content: 'Не вдалося додати відвідування',
        icon: 'fail',
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <SpinLoading color="primary" />
        <p style={{ marginTop: '16px', color: '#999' }}>Завантаження...</p>
      </div>
    )
  }

  return (
    <div style={{ padding: '16px' }}>
      <h3 style={{ marginBottom: '16px' }}>Додати відвідування</h3>

      <Form form={form} layout="vertical">
        <Form.Item
          name="staff_id"
          label="Співробітник"
          rules={[{ required: true, message: 'Оберіть співробітника' }]}
        >
          <Selector
            options={staffList.map((staff) => ({
              label: `${staff.pib_nom} - ${staff.position}`,
              value: staff.id,
            }))}
            placeholder="Оберіть співробітника"
          />
        </Form.Item>

        <Form.Item
          name="date"
          label="Дата"
          rules={[{ required: true, message: 'Оберіть дату' }]}
        >
          <DatePicker placeholder="Оберіть дату" />
        </Form.Item>

        <Form.Item
          name="code"
          label="Код відвідування"
          rules={[{ required: true, message: 'Оберіть код' }]}
        >
          <Selector
            options={ATTENDANCE_CODES.map((code) => ({
              label: `${code.code} - ${code.name}`,
              value: code.code,
              description: code.description,
            }))}
            placeholder="Оберіть код"
          />
        </Form.Item>

        <Form.Item
          name="hours"
          label="Кількість годин (опціонально)"
        >
          <Input
            type="number"
            placeholder="Введіть кількість годин"
            min={0}
            max={24}
            step={0.25}
          />
        </Form.Item>
      </Form>

      <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
        <Button
          block
          color="primary"
          size="large"
          onClick={handleSubmit}
          loading={submitting}
        >
          <PlusOutlined style={{ marginRight: '8px' }} />
          Додати
        </Button>
        {onCancel && (
          <Button
            size="large"
            onClick={onCancel}
          >
            Скасувати
          </Button>
        )}
      </div>
    </div>
  )
}

export default AttendanceForm
