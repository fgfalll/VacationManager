import React from 'react';
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
} from 'antd';
import {
  ArrowLeftOutlined,
} from '@ant-design/icons';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { Staff, Document, DailyAttendance, StaffHistoryItem } from '../../api/types';
import { getPositionLabel, getActionTypeLabel, getAttendanceCodeLabel } from '../../api/constants';
import { format } from 'date-fns';

const { Title, Text } = Typography;

const StaffDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: staff, isLoading: staffLoading } = useQuery<Staff>({
    queryKey: ['staff', id],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.detail(Number(id)));
      return response.data;
    },
    enabled: !!id,
  });

  const { data: documents } = useQuery<Document[]>({
    queryKey: ['staff-documents', id],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.documents(Number(id)));
      return response.data;
    },
    enabled: !!id,
  });

  const { data: attendance } = useQuery<DailyAttendance[]>({
    queryKey: ['staff-attendance', id],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.attendance(Number(id)));
      return response.data;
    },
    enabled: !!id,
  });

  const { data: history } = useQuery<StaffHistoryItem[]>({
    queryKey: ['staff-history', id],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.history(Number(id)));
      return response.data;
    },
    enabled: !!id,
  });

  const documentColumns = [
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
    },
    {
      title: 'Type',
      dataIndex: 'document_type',
      key: 'document_type',
      render: (type: { name: string }) => type?.name || '-',
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
      render: (_: unknown, record: Document) => {
        const startDate = record.start_date ? new Date(record.start_date) : null;
        const endDate = record.end_date ? new Date(record.end_date) : null;

        if (!startDate || !endDate || isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
          return <Text type="secondary">-</Text>;
        }

        return (
          <Text type="secondary">
            {format(startDate, 'MMM dd')} - {format(endDate, 'MMM dd, yyyy')}
          </Text>
        );
      },
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
              title: 'Hours',
              dataIndex: 'hours',
              key: 'hours',
              render: (hours: number) => hours?.toString() || '0',
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

  if (!staff) {
    return <Card><Text type="secondary">Staff not found</Text></Card>;
  }

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
              <Text type="secondary">{getPositionLabel(staff.position)}</Text>
              <Tag color={staff.status === 'active' ? 'green' : 'orange'}>
                {staff.status?.toUpperCase() || 'N/A'}
              </Tag>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={18}>
          <Card>
            <Descriptions title="Staff Information" column={{ xs: 1, sm: 2 }}>
              <Descriptions.Item label="Email">{staff.email || '-'}</Descriptions.Item>
              <Descriptions.Item label="Phone">{staff.phone || '-'}</Descriptions.Item>
              <Descriptions.Item label="Position">{getPositionLabel(staff.position)}</Descriptions.Item>
              <Descriptions.Item label="Start Date">
                {staff.start_date ? format(new Date(staff.start_date), 'MMMM dd, yyyy') : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="End Date">
                {staff.end_date ? format(new Date(staff.end_date), 'MMMM dd, yyyy') : '-'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card style={{ marginTop: 16 }}>
            <Tabs items={tabItems} />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default StaffDetail;
