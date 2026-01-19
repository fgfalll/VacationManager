import React, { useState } from 'react';
import {
  Card,
  Steps,
  Form,
  Select,
  Input,
  Button,
  Typography,
  Space,
  message,
  Row,
  Col,
  Avatar,
  List,
  Popconfirm,
} from 'antd';
import DatePicker from 'react-datepicker';
import "react-datepicker/dist/react-datepicker.css";
import {
  UserOutlined,
  FileTextOutlined,
  CalendarOutlined,
  EyeOutlined,
  CheckOutlined,
  LeftOutlined,
  RightOutlined,
  DeleteOutlined,
  ClearOutlined,
  PrinterOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { DocumentCreateRequest, DocumentType, Staff } from '../../api/types';
import { format, addDays, isSameDay, isWithinInterval, differenceInDays } from 'date-fns';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

// Custom styling for react-datepicker
const datePickerStyles = `
  .react-datepicker {
    font-family: inherit !important;
    border: 1px solid #e8e8e8 !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
  }
  .react-datepicker__header {
    background-color: #f5f5f5 !important;
    border-bottom: 1px solid #e8e8e8 !important;
    border-radius: 8px 8px 0 0 !important;
    padding-top: 12px !important;
  }
  .react-datepicker__current-month {
    font-size: 14px !important;
    font-weight: 600 !important;
  }
  .react-datepicker__day-name {
    font-size: 12px !important;
    color: #666 !important;
  }
  .react-datepicker__day {
    width: 36px !important;
    height: 36px !important;
    line-height: 36px !important;
    border-radius: 4px !important;
    margin: 2px !important;
  }
  .react-datepicker__day:hover {
    background-color: #e6f7ff !important;
    color: #1890ff !important;
  }
  .react-datepicker__day--selected, .react-datepicker__day--in-range {
    background-color: #1890ff !important;
    color: white !important;
  }
  .react-datepicker__day--disabled {
    color: #ccc !important;
    cursor: not-allowed !important;
  }
  .react-datepicker__day--booked {
    background-color: #fff1f0 !important;
    border: 2px solid #ff4d4f !important;
    color: #ff4d4f !important;
  }
  .react-datepicker__day--in-range.react-datepicker__day--booked {
    background-color: #bae7ff !important;
    border-color: #1890ff !important;
    color: #1890ff !important;
  }
  .react-datepicker__navigation {
    top: 12px !important;
  }
  .react-datepicker__navigation--previous {
    left: 8px !important;
  }
  .react-datepicker__navigation--next {
    right: 8px !important;
  }
`;

const DocumentCreate: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [currentStep, setCurrentStep] = useState(0);
  const [form] = Form.useForm();
  const [formData, setFormData] = useState<Partial<DocumentCreateRequest>>({});
  const [dateRanges, setDateRanges] = useState<{ start: Date; end: Date }[]>([]);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [tempRange, setTempRange] = useState<[Date | null, Date | null]>([null, null]);
  const [bookedDates, setBookedDates] = useState<{ date: Date; docId: number; docType: string; source: string }[]>([]);
  const [customText, setCustomText] = useState('');
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);

  const previewMutation = useMutation({
    mutationFn: async (data: DocumentCreateRequest) => {
      const response = await apiClient.post(endpoints.documents.preview, data);
      return response.data;
    },
    onSuccess: (data) => {
      setPreviewHtml(data.html);
    },
    onError: () => {
      message.error("Failed to load preview");
    }
  });

  React.useEffect(() => {
    if (currentStep === 3 && dateRanges.length > 0) {
      const formValues = form.getFieldsValue();
      const allDates = dateRanges.flatMap(r => {
        const dates = [];
        let current = r.start;
        while (current <= r.end) {
          dates.push(current);
          current = addDays(current, 1);
        }
        return dates;
      });

      if (allDates.length > 0) {
        const dateStart = allDates[0];
        const dateEnd = allDates[allDates.length - 1];

        const previewData: DocumentCreateRequest = {
          ...formData,
          ...formValues,
          date_start: format(dateStart, 'yyyy-MM-dd'),
          date_end: format(dateEnd, 'yyyy-MM-dd'),
          custom_text: customText || undefined,
        };
        previewMutation.mutate(previewData);
      }
    }
  }, [currentStep]);

  const { data: staffList, isLoading: staffLoading } = useQuery<Staff[]>({
    queryKey: ['staff-for-document'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.staff.list, {
        params: { page_size: 1000, is_active: true },
      });
      return response.data.items;
    },
  });

  const { data: documentTypes } = useQuery<DocumentType[]>({
    queryKey: ['document-types'],
    queryFn: async () => {
      const response = await apiClient.get(endpoints.documents.types);
      return response.data;
    },
  });

  const selectedStaffId = form.getFieldValue('staff_id');
  useQuery({
    queryKey: ['staff-blocked-days', selectedStaffId],
    queryFn: async () => {
      if (!selectedStaffId) return [];
      try {
        const response = await apiClient.get(endpoints.documents.blockedDays(selectedStaffId));
        const blockedData = response.data.blocked_dates || [];
        const dates: { date: Date; docId: number; docType: string; source: string }[] = blockedData.map((item: any) => ({
          date: new Date(item.date),
          docId: item.doc_id,
          docType: item.doc_type_name,
          source: item.source || 'document',
        }));
        setBookedDates(dates);
        return dates;
      } catch (error: any) {
        console.error('Error fetching blocked days:', error.response?.data || error);
        return [];
      }
    },
    enabled: !!selectedStaffId,
  });

  const createMutation = useMutation({
    mutationFn: async (data: DocumentCreateRequest) => {
      const response = await apiClient.post(endpoints.documents.create, data);
      return response.data;
    },
    onSuccess: (data) => {
      message.success('Документ створено успішно');
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      navigate(`/documents/${data.id}`);
    },
    onError: (error: Error) => {
      message.error(error.message || 'Не вдалося створити документ');
    },
  });

  const handleNext = async () => {
    try {
      let fieldsToValidate: string[] = [];
      switch (currentStep) {
        case 0: fieldsToValidate = ['staff_id']; break;
        case 1: fieldsToValidate = ['doc_type']; break;
        case 2: fieldsToValidate = []; break;
        case 3: fieldsToValidate = []; break;
      }
      await form.validateFields(fieldsToValidate);
      const values = form.getFieldsValue();
      setFormData((prev) => ({ ...prev, ...values }));
      setCurrentStep((prev) => prev + 1);
    } catch (error) {
      // Validation failed
    }
  };

  const handlePrev = () => {
    const values = form.getFieldsValue();
    setFormData((prev) => ({ ...prev, ...values }));
    setCurrentStep((prev) => prev - 1);
  };

  const handleSubmit = async () => {
    try {
      await form.validateFields();
      const values = form.getFieldsValue();

      if (dateRanges.length === 0) {
        message.error('Оберіть дати відпустки');
        return;
      }

      const allDates = dateRanges.flatMap(r => {
        const dates = [];
        let current = r.start;
        while (current <= r.end) {
          dates.push(current);
          current = addDays(current, 1);
        }
        return dates;
      });

      const dateStart = allDates[0];
      const dateEnd = allDates[allDates.length - 1];

      const finalData: DocumentCreateRequest = {
        ...formData,
        ...values,
        date_start: format(dateStart, 'yyyy-MM-dd'),
        date_end: format(dateEnd, 'yyyy-MM-dd'),
        custom_text: customText || undefined,
      };

      createMutation.mutate(finalData);
    } catch (error) {
      // Validation failed
    }
  };

  const handleAddRange = (start: Date, end: Date) => {
    setDateRanges(prev => [...prev, { start, end }]);
  };

  const handleRemoveRange = (index: number) => {
    setDateRanges(prev => prev.filter((_, i) => i !== index));
  };

  const handleClearAllDates = () => {
    setDateRanges([]);
  };

  const selectedStaff = staffList?.find((s) => s.id === form.getFieldValue('staff_id'));
  const selectedDocType = documentTypes?.find((t) => t.id === form.getFieldValue('doc_type'));

  const totalDays = dateRanges.reduce((acc, range) => {
    return acc + differenceInDays(range.end, range.start) + 1;
  }, 0);

  const steps = [
    { title: 'Співробітник', icon: <UserOutlined /> },
    { title: 'Тип', icon: <FileTextOutlined /> },
    { title: 'Дати', icon: <CalendarOutlined /> },
    { title: 'Перегляд', icon: <EyeOutlined /> },
  ];

  // Helper to check if date is booked
  const isDateBooked = (date: Date) => {
    return bookedDates.some(d => isSameDay(d.date, date));
  };

  // Helper to check if date is in any selected range
  const isDateInRanges = (date: Date) => {
    return dateRanges.some(range =>
      isWithinInterval(date, { start: range.start, end: range.end })
    );
  };

  // Custom day className for react-datepicker
  const getDayClassName = (date: Date) => {
    if (isDateBooked(date)) return 'react-datepicker__day--booked';
    if (isDateInRanges(date)) return 'react-datepicker__day--in-range';
    return '';
  };

  return (
    <>
      <style>{datePickerStyles}</style>
      <div>
        <Title level={3} style={{ marginBottom: 24 }}>Створення документа</Title>

        <Card>
          <Steps current={currentStep} items={steps} style={{ marginBottom: 32 }} />

          <Form form={form} layout="vertical" initialValues={formData}>
            {/* Step 0: Staff Selection */}
            {currentStep === 0 && (
              <div>
                <Title level={4}>Оберіть співробітника</Title>
                <Form.Item name="staff_id" rules={[{ required: true, message: 'Оберіть співробітника' }]}>
                  <Select placeholder="Оберіть співробітника" showSearch optionFilterProp="children" style={{ width: '100%' }} loading={staffLoading}>
                    {staffList?.map((staff) => (
                      <Option key={staff.id} value={staff.id}>
                        <Space>
                          <Avatar size="small" style={{ backgroundColor: '#1890ff' }}>
                            {staff.pib_nom?.split(' ').map(n => n[0]).join('').slice(0, 2) || '?'}
                          </Avatar>
                          <span>{staff.pib_nom}</span>
                          <Text type="secondary">- {staff.position?.toLowerCase()}</Text>
                          <Text type="secondary">({staff.rate} ст.)</Text>
                        </Space>
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </div>
            )}

            {/* Step 1: Document Type */}
            {currentStep === 1 && (
              <div>
                <Title level={4}>Оберіть тип документа</Title>
                <Form.Item name="doc_type" rules={[{ required: true, message: 'Оберіть тип документа' }]}>
                  <Select placeholder="Оберіть тип документа" style={{ width: '100%' }}>
                    {documentTypes?.map((type) => (
                      <Option key={type.id} value={type.id}>
                        <Text strong>{type.name}</Text>
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </div>
            )}

            {/* Step 2: Date Selection with Calendar */}
            {currentStep === 2 && (
              <div>
                <Title level={4}>Оберіть дати відпустки</Title>
                <Row gutter={16}>
                  <Col xs={24} md={15}>
                    <Card
                      size="small"
                      title="Календар"
                      extra={
                        <Button
                          type="text"
                          size="small"
                          icon={<ClearOutlined />}
                          onClick={handleClearAllDates}
                          disabled={dateRanges.length === 0}
                        >
                          Очистити
                        </Button>
                      }
                    >
                      <div style={{ display: 'flex', justifyContent: 'center' }}>
                        <DatePicker
                          startDate={tempRange[0] || undefined}
                          endDate={tempRange[1] || undefined}
                          onChange={(update: [Date | null, Date | null]) => {
                            setTempRange(update);
                            if (update[0] && update[1]) {
                              handleAddRange(update[0], update[1]);
                              setTempRange([null, null]);
                            }
                          }}
                          selectsRange
                          inline
                          minDate={new Date()}
                          maxDate={addDays(new Date(), 365)}
                          showMonthDropdown
                          showYearDropdown
                          dropdownMode="select"
                          dateFormat="dd.MM.yyyy"
                          calendarStartDay={1}
                          dayClassName={getDayClassName}
                          renderCustomHeader={({
                            date,
                            decreaseMonth,
                            increaseMonth,
                            prevMonthButtonDisabled,
                            nextMonthButtonDisabled,
                          }) => (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px' }}>
                              <Button
                                size="small"
                                onClick={decreaseMonth}
                                disabled={prevMonthButtonDisabled}
                                icon={<LeftOutlined />}
                              />
                              <span style={{ fontWeight: 600, fontSize: 14 }}>
                                {format(date, 'LLLL yyyy')}
                              </span>
                              <Button
                                size="small"
                                onClick={increaseMonth}
                                disabled={nextMonthButtonDisabled}
                                icon={<RightOutlined />}
                              />
                            </div>
                          )}
                          excludeDates={bookedDates.map(d => d.date)}
                        />
                      </div>
                      <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
                        <Text type="secondary">
                          Оберіть початок і кінець відпустки
                        </Text>
                      </div>
                    </Card>
                  </Col>
                  <Col xs={24} md={9}>
                    <Card size="small" title="Обрані періоди" style={{ marginBottom: 16 }}>
                      {dateRanges.length === 0 ? (
                        <Text type="secondary">Періоди не обрані</Text>
                      ) : (
                        <>
                          <List
                            size="small"
                            dataSource={dateRanges.map((range, index) => ({
                              key: index,
                              start: format(range.start, 'dd.MM.yyyy'),
                              end: format(range.end, 'dd.MM.yyyy'),
                              days: differenceInDays(range.end, range.start) + 1,
                            }))}
                            renderItem={(item) => (
                              <List.Item
                                actions={[
                                  <Popconfirm
                                    key="remove"
                                    title="Видалити період"
                                    description={`${item.start} - ${item.end} (${item.days} дн.)`}
                                    onConfirm={() => handleRemoveRange(item.key as number)}
                                    okText="Так"
                                    cancelText="Ні"
                                  >
                                    <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                                  </Popconfirm>
                                ]}
                              >
                                <List.Item.Meta
                                  title={`${item.start} - ${item.end}`}
                                  description={`${item.days} ${getDaysWord(item.days)}`}
                                />
                              </List.Item>
                            )}
                            style={{ maxHeight: 250, overflow: 'auto' }}
                          />
                          <div style={{ marginTop: 12 }}>
                            <Text strong>Всього: {totalDays} {getDaysWord(totalDays)}</Text>
                          </div>
                        </>
                      )}
                    </Card>
                  </Col>
                </Row>
                <Form.Item name="custom_text" label="Додатковий текст (необов'язково)" style={{ marginTop: 16 }}>
                  <TextArea rows={3} placeholder="Додатковий текст для заяви..." value={customText} onChange={(e) => setCustomText(e.target.value)} />
                </Form.Item>
              </div>
            )}

            {/* Step 3: Preview */}
            {currentStep === 3 && (
              <div>
                <Title level={4}>Перегляд документа</Title>
                {previewMutation.isPending ? (
                  <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
                    <Text type="secondary">Завантаження...</Text>
                  </div>
                ) : previewHtml ? (
                  <div style={{
                    width: '100%',
                    height: '800px',
                    border: '1px solid #e0e0e0',
                    backgroundColor: '#f5f5f5',
                    display: 'flex',
                    justifyContent: 'center',
                    padding: '20px 0'
                  }}>
                    <iframe
                      title="Document Preview"
                      srcDoc={previewHtml}
                      style={{
                        width: '210mm',
                        height: '100%',
                        border: 'none',
                        backgroundColor: 'white',
                        boxShadow: '0 0 10px rgba(0,0,0,0.1)'
                      }}
                    />
                  </div>
                ) : (
                  <Text type="secondary">Попередній перегляд недоступний</Text>
                )}
                <Card size="small" style={{ marginTop: 16 }}>
                  <Title level={5}>Підсумок</Title>
                  <Row gutter={16}>
                    <Col span={8}>
                      <Text type="secondary">Співробітник:</Text><br /><Text strong>{selectedStaff?.pib_nom}</Text>
                    </Col>
                    <Col span={8}>
                      <Text type="secondary">Посада:</Text><br /><Text strong>{selectedStaff?.position?.toLowerCase()}</Text>
                    </Col>
                    <Col span={8}>
                      <Text type="secondary">Тип документа:</Text><br /><Text strong>{selectedDocType?.name}</Text>
                    </Col>
                  </Row>
                  <Row gutter={16} style={{ marginTop: 16 }}>
                    <Col span={12}>
                      <Text type="secondary">Період:</Text><br />
                      <Text strong>
                        {dateRanges.length > 0
                          ? dateRanges.map(r => `${format(r.start, 'dd.MM.yyyy')} - ${format(r.end, 'dd.MM.yyyy')}`).join(', ')
                          : 'Не обрано'}
                      </Text>
                    </Col>
                    <Col span={12}>
                      <Text type="secondary">Всього днів:</Text><br /><Text strong>{totalDays} {getDaysWord(totalDays)}</Text>
                    </Col>
                  </Row>
                </Card>
              </div>
            )}

            {/* Navigation Buttons */}
            <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
              <Button onClick={() => navigate('/documents')}>Скасувати</Button>
              <Space>
                {currentStep > 0 && (
                  <Button icon={<LeftOutlined />} onClick={handlePrev}>Назад</Button>
                )}
                {currentStep < 3 ? (
                  <Button type="primary" icon={<RightOutlined />} onClick={handleNext}>Далі</Button>
                ) : (
                  <Space>
                    <Button icon={<PrinterOutlined />}>Друкувати</Button>
                    <Button type="primary" icon={<CheckOutlined />} onClick={handleSubmit} loading={createMutation.isPending}>Створити документ</Button>
                  </Space>
                )}
              </Space>
            </div>
          </Form>
        </Card>
      </div>
    </>
  );
};

function getDaysWord(n: number): string {
  const absN = Math.abs(n);
  if (absN % 10 === 1 && absN % 100 !== 11) return 'день';
  if (absN % 10 >= 2 && absN % 10 <= 4 && (absN % 100 < 10 || absN % 100 >= 20)) return 'дні';
  return 'днів';
}

export default DocumentCreate;
