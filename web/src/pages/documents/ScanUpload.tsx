import React, { useState } from 'react';
import {
    Card,
    Table,
    Button,
    Upload,
    message,
    Typography,
    Tag,
    Space,
    Modal,
    Select,
    Input,
} from 'antd';
import {
    UploadOutlined,
    ScanOutlined,
    EyeOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { Document, DocumentStatus, PaginatedResponse } from '../../api/types';
import { format } from 'date-fns';

const { Title, Text, Paragraph } = Typography;

const ScanUpload: React.FC = () => {
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    // Upload Modal State
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
    const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
    const [fileList, setFileList] = useState<any[]>([]);

    // Direct Upload Form State
    const [isDirectUploadModalOpen, setIsDirectUploadModalOpen] = useState(false);
    const [directUploadStaff, setDirectUploadStaff] = useState<number | null>(null);
    const [directUploadType, setDirectUploadType] = useState<string>('vacation_paid');
    const [directUploadStart, setDirectUploadStart] = useState<string>('');
    const [directUploadEnd, setDirectUploadEnd] = useState<string>('');
    const [directUploadDays, setDirectUploadDays] = useState<number>(0);
    const [directUploadFile, setDirectUploadFile] = useState<File | null>(null);

    // Fetch documents
    const { data: documentsData, isLoading } = useQuery<PaginatedResponse<Document>>({
        queryKey: ['documents', 'scan_queue'],
        queryFn: async () => {
            const response = await apiClient.get(endpoints.documents.list, {
                params: {
                    needs_scan: true,
                    page_size: 100,
                },
            });
            return response.data;
        },
    });

    // Fetch staff list
    const { data: staffList } = useQuery({
        queryKey: ['staff'],
        queryFn: async () => {
            // @ts-ignore
            const res = await apiClient.get(endpoints.staff.list);
            return res.data;
        },
    });

    // @ts-ignore
    const staffOptions = (staffList as any)?.data?.map((s: any) => ({
        label: `${s.pib_nom} (${s.position})`,
        value: s.id,
    })) || [];

    // Upload Mutation
    const uploadScanMutation = useMutation({
        mutationFn: async ({ id, file }: { id: number; file: File }) => {
            const formData = new FormData();
            formData.append('file', file);
            await apiClient.post(endpoints.documents.uploadScan(id), formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
        },
        onSuccess: () => {
            message.success('Scan uploaded successfully');
            queryClient.invalidateQueries({ queryKey: ['documents'] });
            setIsUploadModalOpen(false);
            setSelectedDocument(null);
        },
        onError: (error: Error) => {
            message.error(error.message || 'Upload failed');
        },
    });

    // Handlers
    const handleUploadClick = (doc: Document) => {
        setSelectedDocument(doc);
        setFileList([]);
        setIsUploadModalOpen(true);
    };

    const handleModalOk = () => {
        if (fileList.length > 0 && selectedDocument) {
            uploadScanMutation.mutate({
                id: selectedDocument.id,
                file: fileList[0] as File,
            });
        } else {
            message.warning("Please select a file first");
        }
    };

    const handleDirectUploadOk = async () => {
        if (!directUploadStaff || !directUploadStart || !directUploadEnd || !directUploadFile) {
            message.warning("Please fill in all fields and select a file");
            return;
        }

        const formData = new FormData();
        formData.append('staff_id', directUploadStaff.toString());
        formData.append('doc_type', directUploadType);
        formData.append('date_start', directUploadStart);
        formData.append('date_end', directUploadEnd);
        formData.append('days_count', directUploadDays.toString());
        formData.append('file', directUploadFile);

        try {
            await apiClient.post('/documents/direct-scan-upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            message.success("Document created and uploaded successfully");
            setIsDirectUploadModalOpen(false);
            setDirectUploadFile(null);
            setDirectUploadStaff(null);
            setDirectUploadStart('');
            setDirectUploadEnd('');
            queryClient.invalidateQueries({ queryKey: ['documents'] });
        } catch (error: any) {
            message.error(error.message || "Upload failed");
        }
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
                <span>{record.staff_name}</span>
            ),
        },
        {
            title: 'Status',
            dataIndex: 'status',
            key: 'status',
            render: (status: DocumentStatus) => (
                <Tag color="warning">
                    {status.replace(/_/g, ' ').toUpperCase()}
                </Tag>
            ),
        },
        {
            title: 'Date',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (date: string) => date ? format(new Date(date), 'MMM dd, yyyy') : '-',
        },
        {
            title: 'Action',
            key: 'action',
            render: (_: unknown, record: Document) => (
                <Space>
                    <Button
                        type="default"
                        icon={<EyeOutlined />}
                        onClick={() => navigate(`/documents/${record.id}`)}
                    >
                        View
                    </Button>
                    <Button
                        type="primary"
                        icon={<UploadOutlined />}
                        onClick={() => handleUploadClick(record)}
                    >
                        Upload Scan
                    </Button>
                </Space>
            ),
        },
    ];

    return (
        <div>
            <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <Title level={3} style={{ margin: 0 }}>
                        <ScanOutlined /> Scan Upload Portal
                    </Title>
                    <Paragraph type="secondary">
                        Upload signed scans for documents that have been approved and signed by the Rector.
                    </Paragraph>
                </div>
                <Button type="primary" onClick={() => setIsDirectUploadModalOpen(true)}>
                    Direct Upload (No Generation)
                </Button>
            </div>

            <Card>
                <Table
                    columns={columns}
                    dataSource={documentsData?.data || []}
                    loading={isLoading}
                    rowKey="id"
                    locale={{ emptyText: 'No documents pending scan upload' }}
                />
            </Card>

            <Modal
                title={`Upload Scan for "${selectedDocument?.title}"`}
                open={isUploadModalOpen}
                onCancel={() => setIsUploadModalOpen(false)}
                onOk={handleModalOk}
                confirmLoading={uploadScanMutation.isPending}
            >
                <Upload.Dragger
                    accept=".pdf,.png,.jpg,.jpeg"
                    maxCount={1}
                    openFileDialogOnClick={true}
                    customRequest={({ onSuccess }) => {
                        setTimeout(() => onSuccess && onSuccess("ok"), 0);
                    }}
                    fileList={fileList}
                    beforeUpload={(file) => {
                        const isValid = ['application/pdf', 'image/png', 'image/jpeg'].includes(file.type);
                        if (!isValid) {
                            message.error('Only PDF, PNG, and JPG files are allowed!');
                            return Upload.LIST_IGNORE;
                        }
                        setFileList([file]);
                        return false;
                    }}
                    onRemove={() => {
                        setFileList([]);
                    }}
                >
                    <p className="ant-upload-drag-icon">
                        <UploadOutlined />
                    </p>
                    <p className="ant-upload-text">Click or drag file to upload</p>
                    <p className="ant-upload-hint">Support PDF, PNG, JPG</p>
                </Upload.Dragger>
            </Modal>

            {/* Direct Upload Modal */}
            <Modal
                title="Direct Document Upload"
                open={isDirectUploadModalOpen}
                onCancel={() => setIsDirectUploadModalOpen(false)}
                onOk={handleDirectUploadOk}
                width={600}
            >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <div>
                        <Text strong>Staff Member:</Text>
                        <Select
                            showSearch
                            style={{ width: '100%' }}
                            placeholder="Select staff"
                            optionFilterProp="label"
                            options={staffOptions}
                            value={directUploadStaff}
                            onChange={(val) => setDirectUploadStaff(val)}
                        />
                    </div>

                    <div>
                        <Text strong>Document Type:</Text>
                        <Select
                            style={{ width: '100%' }}
                            value={directUploadType}
                            onChange={(val) => setDirectUploadType(val)}
                            options={[
                                { label: "Відпустка оплачувана", value: "vacation_paid" },
                                { label: "Відпустка без збереження", value: "vacation_unpaid" },
                                { label: "Інший документ", value: "other" }
                            ]}
                        />
                    </div>

                    <div style={{ display: 'flex', gap: 16 }}>
                        <div style={{ flex: 1 }}>
                            <Text strong>Start Date:</Text>
                            <Input
                                type="date"
                                value={directUploadStart}
                                onChange={(e) => setDirectUploadStart(e.target.value)}
                            />
                        </div>
                        <div style={{ flex: 1 }}>
                            <Text strong>End Date:</Text>
                            <Input
                                type="date"
                                value={directUploadEnd}
                                onChange={(e) => {
                                    setDirectUploadEnd(e.target.value);
                                    if (directUploadStart && e.target.value) {
                                        const start = new Date(directUploadStart);
                                        const end = new Date(e.target.value);
                                        const diffTime = Math.abs(end.getTime() - start.getTime());
                                        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
                                        setDirectUploadDays(diffDays);
                                    }
                                }}
                            />
                        </div>
                    </div>

                    <div>
                        <Text strong>Days Count:</Text>
                        <Input
                            type="number"
                            value={directUploadDays}
                            onChange={(e) => setDirectUploadDays(Number(e.target.value))}
                        />
                    </div>

                    <div>
                        <Text strong>Scan File:</Text>
                        <Upload.Dragger
                            accept=".pdf,.png,.jpg,.jpeg"
                            maxCount={1}
                            beforeUpload={(file) => {
                                setDirectUploadFile(file);
                                return false;
                            }}
                            onRemove={() => setDirectUploadFile(null)}
                            fileList={directUploadFile ? [{ uid: '-1', name: directUploadFile.name || 'file', status: 'done' } as any] : []}
                        >
                            <p className="ant-upload-drag-icon"><UploadOutlined /></p>
                            <p className="ant-upload-text">Click or drag file</p>
                        </Upload.Dragger>
                    </div>
                </div>
            </Modal>
        </div>
    );
};

export default ScanUpload;
