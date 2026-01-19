import React, { useState } from 'react';
import {
  Table,
  Card,
  Button,
  Input,
  Space,
  Tag,
  Modal,
  Form,
  Select,
  message,
  Popconfirm,
  Typography,
  Row,
  Col,
  Alert,
} from 'antd';
import { PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, EyeOutlined, ReloadOutlined, FileTextOutlined, UploadOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { Staff, StaffCreateRequest, StaffUpdateRequest, PaginatedResponse } from '../../api/types';
import {
  STAFF_POSITION_LABELS,
  EmploymentType,
  EMPLOYMENT_TYPE_LABELS,
  WorkBasis,
  WORK_BASIS_LABELS,
  getPositionLabel,
} from '../../api/constants';
import { format } from 'date-fns';

const { Title, Text } = Typography;
const { Option } = Select;

const StaffList: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isReactivateModalOpen, setIsReactivateModalOpen] = useState(false);
  const [reactivatingStaff, setReactivatingStaff] = useState<Staff | null>(null);
  const [editingStaff, setEditingStaff] = useState<Staff | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });
  const [form] = Form.useForm();

  const { data: staffData, isLoading } = useQuery<PaginatedResponse<Staff>>({
    queryKey: ['staff', pagination, searchTerm],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.list, {
        params: {
          skip: (pagination.current - 1) * pagination.pageSize,
          limit: pagination.pageSize,
          search: searchTerm,
        },
      });
      return {
        data: response.data.items || [],
        total: response.data.total || 0,
        page: response.data.page || 1,
        page_size: response.data.page_size || 10,
        total_pages: Math.ceil((response.data.total || 0) / pagination.pageSize),
      };
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: StaffCreateRequest) => {
      const response = await apiClient.post(endpoints.staff.create, data);
      return response.data;
    },
    onSuccess: () => {
      message.success('Співробітника створено');
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      handleCloseModal();
    },
    onError: (error: Error) => {
      message.error(error.message || 'Помилка створення');
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: number; data: StaffUpdateRequest }) => {
      const response = await apiClient.put(endpoints.staff.update(id), data);
      return response.data;
    },
    onSuccess: () => {
      message.success('Дані оновлено');
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      handleCloseModal();
    },
    onError: (error: Error) => {
      message.error(error.message || 'Помилка оновлення');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      // Soft delete - deactivate the staff member
      await apiClient.put(endpoints.staff.update(id), { is_active: false });
    },
    onSuccess: () => {
      message.success('Співробітника деактивовано');
      queryClient.invalidateQueries({ queryKey: ['staff'] });
    },
    onError: (error: Error) => {
      message.error(error.message || 'Помилка деактивації');
    },
  });

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingStaff(null);
    form.resetFields();
  };

  const handleEdit = (staff: Staff) => {
    setEditingStaff(staff);
    form.setFieldsValue({
      ...staff,
      term_start: staff.term_start ? format(new Date(staff.term_start), 'yyyy-MM-dd') : undefined,
      term_end: staff.term_end ? format(new Date(staff.term_end), 'yyyy-MM-dd') : undefined,
    });
    setIsModalOpen(true);
  };

  const handleReactivate = (staff: Staff) => {
    setReactivatingStaff(staff);
    setIsReactivateModalOpen(true);
  };

  const handleReactivateWithDocument = () => {
    if (!reactivatingStaff) return;
    setIsReactivateModalOpen(false);
    // Navigate to document creation with pre-filled staff data
    navigate('/documents', {
      state: {
        prefillStaff: {
          staff_id: reactivatingStaff.id,
          pib_nom: reactivatingStaff.pib_nom,
          position: reactivatingStaff.position,
          rate: reactivatingStaff.rate,
          employment_type: reactivatingStaff.employment_type,
          work_basis: reactivatingStaff.work_basis,
        },
        documentType: 'term_extension',
      },
    });
  };

  const handleReactivateWithScan = () => {
    if (!reactivatingStaff) return;
    setIsReactivateModalOpen(false);
    // Navigate to scan upload with pre-filled staff data
    navigate('/documents/upload', {
      state: {
        prefillStaff: {
          staff_id: reactivatingStaff.id,
          pib_nom: reactivatingStaff.pib_nom,
          position: reactivatingStaff.position,
          rate: reactivatingStaff.rate,
          employment_type: reactivatingStaff.employment_type,
          work_basis: reactivatingStaff.work_basis,
        },
      },
    });
  };

  const handleSubmit = async (values: StaffCreateRequest | StaffUpdateRequest) => {
    // Check head of department uniqueness only when editing (not for new employees)
    // New employees should use backend validation
    if (editingStaff) {
      const headPositions = ['head_of_department', 'acting_head'];
      if (values.position && headPositions.includes(values.position) && editingStaff.position !== values.position) {
        try {
          const response = await apiClient.get('/staff/expiring-soon', {
            params: { days: 365 },
          });
          const existingHead = response.data.items?.find((s: Staff) =>
            headPositions.includes(s.position) && s.is_active && s.id !== editingStaff.id
          );
          if (existingHead) {
            message.warning(`Посада завідувача кафедри вже зайнята: ${existingHead.pib_nom}`);
            return;
          }
        } catch (e) {
          // Ignore error, backend will validate
        }
      }
    }

    if (editingStaff) {
      updateMutation.mutate({ id: editingStaff.id, data: values as StaffUpdateRequest });
    } else {
      createMutation.mutate(values as StaffCreateRequest);
    }
  };

  const columns = [
    {
      title: 'ПІБ',
      key: 'name',
      render: (_: unknown, record: Staff) => (
        <Space>
          <span>{record.pib_nom}</span>
        </Space>
      ),
    },
    {
      title: 'Посади (сумісництво)',
      key: 'positions',
      render: (_: unknown, record: Staff) => {
        // Get all staff records with the same name
        const allRecords = staffData?.data || [];
        const sameNameRecords = allRecords.filter(r => r.pib_nom === record.pib_nom);

        if (sameNameRecords.length === 1) {
          const empType = record.employment_type;
          return (
            <Space size={4}>
              {empType === 'main' && <Tag color="blue">Основна</Tag>}
              {empType === 'internal' && <Tag color="orange">Внутр. сумісник</Tag>}
              {empType === 'external' && <Tag color="purple">Зовн. сумісник</Tag>}
              <Text style={{ textTransform: 'lowercase' }}>{getPositionLabel(record.position)}</Text>
              {record.rate !== 1 && <Tag>{record.rate} ст.</Tag>}
            </Space>
          );
        }

        return (
          <Space direction="vertical" size={2}>
            {sameNameRecords.map((r) => {
              const empType = r.employment_type;
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
                <div key={r.id} style={{ fontSize: 13 }}>
                  <Tag color={color}>{label}</Tag>
                  <span style={{ marginLeft: 4, textTransform: 'lowercase' }}>{getPositionLabel(r.position)}</span>
                  {r.rate !== 1 && <Tag style={{ marginLeft: 4 }}>{r.rate} ст.</Tag>}
                </div>
              );
            })}
          </Space>
        );
      },
    },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      key: 'status',
      render: (_: unknown, record: Staff) => {
        const status = record.is_active ? 'active' : 'inactive';
        const colors: Record<string, string> = {
          active: 'green',
          inactive: 'orange',
        };
        return <Tag color={colors[status]}>{status === 'active' ? 'Активний' : 'Неактивний'}</Tag>;
      },
    },
    {
      title: 'Термін роботи',
      key: 'term',
      render: (_: unknown, record: Staff) => {
        const startDate = record.term_start ? new Date(record.term_start) : null;
        const endDate = record.term_end ? new Date(record.term_end) : null;

        // Check if ending soon (within 1 month) for active employees
        const isEndingSoon = endDate && record.is_active;
        const daysUntilEnd = isEndingSoon ? Math.ceil((endDate.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)) : null;
        const warningShown = isEndingSoon && daysUntilEnd !== null && daysUntilEnd > 0 && daysUntilEnd <= 30;

        if (!startDate) return '-';

        return (
          <Space direction="vertical" size={0}>
            <Text>
              {format(startDate, 'dd.MM.yyyy')}
              {endDate ? ` - ${format(endDate, 'dd.MM.yyyy')}` : ' - необмежено'}
            </Text>
            {warningShown && (
              <Text type="danger" style={{ fontSize: 11 }}>
                ⚠ Закінчується через {daysUntilEnd} дн.
              </Text>
            )}
          </Space>
        );
      },
    },
    {
      title: 'Дії',
      key: 'actions',
      render: (_: unknown, record: Staff) => (
        <Space>
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/staff/${record.id}`)}
          />
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          {record.is_active ? (
            <Popconfirm
              title="Деактивувати співробітника?"
              description="Ця дія приховає співробітника та всі його дані"
              onConfirm={() => deleteMutation.mutate(record.id)}
              okText="Так"
              cancelText="Ні"
            >
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          ) : (
            <Button
              type="text"
              icon={<ReloadOutlined />}
              onClick={() => handleReactivate(record)}
              style={{ color: '#52c41a' }}
            >
              Реактивувати
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Співробітники</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setIsModalOpen(true)}
        >
          Додати
        </Button>
      </div>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="Пошук за ПІБ"
            prefix={<SearchOutlined />}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ width: 300 }}
            allowClear
          />
        </Space>

        <Table
          columns={columns}
          dataSource={(() => {
            // Group staff by name to show combined positions
            const allStaff = staffData?.data || [];
            const seenNames = new Set<string>();
            const uniqueStaff: Staff[] = [];

            for (const staff of allStaff) {
              if (!seenNames.has(staff.pib_nom)) {
                seenNames.add(staff.pib_nom);
                uniqueStaff.push(staff);
              }
            }
            return uniqueStaff;
          })()}
          loading={isLoading || deleteMutation.isPending}
          rowKey="id"
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: (() => {
              // Count unique names for pagination
              const allStaff = staffData?.data || [];
              const seenNames = new Set<string>();
              allStaff.forEach(s => seenNames.add(s.pib_nom));
              return seenNames.size;
            })(),
            onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
          }}
        />
      </Card>

      <Modal
        title={editingStaff ? 'Редагування' : 'Новий співробітник'}
        open={isModalOpen}
        onCancel={handleCloseModal}
        footer={null}
        destroyOnHidden
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          style={{ marginTop: 16 }}
        >
          <Row gutter={16}>
            <Col span={24}>
              <Form.Item
                name="pib_nom"
                label="ПІБ"
                rules={[
                  { required: true, message: 'Введіть ПІБ' },
                  {
                    validator: (_, value) => {
                      if (!value) return Promise.resolve();
                      const parts = value.trim().split(/\s+/);
                      if (parts.length !== 3) {
                        return Promise.reject(new Error("ПІБ має складатися з 3 частин: Прізвище Ім'я По батькові"));
                      }
                      // Pattern: starts with uppercase letter, contains only letters and hyphens
                      const pattern = /^[A-ZА-ЩЬЮЯЇІЄҐ][a-zA-Zа-щьюяїієҐ\-]+$/;
                      for (const part of parts) {
                        if (!pattern.test(part)) {
                          return Promise.reject(new Error(part + " - кожна частина ПІБ має починатися з великої літери та містити лише літери"));
                        }
                      }
                      return Promise.resolve();
                    },
                  },
                ]}
              >
                <Input placeholder="Прізвище Ім'я По батькові" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={24}>
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
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="term_start"
                label="Дата початку"
                rules={[{ required: true, message: 'Оберіть дату' }]}
              >
                <Input type="date" />
              </Form.Item>
            </Col>
            <Col span={12}>
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
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="email"
                label="Email"
              >
                <Input placeholder="Email" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="phone"
                label="Телефон"
              >
                <Input placeholder="Телефон" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="degree"
                label="Вчений ступінь"
              >
                <Select placeholder="Оберіть" allowClear>
                  <Option value="кн.">к.т..т.н.</Option>
                  <Option value="д.т.н.">д.т.н.</Option>
                  <Option value="к.е.н.">к.е.н.</Option>
                  <Option value="д.е.н.">д.е.н.</Option>
                  <Option value="к.ф.-м.н.">к.ф.-м.н.</Option>
                  <Option value="к.х.н.">к.х.н.</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
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
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
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
            </Col>
            <Col span={12}>
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
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="vacation_balance"
                label="Баланс відпусток"
                initialValue={0}
              >
                <Input type="number" min={0} max={365} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }} shouldUpdate>
            {() => {
              const errors = form.getFieldsError();
              const hasErrors = errors.some(e => e.errors.length > 0);
              // Check if all required fields have values
              const requiredFields = ['pib_nom', 'position', 'term_start', 'term_end', 'employment_type', 'work_basis', 'rate'];
              const values = form.getFieldsValue();
              const hasAllRequired = requiredFields.every(f => values[f] !== undefined && values[f] !== '' && values[f] !== null);
              const disabled = hasErrors || !hasAllRequired;

              return (
                <Space>
                  <Button onClick={handleCloseModal}>Скасувати</Button>
                  <Button
                    type="primary"
                    htmlType="submit"
                    disabled={disabled}
                    loading={createMutation.isPending || updateMutation.isPending}
                  >
                    {editingStaff ? 'Зберегти' : 'Створити'}
                  </Button>
                </Space>
              );
            }}
          </Form.Item>
        </Form>
      </Modal>

      {/* Reactivate Modal */}
      <Modal
        title="Реактивація співробітника"
        open={isReactivateModalOpen}
        onCancel={() => {
          setIsReactivateModalOpen(false);
          setReactivatingStaff(null);
        }}
        footer={null}
        destroyOnHidden
        width={600}
      >
        {reactivatingStaff && (
          <Space direction="vertical" style={{ width: '100%' }} size={16}>
            <Alert
              message="Для реактивації співробітника оберіть один з варіантів:"
              description="Збережено попередню ставку та посаду"
              type="info"
              showIcon
            />

            <div>
              <Text strong>Співробітник:</Text> {reactivatingStaff.pib_nom}
            </div>
            <div>
              <Text strong>Попередня посада:</Text> {getPositionLabel(reactivatingStaff.position)}
            </div>
            <div>
              <Text strong>Ставка:</Text> {reactivatingStaff.rate}
            </div>
            <div>
              <Text strong>Тип працевлаштування:</Text> {EMPLOYMENT_TYPE_LABELS[reactivatingStaff.employment_type as keyof typeof EMPLOYMENT_TYPE_LABELS]}
            </div>

            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Button
                type="primary"
                icon={<FileTextOutlined />}
                onClick={handleReactivateWithDocument}
                block
                size="large"
              >
                Створити документ (продовження контракту)
              </Button>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Перейти до створення документу з попередньо заповненими даними
              </Text>

              <Button
                icon={<UploadOutlined />}
                onClick={handleReactivateWithScan}
                block
                size="large"
              >
                Завантажити скан договору
              </Button>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Завантажити скан для створення нового запису про працевлаштування
              </Text>
            </Space>
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default StaffList;
