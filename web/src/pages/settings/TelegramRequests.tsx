import React, { useState } from 'react';
import {
    Table,
    Card,
    Button,
    Tag,
    Space,
    Modal,
    Select,
    Checkbox,
    Form,
    Input,
    Typography,
    message,
    Popconfirm
} from 'antd';
import { ReloadOutlined, CheckOutlined, CloseOutlined, SendOutlined, DisconnectOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { format } from 'date-fns';

const { Text } = Typography;

interface TelegramRequest {
    id: number;
    telegram_user_id: string;
    telegram_username: string | null;
    phone_number: string | null;
    first_name: string;
    last_name: string | null;
    status: 'pending' | 'approved' | 'rejected';
    staff_id: number | null;
    staff_name: string | null;
    created_at: string;
}

interface Staff {
    id: number;
    pib_nom: string;
    position: string;
    telegram_user_id: string | null;
}

const TelegramRequests: React.FC = () => {
    const queryClient = useQueryClient();
    const [approveModalVisible, setApproveModalVisible] = useState(false);
    const [rejectModalVisible, setRejectModalVisible] = useState(false);
    const [selectedRequest, setSelectedRequest] = useState<TelegramRequest | null>(null);

    const [approveForm] = Form.useForm();
    const [rejectForm] = Form.useForm();

    // Queries
    const { data: requests, isLoading } = useQuery({
        queryKey: ['telegram-requests'],
        queryFn: async () => {
            const response = await apiClient.get<TelegramRequest[]>(endpoints.telegram.requests);
            return response.data;
        },
    });

    const { data: staffList } = useQuery({
        queryKey: ['staff-for-link'],
        queryFn: async () => {
            const response = await apiClient.get<Staff[]>(endpoints.staff.list);
            return response.data;
        },
        enabled: approveModalVisible,
    });

    // Mutations
    const approveMutation = useMutation({
        mutationFn: async (data: { staff_id: number; permissions: string[] }) => {
            if (!selectedRequest) return;
            await apiClient.post(endpoints.telegram.approve(selectedRequest.id), data);
        },
        onSuccess: () => {
            message.success('Request approved successfully');
            setApproveModalVisible(false);
            approveForm.resetFields();
            queryClient.invalidateQueries({ queryKey: ['telegram-requests'] });
        },
        onError: (error: any) => {
            message.error(error.response?.data?.detail || 'Failed to approve request');
        },
    });

    const rejectMutation = useMutation({
        mutationFn: async (data: { reason: string }) => {
            if (!selectedRequest) return;
            await apiClient.post(endpoints.telegram.reject(selectedRequest.id), data);
        },
        onSuccess: () => {
            message.success('Request rejected');
            setRejectModalVisible(false);
            rejectForm.resetFields();
            queryClient.invalidateQueries({ queryKey: ['telegram-requests'] });
        },
        onError: (error: any) => {
            message.error(error.response?.data?.detail || 'Failed to reject request');
        },
    },
    });

const unlinkMutation = useMutation({
    mutationFn: async (id: number) => {
        await apiClient.post(endpoints.telegram.unlink(id));
    },
    onSuccess: () => {
        message.success('User unlinked successfully');
        queryClient.invalidateQueries({ queryKey: ['telegram-requests'] });
    },
    onError: (error: any) => {
        message.error(error.response?.data?.detail || 'Failed to unlink user');
    },
});

const handleApproveClick = (record: TelegramRequest) => {
    setSelectedRequest(record);
    setApproveModalVisible(true);
    // Try to find matching staff by name if possible (simple heuristic)
    // For now just partial string match could be nice, or leave empty
};

const handleRejectClick = (record: TelegramRequest) => {
    setSelectedRequest(record);
    setRejectModalVisible(true);
};

const columns = [
    {
        title: 'User',
        key: 'user',
        render: (_: any, record: TelegramRequest) => (
            <Space direction="vertical" size={0}>
                <Text strong>{record.first_name} {record.last_name}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>ID: {record.telegram_user_id}</Text>
            </Space>
        ),
    },
    {
        title: 'Contact',
        key: 'contact',
        render: (_: any, record: TelegramRequest) => (
            <Space direction="vertical" size={0}>
                {record.telegram_username && <Text>@{record.telegram_username}</Text>}
                {record.phone_number && <Text>{record.phone_number}</Text>}
            </Space>
        ),
    },
    {
        title: 'Status',
        dataIndex: 'status',
        key: 'status',
        render: (status: string) => {
            let color = 'default';
            if (status === 'approved') color = 'success';
            if (status === 'rejected') color = 'error';
            if (status === 'pending') color = 'processing';
            return <Tag color={color}>{status.toUpperCase()}</Tag>;
        },
    },
    {
        title: 'Created At',
        dataIndex: 'created_at',
        key: 'created_at',
        render: (date: string) => format(new Date(date), 'yyyy-MM-dd HH:mm'),
    },
    {
        title: 'Actions',
        key: 'actions',
        render: (_: any, record: TelegramRequest) => (
            record.status === 'pending' ? (
                <Space>
                    <Button
                        type="primary"
                        size="small"
                        icon={<CheckOutlined />}
                        onClick={() => handleApproveClick(record)}
                    >
                        Approve
                    </Button>
                    <Button
                        danger
                        size="small"
                        icon={<CloseOutlined />}
                        onClick={() => handleRejectClick(record)}
                    >
                        Reject
                    </Button>
                </Space>
            ) : record.status === 'approved' && (
                <Popconfirm
                    title="Unlink User"
                    description="Are you sure you want to unlink this user and remove all permissions?"
                    onConfirm={() => unlinkMutation.mutate(record.id)}
                    okText="Yes, Unlink"
                    cancelText="Cancel"
                    okButtonProps={{ danger: true }}
                >
                    <Button
                        danger
                        size="small"
                        icon={<DisconnectOutlined />}
                    >
                        Unlink
                    </Button>
                </Popconfirm>
            )
        ),
    },
];

return (
    <Card
        title={<Space><SendOutlined /> Telegram Connection Requests</Space>}
        extra={
            <Button
                icon={<ReloadOutlined />}
                onClick={() => queryClient.invalidateQueries({ queryKey: ['telegram-requests'] })}
            >
                Refresh
            </Button>
        }
    >
        <Table
            dataSource={requests || []}
            columns={columns}
            rowKey="id"
            loading={isLoading}
            pagination={{ pageSize: 5 }}
        />

        {/* Approve Modal */}
        <Modal
            title="Approve Request"
            open={approveModalVisible}
            onCancel={() => setApproveModalVisible(false)}
            footer={null}
        >
            <Form
                form={approveForm}
                layout="vertical"
                onFinish={(values) => approveMutation.mutate(values)}
                initialValues={{
                    permissions: ['view_documents']
                }}
            >
                <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
                    <Text strong>User:</Text> {selectedRequest?.first_name} {selectedRequest?.last_name}<br />
                    <Text strong>Telegram ID:</Text> {selectedRequest?.telegram_user_id}
                </div>

                <Form.Item
                    name="staff_id"
                    label="Link to Staff Member"
                    rules={[{ required: true, message: 'Please select a staff member' }]}
                >
                    <Select
                        showSearch
                        placeholder="Select staff..."
                        optionFilterProp="children"
                        filterOption={(input, option) =>
                            (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                        }
                        options={staffList?.map(s => ({
                            value: s.id,
                            label: `${s.pib_nom} - ${s.position} ${s.telegram_user_id ? '(Linked)' : ''}`,
                            disabled: !!s.telegram_user_id && s.telegram_user_id !== selectedRequest?.telegram_user_id
                        }))}
                    />
                </Form.Item>

                <Form.Item
                    name="permissions"
                    label="Permissions"
                >
                    <Checkbox.Group style={{ width: '100%' }}>
                        <Space direction="vertical">
                            <Checkbox value="view_documents" disabled checked>View Own Documents</Checkbox>
                            <Checkbox value="sign_documents">Sign/Approve Documents</Checkbox>
                            <Checkbox value="view_stale">View Stale Documents</Checkbox>
                            <Checkbox value="manage_stale">Manage Stale Documents</Checkbox>
                        </Space>
                    </Checkbox.Group>
                </Form.Item>

                <Form.Item>
                    <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                        <Button onClick={() => setApproveModalVisible(false)}>Cancel</Button>
                        <Button type="primary" htmlType="submit" loading={approveMutation.isPending}>
                            Approve & Link
                        </Button>
                    </Space>
                </Form.Item>
            </Form>
        </Modal>

        {/* Reject Modal */}
        <Modal
            title="Reject Request"
            open={rejectModalVisible}
            onCancel={() => setRejectModalVisible(false)}
            footer={null}
        >
            <Form
                form={rejectForm}
                layout="vertical"
                onFinish={(values) => rejectMutation.mutate(values)}
            >
                <Form.Item
                    name="reason"
                    label="Rejection Reason (Optional)"
                >
                    <Input.TextArea rows={3} placeholder="Why is this request being rejected?" />
                </Form.Item>

                <Form.Item>
                    <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                        <Button onClick={() => setRejectModalVisible(false)}>Cancel</Button>
                        <Button type="primary" danger htmlType="submit" loading={rejectMutation.isPending}>
                            Reject Request
                        </Button>
                    </Space>
                </Form.Item>
            </Form>
        </Modal>
    </Card>
);
};

export default TelegramRequests;
