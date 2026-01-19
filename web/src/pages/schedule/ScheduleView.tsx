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
  InputNumber,
  Statistic,
  message,
  Progress,
} from 'antd';
import {
  LeftOutlined,
  RightOutlined,
  ThunderboltOutlined,
  PlusOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { AnnualSchedule, ScheduleDay, AutoDistributeRequest } from '../../api/types';
import { format, addMonths, subMonths, startOfMonth, endOfMonth, eachDayOfInterval } from 'date-fns';

const { Title, Text } = Typography;
const { Option } = Select;

const ScheduleView: React.FC = () => {
  const queryClient = useQueryClient();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedYear, setSelectedYear] = useState(currentDate.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(currentDate.getMonth() + 1);
  const [selectedDepartment, setSelectedDepartment] = useState<string | undefined>();
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isAutoDistributeModalOpen, setIsAutoDistributeModalOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<{ id: number; day: number; dayType: string } | null>(null);
  const [form] = Form.useForm();

  const { data: schedules, isLoading } = useQuery<AnnualSchedule[]>({
    queryKey: ['schedules', selectedYear, selectedMonth, selectedDepartment],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.schedule.annual, {
        params: {
          year: selectedYear,
          month: selectedMonth,
          department: selectedDepartment,
        },
      });
      return response.data;
    },
  });

  const { data: stats } = useQuery({
    queryKey: ['schedule-stats', selectedYear, selectedMonth],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.schedule.stats, {
        params: { year: selectedYear, month: selectedMonth },
      });
      return response.data;
    },
  });

  const updateDayMutation = useMutation({
    mutationFn: async ({ scheduleId, day, dayType }: { scheduleId: number; day: number; dayType: string }) => {
      await apiClient.put(endpoints.schedule.update(scheduleId), {
        day,
        day_type: dayType,
      });
    },
    onSuccess: () => {
      message.success('Day updated successfully');
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      setIsEditModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to update day');
    },
  });

  const autoDistributeMutation = useMutation({
    mutationFn: async (data: AutoDistributeRequest) => {
      await apiClient.post(endpoints.schedule.autoDistribute, data);
    },
    onSuccess: () => {
      message.success('Auto-distribution completed');
      queryClient.invalidateQueries({ queryKey: ['schedules'] });
      setIsAutoDistributeModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(error.message || 'Auto-distribution failed');
    },
  });

  const handlePrevMonth = () => {
    const prev = subMonths(new Date(selectedYear, selectedMonth - 1, 1), 1);
    setSelectedYear(prev.getFullYear());
    setSelectedMonth(prev.getMonth() + 1);
  };

  const handleNextMonth = () => {
    const next = addMonths(new Date(selectedYear, selectedMonth - 1, 1), 1);
    setSelectedYear(next.getFullYear());
    setSelectedMonth(next.getMonth() + 1);
  };

  const handleEditDay = (schedule: AnnualSchedule, day: number) => {
    const dayData = schedule.days.find((d) => d.day === day);
    if (dayData && !dayData.is_locked) {
      setEditingSchedule({ id: schedule.id, day, dayType: dayData.day_type });
      form.setFieldsValue({ day_type: dayData.day_type, hours: dayData.hours });
      setIsEditModalOpen(true);
    }
  };

  const handleSaveDay = async () => {
    const values = await form.validateFields();
    if (editingSchedule) {
      updateDayMutation.mutate({
        scheduleId: editingSchedule.id,
        day: editingSchedule.day,
        dayType: values.day_type,
      });
    }
  };

  const handleAutoDistribute = async (values: AutoDistributeRequest) => {
    autoDistributeMutation.mutate({
      ...values,
      year: selectedYear,
      month: selectedMonth,
    });
  };

  const getDayTypeColor = (dayType: string) => {
    const colors: Record<string, string> = {
      working: 'blue',
      vacation: 'green',
      sick: 'orange',
      holiday: 'purple',
      unpaid: 'default',
    };
    return colors[dayType] || 'default';
  };

  const getDayTypeLabel = (dayType: string) => {
    return dayType.charAt(0).toUpperCase() + dayType.slice(1);
  };

  const monthStart = startOfMonth(new Date(selectedYear, selectedMonth - 1));
  const monthEnd = endOfMonth(new Date(selectedYear, selectedMonth - 1));
  const daysInMonth = eachDayOfInterval({ start: monthStart, end: monthEnd });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>Assignments</Title>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={() => setIsAutoDistributeModalOpen(true)}
        >
          Auto-Distribute
        </Button>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Total Staff"
              value={stats?.total_staff || schedules?.length || 0}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Working Days"
              value={stats?.total_working_days || 0}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Progress
              percent={stats ? Math.round((stats.total_staff * 20 - (stats as any).remaining_vacation_days) / (stats.total_staff * 20) * 100) : 0}
              status="active"
            />
            <Text type="secondary">Vacation Usage</Text>
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Select
            placeholder="Filter by department"
            value={selectedDepartment}
            onChange={setSelectedDepartment}
            allowClear
            style={{ width: '100%' }}
          >
            <Option value="Engineering">Engineering</Option>
            <Option value="HR">HR</Option>
            <Option value="Finance">Finance</Option>
            <Option value="Marketing">Marketing</Option>
            <Option value="Sales">Sales</Option>
          </Select>
        </Col>
      </Row>

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Button icon={<LeftOutlined />} onClick={handlePrevMonth}>Previous</Button>
          <Title level={4} style={{ margin: 0 }}>
            {format(new Date(selectedYear, selectedMonth - 1), 'MMMM yyyy')}
          </Title>
          <Button icon={<RightOutlined />} onClick={handleNextMonth}>Next</Button>
        </div>

        <Table
          dataSource={schedules}
          loading={isLoading}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 1500 }}
        >
          <Table.Column
            title="Staff"
            key="staff"
            render={(_, record: AnnualSchedule) => (
              <Space>
                <Text strong>{record.staff?.first_name} {record.staff?.last_name}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>{record.staff?.position}</Text>
              </Space>
            )}
          />
          {daysInMonth.map((date) => {
            const day = date.getDate();
            const isWeekend = date.getDay() === 0 || date.getDay() === 6;
            return (
              <Table.Column
                key={day}
                title={day}
                width={40}
                render={(_, record: AnnualSchedule) => {
                  const dayData = record.days.find((d) => d.day === day);
                  const bgColor = isWeekend && dayData?.day_type === 'working' ? '#fff7e6' : undefined;
                  return (
                    <div
                      style={{
                        backgroundColor: bgColor,
                        cursor: dayData && !dayData.is_locked ? 'pointer' : 'default',
                        textAlign: 'center',
                        padding: 4,
                      }}
                      onClick={() => dayData && handleEditDay(record, day)}
                    >
                      {dayData ? (
                        <Tag color={getDayTypeColor(dayData.day_type)} style={{ margin: 0, fontSize: 10 }}>
                          {getDayTypeLabel(dayData.day_type)}
                        </Tag>
                      ) : (
                        <Text type="secondary" style={{ fontSize: 10 }}>-</Text>
                      )}
                    </div>
                  );
                }}
              />
            );
          })}
        </Table>
      </Card>

      {/* Edit Day Modal */}
      <Modal
        title="Edit Schedule Day"
        open={isEditModalOpen}
        onCancel={() => setIsEditModalOpen(false)}
        onOk={handleSaveDay}
        confirmLoading={updateDayMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="day_type"
            label="Day Type"
            rules={[{ required: true, message: 'Please select day type' }]}
          >
            <Select>
              <Option value="working">Working</Option>
              <Option value="vacation">Vacation</Option>
              <Option value="sick">Sick Leave</Option>
              <Option value="holiday">Holiday</Option>
              <Option value="unpaid">Unpaid Leave</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="hours"
            label="Hours"
            rules={[{ required: true, message: 'Please enter hours' }]}
          >
            <InputNumber min={0} max={24} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Auto-Distribute Modal */}
      <Modal
        title="Auto-Distribute Schedule"
        open={isAutoDistributeModalOpen}
        onCancel={() => setIsAutoDistributeModalOpen(false)}
        footer={null}
      >
        <Form layout="vertical" onFinish={handleAutoDistribute}>
          <Form.Item
            name="distribution_type"
            label="Distribution Type"
            rules={[{ required: true, message: 'Please select distribution type' }]}
          >
            <Select>
              <Option value="even">Even Distribution</Option>
              <Option value="random">Random</Option>
              <Option value="balanced">Balanced</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="departments"
            label="Departments (leave empty for all)"
          >
            <Select mode="multiple" allowClear>
              <Option value="Engineering">Engineering</Option>
              <Option value="HR">HR</Option>
              <Option value="Finance">Finance</Option>
              <Option value="Marketing">Marketing</Option>
              <Option value="Sales">Sales</Option>
            </Select>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={autoDistributeMutation.isPending}>
                Run Auto-Distribute
              </Button>
              <Button onClick={() => setIsAutoDistributeModalOpen(false)}>Cancel</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ScheduleView;
