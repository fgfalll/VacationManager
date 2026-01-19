import React, { useState } from 'react';
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
import { useNavigate } from 'react-router-dom';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { Document, DocumentStatus, PaginatedResponse } from '../../api/types';
import { format } from 'date-fns';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

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
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | undefined>();
  const [dateRange, setDateRange] = useState<[Date, Date] | undefined>();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });

  const { data: documentsData, isLoading } = useQuery<PaginatedResponse<Document>>({
    queryKey: ['documents', pagination, searchTerm, statusFilter, dateRange],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.documents.list, {
        params: {
          page: pagination.current,
          page_size: pagination.pageSize,
          search: searchTerm,
          status: statusFilter,
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
    const colors: Record<DocumentStatus, string> = {
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
    } as any;
    return colors[status] || 'default';
  };

  const getStatusLabel = (status: DocumentStatus) => {
    return status.replace(/_/g, ' ').toUpperCase();
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
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_: unknown, record: Document) => {
        const isBlocked = record.is_blocked;

        const items = [
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
          });
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
        <Title level={3} style={{ margin: 0 }}>Documents</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate('/documents/create')}
        >
          Create Document
        </Button>
      </div>

      <Card>
        <Space style={{ marginBottom: 16, flexWrap: 'wrap' }}>
          <Input
            placeholder="Search by title"
            prefix={<SearchOutlined />}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Select
            placeholder="Filter by status"
            value={statusFilter}
            onChange={setStatusFilter}
            allowClear
            style={{ width: 180 }}
          >
            <Select.Option value="draft">Draft</Select.Option>
            <Select.Option value="on_signature">On Signature</Select.Option>
            <Select.Option value="agreed">Agreed</Select.Option>
            <Select.Option value="signed">Signed</Select.Option>
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
    </div>
  );
};

export default DocumentList;
