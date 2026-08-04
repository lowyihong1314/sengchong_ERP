export const today = () => new Date().toISOString().slice(0, 10);

export const MONEY = { type: "number", step: "0.01" };

export const QTY = { type: "number", step: "0.0001" };

export const ENABLE_BACKGROUND_DETAIL_PREFETCH = false;

export const AUTO_LINK_RECOMMENDED_MIN_SCORE = 70;

export const PROJECT_SERVICE_CATEGORIES = [
  "电视机橱",
  "商场橱",
  "厨房橱",
  "衣橱",
  "床头柜",
  "拱门",
  "水盆橱",
  "展示柜",
  "设计",
];

export const PROJECT_STATUSES = [
  "Lead",
  "Quoted",
  "Confirmed",
  "In Progress",
  "Installed",
  "Completed",
  "On Hold",
  "Cancelled",
];

export const PROJECT_LINK_MODULES = new Set([
  "quotations",
  "invoices",
  "ar-payments",
  "ap-invoices",
  "purchase-orders",
]);

// Modules whose data this ERP owns. Everything else is an AutoCount
// passthrough under /api/autocount.
export const ERP_OWNED_MODULES = new Set(["projects", "employees", "salary", "work-entries"]);

export const EMPLOYEE_POSITIONS = [
  "设计",
  "量尺",
  "木工",
  "安装",
  "油漆",
  "采购",
  "行政",
  "司机",
];
export const EMPLOYEE_STATUSES = ["Active", "On Leave", "Resigned"];
export const PAY_TYPES = ["Monthly", "Daily", "Hourly"];

// How a night away is paid. All four arrangements are in use here, so this is
// configured per person rather than being one company-wide formula.
export const OVERNIGHT_MODES = [
  "allowance",
  "hourly",
  "extra_day",
  "allowance_plus_hours",
];

// The sidebar is grouped; moduleKeys is derived so there is one source of
// truth for "which module keys exist" (routing validates against it).
export const MODULE_GROUPS = [
  { key: "projects", label: "Projects", modules: ["projects"] },
  // Its own group rather than filed under Sales or Purchasing: the inbox takes
  // anything and works out which it is afterwards, so putting it under either
  // would be putting it under the answer to the question it exists to ask.
  { key: "documents", label: "Documents", modules: ["documents"] },
  {
    key: "sales",
    label: "Sales",
    modules: ["quotations", "invoices", "ar-payments", "ar-deposits"],
  },
  {
    key: "purchasing",
    label: "Purchasing",
    modules: ["purchase-orders", "ap-invoices", "ap-payments", "ap-deposits"],
  },
  { key: "banking", label: "Banking", modules: ["cash-book", "bank-transactions"] },
  { key: "masters", label: "Masters", modules: ["items", "debtors", "creditors"] },
  {
    key: "employees",
    label: "Employees",
    modules: ["employees", "salary", "work-entries", "work-day-sheet", "payroll"],
  },
  {
    key: "system",
    label: "System",
    modules: ["rdp-allow", "user-management", "website-content"],
  },
];

export const moduleKeys = MODULE_GROUPS.flatMap((group) => group.modules);

export const COMPANY_DATABASES = [
  { value: "AED_SENG", label: "SENG CHONG INTERIOR DESIGN" },
  { value: "AED_MANSON", label: "MANSON LIANG INTERIOR & RENOVATION" },
];

export const USER_ROLE_OPTIONS = ["user", "admin"];

export const EMPTY_USER_DRAFT = {
  username: "",
  displayName: "",
  password: "",
  role: "user",
  defaultCompany: "",
};

export const BANK_RECON_FILTERS = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "reconciled", label: "Reconciled" },
];

export const TOKEN_STORAGE_KEY = "erp_gateway_token";

export const PDF_EXPORT_MODULES = new Set([
  "quotations",
  "invoices",
  "ar-payments",
  "purchase-orders",
  "debtors",
]);

export const REQUEST_AMOUNT_PERCENTAGES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

export const WEBSITE_FOOTER_FIELDS = [
  ["year", "Year", "input"],
  ["company_name", "Company Name", "input"],
  ["registration_no", "Registration No", "input"],
  ["contact_person", "Contact Person", "input"],
  ["phone", "Phone", "input"],
  ["business_hours", "Business Hours", "input"],
  ["address", "Address", "textarea"],
];
