/** System constants and translations */

// Ukrainian document type labels
export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
    vacation_paid: 'Відпустка оплачувана',
    vacation_main: 'Основна щорічна відпустка',
    vacation_additional: 'Додаткова щорічна відпустка',
    vacation_chornobyl: 'Додаткова відпустка чорнобильцям',
    vacation_creative: 'Творча відпустка',
    vacation_study: 'Навчальна відпустка',
    vacation_children: "Відпустка працівникам з дітьми",
    vacation_maternity: "Відпустка у зв'язку з вагітністю та пологами",
    vacation_childcare: 'Відпустка для догляду за дитиною',
    vacation_unpaid: 'Відпустка без збереження зарплати',
    vacation_unpaid_study: 'Навчальна відпустка без збереження зарплати',
    vacation_unpaid_mandatory: "Відпустка без збереження (обов'язкова)",
    vacation_unpaid_agreement: 'Відпустка без збереження (за згодою)',
    vacation_unpaid_other: 'Інша відпустка без збереження зарплати',
    term_extension: 'Продовження терміну контракту',
    term_extension_contract: 'Продовження контракту (контракт)',
    term_extension_competition: 'Продовження контракту (конкурс)',
    term_extension_pdf: 'Продовження контракту (PDF)',
    employment_contract: 'Прийом на роботу (контракт)',
    employment_competition: 'Прийом на роботу (конкурс)',
    employment_pdf: 'Прийом на роботу (PDF)',
};

// Ukrainian status labels
export const STATUS_LABELS: Record<string, string> = {
    draft: 'Чернетка',
    signed_by_applicant: 'Підписав заявник',
    approved_by_dispatcher: 'Погоджено диспетчером',
    signed_dep_head: 'Підписано зав. кафедри',
    agreed: 'Погоджено',
    signed_rector: 'Підписано ректором',
    scanned: 'Відскановано',
    processed: 'В табелі',
};

// Status colors (mapping to antd/css colors)
export const STATUS_COLORS: Record<string, string> = {
    draft: '#d9d9d9', // default
    signed_by_applicant: '#1677ff', // blue
    approved_by_dispatcher: '#13c2c2', // cyan
    signed_dep_head: '#52c41a', // green
    agreed: '#faad14', // orange
    signed_rector: '#722ed1', // purple
    scanned: '#eb2f96', // magenta
    processed: '#52c41a', // success (green)
};

// Helper to normalize status string
export const normalizeStatus = (s: string) => s?.toLowerCase().replace(/ /g, '_') || '';

// Helper to normalize doc_type string
export const normalizeDocType = (s: string) => s?.toLowerCase() || '';
