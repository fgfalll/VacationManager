import React, { useState, useEffect } from 'react';
import {
  Table,
  Card,
  Button,
  Input,
  Space,
  Tag,
  Select,
  DatePicker,
  Typography,
  Dropdown,
  message,
  Popconfirm,
  Tooltip,
  Radio,
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  EyeOutlined,
  EditOutlined,
  DeleteOutlined,
  DownloadOutlined,
  DownOutlined,
  FilterOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { Document, DocumentStatus, PaginatedResponse } from '../../api/types';
import { format } from 'date-fns';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;


import ResolveStaleModal from './ResolveStaleModal';

// Ukrainian status labels for documents - full workflow (no legacy)
const STATUS_LABELS: Record<string, string> = {
  draft: 'Чернетка',
  signed_by_applicant: 'Підписав заявник',
  approved_by_dispatcher: 'Погоджено диспетчером',
  signed_dep_head: 'Підписано зав. кафедри',
  agreed: 'Погоджено',
  signed_rector: 'Підписано ректором',
  scanned: 'Відсконовано',
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

const normalizeStatus = (status: string) => status?.toLowerCase().replace(/ /g, '_') || '';

// Transform backend response to frontend format
const transformDocument = (doc: any) => ({
  ...doc,
  start_date: doc.date_start,
  end_date: doc.date_end,
  total_days: doc.days_count,
  is_blocked: doc.is_blocked || false,
  blocked_reason: doc.blocked_reason,
  file_scan_path: doc.file_scan_path,
  staff: doc.staff ? {
    first_name: doc.staff.pib_nom?.split(' ')[0] || '',
    last_name: doc.staff.pib_nom?.split(' ').slice(1).join(' ') || '',
  } : undefined,
});

const DocumentList: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | undefined>();
  const [filterParam, setFilterParam] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[Date, Date] | undefined>();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });
  const [viewMode, setViewMode] = useState<'all' | 'stale'>('all');
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);

  // Sync status filter and filter param with URL params
  useEffect(() => {
    const statusParam = searchParams.get('status');
    const filter = searchParams.get('filter');

    if (statusParam) {
      setStatusFilter(statusParam as DocumentStatus);
      setFilterParam(undefined);
    } else {
      setStatusFilter(undefined);
    }

    if (filter) {
      setFilterParam(filter);
    }
  }, [searchParams]);

  // Update URL when status filter changes
  const handleStatusChange = (value: DocumentStatus | undefined) => {
    setStatusFilter(value);
    setFilterParam(undefined);
    setPagination({ ...pagination, current: 1 }); // Reset to first page

    // Clear existing params and set new status
    searchParams.delete('filter');
    if (value) {
      searchParams.set('status', value);
    } else {
      searchParams.delete('status');
    }
    setSearchParams(searchParams);
  };

  const { data: documentsData, isLoading } = useQuery<PaginatedResponse<Document>>({
    queryKey: ['documents', pagination, searchTerm, statusFilter, dateRange, filterParam, viewMode],
    queryFn: async () => {
      const endpoint = viewMode === 'stale' ? endpoints.documents.stale : endpoints.documents.list;
      const response = await apiClient.get(endpoint, {
        params: {
          page: pagination.current,
          page_size: pagination.pageSize,
          search: searchTerm,
          status: statusFilter,
          filter: filterParam,
          start_date: dateRange?.[0] ? format(dateRange[0], 'yyyy-MM-dd') : undefined,
          end_date: dateRange?.[1] ? format(dateRange[1], 'yyyy-MM-dd') : undefined,
        },
      });
      // Transform backend response
      return {
        ...response.data,
        data: response.data.data.map(transformDocument),
      };
    },
  });

  // Reset pagination when view mode changes
  const handleViewModeChange = (mode: 'all' | 'stale') => {
    setViewMode(mode);
    setPagination({ ...pagination, current: 1 });
  };


  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(endpoints.documents.delete(id));
    },
    onSuccess: () => {
      message.success('Document deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to delete document');
    },
  });

  const getStatusColor = (status: DocumentStatus) => {
    const normalized = normalizeStatus(status);
    return STATUS_COLORS[normalized] || 'default';
  };

  const getStatusLabel = (status: DocumentStatus) => {
    const normalized = normalizeStatus(status);
    return STATUS_LABELS[normalized] || status.replace(/_/g, ' ').toUpperCase();
  };

  const handleResolve = (docId: number) => {
    setSelectedDocId(docId);
    setResolveModalOpen(true);
  };

  const columns = [
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: 'Staff',
      key: 'staff',
      render: (_: unknown, record: Document) => (
        <span>{record.staff?.first_name} {record.staff?.last_name}</span>
      ),
    },
    {
      title: 'Type',
      dataIndex: ['document_type', 'name'],
      key: 'document_type',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: DocumentStatus) => (
        <Tag color={getStatusColor(status)}>{getStatusLabel(status)}</Tag>
      ),
    },
    {
      title: 'Dates',
      key: 'dates',
      render: (_: unknown, record: Document) => {
        const start = record.start_date ? format(new Date(record.start_date), 'MMM dd') : '-';
        const end = record.end_date ? format(new Date(record.end_date), 'MMM dd, yyyy') : '-';
        return (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {start} - {end}
            <br />
            ({record.total_days || 0} days)
          </Text>
        );
      },
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => date ? format(new Date(date), 'MMM dd, yyyy') : '-',
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => date ? format(new Date(date), 'MMM dd, yyyy') : '-',
    },
    ...(viewMode === 'stale' ? [{
      title: 'Days Stale',
      key: 'stale_info',
      render: (_: unknown, record: Document) => (
        <Space direction="vertical" size={0}>
          <Tag color="error">{record.stale_info?.days_stale || 0} days</Tag>
          {record.stale_info?.notification_count > 0 && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              {record.stale_info.notification_count} warnings
            </Text>
          )}
        </Space>
      ),
    }] : []),
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_: unknown, record: Document) => {
        const isBlocked = record.is_blocked;
        const isStale = viewMode === 'stale';

        if (isStale) {
          return (
            <Button
              type="primary"
              danger
              onClick={() => handleResolve(record.id)}
            >
              Resolve
            </Button>
          );
        }

        // Standard actions
        const items: any[] = [
          {
            key: 'view',
            icon: <EyeOutlined />,
            label: 'View',
            onClick: () => navigate(`/documents/${record.id}`),
          },
          {
            key: 'download',
            icon: <DownloadOutlined />,
            label: 'Download PDF',
            onClick: () => window.open(endpoints.documents.download(record.id), '_blank'),
          },
        ];

        // Only show edit/delete for draft documents that are NOT blocked
        if (record.status === 'draft' && !isBlocked) {
          items.push({
            key: 'edit',
            icon: <EditOutlined />,
            label: 'Edit',
            onClick: () => navigate(`/documents/${record.id}/edit`),
          });
          items.push({
            key: 'delete',
            icon: <DeleteOutlined />,
            label: 'Delete',
            danger: true,
            onClick: () => deleteMutation.mutate(record.id),
          } as any);
        }

        return (
          <Space size="small">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => navigate(`/documents/${record.id}`)}
            />
            {isBlocked ? (
              <Tooltip title={record.blocked_reason || 'Документ заблоковано'}>
                <Button
                  type="text"
                  icon={<LockOutlined />}
                  disabled
                  style={{ cursor: 'not-allowed' }}
                />
              </Tooltip>
            ) : (
              <Dropdown menu={{ items }} trigger={['click']}>
                <Button type="text" icon={<DownOutlined />} />
              </Dropdown>
            )}
          </Space>
        );
      },
    },
  ];



  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Title level={3} style={{ margin: 0 }}>Документи</Title>
          <Radio.Group value={viewMode} onChange={(e) => handleViewModeChange(e.target.value)} buttonStyle="solid">
            <Radio.Button value="all">Всі документи</Radio.Button>
            <Radio.Button value="stale">Attention Needed</Radio.Button>
          </Radio.Group>
        </Space>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate('/documents/create')}
        >
          Створити документ
        </Button>
      </div>

      <Card>
        <Space style={{ marginBottom: 16, flexWrap: 'wrap' }}>
          <Input
            placeholder="Пошук за назвою"
            prefix={<SearchOutlined />}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Select
            placeholder="Фільтр за статусом"
            value={statusFilter}
            onChange={handleStatusChange}
            allowClear
            style={{ width: 180 }}
          >
            <Select.Option value="draft">Draft</Select.Option>
            <Select.Option value="signed_by_applicant">Signed by Applicant</Select.Option>
            <Select.Option value="approved_by_dispatcher">Approved by Dispatcher</Select.Option>
            <Select.Option value="signed_dep_head">Signed by Dept Head</Select.Option>
            <Select.Option value="agreed">Agreed</Select.Option>
            <Select.Option value="signed_rector">Signed by Rector</Select.Option>
            <Select.Option value="scanned">Scanned</Select.Option>
            <Select.Option value="processed">Processed</Select.Option>
          </Select>
          <RangePicker
            value={dateRange ? [dateRange[0] as any, dateRange[1] as any] : undefined}
            onChange={(dates) => {
              if (dates && dates[0] && dates[1]) {
                setDateRange([dates[0].toDate(), dates[1].toDate()]);
              } else {
                setDateRange(undefined);
              }
            }}
          />
        </Space>

        <Table
          columns={columns}
          dataSource={documentsData?.data}
          loading={isLoading || deleteMutation.isPending}
          rowKey="id"
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: documentsData?.total || 0,
            onChange: (page, pageSize) => setPagination({ current: page, pageSize }),
          }}
        />
      </Card>

      <ResolveStaleModal
        open={resolveModalOpen}
        onCancel={() => {
          setResolveModalOpen(false);
          setSelectedDocId(null);
        }}
        documentId={selectedDocId}
        onSuccess={() => {
          setResolveModalOpen(false);
          setSelectedDocId(null);
          queryClient.invalidateQueries({ queryKey: ['documents'] });
        }}
      />
    </div>
  );
};

export default DocumentList;
