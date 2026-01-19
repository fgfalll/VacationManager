import React from 'react';
import { Card, Typography, Form, Input, Button, Switch, Select, Divider, message, Row, Col, Tag, Space } from 'antd';
import { UserOutlined, BellOutlined, LockOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { useAuthStore } from '../../stores/index';
import { format } from 'date-fns';

const { Title, Text } = Typography;

const Settings: React.FC = () => {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const [profileForm] = Form.useForm();
  const [passwordForm] = Form.useForm();

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.settings.current);
      return response.data;
    },
  });

  const updateProfileMutation = useMutation({
    mutationFn: async (data: { first_name: string; last_name: string; email: string }) => {
      await apiClient.put(endpoints.settings.update, data);
    },
    onSuccess: () => {
      message.success('Profile updated successfully');
      queryClient.invalidateQueries({ queryKey: ['auth'] });
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to update profile');
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: async (data: { current_password: string; new_password: string }) => {
      await apiClient.post('/auth/change-password', data);
    },
    onSuccess: () => {
      message.success('Password changed successfully');
      passwordForm.resetFields();
    },
    onError: (error: Error) => {
      message.error(error.message || 'Failed to change password');
    },
  });

  React.useEffect(() => {
    if (user) {
      profileForm.setFieldsValue({
        first_name: user.first_name,
        last_name: user.last_name,
        email: user.email,
        username: user.username,
      });
    }
  }, [user, profileForm]);

  return (
    <div>
      <Title level={3} style={{ marginBottom: 24 }}>Settings</Title>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          {/* Profile Settings */}
          <Card title={<><UserOutlined /> Profile Settings</>}>
            <Form
              form={profileForm}
              layout="vertical"
              onFinish={updateProfileMutation.mutate}
            >
              <Form.Item
                name="username"
                label="Username"
              >
                <Input disabled prefix={<UserOutlined />} />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="first_name"
                    label="First Name"
                    rules={[{ required: true, message: 'Please enter first name' }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="last_name"
                    label="Last Name"
                    rules={[{ required: true, message: 'Please enter last name' }]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="email"
                label="Email"
                rules={[
                  { required: true, message: 'Please enter email' },
                  { type: 'email', message: 'Please enter a valid email' },
                ]}
              >
                <Input />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit" loading={updateProfileMutation.isPending}>
                  Update Profile
                </Button>
              </Form.Item>
            </Form>
          </Card>

          {/* Password Settings */}
          <Card title={<><LockOutlined /> Change Password</>} style={{ marginTop: 24 }}>
            <Form
              form={passwordForm}
              layout="vertical"
              onFinish={changePasswordMutation.mutate}
            >
              <Form.Item
                name="current_password"
                label="Current Password"
                rules={[{ required: true, message: 'Please enter current password' }]}
              >
                <Input.Password />
              </Form.Item>

              <Form.Item
                name="new_password"
                label="New Password"
                rules={[
                  { required: true, message: 'Please enter new password' },
                  { min: 8, message: 'Password must be at least 8 characters' },
                ]}
              >
                <Input.Password />
              </Form.Item>

              <Form.Item
                name="confirm_password"
                label="Confirm New Password"
                dependencies={['new_password']}
                rules={[
                  { required: true, message: 'Please confirm password' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('new_password') === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error('Passwords do not match'));
                    },
                  }),
                ]}
              >
                <Input.Password />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit" loading={changePasswordMutation.isPending}>
                  Change Password
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          {/* Account Info */}
          <Card title="Account Information">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">Role</Text>
                <br />
                <Text strong style={{ textTransform: 'capitalize' }}>{user?.role}</Text>
              </div>
              <Divider />
              <div>
                <Text type="secondary">Staff ID</Text>
                <br />
                <Text strong>{user?.staff_id || 'Not assigned'}</Text>
              </div>
              <Divider />
              <div>
                <Text type="secondary">Created At</Text>
                <br />
                <Text strong>
                  {user?.created_at && format(new Date(user.created_at), 'MMMM dd, yyyy')}
                </Text>
              </div>
              <Divider />
              <div>
                <Text type="secondary">Status</Text>
                <br />
                <Tag color={user?.is_active ? 'green' : 'red'}>
                  {user?.is_active ? 'Active' : 'Inactive'}
                </Tag>
              </div>
            </Space>
          </Card>

          {/* Notification Settings */}
          <Card title={<><BellOutlined /> Notifications</>} style={{ marginTop: 24 }}>
            <Form layout="vertical">
              <Form.Item label="Email Notifications">
                <Switch checkedChildren="On" unCheckedChildren="Off" defaultChecked />
              </Form.Item>
              <Form.Item label="Document Updates">
                <Switch checkedChildren="On" unCheckedChildren="Off" defaultChecked />
              </Form.Item>
              <Form.Item label="Schedule Reminders">
                <Switch checkedChildren="On" unCheckedChildren="Off" defaultChecked />
              </Form.Item>
            </Form>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Settings;
