import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Select,
  Button,
  Typography,
  Table,
  Tag,
  Space,
  Modal,
  Form,
  Input,
  message,
  DatePicker,
  Popconfirm,
  Tooltip,
} from 'antd';
import dayjs from 'dayjs';
import {
  PlusOutlined,
  FilterOutlined,
  EditOutlined,
  DeleteOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { DailyAttendance, AttendanceListResponse } from '../../api/types';
import { getAttendanceCodeLabel } from '../../api/constants';

const { Title, Text } = Typography;
const { Option } = Select;

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
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isCorrectionModalOpen, setIsCorrectionModalOpen] = useState(false);
  const [selectedAttendance, setSelectedAttendance] = useState<DailyAttendance | null>(null);
  const [form] = Form.useForm();
  const [correctionForm] = Form.useForm();
  const [filters, setFilters] = useState<{
    staff_id?: number;
    year?: number;
    month?: number;
    is_correction?: boolean;
  }>({});

  // Fetch staff list for dropdown
  const { data: staffList } = useQuery({
    queryKey: ['staff-list'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.list, { params: { limit: 1000 } });
      return response.data.items;
    },
  });

  // Fetch all attendance records with pagination
  const { data: response, isLoading } = useQuery<AttendanceListResponse>({
    queryKey: ['attendance-list', currentPage, pageSize, filters],
    queryFn: async () => {
      const params: any = {
        skip: (currentPage - 1) * pageSize,
        limit: pageSize,
      };
      if (filters.staff_id) params.staff_id = filters.staff_id;
      if (filters.year) params.year = filters.year;
      if (filters.month) params.month = filters.month;
      if (filters.is_correction !== undefined) params.is_correction = filters.is_correction;

      const res = await apiClient.get(endpoints.attendance.list, { params });
      return res.data;
    },
  });

  const attendanceData = response?.items || [];
  const totalRecords = response?.total || 0;

  const createMutation = useMutation({
    mutationFn: async (data: { staff_id: number; date: string; code: string; notes?: string }) => {
      await apiClient.post(endpoints.attendance.create, data);
    },
    onSuccess: () => {
      message.success('Attendance record added');
      queryClient.invalidateQueries({ queryKey: ['attendance-list'] });
      setIsAddModalOpen(false);
      form.resetFields();
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to add attendance');
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, code, notes }: { id: number; code: string; notes?: string }) => {
      await apiClient.put(endpoints.attendance.update(id), { code, notes });
    },
    onSuccess: () => {
      message.success('Attendance record updated');
      queryClient.invalidateQueries({ queryKey: ['attendance-list'] });
      setIsCorrectionModalOpen(false);
      setSelectedAttendance(null);
      correctionForm.resetFields();
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to update attendance');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(endpoints.attendance.delete(id));
    },
    onSuccess: () => {
      message.success('Attendance record deleted');
      queryClient.invalidateQueries({ queryKey: ['attendance-list'] });
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to delete attendance');
    },
  });

  const handleAddRecord = async () => {
    const values = await form.validateFields();
    const dateValue = values.date || dayjs();
    createMutation.mutate({
      ...values,
      date: dateValue.format('YYYY-MM-DD'),
    });
  };

  const handleCorrection = async () => {
    const values = await correctionForm.validateFields();
    if (selectedAttendance) {
      updateMutation.mutate({
        id: selectedAttendance.id,
        code: values.code,
        notes: values.reason,
      });
    }
  };

  const handleDelete = async (id: number) => {
    deleteMutation.mutate(id);
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 70,
    },
    {
      title: 'Staff',
      key: 'staff',
      render: (_: unknown, record: AttendanceRecord) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.staff?.pib_nom || 'Unknown'}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.staff?.position} ({record.staff?.rate} ст.)
          </Text>
        </Space>
      ),
    },
    {
      title: 'Date',
      dataIndex: 'date',
      key: 'date',
      render: (date: string) => dayjs(date).format('DD.MM.YYYY'),
    },
    {
      title: 'Code',
      dataIndex: 'code',
      key: 'code',
      render: (code: string) => {
        const label = getAttendanceCodeLabel(code);
        return <Tag color={code === 'Р' ? 'green' : 'blue'}>{code} - {label}</Tag>;
      },
    },
    {
      title: 'Hours',
      dataIndex: 'hours',
      key: 'hours',
      width: 80,
      render: (hours: number) => hours?.toFixed(1) || '0.0',
    },
    {
      title: 'Table Type',
      dataIndex: 'table_type',
      key: 'table_type',
      width: 120,
      render: (tableType: string, record: AttendanceRecord) => {
        if (tableType === 'correction') {
          return (
            <Space direction="vertical" size={0}>
              <Tag color="orange">Correction</Tag>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {record.table_info}
              </Text>
            </Space>
          );
        }
        return <Tag color="blue">Main</Tag>;
      },
    },
    {
      title: 'Notes',
      dataIndex: 'notes',
      key: 'notes',
      ellipsis: true,
      render: (notes: string | null) => notes || '-',
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 100,
      render: (date: string) => dayjs(date).format('DD.MM HH:mm'),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_: unknown, record: AttendanceRecord) => {
        const isBlocked = record.is_blocked;

        if (isBlocked) {
          return (
            <Tooltip title={record.blocked_reason || 'Місяць заблоковано (погоджено з кадрами)'}>
              <Button
                size="small"
                icon={<LockOutlined />}
                disabled
                style={{ cursor: 'not-allowed' }}
              >
                Locked
              </Button>
            </Tooltip>
          );
        }

        return (
          <Space size="small">
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                setSelectedAttendance(record);
                correctionForm.setFieldsValue({
                  code: record.code,
                  reason: record.notes || '',
                });
                setIsCorrectionModalOpen(true);
              }}
            >
              Edit
            </Button>
            <Popconfirm
              title="Видалити запис?"
              description="Ця дія незворотня"
              onConfirm={() => handleDelete(record.id)}
              okText="Так"
              cancelText="Ні"
            >
              <Button
                size="small"
                danger
                icon={<DeleteOutlined />}
              >
                Remove
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          Attendance Records ({totalRecords})
        </Title>
        <Space>
          <Button icon={<FilterOutlined />} onClick={() => setFilters({})}>
            Clear Filters
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsAddModalOpen(true)}>
            Add Record
          </Button>
        </Space>
      </div>

      {/* Filters */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder="Filter by Staff"
            allowClear
            style={{ width: 250 }}
            value={filters.staff_id}
            onChange={(value) => setFilters({ ...filters, staff_id: value || undefined })}
            showSearch
            optionFilterProp="children"
          >
            {staffList?.map((staff: any) => (
              <Option key={staff.id} value={staff.id}>
                {staff.pib_nom} - {staff.position}
              </Option>
            ))}
          </Select>

          <DatePicker.YearPicker
            placeholder="Filter by Year"
            value={filters.year ? dayjs().year(filters.year) : null}
            onChange={(date) => setFilters({ ...filters, year: date?.year() || undefined })}
          />

          <Select
            placeholder="Filter by Month"
            allowClear
            style={{ width: 150 }}
            value={filters.month}
            onChange={(value) => setFilters({ ...filters, month: value || undefined })}
          >
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((m) => (
              <Option key={m} value={m}>{dayjs().month(m - 1).format('MMMM')}</Option>
            ))}
          </Select>

          <Select
            placeholder="Filter by Table Type"
            allowClear
            style={{ width: 180 }}
            value={filters.is_correction}
            onChange={(value) => setFilters({ ...filters, is_correction: value })}
          >
            <Option value={false}>Main Table</Option>
            <Option value={true}>Correction Table</Option>
          </Select>
        </Space>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={attendanceData}
          loading={isLoading}
          rowKey="id"
          pagination={{
            current: currentPage,
            pageSize: pageSize,
            total: totalRecords,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} records`,
            onChange: (page, size) => {
              setCurrentPage(page);
              setPageSize(size || 50);
            },
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* Add Record Modal */}
      <Modal
        title="Add Attendance Record"
        open={isAddModalOpen}
        onCancel={() => setIsAddModalOpen(false)}
        onOk={handleAddRecord}
        confirmLoading={createMutation.isPending}
        width={500}
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
            name="date"
            label="Date"
            rules={[{ required: true, message: 'Please select date' }]}
            initialValue={dayjs()}
          >
            <DatePicker style={{ width: '100%' }} />
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

      {/* Edit Modal */}
      <Modal
        title="Edit Attendance Record"
        open={isCorrectionModalOpen}
        onCancel={() => setIsCorrectionModalOpen(false)}
        onOk={handleCorrection}
        confirmLoading={updateMutation.isPending}
        width={500}
      >
        <Form form={correctionForm} layout="vertical">
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
            name="reason"
            label="Notes"
          >
            <Input.TextArea rows={3} placeholder="Additional notes" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AttendanceView;
