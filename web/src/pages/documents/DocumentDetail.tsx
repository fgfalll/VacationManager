import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Row,
  Col,
  Typography,
  Tag,
  Button,
  Space,
  Timeline,
  Descriptions,
  Modal,
  Upload,
  message,
  Divider,
  Alert,
  Badge,
  Tooltip,
  Input,
  Tabs,
} from 'antd';
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  UploadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  EditOutlined,
  SendOutlined,
  FileTextOutlined,
  SafetyCertificateOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { Document } from '../../api/types';
import { format } from 'date-fns';

const { Title, Text, Paragraph } = Typography;

const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-';
  try {
    return format(new Date(dateStr), 'dd MMMM yyyy');
  } catch {
    return '-';
  }
};

const formatDateForDocument = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '____';
  try {
    return format(new Date(dateStr), 'dd MMMM yyyy');
  } catch {
    return '____';
  }
};

const formatDateTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-';
  try {
    return format(new Date(dateStr), 'MMM dd, yyyy HH:mm');
  } catch {
    return '-';
  }
};

// Component to render HTML document content
const DocumentContent: React.FC<{ document: Document | undefined }> = ({ document }) => {
  if (!document) {
    return (
      <Card type="inner" style={{ textAlign: 'center', padding: 40 }}>
        <FileTextOutlined style={{ fontSize: 48, color: '#bfbfbf', marginBottom: 16 }} />
        <Title level={4}>Document Not Found</Title>
        <Paragraph type="secondary">
          The document could not be loaded.
        </Paragraph>
      </Card>
    );
  }

  // Use rendered_html from backend (uses proper templates)
  if (document.rendered_html && typeof document.rendered_html === 'string') {
    return (
      <div
        className="document-container"
        style={{
          background: 'white', // Changed from gray to white
          padding: '0',        // Removed padding
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          minHeight: '600px'
        }}
      >
        <iframe
          title="Document Preview"
          srcDoc={document.rendered_html}
          style={{
            width: '100%', // Use full width of container
            maxWidth: '21cm', // Keep A4 max width constraint centrally
            height: '29.7cm', // Initial height (A4)
            minHeight: '1200px', // Ensure it's tall enough to not scroll internally
            border: 'none',
            background: 'white',
            // Removed box-shadow
          }}
          sandbox="allow-same-origin"
        />
      </div>
    );
  }

  return (
    <Card type="inner" style={{ textAlign: 'center', padding: 40 }}>
      <FileTextOutlined style={{ fontSize: 48, color: '#bfbfbf', marginBottom: 16 }} />
      <Title level={4}>Document content not available</Title>
      <Paragraph type="secondary">
        The document has not been rendered yet.
      </Paragraph>
    </Card>
  );
};

const DocumentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isWorkflowModalOpen, setIsWorkflowModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [workflowAction, setWorkflowAction] = useState('');
  const [comment, setComment] = useState('');

  const { data: document, isLoading } = useQuery<Document>({
    queryKey: ['document', id],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.documents.detail(Number(id)));
      // Transform backend response to match frontend types
      const data = response.data;
      return {
        ...data,
        start_date: data.date_start,
        end_date: data.date_end,
        total_days: data.days_count,
        staff_name: data.staff_name,
        staff_position: data.staff_position,
        doc_type: data.doc_type,
        payment_period: data.payment_period,
        rendered_html: data.rendered_html,
        from_archive: data.from_archive || false,
        signatories: data.signatories || [],
        archive_metadata_path: data.archive_metadata_path,
        document_type: {
          name: data.document_type?.name || data.doc_type || '',
        },
      };
    },
    enabled: !!id,
  });

  const workflowMutation = useMutation({
    mutationFn: async ({ action, comment }: { action: string; comment?: string }) => {
      await apiClient.post(endpoints.documents.workflow(Number(id), action), { comment });
    },
    onSuccess: () => {
      message.success('Action completed successfully');
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      setIsWorkflowModalOpen(false);
      setComment('');
    },
    onError: (error: Error) => {
      message.error(error.message || 'Action failed');
    },
  });

  const uploadScanMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      await apiClient.post(endpoints.documents.uploadScan(Number(id)), formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    },
    onSuccess: () => {
      message.success('Scan uploaded successfully');
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      setIsUploadModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(error.message || 'Upload failed');
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

      // Keep legacy/other mappings just in case
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

  const getStatusLabel = (status: string) => {
    return status.replace(/_/g, ' ').toUpperCase();
  };

  const getWorkflowActions = (status: string) => {
    const actions: { key: string; label: string; icon: React.ReactNode; danger?: boolean }[] = [];
    if (['pending_hr', 'pending_director', 'pending_manager', 'pending_signature'].includes(status)) {
      actions.push({ key: 'approve', label: 'Approve', icon: <CheckCircleOutlined /> });
      actions.push({ key: 'reject', label: 'Reject', icon: <CloseCircleOutlined />, danger: true });
    }
    if (status === 'pending_signature' || status === 'approved') {
      actions.push({ key: 'cancel', label: 'Cancel', icon: <CloseCircleOutlined />, danger: true });
    }
    return actions;
  };

  if (isLoading) {
    return <Card loading={true} />;
  }

  if (!document) {
    return <Card><Text type="secondary">Document not found</Text></Card>;
  }

  return (
    <div>
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/documents')}
        style={{ marginBottom: 16, paddingLeft: 0 }}
      >
        Back to Documents
      </Button>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card
            title={
              <Space>
                <Text strong style={{ fontSize: 18 }}>{document.title}</Text>
                <Tag color={getStatusColor(document.status)}>{getStatusLabel(document.status)}</Tag>
                {document.from_archive && (
                  <Tooltip title="Дані завантажено з архіву (snapshot)">
                    <Tag icon={<SafetyCertificateOutlined />} color="green">Archived</Tag>
                  </Tooltip>
                )}
              </Space>
            }
            extra={
              <Space>
                <Button icon={<DownloadOutlined />} onClick={() => window.open(endpoints.documents.download(document.id), '_blank')}>
                  Download PDF
                </Button>
                {document.status === 'draft' && (
                  <Button type="primary" icon={<SendOutlined />} onClick={() => workflowMutation.mutate({ action: 'submit' })}>
                    Submit
                  </Button>
                )}
              </Space>
            }
          >
            <Tabs
              items={[
                {
                  key: 'document',
                  label: <span><FileTextOutlined /> Document</span>,
                  children: (
                    <div style={{ background: '#fff', padding: 24, border: '1px solid #f0f0f0', borderRadius: 8 }}>
                      <DocumentContent document={document} />
                    </div>
                  ),
                },
                {
                  key: 'details',
                  label: <span><FileTextOutlined /> Details</span>,
                  children: (
                    <Descriptions column={{ xs: 1, sm: 2 }} bordered size="small">
                      <Descriptions.Item label="Staff">
                        {document.staff_name || '-'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Position">
                        {document.staff_position || '-'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Document Type">
                        {document.doc_type?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || '-'}
                      </Descriptions.Item>
                      <Descriptions.Item label="Status">
                        <Tag color={getStatusColor(document.status)}>{getStatusLabel(document.status)}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Start Date">
                        {formatDate(document.start_date)}
                      </Descriptions.Item>
                      <Descriptions.Item label="End Date">
                        {formatDate(document.end_date)}
                      </Descriptions.Item>
                      <Descriptions.Item label="Total Days">
                        {document.total_days} days
                      </Descriptions.Item>
                      <Descriptions.Item label="Created">
                        {formatDate(document.created_at)}
                      </Descriptions.Item>
                      <Descriptions.Item label="Updated">
                        {formatDate(document.updated_at)}
                      </Descriptions.Item>
                      <Descriptions.Item label="Data Source">
                        {document.from_archive ? (
                          <Tag icon={<SafetyCertificateOutlined />} color="green">Archived Snapshot</Tag>
                        ) : (
                          <Tag icon={<DatabaseOutlined />}>Live Database</Tag>
                        )}
                      </Descriptions.Item>
                      {document.signatories && document.signatories.length > 0 && (
                        <Descriptions.Item label="Signatories" span={2}>
                          {document.signatories.map((sig: any, idx: number) => (
                            <Tag key={idx} style={{ marginBottom: 4 }}>
                              {sig.position}: {sig.name}
                            </Tag>
                          ))}
                        </Descriptions.Item>
                      )}
                    </Descriptions>
                  ),
                },
              ]}
            />
          </Card>

          {document.status === 'pending_scan' && (
            <Card style={{ marginTop: 16 }}>
              <Alert
                type="info"
                message="Scan Upload Required"
                description="Please upload the signed document scan to complete the workflow."
                action={
                  <Button type="primary" onClick={() => setIsUploadModalOpen(true)}>
                    Upload Scan
                  </Button>
                }
              />
            </Card>
          )}
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Workflow Progress">
            <Timeline
              items={[
                document.progress?.applicant ? {
                  color: document.progress.applicant.completed ? 'green' : 'gray',
                  children: (
                    <div>
                      <Text strong>Applicant Signed</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {document.progress.applicant.completed ? 'Completed' : 'Pending'}
                      </Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {formatDateTime(document.progress.applicant.at)}
                      </Text>
                      {document.progress.applicant.comment && (
                        <>
                          <br />
                          <Text style={{ fontSize: 12 }}>"{document.progress.applicant.comment}"</Text>
                        </>
                      )}
                    </div>
                  ),
                } : null,
                document.progress?.approval ? {
                  color: document.progress.approval.completed ? 'green' : 'gray',
                  children: (
                    <div>
                      <Text strong>Dispatch Approval</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {document.progress.approval.completed ? 'Completed' : 'Pending'}
                      </Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {formatDateTime(document.progress.approval.at)}
                      </Text>
                      {document.progress.approval.comment && (
                        <>
                          <br />
                          <Text style={{ fontSize: 12 }}>"{document.progress.approval.comment}"</Text>
                        </>
                      )}
                    </div>
                  ),
                } : null,
                document.progress?.department_head ? {
                  color: document.progress.department_head.completed ? 'green' : 'gray',
                  children: (
                    <div>
                      <Text strong>Department Head</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {document.progress.department_head.completed ? 'Completed' : 'Pending'}
                      </Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {formatDateTime(document.progress.department_head.at)}
                      </Text>
                      {document.progress.department_head.comment && (
                        <>
                          <br />
                          <Text style={{ fontSize: 12 }}>"{document.progress.department_head.comment}"</Text>
                        </>
                      )}
                    </div>
                  ),
                } : null,
                document.progress?.approval_order ? {
                  color: document.progress.approval_order.completed ? 'green' : 'gray',
                  children: (
                    <div>
                      <Text strong>Approval Order</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {document.progress.approval_order.completed ? 'Completed' : 'Pending'}
                      </Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {formatDateTime(document.progress.approval_order.at)}
                      </Text>
                      {document.progress.approval_order.comment && (
                        <>
                          <br />
                          <Text style={{ fontSize: 12 }}>"{document.progress.approval_order.comment}"</Text>
                        </>
                      )}
                    </div>
                  ),
                } : null,
                document.progress?.rector ? {
                  color: document.progress.rector.completed ? 'green' : 'gray',
                  children: (
                    <div>
                      <Text strong>Rector Signature</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {document.progress.rector.completed ? 'Completed' : 'Pending'}
                      </Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {formatDateTime(document.progress.rector.at)}
                      </Text>
                      {document.progress.rector.comment && (
                        <>
                          <br />
                          <Text style={{ fontSize: 12 }}>"{document.progress.rector.comment}"</Text>
                        </>
                      )}
                    </div>
                  ),
                } : null,
                document.progress?.scanned ? {
                  color: document.progress.scanned.completed ? 'green' : 'gray',
                  children: (
                    <div>
                      <Text strong>Scanned Document</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {document.progress.scanned.completed ? 'Completed' : 'Pending'}
                      </Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {formatDateTime(document.progress.scanned.at)}
                      </Text>
                      {document.progress.scanned.comment && (
                        <>
                          <br />
                          <Text style={{ fontSize: 12 }}>"{document.progress.scanned.comment}"</Text>
                        </>
                      )}
                    </div>
                  ),
                } : null,
                document.progress?.tabel ? {
                  color: document.progress.tabel.completed ? 'green' : 'gray',
                  children: (
                    <div>
                      <Text strong>Added to Tabel</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {document.progress.tabel.completed ? 'Completed' : 'Pending'}
                      </Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {formatDateTime(document.progress.tabel.at)}
                      </Text>
                      {document.progress.tabel.comment && (
                        <>
                          <br />
                          <Text style={{ fontSize: 12 }}>"{document.progress.tabel.comment}"</Text>
                        </>
                      )}
                    </div>
                  ),
                } : null,
              ].filter(Boolean) as { color: string; children: React.ReactNode }[]}
            />
          </Card>

          <Card title="Actions" style={{ marginTop: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              {getWorkflowActions(document.status).map((action) => (
                <Button
                  key={action.key}
                  block
                  icon={action.icon}
                  danger={action.danger}
                  onClick={() => {
                    setWorkflowAction(action.key);
                    setIsWorkflowModalOpen(true);
                  }}
                >
                  {action.label}
                </Button>
              ))}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* Workflow Modal */}
      <Modal
        title={`${workflowAction === 'approve' ? 'Approve' : workflowAction === 'reject' ? 'Reject' : 'Cancel'} Document`}
        open={isWorkflowModalOpen}
        onCancel={() => setIsWorkflowModalOpen(false)}
        onOk={() => workflowMutation.mutate({ action: workflowAction, comment })}
        confirmLoading={workflowMutation.isPending}
      >
        <Input.TextArea
          rows={4}
          placeholder="Add a comment (optional)"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </Modal>

      {/* Upload Scan Modal */}
      <Modal
        title="Upload Signed Document"
        open={isUploadModalOpen}
        onCancel={() => setIsUploadModalOpen(false)}
        onOk={() => {
          const fileInput = document.getElementById('scan-upload');
          if (fileInput?.files?.[0]) {
            uploadScanMutation.mutate(fileInput.files[0]);
          }
        }}
        confirmLoading={uploadScanMutation.isPending}
      >
        <Upload.Dragger
          accept=".pdf,.png,.jpg,.jpeg"
          maxCount={1}
          beforeUpload={(file) => {
            const isValid = ['application/pdf', 'image/png', 'image/jpeg'].includes(file.type);
            if (!isValid) {
              message.error('Only PDF, PNG, and JPG files are allowed!');
            }
            return false;
          }}
        >
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">Click or drag file to upload</p>
          <p className="ant-upload-hint">Support PDF, PNG, JPG</p>
        </Upload.Dragger>
        <input type="file" id="scan-upload" style={{ display: 'none' }} />
      </Modal>
    </div>
  );
};

export default DocumentDetail;
