import React from "react";
import {
  FileText,
  Plus,
  Search,
  Send,
  Users,
} from "lucide-react";
import { BankingListControls } from "./components/BankingListControls.jsx";
import { DebtorCandidatesPanel } from "./components/DebtorCandidatesPanel.jsx";
import { DocumentCandidatesPanel } from "./components/DocumentCandidatesPanel.jsx";
import { DocumentsPage } from "./pages/DocumentsPage.jsx";
import { PayrollPage } from "./pages/PayrollPage.jsx";
import { ProjectFromDebtorForm } from "./components/ProjectFromDebtorForm.jsx";
import { Sidebar } from "./components/Sidebar.jsx";
import { Topbar } from "./components/Topbar.jsx";
import {
  AUTO_LINK_RECOMMENDED_MIN_SCORE,
  COMPANY_DATABASES,
  ENABLE_BACKGROUND_DETAIL_PREFETCH,
  PDF_EXPORT_MODULES,
  PROJECT_LINK_MODULES,
  TOKEN_STORAGE_KEY,
  today,
} from "./constants.js";
import { requestJson } from "./lib/api.js";
import { getBankReconState, getBankTransactionKey } from "./lib/banking.js";
import {
  applyItemToLine,
  getFormFromDetail,
  cleanFormPayload,
  findDebtor,
  getDocumentCandidateKey,
  getLineTemplate,
  hasDebtorField,
  hasItemLineField,
} from "./lib/documents.js";
import {
  clone,
  formatValue,
  getDownloadFilename,
  getRowKey,
  isAbortError,
  readValue,
  toNumber,
  wait,
} from "./lib/format.js";
import { normalizeDetail, normalizeRows } from "./lib/normalize.js";
import { getPdfExportStatus } from "./lib/pdf.js";
import {
  getProjectDocumentPatch,
  getProjectDocumentUnlinkPatch,
  getProjectFinancialPatch,
  getProjectFormFromDetail,
  getProjectFormFromDocument,
  getProjectFormFromDraft,
  getProjectPrimaryDocumentField,
  getRecommendedProjectCode,
  getRecommendedProjectScore,
  mergeProjectDraft,
} from "./lib/projects.js";
import {
  getDetailCacheKey,
  getEmptyStage,
  getLinkedProjectsPath,
  getModuleCreatePath,
  getModuleDetailPath,
  getModuleListPath,
  getModuleUpdatePath,
  getRouteFromUrl,
  normalizeRoute,
  replaceRouteUrl,
} from "./lib/routing.js";
import { getDocumentCurrency } from "./lib/totals.js";
import { useWebsiteAdmin } from "./hooks/useWebsiteAdmin.js";
import { useAdminSettings } from "./hooks/useAdminSettings.js";
import { useBankReconciliation } from "./hooks/useBankReconciliation.js";
import { MODULES } from "./modules.js";
import { DaySheetPage } from "./pages/DaySheetPage.jsx";
import { DebtorDetailPage } from "./pages/DebtorDetailPage.jsx";
import { DetailPage } from "./pages/DetailPage.jsx";
import { ItemDetailPage } from "./pages/ItemDetailPage.jsx";
import { ItemNewPage } from "./pages/ItemNewPage.jsx";
import { LoginPage } from "./pages/LoginPage.jsx";
import { NewPage } from "./pages/NewPage.jsx";
import { RdpAllowPage } from "./pages/RdpAllowPage.jsx";
import { UserManagementPage } from "./pages/UserManagementPage.jsx";
import { WebsiteContentPage } from "./pages/WebsiteContentPage.jsx";

