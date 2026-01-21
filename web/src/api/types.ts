// User and Auth types
export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: 'admin' | 'department_head' | 'employee';
  staff_id: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

// Staff types
export interface Staff {
  id: number;
  pib_nom: string;
  first_name?: string;
  last_name?: string;
  degree: string | null;
  rate: number;
  position: string;
  email?: string;
  phone?: string;
  status: 'active' | 'inactive';
  start_date?: string;
  end_date?: string;
  employment_type: string;
  work_basis: string;
  term_start: string;
  term_end: string;
  vacation_balance: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Re-export enums for convenience
export { StaffPosition } from './constants';
export { EmploymentType, WorkBasis } from './constants';

export interface StaffPosition {
  id: number;
  staff_id: number;
  position: string;
  department: string;
  is_primary: boolean;
}

export interface StaffCreateRequest {
  pib_nom: string;
  degree?: string;
  rate: number;
  position: string;
  employment_type: string;
  work_basis: string;
  term_start: string;
  term_end: string;
  vacation_balance?: number;
  email?: string;
  phone?: string;
}

export interface StaffUpdateRequest extends Partial<StaffCreateRequest> {
  is_active?: boolean;
}

// Document types
export interface Signatory {
  position: string;
  position_multiline?: string;
  name: string;
  order_index?: number;
}

export interface Document {
  id: number;
  staff_id: number;
  staff?: Staff;
  doc_type: string;
  document_type_id?: number;
  document_type?: DocumentType;
  title: string;
  content: string;
  rendered_html?: string;
  status: DocumentStatus;
  start_date: string;
  end_date: string;
  total_days: number;
  days_count?: number;
  payment_period?: string;
  staff_name?: string;
  staff_position?: string;
  created_at: string;
  updated_at: string;
  progress?: Record<string, any>;
  signatures?: Signature[];
  attachments?: Attachment[];
  workflow_history?: WorkflowHistoryItem[];
  // Archive support
  from_archive?: boolean;
  archive_metadata_path?: string;
  signatories?: Signatory[];
  // Blocking support
  is_blocked?: boolean;
  blocked_reason?: string;
  file_scan_path?: string | null;
  stale_info?: StaleInfo;
}

export type DocumentStatus =
  | 'draft'
  | 'signed_by_applicant'
  | 'approved_by_dispatcher'
  | 'signed_dep_head'
  | 'agreed'
  | 'signed_rector'
  | 'scanned'
  | 'processed';

export interface DocumentType {
  id: string;
  name: string;
  description: string;
}

export interface DocumentCreateRequest {
  staff_id: number;
  doc_type: string;
  date_start: string;
  date_end: string;
  custom_text?: string;
}

export interface StaleResolutionRequest {
  action: 'explain' | 'remove';
  explanation?: string;
}

export interface StaleInfo {
  id: number;
  days_stale: number;
  notification_count: number;
  stale_explanation?: string | null;
  status_changed_at: string | null;
}

export interface Signature {
  id: number;
  document_id: number;
  signed_by: number;
  signed_by_name: string;
  signature_role: string;
  signed_at: string | null;
  signature_image: string | null;
}

export interface Attachment {
  id: number;
  document_id: number;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
  uploaded_at: string;
}

export interface WorkflowHistoryItem {
  id: number;
  document_id: number;
  action: string;
  performed_by: number;
  performed_by_name: string;
  comment: string | null;
  created_at: string;
}

// Staff history types
export interface StaffHistoryItem {
  id: number;
  staff_id: number;
  action: string;
  previous_values: Record<string, unknown>;
  changed_by: string;
  comment: string | null;
  created_at: string;
}

// Schedule types
export interface AnnualSchedule {
  id: number;
  staff_id: number;
  staff?: Staff;
  year: number;
  month: number;
  days: ScheduleDay[];
  total_working_days: number;
  total_vacation_days: number;
  total_holiday_days: number;
  created_at: string;
  updated_at: string;
}

export interface ScheduleDay {
  day: number;
  day_type: 'working' | 'vacation' | 'sick' | 'holiday' | 'unpaid';
  hours: number;
  is_locked: boolean;
}

export interface ScheduleCreateRequest {
  staff_id: number;
  year: number;
  month: number;
  days: Omit<ScheduleDay, 'is_locked'>[];
}

export interface AutoDistributeRequest {
  year: number;
  month: number;
  departments?: string[];
  exclude_staff?: number[];
  distribution_type: 'even' | 'random' | 'balanced';
}

export interface ScheduleStats {
  total_staff: number;
  total_working_days: number;
  department_breakdown: DepartmentStats[];
}

export interface DepartmentStats {
  department: string;
  total_staff: number;
  assigned_vacation_days: number;
  remaining_vacation_days: number;
}

// Attendance types
export interface DailyAttendance {
  id: number;
  staff_id: number;
  staff?: Staff;
  date: string;
  date_end?: string | null;
  code: string;
  hours: number;
  notes: string | null;
  is_correction: boolean;
  correction_month: number | null;
  correction_year: number | null;
  correction_sequence?: number | null;
  table_type?: 'main' | 'correction';
  table_info?: string;
  is_blocked?: boolean;
  blocked_reason?: string;
  created_at: string;
}

export interface AttendanceListResponse {
  items: DailyAttendance[];
  total: number;
  skip: number;
  limit: number;
}

export interface Tabel {
  id: number;
  year: number;
  month: number;
  department: string;
  status: 'draft' | 'submitted' | 'approved' | 'rejected';
  submitted_at: string | null;
  approved_at: string | null;
  approved_by: number | null;
  attendance_records: DailyAttendance[];
  created_at: string;
  updated_at: string;
}

export interface AttendanceCorrection {
  id: number;
  staff_id: number;
  attendance_id: number;
  correction_type: 'check_in' | 'check_out' | 'status' | 'hours';
  original_value: string;
  new_value: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  processed_at: string | null;
  processed_by: number | null;
}

// Dashboard types
export interface DashboardStats {
  total_staff: number;
  active_staff: number;
  pending_documents: number;
  upcoming_vacations: number;
}

export interface RecentDocument {
  id: number;
  title: string;
  document_type: string;
  staff_name: string;
  status: DocumentStatus;
  created_at: string;
}

// API Response types
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  message?: string;
  errors?: Record<string, string[]>;
}
