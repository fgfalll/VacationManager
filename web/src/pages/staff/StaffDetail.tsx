import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  Row,
  Col,
  Descriptions,
  Tabs,
  Table,
  Tag,
  Button,
  Typography,
  Space,
  Avatar,
  Modal,
  Form,
  Input,
  Select,
  message,
  Divider,
  Popconfirm,
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
  PlusOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { Staff, Document, DailyAttendance, StaffHistoryItem } from '../../api/types';
import { getPositionLabel, getActionTypeLabel, getAttendanceCodeLabel, EMPLOYMENT_TYPE_LABELS, WORK_BASIS_LABELS, STAFF_POSITION_LABELS } from '../../api/constants';
import { format } from 'date-fns';
import { useMutation, useQueryClient } from '@tanstack/react-query';

const { Title, Text } = Typography;
const { Option } = Select;

const StaffDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isAddPositionModalOpen, setIsAddPositionModalOpen] = useState(false);
  const [editingPosition, setEditingPosition] = useState<Staff | null>(null);
  const [editForm] = Form.useForm();
  const [addPositionForm] = Form.useForm();

  // Get the specific staff record
  const { data: currentStaff, isLoading: staffLoading } = useQuery<Staff>({
    queryKey: ['staff', id],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.detail(Number(id)));
      return response.data;
    },
    enabled: !!id,
  });

  // Get all staff to find same-name records (additional positions)
  const { data: allStaff } = useQuery<Staff[]>({
    queryKey: ['staff-all'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.list, { params: { limit: 1000 } });
      return response.data.items || [];
    },
  });

  // Get all positions for the same person (same name)
  const allPositions = React.useMemo(() => {
    if (!currentStaff || !allStaff) return [];
    return allStaff.filter(s => s.pib_nom === currentStaff.pib_nom);
  }, [currentStaff, allStaff]);

  const { data: documents } = useQuery<Document[]>({
    queryKey: ['staff-documents', allPositions.map(p => p.id)],
    queryFn: async () => {
      // Fetch documents for all positions
      const staffIds = allPositions.map(p => p.id);
      const promises = staffIds.map(staffId =>
        apiClient.get(endpoints.staff.documents(staffId))
      );
      const responses = await Promise.all(promises);
      // Merge and deduplicate documents by ID
      const allDocs = responses.flatMap(r => r.data || []);
      const seen = new Set<number>();
      return allDocs.filter(doc => {
        if (seen.has(doc.id)) return false;
        seen.add(doc.id);
        return true;
      });
    },
    enabled: allPositions.length > 0,
  });

  const { data: attendance } = useQuery<DailyAttendance[]>({
    queryKey: ['staff-attendance', allPositions.map(p => p.id)],
    queryFn: async () => {
      // Fetch attendance for all positions
      const staffIds = allPositions.map(p => p.id);
      const promises = staffIds.map(staffId =>
        apiClient.get(endpoints.staff.attendance(staffId))
      );
      const responses = await Promise.all(promises);
      // Merge attendance records
      return responses.flatMap(r => r.data || []);
    },
    enabled: allPositions.length > 0,
  });

  const { data: history } = useQuery<StaffHistoryItem[]>({
    queryKey: ['staff-history', allPositions.map(p => p.id)],
    queryFn: async () => {
      // Fetch history for all positions
      const staffIds = allPositions.map(p => p.id);
      const promises = staffIds.map(staffId =>
        apiClient.get(endpoints.staff.history(staffId))
      );
      const responses = await Promise.all(promises);
      // Merge and sort history by date
      const allHistory = responses.flatMap(r => r.data || []);
      return allHistory.sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    },
    enabled: allPositions.length > 0,
  });

  // Mutations
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: any }) => {
      const response = await apiClient.put(endpoints.staff.update(id), data);
      return response.data;
    },
    onSuccess: () => {
      message.success('Посаду оновлено');
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      queryClient.invalidateQueries({ queryKey: ['staff-all'] });
      setIsEditModalOpen(false);
      setEditingPosition(null);
      editForm.resetFields();
    },
    onError: (error: Error) => {
      message.error(error.message || 'Помилка оновлення');
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await apiClient.post(endpoints.staff.create, data);
      return response.data;
    },
    onSuccess: () => {
      message.success('Нову посаду додано');
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      queryClient.invalidateQueries({ queryKey: ['staff-all'] });
      setIsAddPositionModalOpen(false);
      addPositionForm.resetFields();
    },
    onError: (error: Error) => {
      message.error(error.message || 'Помилка створення');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      // Soft delete - deactivate the position
      await apiClient.put(endpoints.staff.update(id), { is_active: false });
    },
    onSuccess: () => {
      message.success('Посаду деактивовано');
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      queryClient.invalidateQueries({ queryKey: ['staff-all'] });
      // Navigate away if current position was deactivated
      if (id === currentStaff?.id && !currentStaff.is_active) {
        navigate('/staff');
      }
    },
    onError: (error: Error) => {
      message.error(error.message || 'Помилка деактивації');
    },
  });

  const handleEditPosition = (position: Staff) => {
    setEditingPosition(position);
    editForm.setFieldsValue({
      ...position,
      term_start: position.term_start ? format(new Date(position.term_start), 'yyyy-MM-dd') : undefined,
      term_end: position.term_end ? format(new Date(position.term_end), 'yyyy-MM-dd') : undefined,
    });
    setIsEditModalOpen(true);
  };

  const handleUpdatePosition = async (values: any) => {
    if (editingPosition) {
      updateMutation.mutate({ id: editingPosition.id, data: values });
    }
  };

  const handleAddPosition = async (values: any) => {
    if (currentStaff) {
      createMutation.mutate({
        ...values,
        pib_nom: currentStaff.pib_nom,
        email: currentStaff.email,
        phone: currentStaff.phone,
      });
    }
  };

  const handleDeletePosition = (positionId: number) => {
    const position = allPositions.find(p => p.id === positionId);
    if (!position) return;

    if (allPositions.filter(p => p.is_active).length === 1 && position.is_active) {
      message.warning('Не можна деактивувати останню активну посаду');
      return;
    }
    deleteMutation.mutate(positionId);
  };

  const documentColumns = [
    {
      title: 'Position',
      key: 'position',
      width: 130,
      render: (_: unknown, record: Document) => {
        const position = allPositions.find(p => p.id === record.staff_id);
        if (!position) return '-';

        const empType = position.employment_type;
        let label = '';
        let color = '';

        if (empType === 'main') {
          label = 'Основна';
          color = 'blue';
        } else if (empType === 'internal') {
          label = 'Внутр. сумісник';
          color = 'orange';
        } else if (empType === 'external') {
          label = 'Зовн. сумісник';
          color = 'purple';
        } else {
          label = empType || 'Сумісництво';
          color = 'default';
        }

        return (
          <Space direction="vertical" size={0}>
            <Tag color={color} style={{ fontSize: 11 }}>{label}</Tag>
            <Text style={{ fontSize: 11 }}>{getPositionLabel(position.position)}</Text>
          </Space>
        );
      },
    },
    {
      title: 'Type',
      dataIndex: 'document_type',
      key: 'document_type',
      render: (type: { name: string }) => type?.name || '-',
    },
    {
      title: 'Total Days',
      key: 'total_days',
      render: (_: unknown, record: Document) => record.days_count || '-',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colors: Record<string, string> = {
          draft: 'default',        // Gray
          on_signature: 'orange',  // Orange (warning/active)
          agreed: 'blue',          // Blue
          signed: 'cyan',          // Cyan
          scanned: 'purple',       // Purple
          processed: 'green',      // Green (success)

          // Legacy mappings
          pending_hr: 'processing',
          pending_director: 'processing',
          pending_manager: 'processing',
          pending_signature: 'warning',
          pending_scan: 'warning',
          approved: 'success',
          rejected: 'error',
          cancelled: 'default',
        };
        return <Tag color={colors[status] || 'default'}>{status.replace(/_/g, ' ').toUpperCase()}</Tag>;
      },
    },
    {
      title: 'Dates',
      key: 'dates',
      width: 130,
      render: (_: unknown, record: Document) => {
        const startDate = record.start_date ? new Date(record.start_date) : null;
        const endDate = record.end_date ? new Date(record.end_date) : null;

        if (!startDate || !endDate || isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
          return <Text type="secondary">-</Text>;
        }

        return (
          <Text type="secondary" style={{ fontSize: 11 }}>
            {format(startDate, 'dd.MM.yyyy')} - {format(endDate, 'dd.MM.yyyy')}
          </Text>
        );
      },
    },
    {
      title: 'Action',
      key: 'action',
      width: 80,
      render: (_: unknown, record: Document) => (
        <Button
          size="small"
          onClick={() => window.open(`/documents/${record.id}`, '_blank')}
        >
          View
        </Button>
      ),
    },
  ];

  const tabItems = [
    {
      key: 'documents',
      label: 'Documents',
      children: (
        <Table
          columns={documentColumns}
          dataSource={documents}
          rowKey="id"
          pagination={false}
          size="small"
        />
      ),
    },
    {
      key: 'attendance',
      label: 'Attendance',
      children: (
        <Table
          columns={[
            {
              title: 'Position',
              key: 'position',
              width: 180,
              render: (_: unknown, record: DailyAttendance) => {
                const position = allPositions.find(p => p.id === record.staff_id);
                if (!position) return '-';

                const empType = position.employment_type;
                let label = '';
                let color = '';

                if (empType === 'main') {
                  label = 'Основна';
                  color = 'blue';
                } else if (empType === 'internal') {
                  label = 'Внутр. сумісник';
                  color = 'orange';
                } else if (empType === 'external') {
                  label = 'Зовн. сумісник';
                  color = 'purple';
                } else {
                  label = empType || 'Сумісництво';
                  color = 'default';
                }

                return (
                  <Space direction="vertical" size={0}>
                    <Tag color={color} style={{ fontSize: 11 }}>{label}</Tag>
                    <Text style={{ fontSize: 12 }}>{getPositionLabel(position.position)}</Text>
                  </Space>
                );
              },
            },
            {
              title: 'Date',
              dataIndex: 'date',
              key: 'date',
              render: (date: string) => date ? format(new Date(date), 'dd.MM.yyyy') : '-',
            },
            {
              title: 'Code',
              dataIndex: 'code',
              key: 'code',
              render: (code: string) => (
                <Tag color="blue">{code}</Tag>
              ),
            },
            {
              title: 'Description',
              dataIndex: 'code',
              key: 'description',
              render: (_: unknown, record: DailyAttendance) => getAttendanceCodeLabel(record.code),
            },
            {
              title: 'Total Days',
              key: 'total_days',
              render: (_: unknown, record: DailyAttendance) => {
                if (record.date_end && record.date) {
                  const start = new Date(record.date);
                  const end = new Date(record.date_end);
                  const days = Math.floor((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1;
                  return days;
                }
                return 1;
              },
            },
            {
              title: 'Correction',
              dataIndex: 'is_correction',
              key: 'is_correction',
              render: (isCorrection: boolean) => isCorrection ? <Tag color="orange">Correction</Tag> : '-',
            },
          ]}
          dataSource={attendance}
          rowKey="id"
          pagination={false}
          size="small"
        />
      ),
    },
    {
      key: 'history',
      label: 'History',
      children: (
        <Table
          columns={[
            {
              title: 'Position',
              key: 'position',
              width: 150,
              render: (_: unknown, record: StaffHistoryItem) => {
                const position = allPositions.find(p => p.id === record.staff_id);
                if (!position) return '-';

                const empType = position.employment_type;
                let label = '';
                let color = '';

                if (empType === 'main') {
                  label = 'Основна';
                  color = 'blue';
                } else if (empType === 'internal') {
                  label = 'Внутр. сумісник';
                  color = 'orange';
                } else if (empType === 'external') {
                  label = 'Зовн. сумісник';
                  color = 'purple';
                } else {
                  label = empType || 'Сумісництво';
                  color = 'default';
                }

                return (
                  <Space direction="vertical" size={0}>
                    <Tag color={color} style={{ fontSize: 11 }}>{label}</Tag>
                    <Text style={{ fontSize: 11 }}>{getPositionLabel(position.position)}</Text>
                  </Space>
                );
              },
            },
            {
              title: 'Date',
              dataIndex: 'created_at',
              key: 'created_at',
              render: (date: string) => date ? format(new Date(date), 'dd.MM.yyyy HH:mm') : '-',
            },
            {
              title: 'Action',
              dataIndex: 'action',
              key: 'action',
              render: (action: string) => {
                const colors: Record<string, string> = {
                  create: 'green',
                  update: 'blue',
                  deactivate: 'red',
                  restore: 'gold',
                };
                return (
                  <Tag color={colors[action] || 'default'}>
                    {getActionTypeLabel(action)}
                  </Tag>
                );
              },
            },
            {
              title: 'Changed By',
              dataIndex: 'changed_by',
              key: 'changed_by',
            },
            {
              title: 'Comment',
              dataIndex: 'comment',
              key: 'comment',
              render: (comment: string | null) => comment || '-',
            },
          ]}
          dataSource={history}
          rowKey="id"
          pagination={false}
          size="small"
        />
      ),
    },
  ];

  if (staffLoading) {
    return <Card loading={true} />;
  }

  if (!currentStaff) {
    return <Card><Text type="secondary">Staff not found</Text></Card>;
  }

  const staff = currentStaff;

  return (
    <div>
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/staff')}
        style={{ marginBottom: 16, paddingLeft: 0 }}
      >
        Back to Staff List
      </Button>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={6}>
          <Card>
            <Space direction="vertical" style={{ width: '100%', textAlign: 'center' }}>
              <Avatar size={100} style={{ backgroundColor: '#1890ff' }}>
                {staff.pib_nom?.[0]}
              </Avatar>
              <Title level={4} style={{ margin: 0 }}>
                {staff.pib_nom}
              </Title>
              <Text type="secondary">{allPositions.length} {allPositions.length === 1 ? 'позиція' : allPositions.length >= 2 && allPositions.length <= 4 ? 'позиції' : 'позицій'}</Text>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={18}>
          {/* All Positions Card */}
          <Card
            title={<Space>Всі посади <Button size="small" icon={<PlusOutlined />} onClick={() => setIsAddPositionModalOpen(true)}>Додати посаду</Button></Space>}
            extra={
              <Space>
                <Text type="secondary">Всього посад:</Text>
                <Tag>{allPositions.length}</Tag>
              </Space>
            }
          >
            {allPositions.map((position, idx) => (
              <React.Fragment key={position.id}>
                {idx > 0 && <Divider style={{ margin: '12px 0' }} />}
                <Row gutter={16} align="middle">
                  <Col flex="auto">
                    <Space direction="vertical" size={2}>
                      <Space>
                        {(() => {
                          const empType = position.employment_type;
                          let label = '';
                          let color = '';

                          if (empType === 'main') {
                            label = 'Основна';
                            color = 'blue';
                          } else if (empType === 'internal') {
                            label = 'Внутр. сумісник';
                            color = 'orange';
                          } else if (empType === 'external') {
                            label = 'Зовн. сумісник';
                            color = 'purple';
                          } else {
                            label = empType || 'Сумісництво';
                            color = 'default';
                          }

                          return <Tag color={color}>{label}</Tag>;
                        })()}
                        <Text strong>{getPositionLabel(position.position)}</Text>
                        <Tag>{position.rate} ст.</Tag>
                        <Tag color={position.is_active ? 'green' : 'orange'}>
                          {position.is_active ? 'Активний' : 'Неактивний'}
                        </Tag>
                      </Space>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {format(new Date(position.term_start), 'dd.MM.yyyy')} - {position.term_end ? format(new Date(position.term_end), 'dd.MM.yyyy') : 'по теперішній час'}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {WORK_BASIS_LABELS[position.work_basis as keyof typeof WORK_BASIS_LABELS] || position.work_basis}
                      </Text>
                    </Space>
                  </Col>
                  <Col>
                    <Space>
                      <Button
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => handleEditPosition(position)}
                      />
                      {position.is_active && allPositions.filter(p => p.is_active).length > 1 ? (
                        <Popconfirm
                          title="Деактивувати посаду?"
                          description="Ця дія приховає посаду та всі пов'язані дані"
                          onConfirm={() => handleDeletePosition(position.id)}
                          okText="Так"
                          cancelText="Ні"
                        >
                          <Button
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                          />
                        </Popconfirm>
                      ) : !position.is_active ? (
                        <Button
                          size="small"
                          disabled
                          icon={<DeleteOutlined />}
                        />
                      ) : null}
                    </Space>
                  </Col>
                </Row>
              </React.Fragment>
            ))}
          </Card>

          <Card style={{ marginTop: 16 }}>
            <Descriptions title="Контактна інформація" column={{ xs: 1, sm: 2 }}>
              <Descriptions.Item label="Email">{staff.email || '-'}</Descriptions.Item>
              <Descriptions.Item label="Phone">{staff.phone || '-'}</Descriptions.Item>
              <Descriptions.Item label="Вчений ступінь">{staff.degree || '-'}</Descriptions.Item>
              <Descriptions.Item label="Баланс відпусток">{staff.vacation_balance || 0} дн.</Descriptions.Item>
            </Descriptions>
          </Card>

          <Card style={{ marginTop: 16 }}>
            <Tabs items={tabItems} />
          </Card>
        </Col>
      </Row>

      {/* Edit Position Modal */}
      <Modal
        title="Редагувати посаду"
        open={isEditModalOpen}
        onCancel={() => {
          setIsEditModalOpen(false);
          setEditingPosition(null);
          editForm.resetFields();
        }}
        footer={null}
        destroyOnHidden
        width={600}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleUpdatePosition}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="position"
            label="Посада"
            rules={[{ required: true, message: 'Оберіть посаду' }]}
          >
            <Select placeholder="Оберіть посаду" allowClear>
              {Object.entries(STAFF_POSITION_LABELS).map(([value, label]) => (
                <Option key={value} value={value}>{label}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="rate"
            label="Ставка"
            rules={[
              { required: true, message: 'Введіть ставку' },
              {
                pattern: /^(0\.25|0\.5|0\.75|1(\.0+)?)$/,
                message: 'Ставка має бути: 0.25, 0.5, 0.75 або 1.0',
              },
            ]}
          >
            <Input type="number" min={0.25} max={1} step={0.25} placeholder="0.25, 0.5, 0.75, 1.0" />
          </Form.Item>

          <Form.Item
            name="term_start"
            label="Дата початку"
            rules={[{ required: true, message: 'Оберіть дату' }]}
          >
            <Input type="date" />
          </Form.Item>

          <Form.Item
            name="term_end"
            label="Дата кінця"
            dependencies={['term_start']}
            rules={[
              { required: true, message: 'Оберіть дату' },
              ({ getFieldValue }) => ({
                validator: (_, value) => {
                  const termStart = getFieldValue('term_start');
                  if (value && termStart && new Date(value) <= new Date(termStart)) {
                    return Promise.reject(new Error('Кінець контракту має бути пізніше за початок'));
                  }
                  return Promise.resolve();
                },
              }),
            ]}
          >
            <Input type="date" />
          </Form.Item>

          <Form.Item
            name="employment_type"
            label="Тип працевлаштування"
            rules={[{ required: true, message: 'Оберіть тип' }]}
          >
            <Select placeholder="Оберіть тип">
              {Object.entries(EMPLOYMENT_TYPE_LABELS).map(([value, label]) => (
                <Option key={value} value={value}>{label}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="work_basis"
            label="Основа роботи"
            rules={[{ required: true, message: 'Оберіть основу' }]}
          >
            <Select placeholder="Оберіть основу">
              {Object.entries(WORK_BASIS_LABELS).map(([value, label]) => (
                <Option key={value} value={value}>{label}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="is_active"
            label="Статус"
            rules={[{ required: true, message: 'Оберіть статус' }]}
          >
            <Select>
              <Option value={true}>Активний</Option>
              <Option value={false}>Неактивний</Option>
            </Select>
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }} shouldUpdate>
            {() => {
              const errors = editForm.getFieldsError();
              const hasErrors = errors.some(e => e.errors.length > 0);
              const requiredFields = ['position', 'term_start', 'term_end', 'employment_type', 'work_basis', 'rate'];
              const values = editForm.getFieldsValue();
              const hasAllRequired = requiredFields.every(f => values[f] !== undefined && values[f] !== '' && values[f] !== null);
              const disabled = hasErrors || !hasAllRequired;

              return (
                <Space>
                  <Button onClick={() => {
                    setIsEditModalOpen(false);
                    setEditingPosition(null);
                    editForm.resetFields();
                  }}>Скасувати</Button>
                  <Button
                    type="primary"
                    htmlType="submit"
                    disabled={disabled}
                    loading={updateMutation.isPending}
                  >
                    Зберегти
                  </Button>
                </Space>
              );
            }}
          </Form.Item>
        </Form>
      </Modal>

      {/* Add Position Modal */}
      <Modal
        title="Додати посаду (сумісництво)"
        open={isAddPositionModalOpen}
        onCancel={() => {
          setIsAddPositionModalOpen(false);
          addPositionForm.resetFields();
        }}
        footer={null}
        destroyOnHidden
        width={600}
      >
        <Form
          form={addPositionForm}
          layout="vertical"
          onFinish={handleAddPosition}
          style={{ marginTop: 16 }}
          initialValues={{
            rate: 0.5,
            is_active: true,
          }}
        >
          <Form.Item
            name="position"
            label="Посада"
            rules={[{ required: true, message: 'Оберіть посаду' }]}
          >
            <Select placeholder="Оберіть посаду" allowClear>
              {Object.entries(STAFF_POSITION_LABELS).map(([value, label]) => (
                <Option key={value} value={value}>{label}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="rate"
            label="Ставка"
            rules={[
              { required: true, message: 'Введіть ставку' },
              {
                pattern: /^(0\.25|0\.5|0\.75|1(\.0+)?)$/,
                message: 'Ставка має бути: 0.25, 0.5, 0.75 або 1.0',
              },
            ]}
          >
            <Input type="number" min={0.25} max={1} step={0.25} placeholder="0.25, 0.5, 0.75, 1.0" />
          </Form.Item>

          <Form.Item
            name="term_start"
            label="Дата початку"
            rules={[{ required: true, message: 'Оберіть дату' }]}
          >
            <Input type="date" />
          </Form.Item>

          <Form.Item
            name="term_end"
            label="Дата кінця"
            dependencies={['term_start']}
            rules={[
              { required: true, message: 'Оберіть дату' },
              ({ getFieldValue }) => ({
                validator: (_, value) => {
                  const termStart = getFieldValue('term_start');
                  if (value && termStart && new Date(value) <= new Date(termStart)) {
                    return Promise.reject(new Error('Кінець контракту має бути пізніше за початок'));
                  }
                  return Promise.resolve();
                },
              }),
            ]}
          >
            <Input type="date" />
          </Form.Item>

          <Form.Item
            name="employment_type"
            label="Тип працевлаштування"
            rules={[{ required: true, message: 'Оберіть тип' }]}
          >
            <Select placeholder="Оберіть тип">
              {Object.entries(EMPLOYMENT_TYPE_LABELS).map(([value, label]) => (
                <Option key={value} value={value}>{label}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="work_basis"
            label="Основа роботи"
            rules={[{ required: true, message: 'Оберіть основу' }]}
          >
            <Select placeholder="Оберіть основу">
              {Object.entries(WORK_BASIS_LABELS).map(([value, label]) => (
                <Option key={value} value={value}>{label}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }} shouldUpdate>
            {() => {
              const errors = addPositionForm.getFieldsError();
              const hasErrors = errors.some(e => e.errors.length > 0);
              const requiredFields = ['position', 'term_start', 'term_end', 'employment_type', 'work_basis', 'rate'];
              const values = addPositionForm.getFieldsValue();
              const hasAllRequired = requiredFields.every(f => values[f] !== undefined && values[f] !== '' && values[f] !== null);
              const disabled = hasErrors || !hasAllRequired;

              return (
                <Space>
                  <Button onClick={() => {
                    setIsAddPositionModalOpen(false);
                    addPositionForm.resetFields();
                  }}>Скасувати</Button>
                  <Button
                    type="primary"
                    htmlType="submit"
                    disabled={disabled}
                    loading={createMutation.isPending}
                  >
                    Додати
                  </Button>
                </Space>
              );
            }}
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default StaffDetail;
