import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Select,
  DatePicker,
  Button,
  Typography,
  Table,
  Tag,
  Space,
  Modal,
  Form,
  Input,
  Statistic,
  message,
} from 'antd';
import dayjs from 'dayjs';
import {
  LeftOutlined,
  RightOutlined,
  PlusOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { DailyAttendance } from '../../api/types';
import { getAttendanceCodeLabel } from '../../api/constants';

const { Title, Text } = Typography;
const { Option } = Select;

// API Response type
interface DailyAttendanceResponse {
  items: DailyAttendance[];
  total: number;
  date: string;
  present: number;
  absent: number;
  late: number;
  remote: number;
}

// Extended attendance record with staff info
interface AttendanceRecord extends DailyAttendance {
  staff?: {
    pib_nom: string;
    position: string;
    rate: number;
  };
}

const AttendanceView: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isCorrectionModalOpen, setIsCorrectionModalOpen] = useState(false);
  const [selectedAttendance, setSelectedAttendance] = useState<DailyAttendance | null>(null);
  const [form] = Form.useForm();
  const [correctionForm] = Form.useForm();

  // Fetch staff list for dropdown
  const { data: staffList } = useQuery({
    queryKey: ['staff-list'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.list, { params: { limit: 1000 } });
      return response.data.items;
    },
  });

  const { data: response, isLoading } = useQuery<DailyAttendanceResponse>({
    queryKey: ['attendance-daily', selectedDate.format('YYYY-MM-DD')],
    queryFn: async () => {
      const res = await apiClient.get(endpoints.attendance.daily, {
        params: { date: selectedDate.format('YYYY-MM-DD') },
      });
      return res.data;
    },
  });

  const attendanceData = response?.items || [];
  const stats = response ? {
    present: response.present,
    absent: response.absent,
    late: response.late,
    remote: response.remote,
  } : null;

  const createMutation = useMutation({
    mutationFn: async (data: { staff_id: number; date: string; code: string; notes?: string }) => {
      await apiClient.post(endpoints.attendance.daily, data);
    },
    onSuccess: () => {
      message.success('Attendance record added');
      queryClient.invalidateQueries({ queryKey: ['attendance-daily'] });
      setIsAddModalOpen(false);
      form.resetFields();
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to add attendance');
    },
  });

  const correctionMutation = useMutation({
    mutationFn: async (data: {
      staff_id: number;
      attendance_id: number;
      correction_type: string;
      original_value: string;
      new_code: string;
      reason: string;
    }) => {
      await apiClient.post(endpoints.attendance.correction, data);
    },
    onSuccess: () => {
      message.success('Correction submitted');
      queryClient.invalidateQueries({ queryKey: ['attendance-daily'] });
      setIsCorrectionModalOpen(false);
      correctionForm.resetFields();
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to submit correction');
    },
  });

  const handlePrevDay = () => setSelectedDate(selectedDate.subtract(1, 'day'));
  const handleNextDay = () => setSelectedDate(selectedDate.add(1, 'day'));

  const handleAddRecord = async () => {
    const values = await form.validateFields();
    createMutation.mutate({
      ...values,
      date: selectedDate.format('YYYY-MM-DD'),
    });
  };

  const handleCorrection = async () => {
    const values = await correctionForm.validateFields();
    if (selectedAttendance) {
      correctionMutation.mutate({
        ...values,
        staff_id: selectedAttendance.staff_id,
        attendance_id: selectedAttendance.id,
        correction_type: 'status',
        original_value: selectedAttendance.code,
        new_code: values.code,
      });
    }
  };

  const columns = [
    {
      title: 'Staff',
      key: 'staff',
      render: (_, record: AttendanceRecord) => (
        <Space>
          <Text strong>{record.staff?.pib_nom}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.staff?.position} ({record.staff?.rate} ст.)
          </Text>
        </Space>
      ),
    },
    {
      title: 'Code',
      dataIndex: 'code',
      key: 'code',
      render: (code: string) => {
        const label = getAttendanceCodeLabel(code);
        return <Tag>{code} - {label}</Tag>;
      },
    },
    {
      title: 'Hours',
      dataIndex: 'hours',
      key: 'hours',
      render: (hours: number) => hours?.toFixed(1) || '0.0',
    },
    {
      title: 'Notes',
      dataIndex: 'notes',
      key: 'notes',
      render: (notes: string | null) => notes || '-',
    },
    {
      title: 'Correction',
      dataIndex: 'is_correction',
      key: 'is_correction',
      render: (isCorrection: boolean) => isCorrection ? <Tag color="orange">Correction</Tag> : '-',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record: AttendanceRecord) => (
        <Button
          size="small"
          onClick={() => {
            setSelectedAttendance(record);
            correctionForm.setFieldsValue({ code: record.code });
            setIsCorrectionModalOpen(true);
          }}
          disabled={record.is_correction}
        >
          {record.is_correction ? 'Locked' : 'Correct'}
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>Attendance</Title>
        <Space>
          <Button icon={<LeftOutlined />} onClick={handlePrevDay}>Previous</Button>
          <DatePicker
            value={selectedDate}
            onChange={(date) => date && setSelectedDate(date)}
            allowClear={false}
          />
          <Button onClick={handleNextDay}>Next<RightOutlined /></Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsAddModalOpen(true)}>
            Add Record
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Present"
              value={stats?.present || 0}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Absent"
              value={stats?.absent || 0}
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Late"
              value={stats?.late || 0}
              valueStyle={{ color: '#faad14' }}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Total Records"
              value={attendanceData.length}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Table
          columns={columns}
          dataSource={attendanceData}
          loading={isLoading}
          rowKey="id"
          pagination={false}
        />
      </Card>

      {/* Add Record Modal */}
      <Modal
        title="Add Attendance Record"
        open={isAddModalOpen}
        onCancel={() => setIsAddModalOpen(false)}
        onOk={handleAddRecord}
        confirmLoading={createMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="staff_id"
            label="Staff"
            rules={[{ required: true, message: 'Please select staff' }]}
          >
            <Select
              placeholder="Select staff"
              showSearch
              optionFilterProp="children"
            >
              {staffList?.map((staff: any) => (
                <Option key={staff.id} value={staff.id}>
                  {staff.pib_nom} - {staff.position} ({staff.rate} ст.)
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="code"
            label="Code"
            rules={[{ required: true, message: 'Please select code' }]}
          >
            <Select placeholder="Select code">
              <Option value="Р">Р - Відпрацьовано</Option>
              <Option value="В">В - Відпустка</Option>
              <Option value="ТН">ТН - Лікарняний</Option>
              <Option value="ВД">ВД - Відрядження</Option>
              <Option value="Н">Н - Навчальна</Option>
              <Option value="ДО">ДО - Догляд за дитиною</Option>
              <Option value="П">П - Простої</Option>
              <Option value="ПР">ПР - Прогули</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="notes"
            label="Notes"
          >
            <Input.TextArea rows={2} placeholder="Additional notes" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Correction Modal */}
      <Modal
        title="Attendance Correction"
        open={isCorrectionModalOpen}
        onCancel={() => setIsCorrectionModalOpen(false)}
        onOk={handleCorrection}
        confirmLoading={correctionMutation.isPending}
      >
        <Form form={correctionForm} layout="vertical">
          <Form.Item
            name="code"
            label="New Code"
            rules={[{ required: true, message: 'Please select code' }]}
          >
            <Select placeholder="Select code">
              <Option value="Р">Р - Відпрацьовано</Option>
              <Option value="В">В - Відпустка</Option>
              <Option value="ТН">ТН - Лікарняний</Option>
              <Option value="ВД">ВД - Відрядження</Option>
              <Option value="Н">Н - Навчальна</Option>
              <Option value="ДО">ДО - Догляд за дитиною</Option>
              <Option value="П">П - Простої</Option>
              <Option value="ПР">ПР - Прогули</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="reason"
            label="Reason"
            rules={[{ required: true, message: 'Please enter reason' }]}
          >
            <Input.TextArea rows={3} placeholder="Enter reason for correction" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AttendanceView;
