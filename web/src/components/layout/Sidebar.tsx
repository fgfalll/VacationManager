import React from 'react';
import { Layout, Menu, Typography } from 'antd';
import {
  DashboardOutlined,
  TeamOutlined,
  FileTextOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  SettingOutlined,
  ScanOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useUIStore, useAuthStore, isAdmin, isHR } from '../../stores/index';

const { Sider } = Layout;
const { Title } = Typography;

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { sidebarCollapsed } = useUIStore();
  const { user } = useAuthStore();

  const canViewStaff = isAdmin(user) || isHR(user);
  const canViewDocuments = isAdmin(user) || isHR(user) || user?.role === 'employee';
  const canViewSchedule = isAdmin(user) || isHR(user);
  const canViewAttendance = isAdmin(user) || isHR(user);
  const canViewSettings = isAdmin(user);

  const menuItems = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: 'Dashboard',
      onClick: () => navigate('/dashboard'),
    },
    ...(canViewStaff
      ? [
          {
            key: '/staff',
            icon: <TeamOutlined />,
            label: 'Staff',
            onClick: () => navigate('/staff'),
          },
        ]
      : []),
    ...(canViewDocuments
      ? [
          {
            key: '/documents',
            icon: <FileTextOutlined />,
            label: 'Документи',
            onClick: () => navigate('/documents'),
          },
          {
            key: '/scan-upload',
            icon: <ScanOutlined />,
            label: 'Scan Upload',
            onClick: () => navigate('/scan-upload'),
          },
        ]
      : []),
    ...(canViewSchedule
      ? [
          {
            key: '/schedule',
            icon: <CalendarOutlined />,
            label: 'Assignments',
            onClick: () => navigate('/schedule'),
          },
        ]
      : []),
    ...(canViewAttendance
      ? [
          {
            key: '/attendance',
            icon: <CheckSquareOutlined />,
            label: 'Attendance',
            onClick: () => navigate('/attendance'),
          },
        ]
      : []),
    ...(canViewSettings
      ? [
          {
            key: '/settings',
            icon: <SettingOutlined />,
            label: 'Settings',
            onClick: () => navigate('/settings'),
          },
        ]
      : []),
  ];

  return (
    <Sider
      trigger={null}
      collapsible
      collapsed={sidebarCollapsed}
      width={200}
      style={{
        overflow: 'auto',
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: 100,
      }}
    >
      <div className="logo" style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {!sidebarCollapsed && (
          <Title level={4} style={{ color: 'white', margin: 0 }}>
            VacationManager
          </Title>
        )}
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        style={{ borderRight: 0 }}
      />
    </Sider>
  );
};

export default Sidebar;
