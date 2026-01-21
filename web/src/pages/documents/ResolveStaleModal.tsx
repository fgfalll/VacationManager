
import React, { useState } from 'react';
import { Modal, Radio, Input, Form, message, Alert } from 'antd';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/axios';
import { endpoints } from '../../api/endpoints';
import { StaleResolutionRequest } from '../../api/types';

interface ResolveStaleModalProps {
    open: boolean;
    onCancel: () => void;
    documentId: number | null;
    onSuccess: () => void;
}

const ResolveStaleModal: React.FC<ResolveStaleModalProps> = ({
    open,
    onCancel,
    documentId,
    onSuccess,
}) => {
    const [form] = Form.useForm();
    const queryClient = useQueryClient();
    const [action, setAction] = useState<'explain' | 'remove'>('explain');

    const mutation = useMutation({
        mutationFn: async (values: StaleResolutionRequest) => {
            if (!documentId) return;
            await apiClient.post(endpoints.documents.resolveStale(documentId), values);
        },
        onSuccess: () => {
            message.success(
                action === 'remove'
                    ? 'Документ успішно видалено'
                    : 'Пояснення успішно додано'
            );
            queryClient.invalidateQueries({ queryKey: ['documents'] });
            queryClient.invalidateQueries({ queryKey: ['stale-documents'] }); // Assuming we might use this key
            form.resetFields();
            onSuccess();
        },
        onError: (error: any) => {
            message.error(error.response?.data?.detail || 'Помилка при оновленні документа');
        },
    });

    const handleSubmit = async () => {
        try {
            const values = await form.validateFields();
            mutation.mutate({
                action: values.action,
                explanation: values.explanation,
            });
        } catch (error) {
            // Validation failed
        }
    };

    return (
        <Modal
            title="Вирішення проблеми з документом"
            open={open}
            onCancel={onCancel}
            onOk={handleSubmit}
            confirmLoading={mutation.isPending}
            okText="Підтвердити"
            cancelText="Скасувати"
            okButtonProps={{ danger: action === 'remove' }}
        >
            <Alert
                message="Увага"
                description="Цей документ не оновлювався довгий час. Виберіть дію для вирішення ситуації."
                type="warning"
                showIcon
                style={{ marginBottom: 16 }}
            />

            <Form
                form={form}
                layout="vertical"
                initialValues={{ action: 'explain' }}
            >
                <Form.Item name="action" label="Дія">
                    <Radio.Group onChange={(e) => setAction(e.target.value)}>
                        <Radio value="explain">Пояснити причину затримки</Radio>
                        <Radio value="remove">Видалити застарілий документ</Radio>
                    </Radio.Group>
                </Form.Item>

                {action === 'explain' && (
                    <Form.Item
                        name="explanation"
                        label="Пояснення"
                        rules={[
                            { required: true, message: 'Будь ласка, вкажіть причину затримки' },
                            { min: 5, message: 'Пояснення має бути змістовним' }
                        ]}
                    >
                        <Input.TextArea
                            rows={4}
                            placeholder="Наприклад: Очікую підпису від завідувача кафедри..."
                        />
                    </Form.Item>
                )}

                {action === 'remove' && (
                    <Alert
                        message="Видалення документа"
                        description="Ви збираєтесь видалити цей документ. Цю дію неможливо скасувати."
                        type="error"
                        showIcon
                    />
                )}
            </Form>
        </Modal>
    );
};

export default ResolveStaleModal;