export function App() {
  const initialRouteRef = React.useRef(getRouteFromUrl());
  const [activeModule, setActiveModule] = React.useState(initialRouteRef.current.moduleKey);
  const [rows, setRows] = React.useState([]);
  const [query, setQuery] = React.useState(initialRouteRef.current.query);
  const [status, setStatus] = React.useState({ tone: "", text: "Ready" });
  const [token, setToken] = React.useState(
    () => sessionStorage.getItem(TOKEN_STORAGE_KEY) || sessionStorage.getItem("autocount_token") || ""
  );
  const [session, setSession] = React.useState(null);
  const [companies, setCompanies] = React.useState(COMPANY_DATABASES);
  const [selectedCompany, setSelectedCompany] = React.useState("AED_SENG");
  const [login, setLogin] = React.useState({
    username: "yukang",
    password: "",
  });
  const [detail, setDetail] = React.useState(null);
  const [detailKey, setDetailKey] = React.useState(initialRouteRef.current.key);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [pdfExporting, setPdfExporting] = React.useState(false);
  const [paymentRequestExporting, setPaymentRequestExporting] = React.useState(false);
  const [view, setView] = React.useState(initialRouteRef.current.view);
  const [formData, setFormData] = React.useState({});
  const [debtors, setDebtors] = React.useState([]);
  const [debtorsLoaded, setDebtorsLoaded] = React.useState(false);
  const [projectFromDebtorOpen, setProjectFromDebtorOpen] = React.useState(false);
  const [projectFromDebtorCode, setProjectFromDebtorCode] = React.useState("");
  const [projectFromDebtorLoading, setProjectFromDebtorLoading] = React.useState(false);
  const [projectCandidates, setProjectCandidates] = React.useState([]);
  const [projectCandidatesOpen, setProjectCandidatesOpen] = React.useState(false);
  const [projectCandidatesLoading, setProjectCandidatesLoading] = React.useState(false);
  const [projectDocumentCandidates, setProjectDocumentCandidates] = React.useState([]);
  const [projectDocumentCandidatesOpen, setProjectDocumentCandidatesOpen] = React.useState(false);
  const [projectDocumentCandidatesLoading, setProjectDocumentCandidatesLoading] = React.useState(false);
  const [projectDocumentCandidateLinks, setProjectDocumentCandidateLinks] = React.useState({});
  const [projectDocumentCandidateLinking, setProjectDocumentCandidateLinking] = React.useState("");
  const [projectDocumentAutoLinking, setProjectDocumentAutoLinking] = React.useState(false);
  const [items, setItems] = React.useState([]);
  const [itemsLoaded, setItemsLoaded] = React.useState(false);
  const [paymentMethods, setPaymentMethods] = React.useState([]);
  const [paymentMethodsLoaded, setPaymentMethodsLoaded] = React.useState(false);
  const [projectChoices, setProjectChoices] = React.useState([]);
  const [projectChoicesLoaded, setProjectChoicesLoaded] = React.useState(false);
  const [projectChoicesLoading, setProjectChoicesLoading] = React.useState(false);
  const [projectPhotoSaving, setProjectPhotoSaving] = React.useState(false);
  const [projectFinancialSyncing, setProjectFinancialSyncing] = React.useState(false);
  const [projectDocumentUnlinking, setProjectDocumentUnlinking] = React.useState("");
  const [arPaymentSaving, setArPaymentSaving] = React.useState(false);
  // Daily Entry: one editable sheet for a date + company, held here rather
  // than in the page so switching tabs and coming back keeps the edits.
  const [daySheetDate, setDaySheetDate] = React.useState(() => today());
  const [daySheetRows, setDaySheetRows] = React.useState([]);
  const [daySheetLoading, setDaySheetLoading] = React.useState(false);
  const [daySheetSaving, setDaySheetSaving] = React.useState(false);
  // Payroll: the selected run and its lines live here so leaving the tab and
  // coming back does not lose an in-progress draft.
  const [payrollPeriod, setPayrollPeriod] = React.useState(() => today().slice(0, 7));
  const [payrollRuns, setPayrollRuns] = React.useState([]);
  const [payrollRun, setPayrollRun] = React.useState(null);
  const [payrollLoading, setPayrollLoading] = React.useState(false);
  const [payrollSaving, setPayrollSaving] = React.useState(false);
  const [payrollEmployees, setPayrollEmployees] = React.useState([]);
  const [documents, setDocuments] = React.useState([]);
  const [documentDetail, setDocumentDetail] = React.useState(null);
  const [documentCounts, setDocumentCounts] = React.useState(null);
  const [documentsLoading, setDocumentsLoading] = React.useState(false);
  const [documentsUploading, setDocumentsUploading] = React.useState(false);
  const [uploadProgress, setUploadProgress] = React.useState({ done: 0, total: 0 });
  const [docFilterClass, setDocFilterClass] = React.useState("");
  const [docFilterStatus, setDocFilterStatus] = React.useState("");
  const [docQuery, setDocQuery] = React.useState("");
  const [prefetchTick, setPrefetchTick] = React.useState(0);
  // Cluster hooks register their teardown here so resetWorkspaceState can reach
  // them even though they are created later in the render.
  const clusterResetRef = React.useRef({});
  const activeModuleRef = React.useRef(activeModule);
  const moduleStageRef = React.useRef(new Map());
  const detailCacheRef = React.useRef(new Map());
  const prefetchAbortRef = React.useRef(null);
  const prefetchRunRef = React.useRef(0);
  const detailRequestRef = React.useRef(0);
  const pendingDetailNavigationRef = React.useRef(
    initialRouteRef.current.view === "detail"
      ? { moduleKey: initialRouteRef.current.moduleKey, key: initialRouteRef.current.key }
      : null
  );
  const forceListNavigationRef = React.useRef(null);
  const navigationHistoryRef = React.useRef([]);
  const debtorsLoadingRef = React.useRef(false);
  const itemsLoadingRef = React.useRef(false);
  const paymentMethodsLoadingRef = React.useRef(false);
  const projectChoicesLoadingRef = React.useRef(false);

  const active = MODULES[activeModule];

  React.useEffect(() => {
    activeModuleRef.current = activeModule;
  }, [activeModule]);

  React.useEffect(() => {
    replaceRouteUrl({
      moduleKey: activeModule,
      view,
      key: detailKey,
      query,
    });
  }, [activeModule, detailKey, query, view]);

  const updateModuleStage = React.useCallback((moduleKey, patch) => {
    const current = moduleStageRef.current.get(moduleKey) || getEmptyStage();
    moduleStageRef.current.set(moduleKey, { ...current, ...patch });
  }, []);

  const applyModuleStage = React.useCallback((moduleKey) => {
    const stage = moduleStageRef.current.get(moduleKey);

    if (!stage) {
      setRows([]);
      setQuery("");
      setDetail(null);
      setDetailKey("");
      setView("list");
      setStatus({ tone: "", text: "Loading..." });
      return false;
    }

    setRows(stage.rows || []);
    setQuery(stage.query || "");
    setDetail(stage.detail || null);
    setDetailKey(stage.detailKey || "");
    setView(stage.view || "list");
    setStatus(stage.status || { tone: "ok", text: "Loaded from stage" });
    setFormData(stage.formData || {});
    setPrefetchTick((current) => current + 1);
    return true;
  }, []);

  const applyModuleListStage = React.useCallback((moduleKey) => {
    const stage = moduleStageRef.current.get(moduleKey);

    if (!stage) {
      setRows([]);
      setQuery("");
      setDetail(null);
      setDetailKey("");
      setView("list");
      setStatus({ tone: "", text: "Loading..." });
      setFormData({});
      return false;
    }

    setRows(stage.rows || []);
    setQuery(stage.query || "");
    setDetail(null);
    setDetailKey("");
    setView("list");
    setStatus(stage.status || { tone: "ok", text: "Loaded from stage" });
    setFormData(stage.formData || {});
    setPrefetchTick((current) => current + 1);
    updateModuleStage(moduleKey, {
      detail: null,
      detailKey: "",
      view: "list",
    });
    return true;
  }, [updateModuleStage]);

  const saveCurrentStage = React.useCallback(() => {
    updateModuleStage(activeModuleRef.current, {
      rows,
      query,
      detail,
      detailKey,
      view,
      status,
      formData,
      loaded: moduleStageRef.current.get(activeModuleRef.current)?.loaded || rows.length > 0,
    });
  }, [detail, detailKey, formData, query, rows, status, updateModuleStage, view]);

  const authHeaders = React.useCallback(
    (headers = {}) => {
      if (!token) return headers;
      return { ...headers, Authorization: `Bearer ${token}` };
    },
    [token]
  );

  const applySession = React.useCallback((payload) => {
    const nextCompanies =
      Array.isArray(payload?.companies) && payload.companies.length
        ? payload.companies
        : COMPANY_DATABASES;
    const nextDatabase = payload?.database || payload?.company?.value || nextCompanies[0]?.value || "";

    setSession(payload || null);
    setCompanies(nextCompanies);
    setSelectedCompany(nextDatabase);
  }, []);

  const resetWorkspaceState = React.useCallback(() => {
    moduleStageRef.current.clear();
    detailCacheRef.current.clear();
    navigationHistoryRef.current = [];
    pendingDetailNavigationRef.current = null;
    forceListNavigationRef.current = null;
    setRows([]);
    setQuery("");
    setDetail(null);
    setDetailKey("");
    setPdfExporting(false);
    setView("list");
    setFormData({});
    setDebtors([]);
    setDebtorsLoaded(false);
    setProjectFromDebtorOpen(false);
    setProjectFromDebtorCode("");
    setProjectFromDebtorLoading(false);
    setProjectCandidates([]);
    setProjectCandidatesOpen(false);
    setProjectCandidatesLoading(false);
    setProjectDocumentCandidates([]);
    setProjectDocumentCandidatesOpen(false);
    setProjectDocumentCandidatesLoading(false);
    setProjectDocumentCandidateLinks({});
    setProjectDocumentCandidateLinking("");
    setProjectDocumentAutoLinking(false);
    setItems([]);
    setItemsLoaded(false);
    setPaymentMethods([]);
    setPaymentMethodsLoaded(false);
    setProjectChoices([]);
    setProjectChoicesLoaded(false);
    setProjectChoicesLoading(false);
    setProjectPhotoSaving(false);
    setProjectFinancialSyncing(false);
    setProjectDocumentUnlinking("");
    setArPaymentSaving(false);
    clusterResetRef.current.adminsettings?.reset?.();
    clusterResetRef.current.bankreconciliation?.reset?.();
    clusterResetRef.current.website?.reset?.();
    debtorsLoadingRef.current = false;
    itemsLoadingRef.current = false;
    paymentMethodsLoadingRef.current = false;
    projectChoicesLoadingRef.current = false;
  }, []);

  const handleAuthError = React.useCallback((error) => {
    if (error.status === 401 || error.message === "not_authenticated") {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
      sessionStorage.removeItem("autocount_token");
      resetWorkspaceState();
      setSession(null);
      setToken("");
    }
  }, [resetWorkspaceState]);

  React.useEffect(() => {
    if (!token) return;

    async function loadCurrentSession() {
      try {
        const payload = await requestJson("/api/auth/me", {
          headers: authHeaders(),
        });
        applySession(payload);
      } catch (error) {
        handleAuthError(error);
      }
    }

    loadCurrentSession();
  }, [applySession, authHeaders, handleAuthError, token]);

  const {
    rdpAllow,
    rdpInput,
    rdpLoading,
    userDraft,
    userManagementLoading,
    userManagementSaving,
    users,
    addRdpIp,
    applyRdpAllowList,
    clearAdminSettingsOnSignOut,
    deleteUser,
    loadRdpAllowList,
    loadUsers,
    removeRdpIp,
    resetAdminSettings,
    setRdpInput,
    submitUser,
    updateUserDraftField,
  } = useAdminSettings({
    token,
    activeModuleRef,
    authHeaders,
    handleAuthError,
    setStatus,
    updateModuleStage,
  });

  clusterResetRef.current.adminsettings = {
    reset: resetAdminSettings,
    signOut: clearAdminSettingsOnSignOut,
  };


  const loadDocuments = React.useCallback(
    async (options = {}) => {
      if (!token) return;
      try {
        if (options.quiet !== true) setDocumentsLoading(true);
        const params = new URLSearchParams({ company: "all", limit: "300" });
        if (options.docClass ?? docFilterClass) params.set("class", options.docClass ?? docFilterClass);
        if (options.docStatus ?? docFilterStatus) params.set("status", options.docStatus ?? docFilterStatus);
        if (options.q ?? docQuery) params.set("q", options.q ?? docQuery);

        const [list, meta] = await Promise.all([
          requestJson(`/api/documents?${params}`, { headers: authHeaders() }),
          requestJson("/api/documents/meta?company=all", { headers: authHeaders() }),
        ]);
        const rows = normalizeRows(list);
        setDocuments(rows);
        setDocumentCounts(meta);
        if (options.quiet !== true) {
          const nextStatus = { tone: "ok", text: `${rows.length} document(s)` };
          updateModuleStage("documents", { rows: [], loaded: true, status: nextStatus });
          if (activeModuleRef.current === "documents") setStatus(nextStatus);
        }
      } catch (error) {
        handleAuthError(error);
        setStatus({ tone: "error", text: error.message });
      } finally {
        setDocumentsLoading(false);
      }
    },
    [authHeaders, docFilterClass, docFilterStatus, docQuery, handleAuthError, token, updateModuleStage]
  );

  // The worker reads documents after the upload has already returned, so the
  // only way this page learns a row finished is to look again. Polls only
  // while something is outstanding, and stops on its own once the queue drains.
  React.useEffect(() => {
    if (activeModule !== "documents") return undefined;
    if (!documentCounts?.queued) return undefined;
    const timer = window.setInterval(() => loadDocuments({ quiet: true }), 3000);
    return () => window.clearInterval(timer);
  }, [activeModule, documentCounts?.queued, loadDocuments]);

  const loadPayroll = React.useCallback(
    async (options = {}) => {
      if (!token) return;

      try {
        setPayrollLoading(true);
        if (options.showStatus !== false) {
          setStatus({ tone: "", text: "Loading payroll..." });
        }
        const payload = await requestJson("/api/payroll?company=all", {
          headers: authHeaders(),
        });
        const runs = normalizeRows(payload);
        setPayrollRuns(runs);

        // Needed by the Add Employee picker. Inactive staff are included on
        // purpose: back-entering last year's payroll means naming people who
        // have since left.
        try {
          const staff = await requestJson("/api/employees", { headers: authHeaders() });
          setPayrollEmployees(normalizeRows(staff));
        } catch (staffError) {
          // The run list is still usable without the picker, so this must not
          // take the whole page down with it.
          setPayrollEmployees([]);
        }
        const nextStatus = {
          tone: "ok",
          text: `${runs.length} payroll run${runs.length === 1 ? "" : "s"}`,
        };
        updateModuleStage("payroll", { rows: [], loaded: true, status: nextStatus });
        if (activeModuleRef.current === "payroll" && options.showStatus !== false) {
          setStatus(nextStatus);
        }
      } catch (error) {
        handleAuthError(error);
        setStatus({ tone: "error", text: error.message });
      } finally {
        setPayrollLoading(false);
      }
    },
    [authHeaders, handleAuthError, token, updateModuleStage]
  );

  const loadDaySheet = React.useCallback(
    async (date, company, options = {}) => {
      if (!token) return;

      try {
        setDaySheetLoading(true);
        if (options.showStatus !== false) {
          setStatus({ tone: "", text: "Loading daily entry..." });
        }
        const params = new URLSearchParams({ date, company });
        const payload = await requestJson(`/api/work-entries/day?${params.toString()}`, {
          headers: authHeaders(),
        });
        const rows = normalizeRows(payload);
        setDaySheetRows(rows);
        const nextStatus = {
          tone: "ok",
          text: `${rows.length} employee${rows.length === 1 ? "" : "s"} for ${date}`,
        };
        updateModuleStage("work-day-sheet", { rows: [], loaded: true, status: nextStatus });
        if (activeModuleRef.current === "work-day-sheet" && options.showStatus !== false) {
          setStatus(nextStatus);
        }
      } catch (error) {
        handleAuthError(error);
        setStatus({ tone: "error", text: error.message });
        setDaySheetRows([]);
      } finally {
        setDaySheetLoading(false);
      }
    },
    [authHeaders, handleAuthError, token, updateModuleStage]
  );

  const {
    websiteAssetUploading,
    websiteAssets,
    websiteAssetsLoading,
    websiteAuditLoading,
    websiteAuditLog,
    websiteContent,
    websiteContentDraft,
    websiteContentLoading,
    websiteContentSaving,
    websiteGallery,
    websiteGalleryDraft,
    websiteGalleryLoading,
    websitePreview,
    websitePreviewLoading,
    clearWebsiteAdminOnSignOut,
    importLegacyWebsiteGallery,
    loadWebsiteAssets,
    loadWebsiteAuditLog,
    loadWebsiteContent,
    loadWebsiteGallery,
    loadWebsitePreview,
    resetWebsiteAdmin,
    saveWebsiteContact,
    saveWebsiteFooter,
    saveWebsiteGalleryPhoto,
    saveWebsiteService,
    updateWebsiteContactField,
    updateWebsiteFooterField,
    updateWebsiteGalleryPhotoField,
    updateWebsiteServiceField,
    uploadWebsiteAsset,
  } = useWebsiteAdmin({
    token,
    activeModuleRef,
    authHeaders,
    handleAuthError,
    setStatus,
    updateModuleStage,
  });

  clusterResetRef.current.website = {
    reset: resetWebsiteAdmin,
    signOut: clearWebsiteAdminOnSignOut,
  };

  const loadDebtors = React.useCallback(
    async (force = false) => {
      if (!token || debtorsLoadingRef.current || (!force && debtorsLoaded)) return;

      try {
        debtorsLoadingRef.current = true;
        const payload = await requestJson("/api/autocount/debtors", {
          headers: authHeaders(),
        });
        const nextDebtors = normalizeRows(payload).filter((debtor) =>
          readValue(debtor, "debtorCode")
        );
        setDebtors(nextDebtors);
        setDebtorsLoaded(true);
      } catch (error) {
        handleAuthError(error);
      } finally {
        debtorsLoadingRef.current = false;
      }
    },
    [authHeaders, debtorsLoaded, handleAuthError, token]
  );

  const loadItems = React.useCallback(
    async (force = false) => {
      if (!token || itemsLoadingRef.current || (!force && itemsLoaded)) return;

      try {
        itemsLoadingRef.current = true;
        const payload = await requestJson("/api/autocount/items", {
          headers: authHeaders(),
        });
        const nextItems = normalizeRows(payload).filter((item) => readValue(item, "itemCode"));
        setItems(nextItems);
        setItemsLoaded(true);
      } catch (error) {
        handleAuthError(error);
      } finally {
        itemsLoadingRef.current = false;
      }
    },
    [authHeaders, handleAuthError, itemsLoaded, token]
  );

  const loadPaymentMethods = React.useCallback(
    async (force = false) => {
      if (
        !token ||
        paymentMethodsLoadingRef.current ||
        (!force && paymentMethodsLoaded)
      ) {
        return;
      }

      try {
        paymentMethodsLoadingRef.current = true;
        const payload = await requestJson("/api/autocount/payment-methods", {
          headers: authHeaders(),
        });
        const nextMethods = normalizeRows(payload).filter((method) =>
          readValue(method, "paymentMethod")
        );
        setPaymentMethods(nextMethods);
        setPaymentMethodsLoaded(true);
      } catch (error) {
        handleAuthError(error);
      } finally {
        paymentMethodsLoadingRef.current = false;
      }
    },
    [authHeaders, handleAuthError, paymentMethodsLoaded, token]
  );

  const loadProjectChoices = React.useCallback(
    async (force = false) => {
      if (!token) return [];
      if (projectChoicesLoadingRef.current) return projectChoices;
      if (!force && projectChoicesLoaded) return projectChoices;

      try {
        projectChoicesLoadingRef.current = true;
        setProjectChoicesLoading(true);
        const payload = await requestJson("/api/projects", {
          headers: authHeaders(),
        });
        const nextProjects = normalizeRows(payload).filter((project) =>
          readValue(project, "projectCode")
        );
        const nextStatus = {
          tone: "ok",
          text: `${nextProjects.length} project${nextProjects.length === 1 ? "" : "s"}`,
        };
        setProjectChoices(nextProjects);
        setProjectChoicesLoaded(true);
        updateModuleStage("projects", {
          rows: nextProjects,
          loaded: true,
          status: nextStatus,
        });
        if (activeModuleRef.current === "projects") {
          setRows(nextProjects);
        }
        return nextProjects;
      } catch (error) {
        handleAuthError(error);
        setStatus({ tone: "error", text: error.message });
        return [];
      } finally {
        projectChoicesLoadingRef.current = false;
        setProjectChoicesLoading(false);
      }
    },
    [
      authHeaders,
      handleAuthError,
      projectChoices,
      projectChoicesLoaded,
      token,
      updateModuleStage,
    ]
  );

  const stopBackgroundPrefetch = React.useCallback(() => {
    prefetchRunRef.current += 1;
    if (prefetchAbortRef.current) {
      prefetchAbortRef.current.abort();
      prefetchAbortRef.current = null;
    }
  }, []);

  const fetchDetail = React.useCallback(
    async (moduleKey, key, options = {}) => {
      const payload = await requestJson(
        getModuleDetailPath(moduleKey, key, options),
        {
          headers: authHeaders(),
          signal: options.signal,
        }
      );
      const nextDetail = normalizeDetail(payload);
      if (nextDetail && PROJECT_LINK_MODULES.has(moduleKey)) {
        try {
          const linkedPayload = await requestJson(getLinkedProjectsPath(moduleKey, key), {
            headers: authHeaders(),
            signal: options.signal,
          });
          nextDetail.projects = normalizeRows(linkedPayload);
        } catch (error) {
          if (error.status === 401 || error.message === "not_authenticated") throw error;
          nextDetail.projects = [];
        }
      }
      detailCacheRef.current.set(getDetailCacheKey(moduleKey, key), nextDetail);
      return nextDetail;
    },
    [authHeaders]
  );

  const loadModule = React.useCallback(async (moduleKey = activeModuleRef.current, options = {}) => {
    if (moduleKey === "rdp-allow") {
      await loadRdpAllowList();
      return;
    }
    if (moduleKey === "user-management") {
      await loadUsers();
      return;
    }
    if (moduleKey === "work-day-sheet") {
      await loadDaySheet(daySheetDate, selectedCompany);
      return;
    }
    if (moduleKey === "payroll") {
      await loadPayroll();
      return;
    }
    if (moduleKey === "documents") {
      await loadDocuments();
      return;
    }
    if (moduleKey === "website-content") {
      await loadWebsiteContent();
      return;
    }

    if (!token) {
      setRows([]);
      setStatus({ tone: "", text: "Login required" });
      return;
    }

    if (moduleKey === activeModuleRef.current) {
      setStatus({ tone: "", text: "Loading..." });
    }

    try {
      const payload = await requestJson(getModuleListPath(moduleKey, options), {
        headers: authHeaders(),
      });
      const nextRows = normalizeRows(payload);
      const nextStatus = {
        tone: "ok",
        text: `${nextRows.length} record${nextRows.length === 1 ? "" : "s"}`,
      };

      updateModuleStage(moduleKey, {
        rows: nextRows,
        detail: null,
        detailKey: "",
        view: "list",
        status: nextStatus,
        loaded: true,
      });

      if (moduleKey === "items") {
        setItems(nextRows.filter((item) => readValue(item, "itemCode")));
        setItemsLoaded(true);
      }
      if (moduleKey === "debtors") {
        setDebtors(nextRows.filter((debtor) => readValue(debtor, "debtorCode")));
        setDebtorsLoaded(true);
      }
      if (moduleKey === "projects") {
        setProjectChoices(nextRows.filter((project) => readValue(project, "projectCode")));
        setProjectChoicesLoaded(true);
      }

      if (moduleKey === activeModuleRef.current) {
        setRows(nextRows);
        setDetail(null);
        setDetailKey("");
        setView("list");
        setStatus(nextStatus);
      }
    } catch (error) {
      handleAuthError(error);
      const nextStatus = { tone: "error", text: error.message };
      updateModuleStage(moduleKey, { status: nextStatus });
      if (moduleKey === activeModuleRef.current) {
        setRows([]);
        setStatus(nextStatus);
      }
    }
  }, [
    authHeaders,
    handleAuthError,
    loadDaySheet,
    loadPayroll,
    loadRdpAllowList,
    loadUsers,
    loadWebsiteContent,
    token,
    updateModuleStage,
  ]);

  const loadDetail = React.useCallback(
    async (key, options = {}) => {
      if (!key || !token) return;

      stopBackgroundPrefetch();

      setDetailKey(key);
      setView("detail");

      const cacheKey = getDetailCacheKey(activeModule, key);
      if (!options.force && detailCacheRef.current.has(cacheKey)) {
        const cachedDetail = detailCacheRef.current.get(cacheKey);
        const nextStatus = { tone: "ok", text: "Detail loaded" };

        setDetail(cachedDetail);
        setDetailLoading(false);
        setStatus(nextStatus);
        updateModuleStage(activeModule, {
          detail: cachedDetail,
          detailKey: key,
          view: "detail",
          status: nextStatus,
        });
        setPrefetchTick((current) => current + 1);
        return;
      }

      const requestId = detailRequestRef.current + 1;
      detailRequestRef.current = requestId;

      try {
        setDetailLoading(true);
        setStatus({ tone: "", text: "Loading detail..." });

        const nextDetail = await fetchDetail(activeModule, key, {
          refresh: options.force,
        });
        if (detailRequestRef.current === requestId) {
          const nextStatus = { tone: "ok", text: "Detail loaded" };
          setDetail(nextDetail);
          setStatus(nextStatus);
          updateModuleStage(activeModule, {
            detail: nextDetail,
            detailKey: key,
            view: "detail",
            status: nextStatus,
          });
        }
      } catch (error) {
        if (isAbortError(error)) return;
        handleAuthError(error);
        if (detailRequestRef.current === requestId) {
          const nextStatus = { tone: "error", text: error.message };
          setDetail(null);
          setStatus(nextStatus);
          updateModuleStage(activeModule, { status: nextStatus });
        }
      } finally {
        if (detailRequestRef.current === requestId) {
          setDetailLoading(false);
        }
        setPrefetchTick((current) => current + 1);
      }
    },
    [activeModule, fetchDetail, handleAuthError, stopBackgroundPrefetch, token, updateModuleStage]
  );

  const getCurrentRoute = React.useCallback(() => {
    return normalizeRoute({
      moduleKey: activeModuleRef.current,
      view,
      key: detailKey,
      query,
    });
  }, [detailKey, query, view]);

  const showModuleList = React.useCallback(
    (moduleKey = activeModuleRef.current) => {
      stopBackgroundPrefetch();
      pendingDetailNavigationRef.current = null;
      detailRequestRef.current += 1;

      if (moduleKey !== activeModuleRef.current) {
        saveCurrentStage();
        forceListNavigationRef.current = moduleKey;
        setActiveModule(moduleKey);
      }

      const restored = applyModuleListStage(moduleKey);
      if (!restored && moduleKey === "rdp-allow") {
        loadRdpAllowList();
      } else if (!restored && moduleKey !== "rdp-allow") {
        loadModule(moduleKey);
      }
    },
    [applyModuleListStage, loadModule, loadRdpAllowList, saveCurrentStage, stopBackgroundPrefetch]
  );

  const restoreRoute = React.useCallback(
    (route) => {
      const nextRoute = normalizeRoute(route);
      stopBackgroundPrefetch();
      pendingDetailNavigationRef.current = null;
      detailRequestRef.current += 1;
      saveCurrentStage();

      if (nextRoute.moduleKey === activeModuleRef.current) {
        setQuery(nextRoute.query);
        if (nextRoute.view === "detail" && nextRoute.key) {
          loadDetail(nextRoute.key);
        } else {
          showModuleList(nextRoute.moduleKey);
        }
        return;
      }

      if (nextRoute.view === "detail" && nextRoute.key) {
        pendingDetailNavigationRef.current = {
          moduleKey: nextRoute.moduleKey,
          key: nextRoute.key,
        };
        forceListNavigationRef.current = null;
        setActiveModule(nextRoute.moduleKey);
        applyModuleStage(nextRoute.moduleKey);
        return;
      }

      showModuleList(nextRoute.moduleKey);
    },
    [applyModuleStage, loadDetail, saveCurrentStage, showModuleList, stopBackgroundPrefetch]
  );

  const navigateBack = React.useCallback(() => {
    const previousRoute = navigationHistoryRef.current.pop();
    if (previousRoute) {
      restoreRoute(previousRoute);
      return;
    }

    showModuleList(activeModuleRef.current);
  }, [restoreRoute, showModuleList]);

  const openRelatedDetail = React.useCallback(
    (moduleKey, key) => {
      const targetKey = String(key || "").trim();
      if (!moduleKey || !targetKey || !token) return;

      stopBackgroundPrefetch();
      navigationHistoryRef.current.push(getCurrentRoute());
      saveCurrentStage();

      if (moduleKey === activeModuleRef.current) {
        loadDetail(targetKey);
        return;
      }

      pendingDetailNavigationRef.current = { moduleKey, key: targetKey };
      setActiveModule(moduleKey);
      applyModuleStage(moduleKey);
    },
    [applyModuleStage, getCurrentRoute, loadDetail, saveCurrentStage, stopBackgroundPrefetch, token]
  );

  React.useEffect(() => {
    if (!ENABLE_BACKGROUND_DETAIL_PREFETCH || !token || rows.length === 0) return undefined;

    const moduleKey = activeModule;
    const module = MODULES[moduleKey];
    const runId = prefetchRunRef.current + 1;
    const controller = new AbortController();

    prefetchRunRef.current = runId;
    prefetchAbortRef.current = controller;

    async function prefetchDetails() {
      for (const row of rows) {
        if (prefetchRunRef.current !== runId || controller.signal.aborted) return;

        const key = getRowKey(row, module);
        if (!key || detailCacheRef.current.has(getDetailCacheKey(moduleKey, key))) {
          continue;
        }

        try {
          await fetchDetail(moduleKey, key, { signal: controller.signal });
        } catch (error) {
          if (isAbortError(error)) return;
          if (error.status === 401 || error.message === "not_authenticated") {
            handleAuthError(error);
            return;
          }
        }

        await wait(120);
      }
    }

    const timer = window.setTimeout(prefetchDetails, 180);

    return () => {
      window.clearTimeout(timer);
      if (prefetchAbortRef.current === controller) {
        controller.abort();
        prefetchAbortRef.current = null;
      }
    };
  }, [activeModule, fetchDetail, handleAuthError, prefetchTick, rows, token]);

  React.useEffect(() => {
    if (token) return;

    setDebtors([]);
    setDebtorsLoaded(false);
    setProjectFromDebtorOpen(false);
    setProjectFromDebtorCode("");
    setProjectFromDebtorLoading(false);
    setProjectCandidates([]);
    setProjectCandidatesOpen(false);
    setProjectCandidatesLoading(false);
    setProjectDocumentCandidates([]);
    setProjectDocumentCandidatesOpen(false);
    setProjectDocumentCandidatesLoading(false);
    setProjectDocumentCandidateLinks({});
    setProjectDocumentCandidateLinking("");
    setProjectDocumentAutoLinking(false);
    setItems([]);
    setItemsLoaded(false);
    setPaymentMethods([]);
    setPaymentMethodsLoaded(false);
    setProjectChoices([]);
    setProjectChoicesLoaded(false);
    setProjectChoicesLoading(false);
    setProjectPhotoSaving(false);
    setProjectFinancialSyncing(false);
    setProjectDocumentUnlinking("");
    clusterResetRef.current.adminsettings?.signOut?.();
    clusterResetRef.current.bankreconciliation?.signOut?.();
    clusterResetRef.current.website?.signOut?.();
  }, [token]);

  React.useEffect(() => {
    stopBackgroundPrefetch();
    detailRequestRef.current += 1;
    const hasPendingDetail =
      pendingDetailNavigationRef.current?.moduleKey === activeModule;
    const forceList = forceListNavigationRef.current === activeModule;
    if (forceList) {
      forceListNavigationRef.current = null;
    }

    let restored = false;
    if (hasPendingDetail) {
      const stage = moduleStageRef.current.get(activeModule);
      setRows(stage?.rows || []);
      setQuery(stage?.query || "");
      setDetail(null);
      setDetailKey(pendingDetailNavigationRef.current.key);
      setView("detail");
      setStatus({ tone: "", text: "Loading detail..." });
      setFormData(stage?.formData || {});
    } else {
      restored = forceList ? applyModuleListStage(activeModule) : applyModuleStage(activeModule);
    }

    if (token) {
      const stage = moduleStageRef.current.get(activeModule);
      if (!stage?.loaded && !hasPendingDetail) {
        loadModule(activeModule);
      } else if (restored && !hasPendingDetail) {
        setStatus({
          tone: "ok",
          text: `${(stage.rows || []).length} staged record${
            (stage.rows || []).length === 1 ? "" : "s"
          }`,
        });
      }
    } else {
      setRows([]);
    }
  }, [
    activeModule,
    applyModuleListStage,
    applyModuleStage,
    loadModule,
    stopBackgroundPrefetch,
    token,
  ]);

  React.useEffect(() => {
    const pending = pendingDetailNavigationRef.current;
    if (!pending || pending.moduleKey !== activeModule || !token) return undefined;

    pendingDetailNavigationRef.current = null;
    let cancelled = false;

    async function loadPendingDetail() {
      const stage = moduleStageRef.current.get(activeModule);
      if (!stage?.loaded) {
        await loadModule(activeModule);
      }
      if (!cancelled) {
        await loadDetail(pending.key);
      }
    }

    loadPendingDetail();

    return () => {
      cancelled = true;
    };
  }, [activeModule, loadDetail, loadModule, token]);

  React.useEffect(() => {
    if (!token || view !== "detail" || !PROJECT_LINK_MODULES.has(activeModule)) return;
    loadProjectChoices();
  }, [activeModule, loadProjectChoices, token, view]);

  const filteredRows = React.useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) => JSON.stringify(row).toLowerCase().includes(needle));
  }, [query, rows]);
  const {
    bankAccountChoices,
    bankFilters,
    bankReconcileActualBalance,
    bankReconcileDraft,
    bankReconcilePreviewLoading,
    bankReconcileSaving,
    bankReconcileStatementDate,
    bankSummary,
    displayedRows,
    selectedBankTransKeys,
    selectedBankTransSet,
    visibleBankSummary,
    visibleOpenBankTransKeys,
    clearBankReconciliationOnSignOut,
    clearBankTransSelection,
    commitBankReconciliation,
    previewBankReconciliation,
    resetBankReconciliation,
    selectVisibleOpenBankTransactions,
    setBankReconcileActualBalance,
    setBankReconcileDraft,
    setBankReconcileStatementDate,
    toggleBankTransSelection,
    toggleVisibleOpenBankTransSelection,
    updateBankFilter,
  } = useBankReconciliation({
    activeModule,
    rows,
    filteredRows,
    authHeaders,
    handleAuthError,
    setStatus,
    loadModule,
    detailCacheRef,
    moduleStageRef,
  });

  clusterResetRef.current.bankreconciliation = {
    reset: resetBankReconciliation,
    signOut: clearBankReconciliationOnSignOut,
  };


  async function openPayrollRun(runId) {
    if (!runId) { setPayrollRun(null); return; }
    try {
      setPayrollLoading(true);
      const run = await requestJson(`/api/payroll/${runId}`, { headers: authHeaders() });
      setPayrollRun(run);
      setPayrollPeriod(run.period);
      setStatus({ tone: "ok", text: `${run.company} ${run.period} - ${run.status}` });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setPayrollLoading(false);
    }
  }

  async function generatePayrollRun(replace) {
    // Regenerate rebuilds from the day sheet, which drops hand-typed lines.
    // Those are the expensive ones -- somebody read them off paper -- so
    // losing them to a button press should take a deliberate answer.
    if (replace) {
      const byHand = (payrollRun?.items || []).filter((item) => item.manual);
      if (byHand.length) {
        const names = byHand.map((item) => item.name).join(", ");
        if (!window.confirm(
          `Regenerating rebuilds this run from the day sheet and will discard ${byHand.length} hand-added line(s): ${names}. Continue?`
        )) return;
      }
    }
    try {
      setPayrollLoading(true);
      setStatus({ tone: "", text: "Generating from timesheet..." });
      const run = await requestJson("/api/payroll", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ company: selectedCompany, period: payrollPeriod, replace }),
      });
      setPayrollRun(run);
      setStatus({ tone: "ok", text: `Generated ${run.headcount} line(s) for ${run.period}` });
      await loadPayroll({ showStatus: false });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setPayrollLoading(false);
    }
  }

  function updatePayrollItem(itemId, field, value) {
    setPayrollRun((current) =>
      current
        ? {
            ...current,
            items: current.items.map((item) =>
              item.id === itemId ? { ...item, [field]: value } : item
            ),
          }
        : current
    );
  }

  async function savePayrollItem(itemId) {
    const item = payrollRun?.items?.find((row) => row.id === itemId);
    if (!item) return;
    try {
      setPayrollSaving(true);
      const saved = await requestJson(`/api/payroll/items/${itemId}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          fixedAllowance: item.fixedAllowance,
          adjustment: item.adjustment,
          epfEmployee: item.epfEmployee,
          socsoEmployee: item.socsoEmployee,
          eisEmployee: item.eisEmployee,
          pcb: item.pcb,
          otherDeduction: item.otherDeduction,
        }),
      });
      // Reload the run so the footer totals move with the line.
      const run = await requestJson(`/api/payroll/${saved.runId}`, { headers: authHeaders() });
      setPayrollRun(run);
      setStatus({ tone: "ok", text: `Saved ${saved.employeeCode}` });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setPayrollSaving(false);
    }
  }

  async function lockPayrollRun() {
    if (!payrollRun) return;
    if (!window.confirm(
      `Lock ${payrollRun.company} ${payrollRun.period}? Figures are frozen and the lines can no longer be edited.`
    )) return;
    try {
      setPayrollSaving(true);
      const run = await requestJson(`/api/payroll/${payrollRun.id}/lock`, {
        method: "POST",
        headers: authHeaders(),
      });
      setPayrollRun(run);
      setStatus({ tone: "ok", text: `Locked ${run.period}` });
      await loadPayroll({ showStatus: false });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setPayrollSaving(false);
    }
  }

  async function deletePayrollRun() {
    if (!payrollRun) return;
    if (!window.confirm(`Delete the draft for ${payrollRun.company} ${payrollRun.period}?`)) return;
    try {
      setPayrollSaving(true);
      await requestJson(`/api/payroll/${payrollRun.id}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      setPayrollRun(null);
      setStatus({ tone: "ok", text: "Draft deleted" });
      await loadPayroll({ showStatus: false });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setPayrollSaving(false);
    }
  }

  async function downloadPayslips() {
    if (!payrollRun) return;
    // Fetched rather than linked. Auth is a Bearer token, and a plain <a href>
    // sends no Authorization header, so navigating to the URL just returns 401.
    //
    // The other way out would be ?token= in the query string, which is what the
    // project-photo route does. Not here: a payslip carries IC numbers and
    // salaries, and a token in the URL ends up in the nginx access log, the
    // browser history and any Referer sent onward.
    try {
      setPayrollSaving(true);
      const response = await fetch(`/api/payroll/${payrollRun.id}/payslips.pdf`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        let message = `Request failed: ${response.status}`;
        try {
          message = (await response.json()).error || message;
        } catch (parseError) {
          /* the error body was not JSON; the status is all we have */
        }
        const error = new Error(message);
        error.status = response.status;
        throw error;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `payslips-${payrollRun.company}-${payrollRun.period}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      // Revoked on a later tick: Chrome aborts the download if the object URL
      // dies before it has actually started reading it.
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
      setStatus({ tone: "ok", text: `Payslips for ${payrollRun.period} downloaded` });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setPayrollSaving(false);
    }
  }

  // Sent in small batches rather than one giant request. Fifty phone photos is
  // a few hundred megabytes; one multipart body that size is a single point of
  // failure and gives no progress until it either lands or times out.
  const UPLOAD_BATCH = 4;

  async function uploadDocuments(files) {
    if (!files.length) return;
    setDocumentsUploading(true);
    setUploadProgress({ done: 0, total: files.length });
    let stored = 0;
    let duplicates = 0;
    let skipped = 0;
    const rejected = [];
    try {
      for (let index = 0; index < files.length; index += UPLOAD_BATCH) {
        const chunk = files.slice(index, index + UPLOAD_BATCH);
        const form = new FormData();
        form.append("company", selectedCompany);
        chunk.forEach((file) => form.append("files", file));
        const result = await requestJson("/api/documents", {
          method: "POST",
          headers: authHeaders(),
          body: form,
        });
        stored += result.stored?.length || 0;
        duplicates += result.duplicates?.length || 0;
        skipped += result.skipped || 0;
        (result.rejected || []).forEach((row) => rejected.push(row));
        setUploadProgress({ done: Math.min(index + chunk.length, files.length), total: files.length });
        await loadDocuments({ quiet: true });
      }
      const parts = [`${stored} filed`];
      if (skipped) parts.push(`${skipped} kept but not read`);
      if (duplicates) parts.push(`${duplicates} already on record`);
      if (rejected.length) parts.push(`${rejected.length} rejected`);
      setStatus({ tone: rejected.length ? "warn" : "ok", text: parts.join(", ") });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setDocumentsUploading(false);
      setUploadProgress({ done: 0, total: 0 });
      await loadDocuments({ quiet: true });
    }
  }

  async function openDocument(documentId) {
    try {
      const detail = await requestJson(`/api/documents/${documentId}`, { headers: authHeaders() });
      setDocumentDetail(detail);
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    }
  }

  async function reanalyseDocument(documentId) {
    try {
      await requestJson(`/api/documents/${documentId}/analyse`, {
        method: "POST",
        headers: authHeaders(),
      });
      setStatus({ tone: "ok", text: "Queued to be read again" });
      await loadDocuments({ quiet: true });
      await openDocument(documentId);
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    }
  }

  async function deleteDocument(documentId) {
    const row = documents.find((item) => item.id === documentId);
    if (!window.confirm(`Delete ${row?.filename || "this document"}? The file is removed too.`)) return;
    try {
      await requestJson(`/api/documents/${documentId}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (documentDetail?.id === documentId) setDocumentDetail(null);
      setStatus({ tone: "ok", text: "Deleted" });
      await loadDocuments({ quiet: true });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    }
  }

  async function addPayrollItem(employeeId) {
    if (!payrollRun || !employeeId) return;
    try {
      setPayrollSaving(true);
      const item = await requestJson(`/api/payroll/${payrollRun.id}/items`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ employeeId }),
      });
      const run = await requestJson(`/api/payroll/${payrollRun.id}`, { headers: authHeaders() });
      setPayrollRun(run);
      setStatus({ tone: "ok", text: `Added ${item.name}; fill in the amounts on the row` });
      await loadPayroll({ showStatus: false });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setPayrollSaving(false);
    }
  }

  async function removePayrollItem(itemId) {
    const line = (payrollRun?.items || []).find((item) => item.id === itemId);
    if (!line) return;
    if (!window.confirm(`Remove ${line.name} from ${payrollRun.period}?`)) return;
    try {
      setPayrollSaving(true);
      await requestJson(`/api/payroll/items/${itemId}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      const run = await requestJson(`/api/payroll/${payrollRun.id}`, { headers: authHeaders() });
      setPayrollRun(run);
      setStatus({ tone: "ok", text: `Removed ${line.name}` });
      await loadPayroll({ showStatus: false });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setPayrollSaving(false);
    }
  }

  function updateDaySheetRow(employeeId, field, value) {
    setDaySheetRows((current) =>
      current.map((row) => (row.employeeId === employeeId ? { ...row, [field]: value } : row))
    );
  }

  async function saveDaySheet() {
    try {
      setDaySheetSaving(true);
      setStatus({ tone: "", text: "Saving daily entry..." });
      const payload = await requestJson("/api/work-entries/day", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          workDate: daySheetDate,
          company: selectedCompany,
          rows: daySheetRows.map((row) => ({
            employeeId: row.employeeId,
            dayUnits: row.dayUnits,
            otHours: row.otHours,
            overnightNights: row.overnightNights,
            overnightHours: row.overnightHours,
            projectCode: row.projectCode,
            note: row.note,
          })),
        }),
      });
      setDaySheetRows(normalizeRows(payload));
      setStatus({
        tone: "ok",
        text: `Saved ${payload.saved || 0}, cleared ${payload.deleted || 0}`,
      });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setDaySheetSaving(false);
    }
  }

  function changeDaySheetDate(value) {
    setDaySheetDate(value);
    loadDaySheet(value, selectedCompany);
  }

  function updateQuery(value) {
    setQuery(value);
    updateModuleStage(activeModuleRef.current, { query: value });
  }

  async function submitLogin(event) {
    event.preventDefault();
    setStatus({ tone: "", text: "Signing in..." });

    try {
      const result = await requestJson("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(login),
      });
      const nextToken =
        result?.access_token ||
        result?.token ||
        result?.sessionToken ||
        result?.session_id ||
        "";

      if (nextToken) {
        sessionStorage.setItem(TOKEN_STORAGE_KEY, nextToken);
        sessionStorage.removeItem("autocount_token");
        resetWorkspaceState();
        applySession(result);
        setLogin((current) => ({ ...current, password: "" }));
        setToken(nextToken);
      }

      setStatus({ tone: "ok", text: "Signed in" });
    } catch (error) {
      setStatus({ tone: "error", text: error.message });
    }
  }

  function logout() {
    stopBackgroundPrefetch();
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    sessionStorage.removeItem("autocount_token");
    resetWorkspaceState();
    setSession(null);
    setToken("");
    setStatus({ tone: "", text: "Signed out" });
  }

  async function refreshModule() {
    if (activeModule === "rdp-allow") {
      await loadRdpAllowList();
      return;
    }
    if (activeModule === "user-management") {
      await loadUsers();
      return;
    }
    if (activeModule === "website-content") {
      await loadWebsiteContent();
      return;
    }

    if (view === "detail" && detailKey) {
      await loadDetail(detailKey, { force: true });
    } else {
      await loadModule(activeModule, { refresh: true });
    }
  }

  async function createArPaymentFromInvoice(payload) {
    const amount = toNumber(payload?.amount, 0);
    if (amount <= 0) {
      const error = new Error("Payment amount must be greater than zero");
      setStatus({ tone: "error", text: error.message });
      throw error;
    }

    try {
      setArPaymentSaving(true);
      setStatus({ tone: "", text: "Saving AR payment..." });
      const result = await requestJson("/api/autocount/ar-payments", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ ...payload, amount }),
      });
      const createdDocNo = result.docNo || "";
      const invoiceKey = payload.invoiceDocNo || detailKey;

      detailCacheRef.current.delete(getDetailCacheKey("invoices", invoiceKey));
      detailCacheRef.current.delete(getDetailCacheKey("invoices", String(payload.invoiceDocKey || "")));
      moduleStageRef.current.delete("ar-payments");

      if (invoiceKey) {
        await loadDetail(invoiceKey, { force: true });
      }

      setStatus({
        tone: "ok",
        text: createdDocNo ? `Saved AR payment ${createdDocNo}` : "AR payment saved",
      });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      throw error;
    } finally {
      setArPaymentSaving(false);
    }
  }

  async function exportDetailPdf() {
    if (!detailKey || !PDF_EXPORT_MODULES.has(activeModule)) return;

    try {
      setPdfExporting(true);
      setStatus({ tone: "", text: getPdfExportStatus(activeModule) });
      const response = await fetch(
        `/api/autocount/${activeModule}/pdf?key=${encodeURIComponent(detailKey)}`,
        {
          headers: authHeaders(),
        }
      );

      if (!response.ok) {
        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json")
          ? await response.json()
          : await response.text();
        const message =
          typeof payload === "object" ? payload.detail || payload.error : payload;
        const error = new Error(message || `PDF export failed: ${response.status}`);
        error.status = response.status;
        throw error;
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = getDownloadFilename(response, `${activeModule}-${detailKey}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setStatus({ tone: "ok", text: getPdfExportStatus(activeModule, true) });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    } finally {
      setPdfExporting(false);
    }
  }

  async function exportPaymentRequestPdf(amount) {
    if (!detailKey || activeModule !== "invoices") return false;
    const outstandingAmount = Math.max(toNumber(readValue(detail, "outstanding"), 0), 0);
    if (outstandingAmount <= 0) {
      setStatus({ tone: "error", text: "Invoice has no outstanding amount" });
      return false;
    }

    const requestAmount = Math.min(Math.max(toNumber(amount, 0), 0), outstandingAmount);
    if (requestAmount <= 0) {
      setStatus({ tone: "error", text: "Request amount must be greater than zero" });
      return false;
    }

    try {
      setPaymentRequestExporting(true);
      setStatus({ tone: "", text: "Preparing payment request..." });
      const response = await fetch("/api/autocount/invoices/payment-request/pdf", {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ key: detailKey, amount: requestAmount }),
      });

      if (!response.ok) {
        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json")
          ? await response.json()
          : await response.text();
        const message =
          typeof payload === "object" ? payload.detail || payload.error : payload;
        const error = new Error(message || `Payment request export failed: ${response.status}`);
        error.status = response.status;
        throw error;
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = getDownloadFilename(response, `payment-request-${detailKey}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setStatus({ tone: "ok", text: "Payment request exported" });
      return true;
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      return false;
    } finally {
      setPaymentRequestExporting(false);
    }
  }

  async function switchCompany(event) {
    const database = event.target.value;
    if (!database || database === selectedCompany) return;

    stopBackgroundPrefetch();
    setSelectedCompany(database);
    setStatus({ tone: "", text: "Switching company..." });

    try {
      const payload = await requestJson("/api/session/company", {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ database }),
      });
      applySession(payload);
      resetWorkspaceState();

      if (activeModule === "rdp-allow") {
        await loadRdpAllowList();
      } else {
        await loadModule(activeModule);
      }
    } catch (error) {
      handleAuthError(error);
      applySession(session);
      setStatus({ tone: "error", text: error.message });
    }
  }

  function openNewForm() {
    setProjectFromDebtorOpen(false);
    setProjectCandidatesOpen(false);
    setProjectDocumentCandidatesOpen(false);
    if (!active.payload || !active.createLabel) {
      const unavailableStatus = { tone: "", text: `Create is not available for ${active.title}` };
      setStatus(unavailableStatus);
      updateModuleStage(activeModule, { status: unavailableStatus });
      return;
    }

    if (hasDebtorField(active) && !debtorsLoaded) {
      loadDebtors();
    }
    if (hasItemLineField(active) && !itemsLoaded) {
      loadItems();
    }

    const stage = moduleStageRef.current.get(activeModule);
    const stagedCreateForm =
      stage?.formData && (!stage.formData.__mode || stage.formData.__mode === "create")
        ? clone(stage.formData)
        : null;
    const nextFormData = stagedCreateForm || active.payload();
    nextFormData.__mode = "create";
    if (!stage?.formData && hasItemLineField(active)) {
      nextFormData.lines = (nextFormData.lines || [getLineTemplate(active)]).map((line) =>
        applyItemToLine(active, line, line.itemCode, items)
      );
    }
    const nextStatus = { tone: "", text: `New ${active.singular}` };
    setFormData(nextFormData);
    setView("new");
    setStatus(nextStatus);
    updateModuleStage(activeModule, {
      formData: nextFormData,
      view: "new",
      status: nextStatus,
    });
  }

  function openProjectEdit() {
    if (!active?.editable || !detail) return;
    // Projects fold several document-number lists into single inputs, so they
    // keep a bespoke builder; everything else is driven by formFields.
    const nextFormData =
      activeModule === "projects"
        ? getProjectFormFromDetail(detail)
        : getFormFromDetail(active, detail, detailKey);
    const nextStatus = {
      tone: "",
      text: `Edit ${readValue(detail, active.rowKey) || active.singular}`,
    };
    if (hasDebtorField(active) && !debtorsLoaded) {
      loadDebtors();
    }
    setFormData(nextFormData);
    setView("new");
    setStatus(nextStatus);
    updateModuleStage(activeModule, {
      formData: nextFormData,
      view: "new",
      status: nextStatus,
      detail,
      detailKey,
    });
  }

  function openProjectFromCurrentDocument() {
    if (!PROJECT_LINK_MODULES.has(activeModule) || !detail) return;
    const nextFormData = getProjectFormFromDocument(activeModule, detail);
    const sourceDocNo = readValue(detail, "docNo");
    const nextStatus = {
      tone: "",
      text: sourceDocNo ? `New Project from ${sourceDocNo}` : "New Project",
    };

    if (!debtorsLoaded) {
      loadDebtors();
    }

    stopBackgroundPrefetch();
    navigationHistoryRef.current.push(getCurrentRoute());
    saveCurrentStage();
    updateModuleStage("projects", {
      rows: moduleStageRef.current.get("projects")?.rows || [],
      detail: null,
      detailKey: "",
      formData: nextFormData,
      view: "new",
      status: nextStatus,
      loaded: moduleStageRef.current.get("projects")?.loaded || false,
    });
    setActiveModule("projects");
    setRows(moduleStageRef.current.get("projects")?.rows || []);
    setDetail(null);
    setDetailKey("");
    setFormData(nextFormData);
    setView("new");
    setStatus(nextStatus);
  }

  async function fetchProjectDraftFromDebtor(debtorCode) {
    const code = String(debtorCode || "").trim();
    if (!code) {
      throw new Error("Debtor code is required");
    }
    return requestJson(`/api/projects/draft-from-debtor/${encodeURIComponent(code)}`, {
      headers: authHeaders(),
    });
  }

  async function applyProjectDraftFromDebtor(debtorCode) {
    const code = String(debtorCode || "").trim();
    if (!code || activeModule !== "projects") return;

    try {
      setStatus({ tone: "", text: "Loading debtor address..." });
      const draft = await fetchProjectDraftFromDebtor(code);
      setFormData((current) => {
        if (String(current?.debtorCode || "").trim() !== code) return current;
        const next = mergeProjectDraft(current, draft);
        updateModuleStage(activeModuleRef.current, { formData: next });
        return next;
      });
      setStatus({ tone: "ok", text: "Debtor address loaded" });
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
    }
  }

  function openProjectDraftForm(draft) {
    const debtorCode = readValue(draft, "debtorCode");
    if (!debtorCode) {
      setStatus({ tone: "error", text: "Debtor code is required" });
      return false;
    }

    const nextFormData = getProjectFormFromDraft(draft);
    const nextStatus = {
      tone: "",
      text: `New Project from ${readValue(draft, "debtorName") || debtorCode}`,
    };

    if (!debtorsLoaded) {
      loadDebtors();
    }

    setProjectFromDebtorOpen(false);
    setProjectCandidatesOpen(false);
    setProjectDocumentCandidatesOpen(false);
    stopBackgroundPrefetch();
    navigationHistoryRef.current.push(getCurrentRoute());
    saveCurrentStage();
    updateModuleStage("projects", {
      rows: moduleStageRef.current.get("projects")?.rows || [],
      detail: null,
      detailKey: "",
      formData: nextFormData,
      view: "new",
      status: nextStatus,
      loaded: moduleStageRef.current.get("projects")?.loaded || false,
    });
    setActiveModule("projects");
    setRows(moduleStageRef.current.get("projects")?.rows || []);
    setDetail(null);
    setDetailKey("");
    setFormData(nextFormData);
    setView("new");
    setStatus(nextStatus);
    return true;
  }

  async function openProjectFromDebtor(debtorSource = detail) {
    const debtorCode = readValue(debtorSource, "debtorCode");
    if (!debtorCode) {
      setStatus({ tone: "error", text: "Debtor code is required" });
      return false;
    }

    try {
      setStatus({ tone: "", text: "Preparing project from debtor..." });
      const draft = await fetchProjectDraftFromDebtor(debtorCode);
      return openProjectDraftForm(draft);
    } catch (error) {
      handleAuthError(error);
      if (!options.silent) {
        setStatus({ tone: "error", text: error.message });
      }
      return false;
    }
  }

  function openProjectFromDebtorPicker() {
    if (!debtorsLoaded) {
      loadDebtors();
    }
    setProjectFromDebtorCode("");
    setProjectCandidatesOpen(false);
    setProjectDocumentCandidatesOpen(false);
    setProjectFromDebtorOpen(true);
    setStatus({ tone: "", text: "Select debtor for new project" });
  }

  async function submitProjectFromDebtor(event) {
    event.preventDefault();
    const debtorCode = String(projectFromDebtorCode || "").trim();
    if (!debtorCode) {
      setStatus({ tone: "error", text: "Debtor is required" });
      return;
    }

    try {
      setProjectFromDebtorLoading(true);
      const opened = await openProjectFromDebtor({ debtorCode });
      if (opened) {
        setProjectFromDebtorOpen(false);
        setProjectFromDebtorCode("");
      }
    } finally {
      setProjectFromDebtorLoading(false);
    }
  }

  async function loadProjectCandidates() {
    if (!token) return [];

    try {
      setProjectFromDebtorOpen(false);
      setProjectDocumentCandidatesOpen(false);
      setProjectCandidatesOpen(true);
      setProjectCandidatesLoading(true);
      setStatus({ tone: "", text: "Scanning AutoCount debtors..." });
      const payload = await requestJson("/api/projects/candidates/from-debtors?limit=300", {
        headers: authHeaders(),
      });
      const nextCandidates = normalizeRows(payload);
      setProjectCandidates(nextCandidates);
      setStatus({
        tone: "ok",
        text: `${nextCandidates.length} debtor candidate${
          nextCandidates.length === 1 ? "" : "s"
        }`,
      });
      return nextCandidates;
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      return [];
    } finally {
      setProjectCandidatesLoading(false);
    }
  }

  function openProjectFromCandidate(candidate) {
    const draft = candidate?.draft || candidate;
    openProjectDraftForm(draft);
  }

  async function loadProjectDocumentCandidates() {
    if (!token) return [];

    try {
      setProjectFromDebtorOpen(false);
      setProjectCandidatesOpen(false);
      setProjectDocumentCandidatesOpen(true);
      setProjectDocumentCandidatesLoading(true);
      setStatus({ tone: "", text: "Scanning AutoCount documents..." });
      if (!projectChoicesLoaded) {
        loadProjectChoices();
      }
      const payload = await requestJson("/api/projects/candidates/from-documents?limit=300", {
        headers: authHeaders(),
      });
      const nextCandidates = normalizeRows(payload);
      setProjectDocumentCandidates(nextCandidates);
      setProjectDocumentCandidateLinks((current) => {
        const next = { ...current };
        nextCandidates.forEach((candidate) => {
          const key = getDocumentCandidateKey(candidate);
          const recommendedCode = readValue(candidate.recommendedProject, "projectCode");
          const existingProjects = candidate.existingProjects || [];
          if (!next[key] && recommendedCode) {
            next[key] = recommendedCode;
          } else if (!next[key] && existingProjects.length === 1) {
            next[key] = readValue(existingProjects[0], "projectCode");
          }
        });
        return next;
      });
      setStatus({
        tone: "ok",
        text: `${nextCandidates.length} document candidate${
          nextCandidates.length === 1 ? "" : "s"
        }`,
      });
      return nextCandidates;
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      return [];
    } finally {
      setProjectDocumentCandidatesLoading(false);
    }
  }

  function openProjectFromDocumentCandidate(candidate) {
    const draft = candidate?.draft || candidate;
    openProjectDraftForm(draft);
  }

  async function linkProjectDocument(moduleKey, docNo, projectCode, options = {}) {
    const targetCode = String(projectCode || "").trim();
    const documentNo = String(docNo || "").trim();
    if (!targetCode || !documentNo) {
      setStatus({ tone: "error", text: "Project and document number are required" });
      return false;
    }

    let projects = options.projects || projectChoices;
    let project = projects.find(
      (item) =>
        String(readValue(item, "projectCode")).trim().toLowerCase() ===
        targetCode.toLowerCase()
    );
    if (!project) {
      projects = await loadProjectChoices(true);
      project = projects.find(
        (item) =>
          String(readValue(item, "projectCode")).trim().toLowerCase() ===
          targetCode.toLowerCase()
      );
    }

    if (!project) {
      setStatus({ tone: "error", text: `Project not found: ${targetCode}` });
      return false;
    }

    const patch = getProjectDocumentPatch(moduleKey, project, documentNo);
    if (!patch) {
      setStatus({ tone: "error", text: "This document type cannot be linked to projects" });
      return false;
    }

    try {
      if (!options.silent) {
        setStatus({ tone: "", text: "Linking project..." });
      }
      const result = await requestJson(getModuleUpdatePath("projects", targetCode), {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(patch),
      });
      const linkedCode = readValue(result, "projectCode") || targetCode;
      detailCacheRef.current.delete(getDetailCacheKey(moduleKey, documentNo));
      detailCacheRef.current.delete(getDetailCacheKey("projects", linkedCode));
      if (!options.skipProjectRefresh) {
        await loadProjectChoices(true);
      }
      if (options.reloadDetail && detailKey) {
        detailCacheRef.current.delete(getDetailCacheKey(activeModule, detailKey));
        await loadDetail(detailKey, { force: true });
      }
      if (!options.silent) {
        setStatus({ tone: "ok", text: `Linked ${linkedCode}` });
      }
      return true;
    } catch (error) {
      handleAuthError(error);
      if (!options.silent) {
        setStatus({ tone: "error", text: error.message });
      }
      return false;
    }
  }

  async function linkDocumentCandidateToProject(candidate) {
    const key = getDocumentCandidateKey(candidate);
    const targetCode = projectDocumentCandidateLinks[key];
    if (!targetCode) {
      setStatus({ tone: "error", text: "Select a project to link" });
      return false;
    }

    try {
      setProjectDocumentCandidateLinking(key);
      const ok = await linkProjectDocument(
        readValue(candidate, "module"),
        readValue(candidate, "docNo"),
        targetCode
      );
      if (ok) {
        setProjectDocumentCandidates((current) =>
          current.filter((item) => getDocumentCandidateKey(item) !== key)
        );
        setProjectDocumentCandidateLinks((current) => {
          const next = { ...current };
          delete next[key];
          return next;
        });
      }
      return ok;
    } finally {
      setProjectDocumentCandidateLinking("");
    }
  }

  async function autoLinkRecommendedDocuments() {
    if (projectDocumentAutoLinking) return;

    try {
      setProjectDocumentAutoLinking(true);
      setProjectDocumentCandidateLinking("auto");
      setStatus({ tone: "", text: "Checking recommended project links..." });

      const projects = await loadProjectChoices(true);
      const projectByCode = new Map(
        projects.map((project) => [
          String(readValue(project, "projectCode")).trim().toLowerCase(),
          project,
        ])
      );
      const reservedSlots = new Set();
      const linkable = [];
      let skipped = 0;

      projectDocumentCandidates.forEach((candidate) => {
        const moduleKey = readValue(candidate, "module");
        const docNo = readValue(candidate, "docNo");
        const recommendedCode = getRecommendedProjectCode(candidate);
        const recommendedScore = getRecommendedProjectScore(candidate);
        const project = projectByCode.get(String(recommendedCode).trim().toLowerCase());
        const primaryField = getProjectPrimaryDocumentField(moduleKey);
        const slotKey = `${String(recommendedCode).trim().toLowerCase()}:${moduleKey}`;

        if (!moduleKey || !docNo || !recommendedCode || recommendedScore < AUTO_LINK_RECOMMENDED_MIN_SCORE) {
          skipped += 1;
          return;
        }
        if (!project) {
          skipped += 1;
          return;
        }
        if (primaryField && readValue(project, primaryField)) {
          skipped += 1;
          return;
        }
        if (reservedSlots.has(slotKey)) {
          skipped += 1;
          return;
        }

        reservedSlots.add(slotKey);
        linkable.push({ candidate, moduleKey, docNo, recommendedCode });
      });

      if (!linkable.length) {
        setStatus({
          tone: "",
          text: `No recommendations at ${AUTO_LINK_RECOMMENDED_MIN_SCORE}+ ready for auto link`,
        });
        return;
      }

      setStatus({ tone: "", text: `Auto linking ${linkable.length} document(s)...` });
      const linkedKeys = [];
      let failed = 0;
      for (const item of linkable) {
        const ok = await linkProjectDocument(
          item.moduleKey,
          item.docNo,
          item.recommendedCode,
          { projects, silent: true, skipProjectRefresh: true }
        );
        if (ok) {
          linkedKeys.push(getDocumentCandidateKey(item.candidate));
        } else {
          failed += 1;
        }
      }

      if (linkedKeys.length) {
        setProjectDocumentCandidates((current) =>
          current.filter((candidate) => !linkedKeys.includes(getDocumentCandidateKey(candidate)))
        );
        setProjectDocumentCandidateLinks((current) => {
          const next = { ...current };
          linkedKeys.forEach((key) => {
            delete next[key];
          });
          return next;
        });
        await loadProjectChoices(true);
      }

      setStatus({
        tone: failed ? "error" : "ok",
        text: `Auto linked ${linkedKeys.length}; failed ${failed}; skipped ${skipped}`,
      });
    } finally {
      setProjectDocumentCandidateLinking("");
      setProjectDocumentAutoLinking(false);
    }
  }

  async function linkCurrentDocumentToProject(projectCode) {
    if (!PROJECT_LINK_MODULES.has(activeModule) || !detail) return false;

    const docNo = readValue(detail, "docNo") || detailKey;
    return linkProjectDocument(activeModule, docNo, projectCode, { reloadDetail: true });
  }

  async function linkDocumentToCurrentProject(moduleKey, docNo) {
    if (activeModule !== "projects" || !detail) return false;

    const projectKey = detailKey || readValue(detail, "projectCode");
    if (!projectKey) {
      setStatus({ tone: "error", text: `${active.singular} key is missing` });
      return false;
    }

    return linkProjectDocument(moduleKey, docNo, projectKey, { reloadDetail: true });
  }

  async function unlinkCurrentProjectDocument(moduleKey, docNo) {
    if (activeModule !== "projects" || !detail) return false;

    const projectKey = detailKey || readValue(detail, "projectCode");
    const patch = getProjectDocumentUnlinkPatch(moduleKey, detail, docNo);
    if (!projectKey || !patch) {
      setStatus({ tone: "error", text: "Project document link is missing" });
      return false;
    }

    const unlinkKey = `${moduleKey}:${docNo}`;
    try {
      setProjectDocumentUnlinking(unlinkKey);
      setStatus({ tone: "", text: "Removing document link..." });
      const result = await requestJson(getModuleUpdatePath("projects", projectKey), {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(patch),
      });
      const updatedProjectKey = readValue(result, "projectCode") || projectKey;
      detailCacheRef.current.delete(getDetailCacheKey("projects", updatedProjectKey));
      detailCacheRef.current.delete(getDetailCacheKey(moduleKey, docNo));
      await loadProjectChoices(true);
      await loadDetail(updatedProjectKey, { force: true });
      setStatus({ tone: "ok", text: `Unlinked ${docNo}` });
      return true;
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      return false;
    } finally {
      setProjectDocumentUnlinking("");
    }
  }

  async function syncCurrentProjectFinancials(summary) {
    if (activeModule !== "projects" || !detail) return false;

    const projectKey = detailKey || readValue(detail, "projectCode");
    if (!projectKey) {
      setStatus({ tone: "error", text: `${active.singular} key is missing` });
      return false;
    }

    try {
      setProjectFinancialSyncing(true);
      setStatus({ tone: "", text: "Syncing project financials..." });
      const patch = getProjectFinancialPatch(summary || {});
      const result = await requestJson(getModuleUpdatePath("projects", projectKey), {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(patch),
      });
      const updatedProjectKey = readValue(result, "projectCode") || projectKey;
      detailCacheRef.current.delete(getDetailCacheKey("projects", updatedProjectKey));
      await loadProjectChoices(true);
      await loadDetail(updatedProjectKey, { force: true });
      setStatus({ tone: "ok", text: "Project financials synced" });
      return true;
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      return false;
    } finally {
      setProjectFinancialSyncing(false);
    }
  }

  async function reloadCurrentProjectAfterPhoto() {
    const projectKey = detailKey || readValue(detail, "projectCode");
    if (!projectKey) return;

    detailCacheRef.current.delete(getDetailCacheKey("projects", projectKey));
    await loadProjectChoices(true);
    await loadDetail(projectKey, { force: true });
  }

  async function uploadProjectPhotos(files, payload = {}) {
    if (activeModule !== "projects" || !detailKey) return false;
    const selectedFiles = Array.from(files || []).filter(Boolean);
    if (!selectedFiles.length) {
      setStatus({ tone: "error", text: "Select at least one image" });
      return false;
    }

    const formData = new FormData();
    selectedFiles.forEach((file) => formData.append("images", file));
    formData.append("serviceCategory", payload.serviceCategory || "");
    formData.append("caption", payload.caption || "");
    formData.append("altText", payload.altText || "");
    formData.append("isPublic", payload.isPublic ? "1" : "0");
    formData.append("websiteVisible", payload.websiteVisible ? "1" : "0");

    try {
      setProjectPhotoSaving(true);
      setStatus({ tone: "", text: "Uploading project photos..." });
      const result = await requestJson(`/api/projects/${encodeURIComponent(detailKey)}/photos`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
      });
      const uploadedCount = normalizeRows(result).length;
      await reloadCurrentProjectAfterPhoto();
      setStatus({
        tone: "ok",
        text: `Uploaded ${uploadedCount || selectedFiles.length} photo${
          (uploadedCount || selectedFiles.length) === 1 ? "" : "s"
        }`,
      });
      return true;
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      return false;
    } finally {
      setProjectPhotoSaving(false);
    }
  }

  async function updateProjectPhoto(photoId, patch) {
    if (activeModule !== "projects" || !photoId) return false;

    try {
      setProjectPhotoSaving(true);
      setStatus({ tone: "", text: "Saving photo..." });
      await requestJson(`/api/project-photos/${encodeURIComponent(photoId)}`, {
        method: "PATCH",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(patch),
      });
      await reloadCurrentProjectAfterPhoto();
      setStatus({ tone: "ok", text: "Photo saved" });
      return true;
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      return false;
    } finally {
      setProjectPhotoSaving(false);
    }
  }

  async function deleteProjectPhoto(photoId) {
    if (activeModule !== "projects" || !photoId) return false;

    try {
      setProjectPhotoSaving(true);
      setStatus({ tone: "", text: "Deleting photo..." });
      await requestJson(`/api/project-photos/${encodeURIComponent(photoId)}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      await reloadCurrentProjectAfterPhoto();
      setStatus({ tone: "ok", text: "Photo deleted" });
      return true;
    } catch (error) {
      handleAuthError(error);
      setStatus({ tone: "error", text: error.message });
      return false;
    } finally {
      setProjectPhotoSaving(false);
    }
  }

  function closeForm() {
    if (formData?.__mode === "edit" && detailKey) {
      const nextStatus = { tone: "ok", text: "Detail loaded" };
      setFormData({});
      setView("detail");
      setStatus(nextStatus);
      updateModuleStage(activeModule, {
        view: "detail",
        status: nextStatus,
        formData: null,
      });
      return;
    }

    const previousRoute = navigationHistoryRef.current.pop();
    if (previousRoute) {
      setFormData({});
      updateModuleStage(activeModule, { formData: null, view: "list" });
      restoreRoute(previousRoute);
      return;
    }

    updateModuleStage(activeModule, { formData: null });
    setFormData({});
    showModuleList(activeModule);
  }

  function updateFormField(name, value) {
    setFormData((current) => {
      const next = { ...current, [name]: value };
      if (name === "debtorCode") {
        const debtor = findDebtor(debtors, value);
        next.debtorName = debtor ? readValue(debtor, "debtorName") : "";
      }
      updateModuleStage(activeModuleRef.current, { formData: next });
      return next;
    });
    if (activeModule === "projects" && name === "debtorCode" && value) {
      applyProjectDraftFromDebtor(value);
    }
  }

  function updateLineField(lineIndex, name, value) {
    setFormData((current) => {
      const lines = [...(current.lines || [])];
      const nextLine =
        name === "itemCode"
          ? applyItemToLine(active, lines[lineIndex], value, items)
          : { ...lines[lineIndex], [name]: value };
      lines[lineIndex] = nextLine;
      const next = { ...current, lines };
      updateModuleStage(activeModuleRef.current, { formData: next });
      return next;
    });
  }

  function addLine() {
    if (hasItemLineField(active) && !itemsLoaded) {
      loadItems();
    }

    setFormData((current) => {
      const nextLine = getLineTemplate(active);
      const next = { ...current, lines: [...(current.lines || []), nextLine] };
      updateModuleStage(activeModuleRef.current, { formData: next });
      return next;
    });
  }

  function removeLine(lineIndex) {
    setFormData((current) => {
      const lines = (current.lines || []).filter((_, index) => index !== lineIndex);
      const next = { ...current, lines: lines.length ? lines : current.lines };
      updateModuleStage(activeModuleRef.current, { formData: next });
      return next;
    });
  }

  async function saveNewForm() {
    const formMode = formData?.__mode || "create";
    const payload = cleanFormPayload(formData);
    const updateKey = formData?.__editKey || detailKey || readValue(formData, active.rowKey);
    if (formMode === "edit" && !updateKey) {
      setStatus({ tone: "error", text: `${active.singular} key is missing` });
      return;
    }
    const savingStatus = { tone: "", text: "Saving..." };
    setStatus(savingStatus);
    updateModuleStage(activeModule, { status: savingStatus, formData });

    try {
      const result = await requestJson(
        formMode === "edit" ? getModuleUpdatePath(activeModule, updateKey) : getModuleCreatePath(activeModule),
        {
          method: formMode === "edit" ? "PATCH" : "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(payload),
        }
      );
      const createdKey =
        readValue(result, active.rowKey) ||
        result.projectCode ||
        result.docNo ||
        result.itemCode ||
        "";

      const savedStatus = { tone: "ok", text: createdKey ? `Saved ${createdKey}` : "Saved" };
      setStatus(savedStatus);
      detailCacheRef.current.delete(getDetailCacheKey(activeModule, createdKey || updateKey));
      updateModuleStage(activeModule, { status: savedStatus, formData: null });
      await loadModule();
      if (createdKey) {
        await loadDetail(createdKey);
      }
    } catch (error) {
      handleAuthError(error);
      const errorStatus = { tone: "error", text: error.message };
      setStatus(errorStatus);
      updateModuleStage(activeModule, { status: errorStatus, view: "new", formData });
    }
  }

  if (!token) {
    return (
      <LoginPage
        login={login}
        status={status}
        onLoginChange={(name, value) => setLogin((current) => ({ ...current, [name]: value }))}
        onSubmit={submitLogin}
      />
    );
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeModule={activeModule}
        onSelectModule={(key) => {
          navigationHistoryRef.current = [];
          showModuleList(key);
        }}
      />

      <main className="workspace">
        <Topbar
          companies={companies}
          module={active}
          selectedCompany={selectedCompany}
          session={session}
          onLogout={logout}
          onRefresh={refreshModule}
          onSwitchCompany={switchCompany}
        />

        {activeModule === "documents" ? (
          <DocumentsPage
            counts={documentCounts}
            detail={documentDetail}
            documents={documents}
            filterClass={docFilterClass}
            filterStatus={docFilterStatus}
            loading={documentsLoading}
            query={docQuery}
            status={status}
            uploadProgress={uploadProgress}
            uploading={documentsUploading}
            onDelete={deleteDocument}
            onFilterClass={(value) => {
              setDocFilterClass(value);
              loadDocuments({ docClass: value });
            }}
            onFilterStatus={(value) => {
              setDocFilterStatus(value);
              loadDocuments({ docStatus: value });
            }}
            onQuery={(value) => {
              setDocQuery(value);
              loadDocuments({ q: value, quiet: true });
            }}
            onReanalyse={reanalyseDocument}
            onRefresh={() => loadDocuments()}
            onSelect={openDocument}
            onUpload={uploadDocuments}
          />
        ) : activeModule === "payroll" ? (
          <PayrollPage
            loading={payrollLoading}
            period={payrollPeriod}
            run={payrollRun}
            runs={payrollRuns}
            saving={payrollSaving}
            status={status}
            onDelete={deletePayrollRun}
            employees={payrollEmployees}
            onAddItem={addPayrollItem}
            onDownloadPayslips={downloadPayslips}
            onRemoveItem={removePayrollItem}
            onGenerate={generatePayrollRun}
            onItemChange={updatePayrollItem}
            onItemSave={savePayrollItem}
            onLock={lockPayrollRun}
            onPeriodChange={setPayrollPeriod}
            onRefresh={() => loadPayroll()}
            onSelectRun={openPayrollRun}
          />
        ) : activeModule === "work-day-sheet" ? (
          <DaySheetPage
            companies={companies}
            company={selectedCompany}
            loading={daySheetLoading}
            rows={daySheetRows}
            saving={daySheetSaving}
            status={status}
            workDate={daySheetDate}
            onCompanyChange={(value) => switchCompany({ target: { value } })}
            onDateChange={changeDaySheetDate}
            onRefresh={() => loadDaySheet(daySheetDate, selectedCompany)}
            onRowChange={updateDaySheetRow}
            onSave={saveDaySheet}
          />
        ) : activeModule === "rdp-allow" ? (
          <RdpAllowPage
            data={rdpAllow}
            input={rdpInput}
            loading={rdpLoading}
            status={status}
            onAdd={addRdpIp}
            onAddCurrent={() => addRdpIp(null, rdpAllow?.currentRdpRemoteIp || "")}
            onApply={applyRdpAllowList}
            onInputChange={setRdpInput}
            onRefresh={() => loadRdpAllowList()}
            onRemove={removeRdpIp}
          />
        ) : activeModule === "user-management" ? (
          <UserManagementPage
            companies={companies}
            draft={userDraft}
            loading={userManagementLoading}
            saving={userManagementSaving}
            status={status}
            users={users}
            onDelete={deleteUser}
            onDraftChange={updateUserDraftField}
            onRefresh={() => loadUsers()}
            onSubmit={submitUser}
          />
        ) : activeModule === "website-content" ? (
          <WebsiteContentPage
            assetUploading={websiteAssetUploading}
            assets={websiteAssets}
            assetsLoading={websiteAssetsLoading}
            auditLoading={websiteAuditLoading}
            auditLog={websiteAuditLog}
            draft={websiteContentDraft || websiteContent}
            galleryDraft={websiteGalleryDraft || websiteGallery}
            gallerySaving={websiteContentSaving}
            loading={
              websiteContentLoading ||
              websiteGalleryLoading ||
              websiteAuditLoading ||
              websitePreviewLoading ||
              websiteAssetsLoading
            }
            preview={websitePreview}
            previewLoading={websitePreviewLoading}
            saving={websiteContentSaving}
            status={status}
            onContactChange={updateWebsiteContactField}
            onFooterChange={updateWebsiteFooterField}
            onGalleryPhotoChange={updateWebsiteGalleryPhotoField}
            onImportLegacyGallery={importLegacyWebsiteGallery}
            onOpenProject={(projectKey) => projectKey && openRelatedDetail("projects", projectKey)}
            onRefresh={() => loadWebsiteContent()}
            onRefreshPreview={() => loadWebsitePreview()}
            onSaveGalleryPhoto={saveWebsiteGalleryPhoto}
            onSaveContact={saveWebsiteContact}
            onSaveFooter={saveWebsiteFooter}
            onSaveService={saveWebsiteService}
            onServiceChange={updateWebsiteServiceField}
            onUploadAsset={uploadWebsiteAsset}
            token={token}
          />
        ) : view === "detail" ? (
          activeModule === "items" ? (
            <ItemDetailPage
              detail={detail}
              detailKey={detailKey}
              loading={detailLoading}
              module={active}
              status={status}
              onBack={navigateBack}
              onRefresh={() => detailKey && loadDetail(detailKey, { force: true })}
            />
          ) : activeModule === "debtors" ? (
            <DebtorDetailPage
              detail={detail}
              exportingPdf={pdfExporting}
              loading={detailLoading}
              status={status}
              onBack={navigateBack}
              onCreateProject={() => openProjectFromDebtor(detail)}
              onExportStatement={
                PDF_EXPORT_MODULES.has(activeModule) && detail ? exportDetailPdf : null
              }
              onRefresh={() => detailKey && loadDetail(detailKey, { force: true })}
            />
          ) : (
            <DetailPage
              debtors={debtors}
              detail={detail}
              detailKey={detailKey}
              exportingPdf={pdfExporting}
              exportingPaymentRequest={paymentRequestExporting}
              loading={detailLoading}
              module={active}
              moduleKey={activeModule}
              creatingPayment={arPaymentSaving}
              paymentMethods={paymentMethods}
              projectChoices={projectChoices}
              projectChoicesLoading={projectChoicesLoading}
              projectPhotoSaving={projectPhotoSaving}
              projectFinancialSyncing={projectFinancialSyncing}
              projectDocumentUnlinking={projectDocumentUnlinking}
              status={status}
              token={token}
              onBack={navigateBack}
              onCreatePayment={createArPaymentFromInvoice}
              onDeleteProjectPhoto={deleteProjectPhoto}
              onExportPdf={
                PDF_EXPORT_MODULES.has(activeModule) && detail ? exportDetailPdf : null
              }
              onExportPaymentRequest={
                activeModule === "invoices" && detail ? exportPaymentRequestPdf : null
              }
              onCreateProjectFromDocument={openProjectFromCurrentDocument}
              onEditProject={openProjectEdit}
              onLinkProjectDocument={linkDocumentToCurrentProject}
              onLinkProject={linkCurrentDocumentToProject}
              onLoadProjects={() => loadProjectChoices()}
              onSyncProjectFinancials={syncCurrentProjectFinancials}
              onUnlinkProjectDocument={unlinkCurrentProjectDocument}
              onUpdateProjectPhoto={updateProjectPhoto}
              onUploadProjectPhotos={uploadProjectPhotos}
              onPaymentFormOpen={() => loadPaymentMethods()}
              onOpenPayment={(paymentKey) => openRelatedDetail("ar-payments", paymentKey)}
              onOpenProject={(projectKey) => openRelatedDetail("projects", projectKey)}
              onOpenDocument={(moduleKey, documentKey) => openRelatedDetail(moduleKey, documentKey)}
              onRefresh={() => detailKey && loadDetail(detailKey, { force: true })}
            />
          )
        ) : view === "new" ? (
          activeModule === "items" ? (
            <ItemNewPage
              data={formData}
              module={active}
              onBack={closeForm}
              onChange={updateFormField}
              onSave={saveNewForm}
              status={status}
            />
          ) : (
            <NewPage
              data={formData}
              debtors={debtors}
              items={items}
              mode={formData?.__mode || "create"}
              module={active}
              onAddLine={addLine}
              onBack={closeForm}
              onChange={updateFormField}
              onLineChange={updateLineField}
              onRemoveLine={removeLine}
              onSave={saveNewForm}
              status={status}
            />
          )
        ) : (
          <section className="content-panel">
            <div className="toolbar">
              <label className="search-box">
                <span>Search</span>
                <div className="input-with-icon">
                  <Search aria-hidden="true" size={16} />
                  <input
                    value={query}
                    onChange={(event) => updateQuery(event.target.value)}
                    type="search"
                    placeholder="Doc no, code, name"
                  />
                </div>
              </label>
              <div className="toolbar-actions">
                {active.createLabel && active.payload && (
                  <button className="secondary-button" type="button" onClick={openNewForm}>
                    <Plus aria-hidden="true" size={16} />
                    {active.createLabel}
                  </button>
                )}
                {activeModule === "projects" && (
                  <button
                    className="secondary-button"
                    disabled={projectDocumentCandidatesLoading}
                    type="button"
                    onClick={loadProjectDocumentCandidates}
                  >
                    <FileText aria-hidden="true" size={16} />
                    {projectDocumentCandidatesLoading ? "Scanning..." : "Document Candidates"}
                  </button>
                )}
                {activeModule === "projects" && (
                  <button
                    className="secondary-button"
                    disabled={projectCandidatesLoading}
                    type="button"
                    onClick={loadProjectCandidates}
                  >
                    <Users aria-hidden="true" size={16} />
                    {projectCandidatesLoading ? "Scanning..." : "Debtor Candidates"}
                  </button>
                )}
                {activeModule === "projects" && (
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={openProjectFromDebtorPicker}
                  >
                    <Users aria-hidden="true" size={16} />
                    From Debtor
                  </button>
                )}
                <button className="primary-button" type="button" onClick={refreshModule}>
                  <Send aria-hidden="true" size={16} />
                  Sync
                </button>
              </div>
            </div>

            {activeModule === "bank-transactions" && bankSummary && visibleBankSummary && (
              <BankingListControls
                accountChoices={bankAccountChoices}
                actualBalance={bankReconcileActualBalance}
                commitLoading={bankReconcileSaving}
                filters={bankFilters}
                previewLoading={bankReconcilePreviewLoading}
                reconcileDraft={bankReconcileDraft}
                selectedCount={selectedBankTransKeys.length}
                statementDate={bankReconcileStatementDate}
                summary={bankSummary}
                visibleSummary={visibleBankSummary}
                onActualBalanceChange={(value) => {
                  setBankReconcileActualBalance(value);
                }}
                onClearSelection={clearBankTransSelection}
                onCommitReconcile={commitBankReconciliation}
                onFilterChange={updateBankFilter}
                onPreviewReconcile={previewBankReconciliation}
                onSelectVisibleOpen={selectVisibleOpenBankTransactions}
                onStatementDateChange={(value) => {
                  setBankReconcileStatementDate(value);
                  setBankReconcileDraft(null);
                }}
              />
            )}

            {activeModule === "projects" && projectCandidatesOpen && (
              <DebtorCandidatesPanel
                candidates={projectCandidates}
                loading={projectCandidatesLoading}
                onClose={() => setProjectCandidatesOpen(false)}
                onCreate={openProjectFromCandidate}
                onRefresh={loadProjectCandidates}
              />
            )}

            {activeModule === "projects" && projectDocumentCandidatesOpen && (
              <DocumentCandidatesPanel
                autoLinking={projectDocumentAutoLinking}
                candidates={projectDocumentCandidates}
                linkingKey={projectDocumentCandidateLinking}
                links={projectDocumentCandidateLinks}
                loading={projectDocumentCandidatesLoading}
                projectChoices={projectChoices}
                projectChoicesLoaded={projectChoicesLoaded}
                projectChoicesLoading={projectChoicesLoading}
                onAutoLink={autoLinkRecommendedDocuments}
                onClose={() => setProjectDocumentCandidatesOpen(false)}
                onCreate={openProjectFromDocumentCandidate}
                onLink={linkDocumentCandidateToProject}
                onLoadProjects={loadProjectChoices}
                onRefresh={loadProjectDocumentCandidates}
                onSelectProject={(candidateKey, value) =>
                  setProjectDocumentCandidateLinks((current) => ({
                    ...current,
                    [candidateKey]: value,
                  }))
                }
              />
            )}

            {activeModule === "projects" && projectFromDebtorOpen && (
              <ProjectFromDebtorForm
                debtorCode={projectFromDebtorCode}
                debtors={debtors}
                debtorsLoaded={debtorsLoaded}
                loading={projectFromDebtorLoading}
                onCancel={() => {
                  setProjectFromDebtorOpen(false);
                  setProjectFromDebtorCode("");
                }}
                onDebtorCodeChange={setProjectFromDebtorCode}
                onSubmit={submitProjectFromDebtor}
              />
            )}

            <div className={`status-bar ${status.tone}`}>{status.text}</div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {activeModule === "bank-transactions" && (
                      <th className="selection-cell">
                        <input
                          aria-label="Select visible open bank transactions"
                          checked={
                            visibleOpenBankTransKeys.length > 0 &&
                            visibleOpenBankTransKeys.every((key) => selectedBankTransSet.has(key))
                          }
                          disabled={visibleOpenBankTransKeys.length === 0}
                          type="checkbox"
                          onChange={(event) =>
                            toggleVisibleOpenBankTransSelection(event.target.checked)
                          }
                        />
                      </th>
                    )}
                    {active.columns.map(([, label]) => (
                      <th key={label}>{label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayedRows.length === 0 ? (
                    <tr className="empty-row">
                      <td colSpan={active.columns.length + (activeModule === "bank-transactions" ? 1 : 0)}>
                        No records
                      </td>
                    </tr>
                  ) : (
                    displayedRows.map((row, rowIndex) => {
                      const key = getRowKey(row, active);
                      const bankTransKey = getBankTransactionKey(row);
                      const bankRowOpen = getBankReconState(row) === "open";
                      const bankRowSelected = selectedBankTransSet.has(bankTransKey);
                      return (
                        <tr
                          className={`${detailKey === key ? "selected-row" : ""} ${
                            bankRowSelected ? "checked-row" : ""
                          }`}
                          key={key || row.DocKey || row.docKey || rowIndex}
                          onClick={() => key && loadDetail(key)}
                        >
                          {activeModule === "bank-transactions" && (
                            <td
                              className="selection-cell"
                              onClick={(event) => event.stopPropagation()}
                            >
                              <input
                                aria-label={`Select bank transaction ${bankTransKey || rowIndex + 1}`}
                                checked={bankRowSelected}
                                disabled={!bankTransKey || !bankRowOpen}
                                type="checkbox"
                                onChange={(event) =>
                                  toggleBankTransSelection(bankTransKey, event.target.checked)
                                }
                              />
                            </td>
                          )}
                          {active.columns.map(([columnKey, , kind]) => (
                            <td
                              className={kind === "number" || kind === "money" ? "number" : ""}
                              key={columnKey}
                            >
                              {formatValue(
                                readValue(row, columnKey),
                                kind,
                                getDocumentCurrency(row)
                              )}
                            </td>
                          ))}
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
