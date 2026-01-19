import React from 'react';
import { Row, Col, Card, Statistic, Table, Tag, Typography, Button, List } from 'antd';
import {
  TeamOutlined,
  FileTextOutlined,
  CalendarOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { useAuthStore } from '../../stores/index';
import { DashboardStats, RecentDocument } from '../../api/types';
import { format } from 'date-fns';

const { Title, Text } = Typography;

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.dashboard.stats);
      return response.data;
    },
  });

  const { data: recentDocuments, isLoading: documentsLoading } = useQuery<RecentDocument[]>({
    queryKey: ['recent-documents'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.documents.list, {
        params: { page_size: 5 },
      });
      return response.data.data || [];
    },
  });

  const getStatusColor = (status: string) => {
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
    return colors[status] || 'default';
  };

  const documentColumns = [
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: 'Type',
      dataIndex: 'document_type',
      key: 'document_type',
    },
    {
      title: 'Staff',
      dataIndex: 'staff_name',
      key: 'staff_name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {status.replace(/_/g, ' ').toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => format(new Date(date), 'MMM dd, yyyy'),
    },
    {
      title: 'Action',
      key: 'action',
      render: (_: unknown, record: RecentDocument) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/documents/${record.id}`)}
        >
          View
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Title level={3} style={{ marginBottom: 24 }}>
        Welcome back, {user?.first_name}!
      </Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Staff"
              value={stats?.total_staff || 0}
              prefix={<TeamOutlined style={{ color: '#1890ff' }} />}
              loading={statsLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Pending Documents"
              value={stats?.pending_documents || 0}
              prefix={<FileTextOutlined style={{ color: '#faad14' }} />}
              loading={statsLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Active Staff"
              value={stats?.active_staff || 0}
              prefix={<TeamOutlined style={{ color: '#52c41a' }} />}
              loading={statsLoading}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card
            title="Recent Documents"
            extra={
              <Button type="link" onClick={() => navigate('/documents')}>
                View All
              </Button>
            }
          >
            <Table
              columns={documentColumns}
              dataSource={recentDocuments}
              loading={documentsLoading}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Quick Actions">
            <List
              size="small"
              dataSource={[
                { icon: <FileTextOutlined />, label: 'Create Document', path: '/documents/create' },
                { icon: <CalendarOutlined />, label: 'View Schedule', path: '/schedule' },
                { icon: <TeamOutlined />, label: 'Manage Staff', path: '/staff' },
              ]}
              renderItem={(item) => (
                <List.Item>
                  <Button
                    type="link"
                    icon={item.icon}
                    onClick={() => navigate(item.path)}
                  >
                    {item.label}
                  </Button>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
