import React, { useState } from 'react';
import { Row, Col, Card, Table, Tag, Typography, Button, Tooltip, Space } from 'antd';
import {
  CalendarOutlined,
  TeamOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  UpOutlined,
  DownOutlined,

} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { useAuthStore } from '../../stores/index';
import { Document } from '../../api/types';
import { format } from 'date-fns';
import { DOCUMENT_TYPE_LABELS } from '../../api/constants';
import ResolveStaleModal from '../documents/ResolveStaleModal';

const { Title, Text } = Typography;

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

const STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  signed_by_applicant: 'blue',
  approved_by_dispatcher: 'cyan',
  signed_dep_head: 'green',
  agreed: 'orange',
  signed_rector: 'purple',
  scanned: 'magenta',
  processed: 'success',
};

// Normalize status from API (may be uppercase or have spaces)
const normalizeStatus = (s: string) => s?.toLowerCase().replace(/ /g, '_') || '';



const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [showStaleTable, setShowStaleTable] = useState(true);
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);

  // Document counts by status
  const { data: docsData } = useQuery({
    queryKey: ['documents-all'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.documents.list, {
        params: { page_size: 100 },
      });
      return response.data || { data: [], total: 0 };
    },
  });

  // Calculate counts from documents data (normalize status to lowercase for comparison)
  const docItems = docsData?.data || [];

  const draftCount = docItems.filter((d: Document) => normalizeStatus(d.status) === 'draft').length;

  // Pending = all documents that are signed by someone but not yet processed
  // This includes: signed_by_applicant, approved_by_dispatcher, signed_dep_head, agreed, signed_rector
  const pendingStatuses = [
    'signed_by_applicant', 'approved_by_dispatcher', 'signed_dep_head', 'agreed', 'signed_rector'
  ];
  const pendingCount = docItems.filter((d: Document) =>
    pendingStatuses.includes(normalizeStatus(d.status))
  ).length;

  // Not confirmed documents (signed but no scan)
  const { data: notConfirmedData } = useQuery({
    queryKey: ['documents-not-confirmed'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.documents.list, {
        params: { filter: 'not_confirmed', page_size: 100 },
      });
      return response.data?.total || 0;
    },
  });
  const notConfirmedCount = notConfirmedData ?? 0;

  // Expiring contracts count
  const { data: expiringData } = useQuery({
    queryKey: ['dashboard-contract-expiring'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.dashboard.contractExpiring);
      return response.data.count || 0;
    },
  });
  const expiringCount = expiringData ?? 0;

  // Documents with problems (stale documents)
  const { data: staleData, isLoading: staleLoading } = useQuery({
    queryKey: ['documents-stale'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.documents.stale);
      return response.data || { data: [], total: 0 };
    },
  });
  const staleDocuments = staleData ?? { data: [], total: 0 };

  // Recent documents
  const { data: recentData, isLoading: documentsLoading } = useQuery({
    queryKey: ['recent-documents'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.documents.list, {
        params: { page_size: 20 },
      });
      return response.data || { data: [], total: 0 };
    },
  });
  const recentDocuments = recentData ?? { data: [], total: 0 };

  const getStatusLabel = (status: string): string => {
    const normalized = normalizeStatus(status);
    return STATUS_LABELS[normalized] || status.replace(/_/g, ' ').toUpperCase();
  };

  const getStatusColor = (status: string): string => {
    const normalized = normalizeStatus(status);
    return STATUS_COLORS[normalized] || 'default';
  };

  const documentColumns = [
    {
      title: 'Документ',
      dataIndex: 'title',
      key: 'title',
      render: (text: string, record: Document) => (
        <Button type="link" onClick={() => navigate(`/documents/${record.id}`)} style={{ padding: 0 }}>
          {DOCUMENT_TYPE_LABELS[text] || text}
        </Button>
      ),
    },
    {
      title: 'Працівник',
      dataIndex: 'staff_name',
      key: 'staff_name',
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {getStatusLabel(status)}
        </Tag>
      ),
    },
    {
      title: 'Дата',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => format(new Date(date), 'dd.MM.yyyy'),
    },
  ];

  const staleColumns = [
    {
      title: 'Документ',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      render: (text: string, record: Document) => (
        <Tooltip title={DOCUMENT_TYPE_LABELS[text] || text} placement="topLeft">
          <Button
            type="link"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/documents/${record.id}`);
            }}
            style={{ padding: 0, maxWidth: 190, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          >
            {DOCUMENT_TYPE_LABELS[text] || text}
          </Button>
        </Tooltip>
      ),
    },
    {
      title: 'Працівник',
      dataIndex: 'staff_name',
      key: 'staff_name',
      width: 130,
      render: (text: string, record: Document) => (
        <Tooltip title={`${text} - ${record.staff_position || ''}`} placement="topLeft">
          <div>
            <div style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {text}
            </div>
            <div style={{ fontSize: '11px', color: '#999', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {record.staff_position || ''}
            </div>
          </div>
        </Tooltip>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {getStatusLabel(status)}
        </Tag>
      ),
    },

    {
      title: 'Сповіщень',
      key: 'notifications',
      width: 90,
      render: (_: unknown, record: Document) => {
        const count = record.stale_info?.notification_count ?? 0;
        return <Tag color={count >= 3 ? 'red' : count > 0 ? 'orange' : 'default'}>{count}/3</Tag>;
      },
    },
    {
      title: 'Пояснення',
      key: 'explanation',
      width: 150,
      render: (_: unknown, record: Document) => {
        const explanation = record.stale_info?.stale_explanation;
        if (!explanation) {
          return <Text type="secondary">-</Text>;
        }
        return (
          <Tooltip title={explanation} placement="topLeft">
            <span style={{ display: 'block', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {explanation}
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: 'Дії',
      key: 'actions',
      width: 100,
      fixed: 'right' as const,
      render: (_: unknown, record: Document) => {
        const count = record.stale_info?.notification_count ?? 0;
        // Button enabled only if count >= 3 or if user wants to force it?
        // Requirement: "should be avalieble only after some eligable number of сповіщень"
        const isEligible = count >= 3;

        return (
          <Tooltip title={isEligible ? "Вирішити проблему" : `Доступно через ${3 - count} сповіщень`}>
            <Button
              type="primary"
              size="small"
              disabled={!isEligible}
              icon={<ExclamationCircleOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                setSelectedDocumentId(record.id);
                setResolveModalOpen(true);
              }}
            >
              Дії
            </Button>
          </Tooltip>
        );
      },
    },
  ];



  // Handler for deleting stale documents directly


  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>Ласкаво просимо, {user?.first_name}!</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/documents/create')}>
          Створити документ
        </Button>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={16}>
          <Card title="Документів сьогодні" extra={<CalendarOutlined />}>
            <Row gutter={[12, 12]}>
              <Col xs={24} sm={8}>
                <Card
                  size="small"
                  hoverable
                  onClick={() => navigate('/documents?status=draft')}
                  style={{ textAlign: 'center', backgroundColor: '#fafafa' }}
                >
                  <div style={{ fontSize: 32, fontWeight: 'bold', color: '#8c8c8f' }}>{draftCount}</div>
                  <div style={{ color: '#666' }}>Чернетки</div>
                </Card>
              </Col>
              <Col xs={24} sm={8}>
                <Card
                  size="small"
                  hoverable
                  onClick={() => navigate('/documents?filter=pending')}
                  style={{ textAlign: 'center', backgroundColor: '#fffbe6' }}
                >
                  <div style={{ fontSize: 32, fontWeight: 'bold', color: '#faad14' }}>{pendingCount}</div>
                  <div style={{ color: '#666' }}>На підписі</div>
                </Card>
              </Col>
              <Col xs={24} sm={8}>
                <Card
                  size="small"
                  hoverable
                  onClick={() => navigate('/documents?filter=not_confirmed')}
                  style={{ textAlign: 'center', backgroundColor: '#fff1f0' }}
                >
                  <div style={{ fontSize: 32, fontWeight: 'bold', color: '#ff4d4f' }}>{notConfirmedCount}</div>
                  <div style={{ color: '#666' }}>Не підтв.</div>
                </Card>
              </Col>
            </Row>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card
            title="Контракт скоро закінчується"
            extra={<TeamOutlined />}
            hoverable
            onClick={() => navigate('/staff?filter=expiring')}
            style={{ height: '100%' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
              <span style={{ fontSize: 48, fontWeight: 'bold', color: expiringCount > 0 ? '#ff4d4f' : '#52c41a' }}>
                {expiringCount || 0}
              </span>
            </div>
          </Card>
        </Col>
      </Row>

      {staleDocuments.data && staleDocuments.data.length > 0 && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24}>
            <Card
              title={
                <Space>
                  <ExclamationCircleOutlined style={{ marginRight: 8, color: '#faad14' }} />
                  <span>Документи з проблемами</span>
                  <Tag color="red">{staleDocuments.data.length}</Tag>
                </Space>
              }
              extra={
                <Button
                  type="text"
                  size="small"
                  icon={showStaleTable ? <UpOutlined /> : <DownOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowStaleTable(!showStaleTable);
                  }}
                />
              }
              bodyStyle={{ padding: showStaleTable ? undefined : 0 }}
            >
              {showStaleTable && (
                <Table
                  columns={staleColumns}
                  dataSource={staleDocuments.data}
                  loading={staleLoading}
                  rowKey="id"
                  pagination={false}
                  size="small"
                  scroll={{ x: 900 }}
                  onRow={(record) => ({
                    onClick: () => navigate(`/documents/${record.id}`),
                    style: { cursor: 'pointer' },
                  })}
                  rowClassName={() => 'clickable-row'}
                />
              )}
            </Card>
          </Col>
        </Row>
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <Card
            title="Останні документи"
            extra={
              <Button type="link" onClick={() => navigate('/documents')}>
                Всі документи
              </Button>
            }
          >
            <Table
              columns={documentColumns}
              dataSource={recentDocuments.data?.filter((d: Document) => {
                const s = normalizeStatus(d.status);
                return s !== 'processed' && s !== 'scanned';
              })}
              loading={documentsLoading}
              rowKey="id"
              pagination={false}
              size="small"
              onRow={(record) => ({
                onClick: () => navigate(`/documents/${record.id}`),
                style: { cursor: 'pointer' },
              })}
            />
          </Card>
        </Col>
      </Row>

      <ResolveStaleModal
        open={resolveModalOpen}
        onCancel={() => {
          setResolveModalOpen(false);
          setSelectedDocumentId(null);
        }}
        documentId={selectedDocumentId}
        staleLockCount={staleDocuments.data?.find((d: any) => d.id === selectedDocumentId)?.stale_info?.stale_lock_count || 0}
        onSuccess={() => {
          setResolveModalOpen(false);
          setSelectedDocumentId(null);
          queryClient.invalidateQueries({ queryKey: ['documents-stale'] });
          queryClient.invalidateQueries({ queryKey: ['documents-all'] });
        }}
      />
    </div>
  );
};

export default Dashboard;

<style jsx global>{`
  .clickable-row:hover {
    background-color: #fffbe6 !important;
  }
`}</style>
