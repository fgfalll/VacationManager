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
  Tooltip,
  Upload,
  DatePicker,
  ConfigProvider,
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
  PlusOutlined,
  DeleteOutlined,
  FileTextOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { Staff, Document, DailyAttendance, StaffHistoryItem } from '../../api/types';
import { getPositionLabel, getActionTypeLabel, getAttendanceCodeLabel, EMPLOYMENT_TYPE_LABELS, WORK_BASIS_LABELS, STAFF_POSITION_LABELS } from '../../api/constants';
import { format } from 'date-fns';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import ukUA from 'antd/locale/uk_UA';

const { Title, Text } = Typography;
const { Option } = Select;

// Ukrainian status labels - full workflow
const STATUS_LABELS: Record<string, string> = {
  draft: 'Чернетка',
  signed_by_applicant: 'Підписав заявник',
  approved_by_dispatcher: 'Погоджено диспетчером',
  signed_dep_head: 'Підписано зав. кафедри',
  agreed: 'Погоджено',
  signed_rector: 'Підписано ректором',
  scanned: 'Відскановано',
  processed: 'В табелі',
};

// Ukrainian document type labels
const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  vacation_paid: 'Відпустка оплачувана',
  vacation_main: 'Основна щорічна відпустка',
  vacation_additional: 'Додаткова щорічна відпустка',
  vacation_chornobyl: 'Додаткова відпустка чорнобильцям',
  vacation_creative: 'Творча відпустка',
  vacation_study: 'Навчальна відпустка',
  vacation_children: 'Відпустка працівникам з дітьми',
  vacation_maternity: 'Відпустка у зв\'язку з вагітністю та пологами',
  vacation_childcare: 'Відпустка для догляду за дитиною',
  vacation_unpaid: 'Відпустка без збереження зарплати',
  vacation_unpaid_study: 'Навчальна відпустка без збереження зарплати',
  vacation_unpaid_mandatory: 'Відпустка без збереження (обов\'язкова)',
  vacation_unpaid_agreement: 'Відпустка без збереження (за згодою)',
  vacation_unpaid_other: 'Інша відпустка без збереження зарплати',
  term_extension: 'Продовження терміну контракту',
  term_extension_contract: 'Продовження контракту (контракт)',
  term_extension_competition: 'Продовження контракту (конкурс)',
  term_extension_pdf: 'Продовження контракту (PDF)',
  employment_contract: 'Прийом на роботу (контракт)',
  employment_competition: 'Прийом на роботу (конкурс)',
  employment_pdf: 'Прийом на роботу (PDF)',
};

const StaffDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isAddPositionModalOpen, setIsAddPositionModalOpen] = useState(false);
  const [editingPosition, setEditingPosition] = useState<Staff | null>(null);
  const [editForm] = Form.useForm();

  // Inline upload modal state for subposition scan
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPosition, setUploadPosition] = useState('LECTURER');
  const [uploadRate, setUploadRate] = useState(0.5);
  const [uploadEmploymentType, setUploadEmploymentType] = useState('internal');
  const [uploadTermStart, setUploadTermStart] = useState('');
  const [uploadTermEnd, setUploadTermEnd] = useState('');
  const [isUploading, setIsUploading] = useState(false);

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


  const handleDeletePosition = (positionId: number) => {
    const position = allPositions.find(p => p.id === positionId);
    if (!position) return;

    if (allPositions.filter(p => p.is_active).length === 1 && position.is_active) {
      message.warning('Не можна деактивувати останню активну посаду');
      return;
    }
    deleteMutation.mutate(positionId);
  };

  // Handle subposition upload submission
  const handleSubpositionUpload = async () => {
    if (!uploadFile || !uploadTermStart || !uploadTermEnd || !currentStaff) {
      message.warning('Заповніть всі поля та виберіть файл');
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append('staff_id', currentStaff.id.toString());
    formData.append('doc_type', 'employment_pdf');
    formData.append('date_start', uploadTermStart);
    formData.append('date_end', uploadTermEnd);
    formData.append('days_count', '0');
    formData.append('file', uploadFile);
    formData.append('new_position', uploadPosition);
    formData.append('new_rate', uploadRate.toString());
    formData.append('new_employment_type', uploadEmploymentType);

    try {
      await apiClient.post('/documents/direct-scan-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      message.success('Сумісництво створено успішно');
      setIsUploadModalOpen(false);
      setUploadFile(null);
      setUploadTermStart('');
      setUploadTermEnd('');
      queryClient.invalidateQueries({ queryKey: ['staff-all'] });
      queryClient.invalidateQueries({ queryKey: ['staff'] });
    } catch (error: any) {
      message.error(error.response?.data?.detail || error.message || 'Помилка завантаження');
    } finally {
      setIsUploading(false);
    }
  };

  const documentColumns = [
    ...(allPositions.length > 1 ? [{
      title: 'Посада',
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
    }] : []),
    {
      title: 'Документ',
      dataIndex: 'document_type',
      key: 'document_type',
      render: (type: { name: string; id?: string }) => {
        // Try to translate using id first, then use name
        if (type?.id) {
          return DOCUMENT_TYPE_LABELS[type.id] || type.name || '-';
        }
        return type?.name || '-';
      },
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colors: Record<string, string> = {
          draft: 'default',
          signed_by_applicant: 'blue',
          approved_by_dispatcher: 'cyan',
          signed_dep_head: 'lime',
          agreed: 'orange',
          signed_rector: 'purple',
          scanned: 'magenta',
          processed: 'success',
        };
        return <Tag color={colors[status] || 'default'}>{STATUS_LABELS[status] || status.replace(/_/g, ' ').toUpperCase()}</Tag>;
      },
    },
    {
      title: 'Дати',
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
      title: 'Днів',
      key: 'total_days',
      render: (_: unknown, record: Document) => record.days_count || '-',
    },
    {
      title: 'Дія',
      key: 'action',
      width: 80,
      render: (_: unknown, record: Document) => (
        <Button
          size="small"
          onClick={() => window.open(`/documents/${record.id}`, '_blank')}
        >
          Перегляд
        </Button>
      ),
    },
  ];

  const tabItems = [
    {
      key: 'documents',
      label: 'Документи',
      children: (
        <Table
          columns={documentColumns}
          dataSource={documents}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
        />
      ),
    },
    {
      key: 'attendance',
      label: 'Відвідування',
      children: (
        <Table
          columns={[
            ...(allPositions.length > 1 ? [{
              title: 'Посада',
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
            }] : []),
            {
              title: 'Дата',
              dataIndex: 'date',
              key: 'date',
              render: (date: string) => date ? format(new Date(date), 'dd.MM.yyyy') : '-',
            },
            {
              title: 'Код',
              dataIndex: 'code',
              key: 'code',
              render: (code: string) => (
                <Tag color="blue">{code}</Tag>
              ),
            },
            {
              title: 'Опис',
              dataIndex: 'code',
              key: 'description',
              render: (_: unknown, record: DailyAttendance) => getAttendanceCodeLabel(record.code),
            },
            {
              title: 'Днів',
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
              title: 'Корекція',
              dataIndex: 'is_correction',
              key: 'is_correction',
              render: (isCorrection: boolean) => isCorrection ? <Tag color="orange">Корекція</Tag> : '-',
            },
          ]}
          dataSource={attendance}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
        />
      ),
    },
    {
      key: 'history',
      label: 'Історія',
      children: (
        <Table
          columns={[
            ...(allPositions.length > 1 ? [{
              title: 'Посада',
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
            }] : []),
            {
              title: 'Дата',
              dataIndex: 'created_at',
              key: 'created_at',
              render: (date: string) => date ? format(new Date(date), 'dd.MM.yyyy HH:mm') : '-',
            },
            {
              title: 'Дія',
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
              title: 'Змінено',
              dataIndex: 'changed_by',
              key: 'changed_by',
            },
            {
              title: 'Коментар',
              dataIndex: 'comment',
              key: 'comment',
              render: (comment: string | null) => comment || '-',
            },
          ]}
          dataSource={history}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
        />
      ),
    },
  ];

  if (staffLoading) {
    return <Card loading={true} />;
  }

  if (!currentStaff) {
    return <Card><Text type="secondary">Співробітника не знайдено</Text></Card>;
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
        Назад до списку
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
            title={<Space>Всі посади {allPositions.some(p => parseFloat(String(p.rate)) === 1.0 && p.is_active && p.position !== 'specialist') ? (
              <Button size="small" icon={<PlusOutlined />} onClick={() => setIsAddPositionModalOpen(true)}>Додати посаду</Button>
            ) : (
              <Tooltip title="Додавати посаду можна тільки з основної позиції (ставка 1.00, крім фахівця)">
                <Button size="small" icon={<PlusOutlined />} disabled>Додати посаду</Button>
              </Tooltip>
            )}</Space>}
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
              <Descriptions.Item label="Телефон">{staff.phone || '-'}</Descriptions.Item>
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

      {/* Add Position Modal - Choice Dialog */}
      <Modal
        title="Додати посаду (сумісництво)"
        open={isAddPositionModalOpen}
        onCancel={() => setIsAddPositionModalOpen(false)}
        footer={null}
        width={500}
      >
        <Card style={{ marginBottom: 16 }}>
          <Space direction="vertical">
            <Text strong>Співробітник: {staff.pib_nom}</Text>
            <Text type="secondary">Оберіть спосіб додавання сумісництва:</Text>
          </Space>
        </Card>

        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Button
            type="primary"
            icon={<FileTextOutlined />}
            block
            size="large"
            onClick={() => {
              setIsAddPositionModalOpen(false);
              navigate(`/documents/create?staff_id=${id}&type=employment`);
            }}
          >
            Створити документ
          </Button>

          <Button
            icon={<UploadOutlined />}
            block
            size="large"
            onClick={() => {
              setIsAddPositionModalOpen(false);
              setIsUploadModalOpen(true);
            }}
          >
            Завантажити скан договору
          </Button>
        </Space>
      </Modal>

      {/* Subposition Upload Modal */}
      <Modal
        title="Завантажити скан договору (сумісництво)"
        open={isUploadModalOpen}
        onCancel={() => {
          setIsUploadModalOpen(false);
          setUploadFile(null);
        }}
        onOk={handleSubpositionUpload}
        okText="Завантажити"
        cancelText="Скасувати"
        confirmLoading={isUploading}
        width={600}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Subposition info */}
          <div style={{ background: '#f5f5f5', padding: 12, borderRadius: 8 }}>
            <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
              Дані нової позиції (сумісництво):
            </Typography.Text>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <Typography.Text strong>Посада:</Typography.Text>
                <Select
                  style={{ width: '100%' }}
                  value={uploadPosition}
                  onChange={(val) => setUploadPosition(val)}
                  options={[
                    { label: "Професор", value: "PROFESSOR" },
                    { label: "Доцент", value: "ASSOCIATE_PROFESSOR" },
                    { label: "Старший викладач", value: "SENIOR_LECTURER" },
                    { label: "Асистент", value: "LECTURER" },
                  ]}
                />
              </div>
              <div style={{ flex: 1 }}>
                <Typography.Text strong>Ставка:</Typography.Text>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <Select
                    style={{ width: 80 }}
                    value={uploadRate}
                    onChange={(val) => setUploadRate(val)}
                    options={[
                      { label: "0.25", value: 0.25 },
                      { label: "0.5", value: 0.5 },
                      { label: "0.75", value: 0.75 },
                    ]}
                  />
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    Зайнято: {allPositions.filter(p => p.is_active).reduce((sum, p) => sum + parseFloat(String(p.rate)), 0).toFixed(2)} |
                    Вільно: {(1.0 - allPositions.filter(p => p.is_active).reduce((sum, p) => sum + parseFloat(String(p.rate)), 0) - uploadRate).toFixed(2)}
                  </Typography.Text>
                </div>
              </div>
            </div>
          </div>

          {/* Contract dates */}
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <Typography.Text strong>Початок контракту:</Typography.Text>
              <ConfigProvider locale={ukUA}>
                <DatePicker
                  style={{ width: '100%' }}
                  format="DD.MM.YYYY"
                  placeholder="Виберіть дату"
                  onChange={(date) => setUploadTermStart(date ? date.format('YYYY-MM-DD') : '')}
                />
              </ConfigProvider>
            </div>
            <div style={{ flex: 1 }}>
              <Typography.Text strong>Кінець контракту:</Typography.Text>
              <ConfigProvider locale={ukUA}>
                <DatePicker
                  style={{ width: '100%' }}
                  format="DD.MM.YYYY"
                  placeholder="Виберіть дату"
                  onChange={(date) => setUploadTermEnd(date ? date.format('YYYY-MM-DD') : '')}
                />
              </ConfigProvider>
            </div>
          </div>

          {/* File upload */}
          <div>
            <Typography.Text strong>Скан договору (PDF):</Typography.Text>
            <Upload.Dragger
              accept=".pdf,.png,.jpg,.jpeg"
              maxCount={1}
              beforeUpload={(file) => {
                setUploadFile(file);
                return false;
              }}
              onRemove={() => setUploadFile(null)}
              fileList={uploadFile ? [{ uid: '-1', name: uploadFile.name, status: 'done' } as any] : []}
            >
              <p className="ant-upload-drag-icon"><UploadOutlined style={{ fontSize: 32 }} /></p>
              <p className="ant-upload-text">Натисніть або перетягніть файл</p>
              <p className="ant-upload-hint">Підтримуються: PDF, PNG, JPG</p>
            </Upload.Dragger>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default StaffDetail;
