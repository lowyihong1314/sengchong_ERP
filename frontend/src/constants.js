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

export const moduleKeys = [
  "projects",
  "quotations",
  "invoices",
  "ar-payments",
  "ar-deposits",
  "cash-book",
  "bank-transactions",
  "purchase-orders",
  "ap-invoices",
  "ap-payments",
  "ap-deposits",
  "items",
  "debtors",
  "creditors",
  "rdp-allow",
  "user-management",
  "website-content",
];

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
