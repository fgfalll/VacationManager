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
} from 'antd';
import { PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
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

const { Title } = Typography;
const { Option } = Select;

const StaffList: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
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
      await apiClient.delete(endpoints.staff.delete(id));
    },
    onSuccess: () => {
      message.success('Співробітника видалено');
      queryClient.invalidateQueries({ queryKey: ['staff'] });
    },
    onError: (error: Error) => {
      message.error(error.message || 'Помилка видалення');
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

  const handleSubmit = async (values: StaffCreateRequest | StaffUpdateRequest) => {
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
      title: 'Посада',
      dataIndex: 'position',
      key: 'position',
      render: (value: string) => getPositionLabel(value),
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
      title: 'Дата початку',
      dataIndex: 'term_start',
      key: 'term_start',
      render: (date: string) => date ? format(new Date(date), 'dd.MM.yyyy') : '-',
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
          <Popconfirm
            title="Видалити співробітника?"
            onConfirm={() => deleteMutation.mutate(record.id)}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
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
          dataSource={staffData?.data}
          loading={isLoading || deleteMutation.isPending}
          rowKey="id"
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: staffData?.total || 0,
            onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
          }}
        />
      </Card>

      <Modal
        title={editingStaff ? 'Редагування' : 'Новий співробітник'}
        open={isModalOpen}
        onCancel={handleCloseModal}
        footer={null}
        destroyOnClose
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
                rules={[{ required: true, message: 'Введіть ПІБ' }]}
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
                rules={[{ required: true, message: 'Оберіть дату' }]}
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
                rules={[{ required: true, message: 'Введіть ставку' }]}
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

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={handleCloseModal}>Скасувати</Button>
              <Button
                type="primary"
                htmlType="submit"
                loading={createMutation.isPending || updateMutation.isPending}
              >
                {editingStaff ? 'Зберегти' : 'Створити'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default StaffList;
