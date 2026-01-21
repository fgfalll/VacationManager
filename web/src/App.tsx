import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';


// Layout
import MainLayout from './components/layout/MainLayout';

// Auth
import Login from './pages/auth/Login';

// Pages
import Dashboard from './pages/dashboard/Dashboard';
import StaffList from './pages/staff/StaffList';
import StaffDetail from './pages/staff/StaffDetail';
import DocumentList from './pages/documents/DocumentList';
import DocumentCreate from './pages/documents/DocumentCreate';
import DocumentDetail from './pages/documents/DocumentDetail';
import ScheduleView from './pages/schedule/ScheduleView';
import AttendanceView from './pages/attendance/AttendanceView';
import Settings from './pages/settings/Settings';

import ScanUpload from './pages/documents/ScanUpload';

// ... (existing imports)

const App: React.FC = () => {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<Login />} />

      {/* Protected Routes */}
      <Route element={<MainLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/staff" element={<StaffList />} />
        <Route path="/staff/:id" element={<StaffDetail />} />
        <Route path="/documents" element={<DocumentList />} />
        <Route path="/documents/create" element={<DocumentCreate />} />
        <Route path="/documents/:id" element={<DocumentDetail />} />
        <Route path="/schedule" element={<ScheduleView />} />
        <Route path="/attendance" element={<AttendanceView />} />
        <Route path="/scan-upload" element={<ScanUpload />} />
        <Route path="/documents/upload" element={<ScanUpload />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      {/* Redirect root to dashboard */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* 404 */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default App;
