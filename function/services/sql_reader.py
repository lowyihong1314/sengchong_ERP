from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


try:
    import pymssql
except ImportError:  # pragma: no cover - handled at runtime
    pymssql = None


class SqlReadService:
    def __init__(self, settings):
        self.settings = settings

    @property
    def configured(self):
        return (
            self.settings.autocount_sql_direct_enabled
            and pymssql is not None
            and bool(self.settings.autocount_sql_user)
            and bool(self.settings.autocount_sql_password)
        )

    def list_resource(self, resource, session):
        if not self.configured:
            return False, {"error": "SQL direct reader is not configured."}

        try:
            with self._connect(session["database"]) as conn:
                if resource == "invoices":
                    return True, {"data": self._list_invoices(conn)}
                if resource == "ar-payments":
                    return True, {"data": self._list_ar_payments(conn)}
                if resource == "ar-deposits":
                    return True, {"data": self._list_ar_deposits(conn)}
                if resource == "ap-invoices":
                    return True, {"data": self._list_ap_invoices(conn)}
                if resource == "ap-payments":
                    return True, {"data": self._list_ap_payments(conn)}
                if resource == "ap-deposits":
                    return True, {"data": self._list_ap_deposits(conn)}
                if resource == "cash-book":
                    return True, {"data": self._list_cash_book(conn)}
                if resource == "bank-transactions":
                    return True, {"data": self._list_bank_transactions(conn)}
                if resource == "creditors":
                    return True, {"data": self._list_creditors(conn)}
                if resource == "payment-methods":
                    return True, {"data": self._list_payment_methods(conn)}
                if resource == "quotations":
                    return True, {"data": self._list_quotations(conn)}
                if resource == "purchase-orders":
                    return True, {"data": self._list_purchase_orders(conn)}
                if resource == "items":
                    return True, {"data": self._list_items(conn)}
                if resource == "debtors":
                    return True, {"data": self._list_debtors(conn)}
        except Exception as exc:
            return False, {"error": f"SQL direct reader failed: {exc}"}

        return False, {"error": f"SQL direct reader does not support resource: {resource}"}

    def list_debtor_project_candidates(self, session, limit=200):
        if not self.configured:
            return False, {"error": "SQL direct reader is not configured."}

        try:
            with self._connect(session["database"]) as conn:
                return True, {"data": self._list_debtor_project_candidates(conn, limit)}
        except Exception as exc:
            return False, {"error": f"SQL direct reader failed: {exc}"}

    def list_debtors_by_codes(self, session, debtor_codes):
        if not self.configured:
            return False, {"error": "SQL direct reader is not configured."}

        codes = []
        seen = set()
        for debtor_code in debtor_codes or []:
            code = str(debtor_code or "").strip()
            key = code.lower()
            if code and key not in seen:
                codes.append(code)
                seen.add(key)
        if not codes:
            return True, {"data": []}

        try:
            with self._connect(session["database"]) as conn:
                return True, {"data": self._list_debtors_by_codes(conn, codes[:500])}
        except Exception as exc:
            return False, {"error": f"SQL direct reader failed: {exc}"}

    def list_bank_transactions_by_keys(self, session, bank_trans_keys):
        if not self.configured:
            return False, {"error": "SQL direct reader is not configured."}

        keys = []
        seen = set()
        for bank_trans_key in bank_trans_keys or []:
            key = str(bank_trans_key or "").strip()
            normalized = key.lower()
            if key and normalized not in seen:
                keys.append(key)
                seen.add(normalized)
        if not keys:
            return True, {"data": []}

        try:
            with self._connect(session["database"]) as conn:
                return True, {"data": self._list_bank_transactions(conn, keys[:500])}
        except Exception as exc:
            return False, {"error": f"SQL direct reader failed: {exc}"}

    def get_resource_detail(self, resource, key, session):
        if not self.configured:
            return False, {"error": "SQL direct reader is not configured."}

        try:
            with self._connect(session["database"]) as conn:
                if resource == "invoices":
                    data = self._get_invoice(conn, key)
                elif resource == "ar-payments":
                    data = self._get_ar_payment(conn, key)
                elif resource == "ar-deposits":
                    data = self._get_ar_deposit(conn, key)
                elif resource == "ap-invoices":
                    data = self._get_ap_invoice(conn, key)
                elif resource == "ap-payments":
                    data = self._get_ap_payment(conn, key)
                elif resource == "ap-deposits":
                    data = self._get_ap_deposit(conn, key)
                elif resource == "cash-book":
                    data = self._get_cash_book(conn, key)
                elif resource == "bank-transactions":
                    data = self._get_bank_transaction(conn, key)
                elif resource == "creditors":
                    data = self._get_creditor(conn, key)
                elif resource == "payment-methods":
                    return False, {"error": "payment-methods only supports list."}
                elif resource == "quotations":
                    data = self._get_quotation(conn, key)
                elif resource == "purchase-orders":
                    data = self._get_purchase_order(conn, key)
                elif resource == "items":
                    data = self._get_item(conn, key)
                elif resource == "debtors":
                    data = self._get_debtor(conn, key)
                else:
                    return False, {
                        "error": f"SQL direct reader does not support resource: {resource}"
                    }

                if data is None:
                    return False, {"error": f"{resource} not found: {key}"}
                return True, {"data": data}
        except Exception as exc:
            return False, {"error": f"SQL direct reader failed: {exc}"}

    def _connect(self, database):
        server, port = self._direct_endpoint()
        kwargs = {
            "server": server,
            "user": self.settings.autocount_sql_user,
            "password": self.settings.autocount_sql_password,
            "database": database,
            "login_timeout": 5,
            "timeout": 15,
            "as_dict": True,
        }
        if port:
            kwargs["port"] = port
        return pymssql.connect(**kwargs)

    def _direct_endpoint(self):
        if self.settings.autocount_sql_direct_server:
            return self.settings.autocount_sql_direct_server, self.settings.autocount_sql_direct_port

        server = self.settings.autocount_sql_server
        if "\\" in server:
            host, instance = server.split("\\", 1)
            if host.upper() in {"DESKTOP-P9E4V36", "(LOCAL)", "LOCALHOST", "."}:
                host = self._windows_host_ip() or host
            return host, self.settings.autocount_sql_direct_port or self._default_instance_port(instance)

        return server, self.settings.autocount_sql_direct_port

    @staticmethod
    def _windows_host_ip():
        resolv_conf = Path("/etc/resolv.conf")
        try:
            for raw_line in resolv_conf.read_text(encoding="utf-8").splitlines():
                parts = raw_line.strip().split()
                if len(parts) == 2 and parts[0] == "nameserver":
                    return parts[1]
        except OSError:
            return ""
        return ""

    @staticmethod
    def _default_instance_port(instance):
        if instance.upper() == "A2006":
            return 50532
        return 0

    def _list_invoices(self, conn):
        sql = """
            SELECT TOP 200
                i.DocKey AS docKey,
                i.DocNo AS docNo,
                i.DocDate AS docDate,
                i.DebtorCode AS debtorCode,
                d.CompanyName AS debtorName,
                i.Description AS description,
                i.CurrencyCode AS currencyCode,
                i.Total AS total,
                i.NetTotal AS netTotal,
                i.PaymentAmt AS paymentAmt,
                i.Outstanding AS outstanding,
                i.DocStatus AS status,
                i.Cancelled AS cancelled
            FROM ARInvoice i
            LEFT JOIN Debtor d ON d.AccNo = i.DebtorCode
            ORDER BY i.DocDate DESC, i.DocKey DESC
        """
        return self._fetch_all(conn, sql)

    def _get_invoice(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    i.DocKey AS docKey,
                    i.DocNo AS docNo,
                    i.DocDate AS docDate,
                    i.DueDate AS dueDate,
                    i.DebtorCode AS debtorCode,
                    d.CompanyName AS debtorName,
                    i.Description AS description,
                    i.CurrencyCode AS currencyCode,
                    i.CurrencyRate AS currencyRate,
                    i.JournalType AS journalType,
                    i.Total AS total,
                    i.Tax AS tax,
                    i.NetTotal AS netTotal,
                    i.PaymentAmt AS paymentAmt,
                    i.Outstanding AS outstanding,
                    i.DocStatus AS status,
                    i.Cancelled AS cancelled
                FROM ARInvoice i
                LEFT JOIN Debtor d ON d.AccNo = i.DebtorCode
                WHERE i.DocNo = %s OR CONVERT(varchar(30), i.DocKey) = %s
                ORDER BY i.DocKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT
                    DtlKey AS dtlKey,
                    Seq AS seq,
                    AccNo AS accNo,
                    Description AS description,
                    Amount AS amount,
                    SubTotal AS subTotal,
                    TaxCode AS taxCode,
                    Tax AS tax,
                    NetAmount AS netAmount,
                    ProjNo AS projNo,
                    DeptNo AS deptNo
                FROM ARInvoiceDTL
                WHERE DocKey = %s
                ORDER BY Seq, DtlKey
            """,
            (master["docKey"],),
        )
        master["arPayments"] = self._get_invoice_ar_payments(conn, master["docKey"])
        master["arPaymentLines"] = self._get_invoice_ar_payment_lines(conn, master["docKey"])
        return master

    def _get_invoice_ar_payments(self, conn, invoice_doc_key):
        return self._fetch_all(
            conn,
            """
                SELECT
                    p.DocKey AS paymentDocKey,
                    p.DocNo AS paymentDocNo,
                    p.DocDate AS paymentDate,
                    p.DebtorCode AS debtorCode,
                    d.CompanyName AS debtorName,
                    p.Description AS paymentDescription,
                    p.CurrencyCode AS currencyCode,
                    p.PaymentAmt AS paymentTotal,
                    p.KnockOffAmt AS paymentKnockOffTotal,
                    p.LocalUnappliedAmount AS unappliedAmount,
                    p.RefundAmt AS refundAmount,
                    p.Cancelled AS cancelled,
                    p.DocStatus AS status,
                    payLine.PaymentMethod AS paymentMethod,
                    payLine.PaymentBy AS paymentBy,
                    payLine.ChequeNo AS chequeNo,
                    ko.KnockOffKey AS knockOffKey,
                    ko.KnockOffDocType AS knockOffDocType,
                    ko.Amount AS paidAmount,
                    ko.DiscountAmt AS discountAmount,
                    ko.GainLossDate AS gainLossDate
                FROM ARPaymentKnockOff ko
                JOIN ARPayment p ON p.DocKey = ko.DocKey
                LEFT JOIN Debtor d ON d.AccNo = p.DebtorCode
                OUTER APPLY (
                    SELECT TOP 1 PaymentMethod, PaymentBy, ChequeNo
                    FROM ARPaymentDTL pd
                    WHERE pd.DocKey = p.DocKey
                    ORDER BY pd.Seq, pd.DtlKey
                ) payLine
                WHERE ko.KnockOffDocKey = %s
                ORDER BY p.DocDate DESC, p.DocKey DESC, ko.KnockOffKey
            """,
            (invoice_doc_key,),
        )

    def _get_invoice_ar_payment_lines(self, conn, invoice_doc_key):
        return self._fetch_all(
            conn,
            """
                SELECT
                    kd.AutoKey AS autoKey,
                    p.DocNo AS paymentDocNo,
                    p.DocDate AS paymentDate,
                    ko.KnockOffKey AS knockOffKey,
                    kd.KnockOffDtlKey AS invoiceDtlKey,
                    iDtl.Seq AS invoiceSeq,
                    iDtl.Description AS invoiceLineDescription,
                    kd.Amount AS paidAmount,
                    kd.LocalPaymentAmt AS localPaymentAmount,
                    kd.LocalInvoiceAmt AS localInvoiceAmount
                FROM ARPaymentKnockOff ko
                JOIN ARPayment p ON p.DocKey = ko.DocKey
                JOIN ARPaymentKnockOffDetail kd ON kd.KnockOffKey = ko.KnockOffKey
                LEFT JOIN ARInvoiceDTL iDtl ON iDtl.DtlKey = kd.KnockOffDtlKey
                WHERE ko.KnockOffDocKey = %s
                ORDER BY p.DocDate DESC, p.DocKey DESC, iDtl.Seq, kd.AutoKey
            """,
            (invoice_doc_key,),
        )

    def _list_ar_payments(self, conn):
        sql = """
            SELECT TOP 200
                p.DocKey AS docKey,
                p.DocNo AS docNo,
                p.DocDate AS docDate,
                p.DebtorCode AS debtorCode,
                d.CompanyName AS debtorName,
                p.Description AS description,
                p.CurrencyCode AS currencyCode,
                p.PaymentAmt AS paymentAmt,
                p.KnockOffAmt AS knockOffAmt,
                p.LocalUnappliedAmount AS unappliedAmount,
                p.RefundAmt AS refundAmount,
                p.CBKey AS cashBookKey,
                cb.DocNo AS cashBookDocNo,
                payLine.PaymentMethod AS paymentMethod,
                payLine.PaymentBy AS paymentBy,
                payLine.ChequeNo AS chequeNo,
                p.Cancelled AS cancelled,
                p.DocStatus AS status
            FROM ARPayment p
            LEFT JOIN Debtor d ON d.AccNo = p.DebtorCode
            LEFT JOIN CB cb ON cb.DocKey = p.CBKey
            OUTER APPLY (
                SELECT TOP 1 PaymentMethod, PaymentBy, ChequeNo
                FROM ARPaymentDTL pd
                WHERE pd.DocKey = p.DocKey
                ORDER BY pd.Seq, pd.DtlKey
            ) payLine
            ORDER BY p.DocDate DESC, p.DocKey DESC
        """
        return self._fetch_all(conn, sql)

    def _get_ar_payment(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    p.DocKey AS docKey,
                    p.DocNo AS docNo,
                    p.DocDate AS docDate,
                    p.DebtorCode AS debtorCode,
                    d.CompanyName AS debtorName,
                    p.Description AS description,
                    p.ProjNo AS projNo,
                    p.DeptNo AS deptNo,
                    p.CurrencyCode AS currencyCode,
                    p.ToDebtorRate AS toDebtorRate,
                    p.ToHomeRate AS toHomeRate,
                    p.PaymentAmt AS paymentAmt,
                    p.LocalPaymentAmt AS localPaymentAmt,
                    p.KnockOffAmt AS knockOffAmt,
                    p.LocalUnappliedAmount AS unappliedAmount,
                    p.RefundAmt AS refundAmount,
                    p.CBKey AS cbKey,
                    p.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    p.SourceType AS sourceType,
                    p.SourceKey AS sourceKey,
                    p.HandOverDate AS handOverDate,
                    p.DocNo2 AS docNo2,
                    p.Cancelled AS cancelled,
                    p.DocStatus AS status,
                    p.Note AS note
                FROM ARPayment p
                LEFT JOIN Debtor d ON d.AccNo = p.DebtorCode
                LEFT JOIN CB cb ON cb.DocKey = p.CBKey
                WHERE p.DocNo = %s OR CONVERT(varchar(30), p.DocKey) = %s
                ORDER BY p.DocKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["paymentLines"] = self._fetch_all(
            conn,
            """
                SELECT
                    DtlKey AS dtlKey,
                    Seq AS seq,
                    PaymentMethod AS paymentMethod,
                    PaymentBy AS paymentBy,
                    ChequeNo AS chequeNo,
                    FloatDay AS floatDay,
                    BankCharge AS bankCharge,
                    PaymentAmt AS paymentAmt,
                    DebtorPaymentAmt AS debtorPaymentAmt,
                    LocalPaymentAmt AS localPaymentAmt,
                    DepositDocKey AS depositDocKey,
                    IsRCHQ AS isReturnedCheque,
                    RCHQDate AS returnedChequeDate
                FROM ARPaymentDTL
                WHERE DocKey = %s
                ORDER BY Seq, DtlKey
            """,
            (master["docKey"],),
        )
        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT
                    ko.KnockOffKey AS knockOffKey,
                    ko.KnockOffDocType AS knockOffDocType,
                    ko.KnockOffDocKey AS invoiceDocKey,
                    i.DocNo AS invoiceDocNo,
                    i.DocDate AS invoiceDate,
                    i.Description AS invoiceDescription,
                    i.CurrencyCode AS currencyCode,
                    i.NetTotal AS invoiceTotal,
                    i.PaymentAmt AS invoicePaymentAmt,
                    i.Outstanding AS invoiceOutstanding,
                    ko.Amount AS amount,
                    ko.DiscountAmt AS discountAmount,
                    ko.GainLossDate AS gainLossDate,
                    ko.Revalue AS revalue
                FROM ARPaymentKnockOff ko
                LEFT JOIN ARInvoice i
                    ON i.DocKey = ko.KnockOffDocKey
                    AND ko.KnockOffDocType = 'RI'
                WHERE ko.DocKey = %s
                ORDER BY i.DocDate, i.DocNo, ko.KnockOffKey
            """,
            (master["docKey"],),
        )
        master["lineAllocations"] = self._fetch_all(
            conn,
            """
                SELECT
                    kd.AutoKey AS autoKey,
                    ko.KnockOffKey AS knockOffKey,
                    ko.KnockOffDocKey AS invoiceDocKey,
                    i.DocNo AS invoiceDocNo,
                    kd.KnockOffDtlKey AS invoiceDtlKey,
                    iDtl.Seq AS invoiceSeq,
                    iDtl.Description AS invoiceLineDescription,
                    kd.Amount AS amount,
                    kd.LocalPaymentAmt AS localPaymentAmount,
                    kd.LocalInvoiceAmt AS localInvoiceAmount
                FROM ARPaymentKnockOff ko
                JOIN ARPaymentKnockOffDetail kd ON kd.KnockOffKey = ko.KnockOffKey
                LEFT JOIN ARInvoice i ON i.DocKey = ko.KnockOffDocKey
                LEFT JOIN ARInvoiceDTL iDtl ON iDtl.DtlKey = kd.KnockOffDtlKey
                WHERE ko.DocKey = %s
                ORDER BY i.DocNo, iDtl.Seq, kd.AutoKey
            """,
            (master["docKey"],),
        )
        return master

    def _list_ar_deposits(self, conn):
        return self._fetch_all(
            conn,
            """
                SELECT TOP 250
                    d.DocKey AS docKey,
                    d.DocNo AS docNo,
                    d.DocDate AS docDate,
                    d.DebtorCode AS debtorCode,
                    COALESCE(debtor.CompanyName, d.DebtorName) AS debtorName,
                    d.Description AS description,
                    d.CurrencyCode AS currencyCode,
                    d.ToDepositRate AS toDepositRate,
                    d.ToHomeRate AS toHomeRate,
                    d.PaymentAmt AS paymentAmt,
                    d.TransferedAmt AS transferredAmt,
                    d.Outstanding AS outstanding,
                    d.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    payLine.PaymentMethod AS paymentMethod,
                    payLine.PaymentBy AS paymentBy,
                    payLine.ChequeNo AS chequeNo,
                    d.IsSecurityDeposit AS isSecurityDeposit,
                    d.Cancelled AS cancelled
                FROM ARDeposit d
                LEFT JOIN Debtor debtor ON debtor.AccNo = d.DebtorCode
                LEFT JOIN CB cb ON cb.DocKey = d.CBKey
                OUTER APPLY (
                    SELECT TOP 1 PaymentMethod, PaymentBy, ChequeNo
                    FROM ARDepositPaymentDTL pd
                    WHERE pd.DocKey = d.DocKey
                    ORDER BY pd.Seq, pd.DtlKey
                ) payLine
                ORDER BY d.DocDate DESC, d.DocKey DESC
            """,
        )

    def _get_ar_deposit(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    d.DocKey AS docKey,
                    d.DocNo AS docNo,
                    d.DocDate AS docDate,
                    d.DebtorCode AS debtorCode,
                    COALESCE(debtor.CompanyName, d.DebtorName) AS debtorName,
                    d.InvAddr1 AS address1,
                    d.InvAddr2 AS address2,
                    d.InvAddr3 AS address3,
                    d.InvAddr4 AS address4,
                    d.Phone1 AS phone,
                    d.Attention AS attention,
                    d.Description AS description,
                    d.ProjNo AS projNo,
                    d.DeptNo AS deptNo,
                    d.DepositPaymentMethod AS depositPaymentMethod,
                    d.CurrencyCode AS currencyCode,
                    d.ToDepositRate AS toDepositRate,
                    d.ToHomeRate AS toHomeRate,
                    d.PaymentAmt AS paymentAmt,
                    d.TransferedAmt AS transferredAmt,
                    d.Outstanding AS outstanding,
                    d.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    d.SourceType AS sourceType,
                    d.SourceKey AS sourceKey,
                    d.GLTrxID AS glTrxId,
                    d.PrintCount AS printCount,
                    d.IsSecurityDeposit AS isSecurityDeposit,
                    d.Cancelled AS cancelled,
                    d.Note AS note
                FROM ARDeposit d
                LEFT JOIN Debtor debtor ON debtor.AccNo = d.DebtorCode
                LEFT JOIN CB cb ON cb.DocKey = d.CBKey
                WHERE d.DocNo = %s OR CONVERT(varchar(30), d.DocKey) = %s
                ORDER BY d.DocKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["paymentLines"] = self._fetch_all(
            conn,
            """
                SELECT
                    DtlKey AS dtlKey,
                    Seq AS seq,
                    PaymentMethod AS paymentMethod,
                    PaymentBy AS paymentBy,
                    ChequeNo AS chequeNo,
                    ToBankRate AS toBankRate,
                    FloatDay AS floatDay,
                    BankCharge AS bankCharge,
                    PaymentAmt AS paymentAmt,
                    IsRCHQ AS isReturnedCheque,
                    RCHQDate AS returnedChequeDate
                FROM ARDepositPaymentDTL
                WHERE DocKey = %s
                ORDER BY Seq, DtlKey
            """,
            (master["docKey"],),
        )
        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT
                    p.DocKey AS paymentDocKey,
                    p.DocNo AS paymentDocNo,
                    p.DocDate AS paymentDate,
                    p.DebtorCode AS debtorCode,
                    debtor.CompanyName AS debtorName,
                    p.Description AS paymentDescription,
                    p.CurrencyCode AS currencyCode,
                    p.PaymentAmt AS paymentTotal,
                    p.KnockOffAmt AS paymentKnockOffTotal,
                    p.LocalUnappliedAmount AS unappliedAmount,
                    p.RefundAmt AS refundAmount,
                    p.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    pd.DtlKey AS paymentDtlKey,
                    pd.Seq AS seq,
                    pd.PaymentMethod AS paymentMethod,
                    pd.PaymentBy AS paymentBy,
                    pd.ChequeNo AS chequeNo,
                    pd.PaymentAmt AS amount,
                    pd.LocalPaymentAmt AS localAmount,
                    p.DocStatus AS status,
                    p.Cancelled AS cancelled
                FROM ARPaymentDTL pd
                JOIN ARPayment p ON p.DocKey = pd.DocKey
                LEFT JOIN Debtor debtor ON debtor.AccNo = p.DebtorCode
                LEFT JOIN CB cb ON cb.DocKey = p.CBKey
                WHERE pd.DepositDocKey = %s
                ORDER BY p.DocDate DESC, p.DocKey DESC, pd.Seq, pd.DtlKey
            """,
            (master["docKey"],),
        )
        master["refundLines"] = self._fetch_all(
            conn,
            """
                SELECT
                    r.RefundKey AS refundKey,
                    r.DocNo AS docNo,
                    r.DocDate AS docDate,
                    r.Name AS name,
                    r.Description AS description,
                    r.RefundAmt AS refundAmt,
                    r.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo
                FROM ARDepositRefund r
                LEFT JOIN CB cb ON cb.DocKey = r.CBKey
                WHERE r.DocKey = %s
                ORDER BY r.DocDate DESC, r.RefundKey DESC
            """,
            (master["docKey"],),
        )
        master["forfeitLines"] = self._fetch_all(
            conn,
            """
                SELECT
                    f.ForfeitKey AS forfeitKey,
                    f.DocDate AS docDate,
                    f.Description AS description,
                    f.ForfeitedAmt AS forfeitedAmt,
                    f.ForfeitedAccNo AS forfeitedAccNo,
                    a.Description AS accountName
                FROM ARDepositForfeit f
                LEFT JOIN GLMast a ON a.AccNo = f.ForfeitedAccNo
                WHERE f.DocKey = %s
                ORDER BY f.DocDate DESC, f.ForfeitKey DESC
            """,
            (master["docKey"],),
        )
        return master

    def _list_ap_invoices(self, conn):
        return self._fetch_all(
            conn,
            """
                SELECT TOP 500
                    i.DocKey AS docKey,
                    i.DocNo AS docNo,
                    i.DocDate AS docDate,
                    i.DueDate AS dueDate,
                    i.CreditorCode AS creditorCode,
                    c.CompanyName AS creditorName,
                    i.SupplierInvoiceNo AS supplierInvoiceNo,
                    i.Description AS description,
                    i.CurrencyCode AS currencyCode,
                    i.Total AS total,
                    i.NetTotal AS netTotal,
                    i.PaymentAmt AS paymentAmt,
                    i.Outstanding AS outstanding,
                    i.DocStatus AS status,
                    i.Cancelled AS cancelled
                FROM APInvoice i
                LEFT JOIN Creditor c ON c.AccNo = i.CreditorCode
                ORDER BY i.DocDate DESC, i.DocKey DESC
            """,
        )

    def _get_ap_invoice(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    i.DocKey AS docKey,
                    i.DocNo AS docNo,
                    i.DocDate AS docDate,
                    i.DisplayTerm AS displayTerm,
                    i.DueDate AS dueDate,
                    i.CreditorCode AS creditorCode,
                    c.CompanyName AS creditorName,
                    i.SupplierInvoiceNo AS supplierInvoiceNo,
                    i.RefNo2 AS refNo2,
                    i.Description AS description,
                    i.PurchaseAgent AS agent,
                    i.JournalType AS journalType,
                    i.CurrencyCode AS currencyCode,
                    i.CurrencyRate AS currencyRate,
                    i.Total AS total,
                    i.LocalTotal AS localTotal,
                    i.Tax AS tax,
                    i.LocalTax AS localTax,
                    i.NetTotal AS netTotal,
                    i.LocalNetTotal AS localNetTotal,
                    i.PaymentAmt AS paymentAmt,
                    i.LocalPaymentAmt AS localPaymentAmt,
                    i.Outstanding AS outstanding,
                    i.TaxableAmt AS taxableAmount,
                    i.LocalTaxableAmt AS localTaxableAmount,
                    i.BranchCode AS branchCode,
                    i.SourceType AS sourceType,
                    i.SourceKey AS sourceKey,
                    i.GLTrxID AS glTrxId,
                    i.Cancelled AS cancelled,
                    i.DocStatus AS status,
                    i.Note AS note
                FROM APInvoice i
                LEFT JOIN Creditor c ON c.AccNo = i.CreditorCode
                WHERE i.DocNo = %s OR CONVERT(varchar(30), i.DocKey) = %s
                ORDER BY i.DocKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT
                    d.DtlKey AS dtlKey,
                    d.Seq AS seq,
                    d.AccNo AS accNo,
                    a.Description AS accountName,
                    d.Description AS description,
                    d.ProjNo AS projNo,
                    d.DeptNo AS deptNo,
                    d.TaxCode AS taxCode,
                    d.Amount AS amount,
                    d.SubTotal AS subTotal,
                    d.Tax AS tax,
                    d.NetAmount AS netAmount,
                    d.KnockOffAmount AS knockOffAmount,
                    d.TaxableAmt AS taxableAmount
                FROM APInvoiceDTL d
                LEFT JOIN GLMast a ON a.AccNo = d.AccNo
                WHERE d.DocKey = %s
                ORDER BY d.Seq, d.DtlKey
            """,
            (master["docKey"],),
        )
        master["paymentLines"] = self._get_ap_invoice_payments(conn, master["docKey"])
        return master

    def _get_ap_invoice_payments(self, conn, invoice_doc_key):
        return self._fetch_all(
            conn,
            """
                SELECT
                    p.DocKey AS paymentDocKey,
                    p.DocNo AS paymentDocNo,
                    p.DocDate AS paymentDate,
                    p.CreditorCode AS creditorCode,
                    c.CompanyName AS creditorName,
                    p.Description AS paymentDescription,
                    p.CurrencyCode AS currencyCode,
                    p.PaymentAmt AS paymentTotal,
                    p.KnockOffAmt AS paymentKnockOffTotal,
                    p.LocalUnappliedAmount AS unappliedAmount,
                    p.RefundAmt AS refundAmount,
                    p.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    p.Cancelled AS cancelled,
                    p.DocStatus AS status,
                    payLine.PaymentMethod AS paymentMethod,
                    payLine.PaymentBy AS paymentBy,
                    payLine.ChequeNo AS chequeNo,
                    ko.KnockOffKey AS knockOffKey,
                    ko.KnockOffDocType AS knockOffDocType,
                    ko.Amount AS paidAmount,
                    ko.DiscountAmt AS discountAmount,
                    ko.GainLossDate AS gainLossDate
                FROM APPaymentKnockOff ko
                JOIN APPayment p ON p.DocKey = ko.DocKey
                LEFT JOIN Creditor c ON c.AccNo = p.CreditorCode
                LEFT JOIN CB cb ON cb.DocKey = p.CBKey
                OUTER APPLY (
                    SELECT TOP 1 PaymentMethod, PaymentBy, ChequeNo
                    FROM APPaymentDTL pd
                    WHERE pd.DocKey = p.DocKey
                    ORDER BY pd.Seq, pd.DtlKey
                ) payLine
                WHERE ko.KnockOffDocKey = %s
                ORDER BY p.DocDate DESC, p.DocKey DESC, ko.KnockOffKey
            """,
            (invoice_doc_key,),
        )

    def _list_ap_payments(self, conn):
        return self._fetch_all(
            conn,
            """
                SELECT TOP 300
                    p.DocKey AS docKey,
                    p.DocNo AS docNo,
                    p.DocDate AS docDate,
                    p.CreditorCode AS creditorCode,
                    c.CompanyName AS creditorName,
                    p.Description AS description,
                    p.CurrencyCode AS currencyCode,
                    p.PaymentAmt AS paymentAmt,
                    p.LocalPaymentAmt AS localPaymentAmt,
                    p.KnockOffAmt AS knockOffAmt,
                    p.LocalUnappliedAmount AS unappliedAmount,
                    p.RefundAmt AS refundAmount,
                    p.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    payLine.PaymentMethod AS paymentMethod,
                    payLine.PaymentBy AS paymentBy,
                    payLine.ChequeNo AS chequeNo,
                    p.Cancelled AS cancelled,
                    p.DocStatus AS status
                FROM APPayment p
                LEFT JOIN Creditor c ON c.AccNo = p.CreditorCode
                LEFT JOIN CB cb ON cb.DocKey = p.CBKey
                OUTER APPLY (
                    SELECT TOP 1 PaymentMethod, PaymentBy, ChequeNo
                    FROM APPaymentDTL pd
                    WHERE pd.DocKey = p.DocKey
                    ORDER BY pd.Seq, pd.DtlKey
                ) payLine
                ORDER BY p.DocDate DESC, p.DocKey DESC
            """,
        )

    def _get_ap_payment(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    p.DocKey AS docKey,
                    p.DocNo AS docNo,
                    p.DocDate AS docDate,
                    p.CreditorCode AS creditorCode,
                    c.CompanyName AS creditorName,
                    p.Description AS description,
                    p.ProjNo AS projNo,
                    p.DeptNo AS deptNo,
                    p.CurrencyCode AS currencyCode,
                    p.ToCreditorRate AS toCreditorRate,
                    p.ToHomeRate AS toHomeRate,
                    p.PaymentAmt AS paymentAmt,
                    p.LocalPaymentAmt AS localPaymentAmt,
                    p.KnockOffAmt AS knockOffAmt,
                    p.LocalUnappliedAmount AS unappliedAmount,
                    p.RefundAmt AS refundAmount,
                    p.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    p.SourceType AS sourceType,
                    p.SourceKey AS sourceKey,
                    p.HandOverDate AS handOverDate,
                    p.DocNo2 AS docNo2,
                    p.GLTrxID AS glTrxId,
                    p.WithholdingTax AS withholdingTax,
                    p.LocalWithholdingTax AS localWithholdingTax,
                    p.Cancelled AS cancelled,
                    p.DocStatus AS status,
                    p.Note AS note
                FROM APPayment p
                LEFT JOIN Creditor c ON c.AccNo = p.CreditorCode
                LEFT JOIN CB cb ON cb.DocKey = p.CBKey
                WHERE p.DocNo = %s OR CONVERT(varchar(30), p.DocKey) = %s
                ORDER BY p.DocKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["paymentLines"] = self._fetch_all(
            conn,
            """
                SELECT
                    DtlKey AS dtlKey,
                    Seq AS seq,
                    PaymentMethod AS paymentMethod,
                    PaymentBy AS paymentBy,
                    ChequeNo AS chequeNo,
                    FloatDay AS floatDay,
                    BankCharge AS bankCharge,
                    PaymentAmt AS paymentAmt,
                    CreditorPaymentAmt AS creditorPaymentAmt,
                    LocalPaymentAmt AS localPaymentAmt,
                    DepositDocKey AS depositDocKey,
                    IsRCHQ AS isReturnedCheque,
                    RCHQDate AS returnedChequeDate
                FROM APPaymentDTL
                WHERE DocKey = %s
                ORDER BY Seq, DtlKey
            """,
            (master["docKey"],),
        )
        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT
                    ko.KnockOffKey AS knockOffKey,
                    ko.KnockOffDocType AS knockOffDocType,
                    ko.KnockOffDocKey AS invoiceDocKey,
                    i.DocNo AS invoiceDocNo,
                    i.SupplierInvoiceNo AS supplierInvoiceNo,
                    i.DocDate AS invoiceDate,
                    i.Description AS invoiceDescription,
                    i.CurrencyCode AS currencyCode,
                    i.NetTotal AS invoiceTotal,
                    i.PaymentAmt AS invoicePaymentAmt,
                    i.Outstanding AS invoiceOutstanding,
                    ko.Amount AS amount,
                    ko.DiscountAmt AS discountAmount,
                    ko.GainLossDate AS gainLossDate,
                    ko.Revalue AS revalue
                FROM APPaymentKnockOff ko
                LEFT JOIN APInvoice i ON i.DocKey = ko.KnockOffDocKey
                WHERE ko.DocKey = %s
                ORDER BY i.DocDate, i.DocNo, ko.KnockOffKey
            """,
            (master["docKey"],),
        )
        return master

    def _list_ap_deposits(self, conn):
        return self._fetch_all(
            conn,
            """
                SELECT TOP 250
                    d.DocKey AS docKey,
                    d.DocNo AS docNo,
                    d.DocDate AS docDate,
                    d.CreditorCode AS creditorCode,
                    COALESCE(creditor.CompanyName, d.CreditorName) AS creditorName,
                    d.Description AS description,
                    d.CurrencyCode AS currencyCode,
                    d.ToDepositRate AS toDepositRate,
                    d.ToHomeRate AS toHomeRate,
                    d.PaymentAmt AS paymentAmt,
                    d.TransferedAmt AS transferredAmt,
                    d.Outstanding AS outstanding,
                    d.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    payLine.PaymentMethod AS paymentMethod,
                    payLine.PaymentBy AS paymentBy,
                    payLine.ChequeNo AS chequeNo,
                    d.Cancelled AS cancelled
                FROM APDeposit d
                LEFT JOIN Creditor creditor ON creditor.AccNo = d.CreditorCode
                LEFT JOIN CB cb ON cb.DocKey = d.CBKey
                OUTER APPLY (
                    SELECT TOP 1 PaymentMethod, PaymentBy, ChequeNo
                    FROM APDepositPaymentDTL pd
                    WHERE pd.DocKey = d.DocKey
                    ORDER BY pd.Seq, pd.DtlKey
                ) payLine
                ORDER BY d.DocDate DESC, d.DocKey DESC
            """,
        )

    def _get_ap_deposit(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    d.DocKey AS docKey,
                    d.DocNo AS docNo,
                    d.DocDate AS docDate,
                    d.CreditorCode AS creditorCode,
                    COALESCE(creditor.CompanyName, d.CreditorName) AS creditorName,
                    d.InvAddr1 AS address1,
                    d.InvAddr2 AS address2,
                    d.InvAddr3 AS address3,
                    d.InvAddr4 AS address4,
                    d.Phone1 AS phone,
                    d.Attention AS attention,
                    d.Description AS description,
                    d.ProjNo AS projNo,
                    d.DeptNo AS deptNo,
                    d.DepositPaymentMethod AS depositPaymentMethod,
                    d.CurrencyCode AS currencyCode,
                    d.ToDepositRate AS toDepositRate,
                    d.ToHomeRate AS toHomeRate,
                    d.PaymentAmt AS paymentAmt,
                    d.TransferedAmt AS transferredAmt,
                    d.Outstanding AS outstanding,
                    d.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    d.SourceType AS sourceType,
                    d.SourceKey AS sourceKey,
                    d.GLTrxID AS glTrxId,
                    d.PrintCount AS printCount,
                    d.Cancelled AS cancelled,
                    d.Note AS note
                FROM APDeposit d
                LEFT JOIN Creditor creditor ON creditor.AccNo = d.CreditorCode
                LEFT JOIN CB cb ON cb.DocKey = d.CBKey
                WHERE d.DocNo = %s OR CONVERT(varchar(30), d.DocKey) = %s
                ORDER BY d.DocKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["paymentLines"] = self._fetch_all(
            conn,
            """
                SELECT
                    DtlKey AS dtlKey,
                    Seq AS seq,
                    PaymentMethod AS paymentMethod,
                    PaymentBy AS paymentBy,
                    ChequeNo AS chequeNo,
                    ToBankRate AS toBankRate,
                    FloatDay AS floatDay,
                    BankCharge AS bankCharge,
                    PaymentAmt AS paymentAmt,
                    IsRCHQ AS isReturnedCheque,
                    RCHQDate AS returnedChequeDate
                FROM APDepositPaymentDTL
                WHERE DocKey = %s
                ORDER BY Seq, DtlKey
            """,
            (master["docKey"],),
        )
        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT
                    p.DocKey AS paymentDocKey,
                    p.DocNo AS paymentDocNo,
                    p.DocDate AS paymentDate,
                    p.CreditorCode AS creditorCode,
                    creditor.CompanyName AS creditorName,
                    p.Description AS paymentDescription,
                    p.CurrencyCode AS currencyCode,
                    p.PaymentAmt AS paymentTotal,
                    p.KnockOffAmt AS paymentKnockOffTotal,
                    p.LocalUnappliedAmount AS unappliedAmount,
                    p.RefundAmt AS refundAmount,
                    p.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo,
                    pd.DtlKey AS paymentDtlKey,
                    pd.Seq AS seq,
                    pd.PaymentMethod AS paymentMethod,
                    pd.PaymentBy AS paymentBy,
                    pd.ChequeNo AS chequeNo,
                    pd.PaymentAmt AS amount,
                    pd.LocalPaymentAmt AS localAmount,
                    p.DocStatus AS status,
                    p.Cancelled AS cancelled
                FROM APPaymentDTL pd
                JOIN APPayment p ON p.DocKey = pd.DocKey
                LEFT JOIN Creditor creditor ON creditor.AccNo = p.CreditorCode
                LEFT JOIN CB cb ON cb.DocKey = p.CBKey
                WHERE pd.DepositDocKey = %s
                ORDER BY p.DocDate DESC, p.DocKey DESC, pd.Seq, pd.DtlKey
            """,
            (master["docKey"],),
        )
        master["refundLines"] = self._fetch_all(
            conn,
            """
                SELECT
                    r.RefundKey AS refundKey,
                    r.DocNo AS docNo,
                    r.DocDate AS docDate,
                    r.Name AS name,
                    r.Description AS description,
                    r.RefundAmt AS refundAmt,
                    r.CBKey AS cashBookKey,
                    cb.DocNo AS cashBookDocNo
                FROM APDepositRefund r
                LEFT JOIN CB cb ON cb.DocKey = r.CBKey
                WHERE r.DocKey = %s
                ORDER BY r.DocDate DESC, r.RefundKey DESC
            """,
            (master["docKey"],),
        )
        master["forfeitLines"] = self._fetch_all(
            conn,
            """
                SELECT
                    f.ForfeitKey AS forfeitKey,
                    f.DocDate AS docDate,
                    f.Description AS description,
                    f.ForfeitedAmt AS forfeitedAmt,
                    f.ForfeitedAccNo AS forfeitedAccNo,
                    a.Description AS accountName
                FROM APDepositForfeit f
                LEFT JOIN GLMast a ON a.AccNo = f.ForfeitedAccNo
                WHERE f.DocKey = %s
                ORDER BY f.DocDate DESC, f.ForfeitKey DESC
            """,
            (master["docKey"],),
        )
        return master

    def _list_cash_book(self, conn):
        return self._fetch_all(
            conn,
            """
                SELECT TOP 250
                    c.DocKey AS docKey,
                    c.DocNo AS docNo,
                    c.DocDate AS docDate,
                    c.DocType AS docType,
                    CASE c.DocType
                        WHEN 'OR' THEN 'Receipt'
                        WHEN 'PV' THEN 'Payment'
                        ELSE c.DocType
                    END AS typeLabel,
                    c.SourceType AS sourceType,
                    c.SourceKey AS sourceKey,
                    c.DealWith AS dealWith,
                    c.Description AS description,
                    c.CurrencyCode AS currencyCode,
                    c.CurrencyRate AS currencyRate,
                    c.TotalPayment AS totalPayment,
                    c.LocalTotal AS localTotal,
                    c.NetTotal AS netTotal,
                    c.Tax AS tax,
                    c.Cancelled AS cancelled,
                    c.DocStatus AS status,
                    CASE
                        WHEN sourceAr.DocNo IS NOT NULL THEN 'ar-payments'
                        WHEN sourceDeposit.DocNo IS NOT NULL THEN 'ar-deposits'
                        WHEN sourceAp.DocNo IS NOT NULL THEN 'ap-payments'
                        ELSE ''
                    END AS sourceDocumentModule,
                    CASE
                        WHEN sourceAr.DocNo IS NOT NULL THEN 'AR Payment'
                        WHEN sourceDeposit.DocNo IS NOT NULL THEN 'AR Deposit'
                        WHEN sourceAp.DocNo IS NOT NULL THEN 'AP Payment'
                        ELSE ''
                    END AS sourceDocumentLabel,
                    COALESCE(sourceAr.DocKey, sourceDeposit.DocKey, sourceAp.DocKey) AS sourceDocumentKey,
                    COALESCE(sourceAr.DocNo, sourceDeposit.DocNo, sourceAp.DocNo) AS sourceDocumentNo,
                    COALESCE(sourceAr.Description, sourceDeposit.Description, sourceAp.Description) AS sourceDocumentDescription,
                    COALESCE(sourceAr.PaymentAmt, sourceDeposit.PaymentAmt, sourceAp.PaymentAmt) AS sourceDocumentAmount,
                    COALESCE(
                        sourceAr.LocalPaymentAmt,
                        sourceDeposit.PaymentAmt * ISNULL(sourceDeposit.ToHomeRate, 1),
                        sourceAp.LocalPaymentAmt
                    ) AS sourceDocumentLocalAmount,
                    pay.PaymentMethod AS paymentMethod,
                    pay.PaymentBy AS paymentBy,
                    pay.ChequeNo AS chequeNo,
                    pay.PaymentAmt AS paymentAmount,
                    bank.AccNo AS bankAccount,
                    bankAcc.Description AS bankAccountName,
                    bank.PaymentAmt AS bankAmount,
                    bank.BankReconStatus AS bankReconStatus,
                    CASE bank.BankReconStatus
                        WHEN 1 THEN 'Reconciled'
                        WHEN 0 THEN 'Open'
                        ELSE ''
                    END AS bankReconStatusLabel
                FROM CB c
                OUTER APPLY (
                    SELECT TOP 1 PaymentMethod, PaymentBy, ChequeNo, PaymentAmt
                    FROM CBPaymentDTL p
                    WHERE p.DocKey = c.DocKey
                    ORDER BY p.Seq, p.DtlKey
                ) pay
                OUTER APPLY (
                    SELECT TOP 1 AccNo, PaymentAmt, BankReconStatus
                    FROM BankTrans b
                    WHERE b.DocNo = c.DocNo
                       OR (c.SourceKey IS NOT NULL AND b.SourceKey = c.SourceKey)
                    ORDER BY b.BankTransKey
                ) bank
                LEFT JOIN GLMast bankAcc ON bankAcc.AccNo = bank.AccNo
                LEFT JOIN ARPayment sourceAr
                    ON sourceAr.DocKey = c.SourceKey
                    AND c.SourceType = 'RP'
                LEFT JOIN ARDeposit sourceDeposit
                    ON sourceDeposit.DocKey = c.SourceKey
                    AND c.SourceType = 'RS'
                LEFT JOIN APPayment sourceAp
                    ON sourceAp.DocKey = c.SourceKey
                    AND c.SourceType = 'PP'
                ORDER BY c.DocDate DESC, c.DocKey DESC
            """,
        )

    def _get_cash_book(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    c.DocKey AS docKey,
                    c.DocNo AS docNo,
                    c.DocDate AS docDate,
                    c.DocType AS docType,
                    CASE c.DocType
                        WHEN 'OR' THEN 'Receipt'
                        WHEN 'PV' THEN 'Payment'
                        ELSE c.DocType
                    END AS typeLabel,
                    c.SourceType AS sourceType,
                    c.SourceKey AS sourceKey,
                    c.DealWith AS dealWith,
                    c.Description AS description,
                    c.CurrencyCode AS currencyCode,
                    c.CurrencyRate AS currencyRate,
                    c.TotalPayment AS totalPayment,
                    c.Total AS total,
                    c.LocalTotal AS localTotal,
                    c.Tax AS tax,
                    c.LocalTax AS localTax,
                    c.NetTotal AS netTotal,
                    c.LocalNetTotal AS localNetTotal,
                    c.ExTax AS exTax,
                    c.LocalExTax AS localExTax,
                    c.InclusiveTax AS inclusiveTax,
                    c.TotalExTax AS totalExTax,
                    c.LocalTotalExTax AS localTotalExTax,
                    c.TaxableAmt AS taxableAmount,
                    c.LocalTaxableAmt AS localTaxableAmount,
                    c.WithholdingTax AS withholdingTax,
                    c.LocalWithholdingTax AS localWithholdingTax,
                    c.PrintCount AS printCount,
                    c.HandOverDate AS handOverDate,
                    c.DocNo2 AS docNo2,
                    c.GLTrxID AS glTrxId,
                    c.TaxDate AS taxDate,
                    c.Cancelled AS cancelled,
                    c.DocStatus AS status,
                    c.Note AS note,
                    CASE
                        WHEN sourceAr.DocNo IS NOT NULL THEN 'ar-payments'
                        WHEN sourceDeposit.DocNo IS NOT NULL THEN 'ar-deposits'
                        WHEN sourceAp.DocNo IS NOT NULL THEN 'ap-payments'
                        ELSE ''
                    END AS sourceDocumentModule,
                    CASE
                        WHEN sourceAr.DocNo IS NOT NULL THEN 'AR Payment'
                        WHEN sourceDeposit.DocNo IS NOT NULL THEN 'AR Deposit'
                        WHEN sourceAp.DocNo IS NOT NULL THEN 'AP Payment'
                        ELSE ''
                    END AS sourceDocumentLabel,
                    COALESCE(sourceAr.DocKey, sourceDeposit.DocKey, sourceAp.DocKey) AS sourceDocumentKey,
                    COALESCE(sourceAr.DocNo, sourceDeposit.DocNo, sourceAp.DocNo) AS sourceDocumentNo,
                    COALESCE(sourceAr.Description, sourceDeposit.Description, sourceAp.Description) AS sourceDocumentDescription,
                    COALESCE(sourceAr.PaymentAmt, sourceDeposit.PaymentAmt, sourceAp.PaymentAmt) AS sourceDocumentAmount,
                    COALESCE(
                        sourceAr.LocalPaymentAmt,
                        sourceDeposit.PaymentAmt * ISNULL(sourceDeposit.ToHomeRate, 1),
                        sourceAp.LocalPaymentAmt
                    ) AS sourceDocumentLocalAmount,
                    pay.PaymentMethod AS paymentMethod,
                    pay.PaymentBy AS paymentBy,
                    pay.ChequeNo AS chequeNo,
                    pay.PaymentAmt AS paymentAmount,
                    bank.AccNo AS bankAccount,
                    bankAcc.Description AS bankAccountName,
                    bank.PaymentAmt AS bankAmount,
                    bank.BankReconStatus AS bankReconStatus,
                    CASE bank.BankReconStatus
                        WHEN 1 THEN 'Reconciled'
                        WHEN 0 THEN 'Open'
                        ELSE ''
                    END AS bankReconStatusLabel
                FROM CB c
                OUTER APPLY (
                    SELECT TOP 1 PaymentMethod, PaymentBy, ChequeNo, PaymentAmt
                    FROM CBPaymentDTL p
                    WHERE p.DocKey = c.DocKey
                    ORDER BY p.Seq, p.DtlKey
                ) pay
                OUTER APPLY (
                    SELECT TOP 1 AccNo, PaymentAmt, BankReconStatus
                    FROM BankTrans b
                    WHERE b.DocNo = c.DocNo
                       OR (c.SourceKey IS NOT NULL AND b.SourceKey = c.SourceKey)
                    ORDER BY b.BankTransKey
                ) bank
                LEFT JOIN GLMast bankAcc ON bankAcc.AccNo = bank.AccNo
                LEFT JOIN ARPayment sourceAr
                    ON sourceAr.DocKey = c.SourceKey
                    AND c.SourceType = 'RP'
                LEFT JOIN ARDeposit sourceDeposit
                    ON sourceDeposit.DocKey = c.SourceKey
                    AND c.SourceType = 'RS'
                LEFT JOIN APPayment sourceAp
                    ON sourceAp.DocKey = c.SourceKey
                    AND c.SourceType = 'PP'
                WHERE c.DocNo = %s OR CONVERT(varchar(30), c.DocKey) = %s
                ORDER BY c.DocKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT
                    d.DtlKey AS dtlKey,
                    d.Seq AS seq,
                    d.AccNo AS accNo,
                    a.Description AS accountName,
                    d.ProjNo AS projNo,
                    d.DeptNo AS deptNo,
                    d.TaxCode AS taxCode,
                    d.Description AS description,
                    d.Amount AS amount,
                    d.LocalAmount AS localAmount,
                    d.TaxableAmt AS taxableAmount,
                    d.Tax AS tax,
                    d.LocalTax AS localTax,
                    d.InclusiveTax AS inclusiveTax,
                    d.AmountExTax AS amountExTax,
                    d.LocalAmountExTax AS localAmountExTax,
                    d.AmountWithTax AS amountWithTax,
                    d.LocalAmountWithTax AS localAmountWithTax
                FROM CBDTL d
                LEFT JOIN GLMast a ON a.AccNo = d.AccNo
                WHERE d.DocKey = %s
                ORDER BY d.Seq, d.DtlKey
            """,
            (master["docKey"],),
        )
        master["paymentLines"] = self._fetch_all(
            conn,
            """
                SELECT
                    DtlKey AS dtlKey,
                    Seq AS seq,
                    PaymentMethod AS paymentMethod,
                    PaymentBy AS paymentBy,
                    ChequeNo AS chequeNo,
                    FloatDay AS floatDay,
                    BankCharge AS bankCharge,
                    PaymentAmt AS paymentAmt,
                    IsRCHQ AS isReturnedCheque,
                    RCHQDate AS returnedChequeDate
                FROM CBPaymentDTL
                WHERE DocKey = %s
                ORDER BY Seq, DtlKey
            """,
            (master["docKey"],),
        )
        master["bankTransactions"] = self._fetch_all(
            conn,
            """
                SELECT
                    b.BankTransKey AS bankTransKey,
                    b.SourceType AS sourceType,
                    b.SourceKey AS sourceKey,
                    b.DtlKey AS dtlKey,
                    b.DocNo AS docNo,
                    b.DocDate AS docDate,
                    b.AccNo AS bankAccount,
                    a.Description AS bankAccountName,
                    b.ChequeNo AS chequeNo,
                    b.FloatDay AS floatDay,
                    b.Description AS description,
                    b.PaymentAmt AS paymentAmt,
                    b.BankStatementDate AS bankStatementDate,
                    b.BankReconStatus AS bankReconStatus,
                    CASE b.BankReconStatus
                        WHEN 1 THEN 'Reconciled'
                        WHEN 0 THEN 'Open'
                        ELSE ''
                    END AS bankReconStatusLabel,
                    b.BankSlipDocKey AS bankSlipDocKey
                FROM BankTrans b
                LEFT JOIN GLMast a ON a.AccNo = b.AccNo
                WHERE b.DocNo = %s
                   OR (%s IS NOT NULL AND b.SourceKey = %s)
                ORDER BY b.DocDate, b.BankTransKey
            """,
            (master["docNo"], master["sourceKey"], master["sourceKey"]),
        )
        master["sourceDocuments"] = self._get_cash_book_source_documents(conn, master)
        return master

    def _list_bank_transactions(self, conn, bank_trans_keys=None):
        normalized_keys = [
            str(key or "").strip()
            for key in (bank_trans_keys or [])
            if str(key or "").strip()
        ]
        where = ""
        params = ()
        if normalized_keys:
            placeholders = ", ".join(["%s"] * len(normalized_keys))
            where = f"""
                WHERE CONVERT(varchar(30), b.BankTransKey) IN ({placeholders})
                   OR b.DocNo IN ({placeholders})
            """
            params = tuple(normalized_keys) + tuple(normalized_keys)

        return self._fetch_all(
            conn,
            f"""
                SELECT TOP 500
                    b.BankTransKey AS bankTransKey,
                    b.SourceType AS sourceType,
                    b.SourceKey AS sourceKey,
                    b.DtlKey AS dtlKey,
                    b.DocNo AS docNo,
                    b.DocDate AS docDate,
                    b.AccNo AS bankAccount,
                    bankAcc.Description AS bankAccountName,
                    b.ChequeNo AS chequeNo,
                    b.FloatDay AS floatDay,
                    b.Description AS description,
                    b.PaymentAmt AS bankAmount,
                    b.BankStatementDate AS bankStatementDate,
                    b.BankReconStatus AS bankReconStatus,
                    CASE b.BankReconStatus
                        WHEN 1 THEN 'Reconciled'
                        WHEN 0 THEN 'Open'
                        ELSE ''
                    END AS bankReconStatusLabel,
                    b.BankSlipDocKey AS bankSlipDocKey,
                    cashBook.DocKey AS cashBookKey,
                    cashBook.DocNo AS cashBookDocNo,
                    cashBook.DocType AS cashBookDocType,
                    CASE cashBook.DocType
                        WHEN 'OR' THEN 'Receipt'
                        WHEN 'PV' THEN 'Payment'
                        ELSE cashBook.DocType
                    END AS cashBookTypeLabel,
                    cashBook.DealWith AS cashBookDealWith,
                    cashBook.Description AS cashBookDescription,
                    cashBook.DocStatus AS cashBookStatus,
                    CASE
                        WHEN sourceAr.DocNo IS NOT NULL THEN 'ar-payments'
                        WHEN sourceDeposit.DocNo IS NOT NULL THEN 'ar-deposits'
                        WHEN sourceAp.DocNo IS NOT NULL THEN 'ap-payments'
                        ELSE ''
                    END AS sourceDocumentModule,
                    CASE
                        WHEN sourceAr.DocNo IS NOT NULL THEN 'AR Payment'
                        WHEN sourceDeposit.DocNo IS NOT NULL THEN 'AR Deposit'
                        WHEN sourceAp.DocNo IS NOT NULL THEN 'AP Payment'
                        ELSE ''
                    END AS sourceDocumentLabel,
                    COALESCE(sourceAr.DocKey, sourceDeposit.DocKey, sourceAp.DocKey) AS sourceDocumentKey,
                    COALESCE(sourceAr.DocNo, sourceDeposit.DocNo, sourceAp.DocNo) AS sourceDocumentNo,
                    COALESCE(sourceAr.Description, sourceDeposit.Description, sourceAp.Description) AS sourceDocumentDescription,
                    COALESCE(sourceAr.PaymentAmt, sourceDeposit.PaymentAmt, sourceAp.PaymentAmt) AS sourceDocumentAmount
                FROM BankTrans b
                LEFT JOIN GLMast bankAcc ON bankAcc.AccNo = b.AccNo
                OUTER APPLY (
                    SELECT TOP 1 c.*
                    FROM CB c
                    WHERE c.DocNo = b.DocNo
                       OR (b.SourceType IN ('PV', 'OR') AND c.DocKey = b.SourceKey)
                    ORDER BY
                        CASE WHEN c.DocNo = b.DocNo THEN 0 ELSE 1 END,
                        c.DocKey DESC
                ) cashBook
                LEFT JOIN ARPayment sourceAr
                    ON sourceAr.DocKey = b.SourceKey
                    AND b.SourceType = 'RP'
                LEFT JOIN ARDeposit sourceDeposit
                    ON sourceDeposit.DocKey = b.SourceKey
                    AND b.SourceType = 'RS'
                LEFT JOIN APPayment sourceAp
                    ON sourceAp.DocKey = b.SourceKey
                    AND b.SourceType = 'PP'
                {where}
                ORDER BY b.DocDate DESC, b.BankTransKey DESC
            """,
            params,
        )

    def _get_bank_transaction(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    b.BankTransKey AS bankTransKey,
                    b.SourceType AS sourceType,
                    b.SourceKey AS sourceKey,
                    b.DtlKey AS dtlKey,
                    b.DocNo AS docNo,
                    b.DocDate AS docDate,
                    b.AccNo AS bankAccount,
                    bankAcc.Description AS bankAccountName,
                    b.ChequeNo AS chequeNo,
                    b.FloatDay AS floatDay,
                    b.Description AS description,
                    b.PaymentAmt AS bankAmount,
                    b.BankStatementDate AS bankStatementDate,
                    b.BankReconStatus AS bankReconStatus,
                    CASE b.BankReconStatus
                        WHEN 1 THEN 'Reconciled'
                        WHEN 0 THEN 'Open'
                        ELSE ''
                    END AS bankReconStatusLabel,
                    b.BankSlipDocKey AS bankSlipDocKey,
                    cashBook.DocKey AS cashBookKey,
                    cashBook.DocNo AS cashBookDocNo,
                    cashBook.DocDate AS cashBookDocDate,
                    cashBook.DocType AS cashBookDocType,
                    CASE cashBook.DocType
                        WHEN 'OR' THEN 'Receipt'
                        WHEN 'PV' THEN 'Payment'
                        ELSE cashBook.DocType
                    END AS cashBookTypeLabel,
                    cashBook.DealWith AS cashBookDealWith,
                    cashBook.Description AS cashBookDescription,
                    cashBook.TotalPayment AS cashBookPayment,
                    cashBook.LocalTotal AS cashBookLocalTotal,
                    cashBook.DocStatus AS cashBookStatus,
                    cashBook.Cancelled AS cashBookCancelled,
                    CASE
                        WHEN sourceAr.DocNo IS NOT NULL THEN 'ar-payments'
                        WHEN sourceDeposit.DocNo IS NOT NULL THEN 'ar-deposits'
                        WHEN sourceAp.DocNo IS NOT NULL THEN 'ap-payments'
                        ELSE ''
                    END AS sourceDocumentModule,
                    CASE
                        WHEN sourceAr.DocNo IS NOT NULL THEN 'AR Payment'
                        WHEN sourceDeposit.DocNo IS NOT NULL THEN 'AR Deposit'
                        WHEN sourceAp.DocNo IS NOT NULL THEN 'AP Payment'
                        ELSE ''
                    END AS sourceDocumentLabel,
                    COALESCE(sourceAr.DocKey, sourceDeposit.DocKey, sourceAp.DocKey) AS sourceDocumentKey,
                    COALESCE(sourceAr.DocNo, sourceDeposit.DocNo, sourceAp.DocNo) AS sourceDocumentNo,
                    COALESCE(sourceAr.DocDate, sourceDeposit.DocDate, sourceAp.DocDate) AS sourceDocumentDate,
                    COALESCE(sourceAr.Description, sourceDeposit.Description, sourceAp.Description) AS sourceDocumentDescription,
                    COALESCE(sourceAr.PaymentAmt, sourceDeposit.PaymentAmt, sourceAp.PaymentAmt) AS sourceDocumentAmount
                FROM BankTrans b
                LEFT JOIN GLMast bankAcc ON bankAcc.AccNo = b.AccNo
                OUTER APPLY (
                    SELECT TOP 1 c.*
                    FROM CB c
                    WHERE c.DocNo = b.DocNo
                       OR (b.SourceType IN ('PV', 'OR') AND c.DocKey = b.SourceKey)
                    ORDER BY
                        CASE WHEN c.DocNo = b.DocNo THEN 0 ELSE 1 END,
                        c.DocKey DESC
                ) cashBook
                LEFT JOIN ARPayment sourceAr
                    ON sourceAr.DocKey = b.SourceKey
                    AND b.SourceType = 'RP'
                LEFT JOIN ARDeposit sourceDeposit
                    ON sourceDeposit.DocKey = b.SourceKey
                    AND b.SourceType = 'RS'
                LEFT JOIN APPayment sourceAp
                    ON sourceAp.DocKey = b.SourceKey
                    AND b.SourceType = 'PP'
                WHERE CONVERT(varchar(30), b.BankTransKey) = %s
                   OR b.DocNo = %s
                ORDER BY b.BankTransKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["lines"] = self._get_bank_transaction_cash_book_documents(conn, master)
        master["sourceDocuments"] = self._get_bank_transaction_source_documents(master)
        return master

    def _get_bank_transaction_cash_book_documents(self, conn, bank_transaction):
        cash_book_key = bank_transaction.get("cashBookKey")
        doc_no = bank_transaction.get("docNo")
        source_key = bank_transaction.get("sourceKey")
        source_type = str(bank_transaction.get("sourceType") or "").strip()
        return self._fetch_all(
            conn,
            """
                SELECT TOP 1
                    'cash-book' AS moduleKey,
                    c.DocKey AS docKey,
                    c.DocNo AS docNo,
                    c.DocDate AS docDate,
                    c.DocType AS docType,
                    CASE c.DocType
                        WHEN 'OR' THEN 'Receipt'
                        WHEN 'PV' THEN 'Payment'
                        ELSE c.DocType
                    END AS typeLabel,
                    c.DealWith AS dealWith,
                    c.Description AS description,
                    c.CurrencyCode AS currencyCode,
                    c.TotalPayment AS totalPayment,
                    c.LocalTotal AS localTotal,
                    c.DocStatus AS status,
                    c.Cancelled AS cancelled
                FROM CB c
                WHERE (%s IS NOT NULL AND c.DocKey = %s)
                   OR c.DocNo = %s
                   OR (%s IN ('PV', 'OR') AND c.DocKey = %s)
                ORDER BY
                    CASE WHEN c.DocKey = %s THEN 0 WHEN c.DocNo = %s THEN 1 ELSE 2 END,
                    c.DocKey DESC
            """,
            (cash_book_key, cash_book_key, doc_no, source_type, source_key, cash_book_key, doc_no),
        )

    @staticmethod
    def _get_bank_transaction_source_documents(bank_transaction):
        module_key = bank_transaction.get("sourceDocumentModule") or ""
        doc_no = bank_transaction.get("sourceDocumentNo") or ""
        if not module_key or not doc_no:
            return []
        return [
            {
                "moduleKey": module_key,
                "documentType": bank_transaction.get("sourceDocumentLabel") or "",
                "docKey": bank_transaction.get("sourceDocumentKey") or "",
                "docNo": doc_no,
                "docDate": bank_transaction.get("sourceDocumentDate") or "",
                "description": bank_transaction.get("sourceDocumentDescription") or "",
                "amount": bank_transaction.get("sourceDocumentAmount"),
            }
        ]

    def _get_cash_book_source_documents(self, conn, cash_book):
        source_type = str(cash_book.get("sourceType") or "").strip()
        source_key = cash_book.get("sourceKey")
        if not source_type or source_key in {None, ""}:
            return []

        if source_type == "RP":
            return self._fetch_all(
                conn,
                """
                    SELECT TOP 1
                        'ar-payments' AS moduleKey,
                        'AR Payment' AS documentType,
                        p.DocKey AS docKey,
                        p.DocNo AS docNo,
                        p.DocDate AS docDate,
                        p.DebtorCode AS accountCode,
                        d.CompanyName AS accountName,
                        p.Description AS description,
                        p.CurrencyCode AS currencyCode,
                        p.PaymentAmt AS amount,
                        p.LocalPaymentAmt AS localAmount,
                        p.KnockOffAmt AS knockOffAmt,
                        p.LocalUnappliedAmount AS unappliedAmount,
                        p.DocStatus AS status,
                        p.Cancelled AS cancelled
                    FROM ARPayment p
                    LEFT JOIN Debtor d ON d.AccNo = p.DebtorCode
                    WHERE p.DocKey = %s
                """,
                (source_key,),
            )

        if source_type == "RS":
            return self._fetch_all(
                conn,
                """
                    SELECT TOP 1
                        'ar-deposits' AS moduleKey,
                        'AR Deposit' AS documentType,
                        d.DocKey AS docKey,
                        d.DocNo AS docNo,
                        d.DocDate AS docDate,
                        d.DebtorCode AS accountCode,
                        COALESCE(debtor.CompanyName, d.DebtorName) AS accountName,
                        d.Description AS description,
                        d.CurrencyCode AS currencyCode,
                        d.PaymentAmt AS amount,
                        d.PaymentAmt * ISNULL(d.ToHomeRate, 1) AS localAmount,
                        d.TransferedAmt AS transferredAmt,
                        d.Outstanding AS outstanding,
                        d.Cancelled AS cancelled
                    FROM ARDeposit d
                    LEFT JOIN Debtor debtor ON debtor.AccNo = d.DebtorCode
                    WHERE d.DocKey = %s
                """,
                (source_key,),
            )

        if source_type == "PP":
            return self._fetch_all(
                conn,
                """
                    SELECT TOP 1
                        'ap-payments' AS moduleKey,
                        'AP Payment' AS documentType,
                        p.DocKey AS docKey,
                        p.DocNo AS docNo,
                        p.DocDate AS docDate,
                        p.CreditorCode AS accountCode,
                        c.CompanyName AS accountName,
                        p.Description AS description,
                        p.CurrencyCode AS currencyCode,
                        p.PaymentAmt AS amount,
                        p.LocalPaymentAmt AS localAmount,
                        p.KnockOffAmt AS knockOffAmt,
                        p.LocalUnappliedAmount AS unappliedAmount,
                        p.DocStatus AS status,
                        p.Cancelled AS cancelled
                    FROM APPayment p
                    LEFT JOIN Creditor c ON c.AccNo = p.CreditorCode
                    WHERE p.DocKey = %s
                """,
                (source_key,),
            )

        return []

    def _list_payment_methods(self, conn):
        return self._fetch_all(
            conn,
            """
                SELECT
                    PaymentMethod AS paymentMethod,
                    PaymentBy AS paymentBy,
                    PaymentType AS paymentType,
                    BankAccount AS bankAccount,
                    AcceptChequeNo AS acceptChequeNo,
                    IsActive AS isActive
                FROM PaymentMethod
                WHERE IsActive = 'T'
                ORDER BY PaymentMethod
            """,
        )

    def _list_quotations(self, conn):
        sql = """
            SELECT TOP 200
                DocKey AS docKey,
                DocNo AS docNo,
                DocDate AS docDate,
                DebtorCode AS debtorCode,
                DebtorName AS debtorName,
                Description AS description,
                CurrencyCode AS currencyCode,
                FinalTotal AS finalTotal,
                DocStatus AS status
            FROM QT
            ORDER BY DocDate DESC, DocKey DESC
        """
        return self._fetch_all(conn, sql)

    def _get_quotation(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    DocKey AS docKey,
                    DocNo AS docNo,
                    DocDate AS docDate,
                    DebtorCode AS debtorCode,
                    DebtorName AS debtorName,
                    Description AS description,
                    CurrencyCode AS currencyCode,
                    CurrencyRate AS currencyRate,
                    SalesAgent AS agent,
                    YourRef AS yourRef,
                    Validity AS validity,
                    PaymentTerm AS paymentTerm,
                    DeliveryTerm AS deliveryTerm,
                    Tax AS tax,
                    NetTotal AS netTotal,
                    FinalTotal AS finalTotal,
                    DocStatus AS status,
                    Transferable AS transferable,
                    CASE WHEN ToDocKey IS NULL THEN CAST(0 AS bit) ELSE CAST(1 AS bit) END AS isTransfered
                FROM QT
                WHERE DocNo = %s OR CONVERT(varchar(30), DocKey) = %s
                ORDER BY DocKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT
                    Seq AS seq,
                    ItemCode AS itemCode,
                    Description AS description,
                    Qty AS qty,
                    UOM AS uom,
                    UnitPrice AS unitPrice,
                    Discount AS discount,
                    SubTotal AS subTotal,
                    TaxCode AS taxCode,
                    Tax AS tax,
                    ProjNo AS projNo,
                    DeptNo AS deptNo
                FROM QTDTL
                WHERE DocKey = %s
                ORDER BY Seq, DtlKey
            """,
            (master["docKey"],),
        )
        return master

    def _list_purchase_orders(self, conn):
        sql = """
            SELECT TOP 200
                DocKey AS docKey,
                DocNo AS docNo,
                DocDate AS docDate,
                CreditorCode AS creditorCode,
                CreditorName AS creditorName,
                Description AS description,
                CurrencyCode AS currencyCode,
                FinalTotal AS finalTotal,
                DocStatus AS status
            FROM PO
            ORDER BY DocDate DESC, DocKey DESC
        """
        return self._fetch_all(conn, sql)

    def _get_purchase_order(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    DocKey AS docKey,
                    DocNo AS docNo,
                    DocDate AS docDate,
                    CreditorCode AS creditorCode,
                    CreditorName AS creditorName,
                    Description AS description,
                    CurrencyCode AS currencyCode,
                    CurrencyRate AS currencyRate,
                    PurchaseAgent AS agent,
                    Tax AS tax,
                    NetTotal AS netTotal,
                    FinalTotal AS finalTotal,
                    DocStatus AS status,
                    Transferable AS transferable,
                    CASE WHEN ToDocKey IS NULL THEN CAST(0 AS bit) ELSE CAST(1 AS bit) END AS isTransfered
                FROM PO
                WHERE DocNo = %s OR CONVERT(varchar(30), DocKey) = %s
                ORDER BY DocKey DESC
            """,
            (key, key),
        )
        if not master:
            return None

        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT
                    Seq AS seq,
                    ItemCode AS itemCode,
                    Description AS description,
                    Qty AS qty,
                    UOM AS uom,
                    UnitPrice AS unitPrice,
                    Discount AS discount,
                    SubTotal AS subTotal,
                    TaxCode AS taxCode,
                    Tax AS tax,
                    ProjNo AS projNo,
                    DeptNo AS deptNo
                FROM PODTL
                WHERE DocKey = %s
                ORDER BY Seq, DtlKey
            """,
            (master["docKey"],),
        )
        return master

    def _list_items(self, conn):
        sql = """
            SELECT TOP 200
                i.ItemCode AS itemCode,
                i.Description AS description,
                i.BaseUOM AS baseUom,
                i.SalesUOM AS salesUom,
                i.PurchaseUOM AS purchaseUom,
                u.Price AS price,
                i.IsActive AS isActive
            FROM Item i
            OUTER APPLY (
                SELECT TOP 1 Price
                FROM ItemUOM u
                WHERE u.ItemCode = i.ItemCode
                ORDER BY
                    CASE
                        WHEN u.UOM = i.SalesUOM THEN 0
                        WHEN u.UOM = i.BaseUOM THEN 1
                        ELSE 2
                    END,
                    u.AutoKey
            ) u
            ORDER BY i.ItemCode
        """
        return self._fetch_all(conn, sql)

    def _get_item(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    ItemCode AS itemCode,
                    Description AS description,
                    Desc2 AS desc2,
                    ItemGroup AS itemGroup,
                    ItemType AS itemType,
                    ItemBrand AS itemBrand,
                    ItemCategory AS itemCategory,
                    BaseUOM AS baseUom,
                    SalesUOM AS salesUom,
                    PurchaseUOM AS purchaseUom,
                    StockControl AS stockControl,
                    TaxCode AS taxCode,
                    PurchaseTaxCode AS purchaseTaxCode,
                    IsActive AS isActive,
                    Discontinued AS discontinued,
                    IsSalesItem AS isSalesItem,
                    IsPurchaseItem AS isPurchaseItem
                FROM Item
                WHERE ItemCode = %s
            """,
            (key,),
        )
        if not master:
            return None

        master["uoms"] = self._fetch_all(
            conn,
            """
                SELECT
                    UOM AS uom,
                    Rate AS rate,
                    Price AS price,
                    Cost AS cost,
                    MinSalePrice AS minSalePrice,
                    MaxSalePrice AS maxSalePrice,
                    BarCode AS barcode
                FROM ItemUOM
                WHERE ItemCode = %s
                ORDER BY AutoKey
            """,
            (key,),
        )
        return master

    def _list_creditors(self, conn):
        return self._fetch_all(
            conn,
            """
                SELECT TOP 300
                    c.AccNo AS creditorCode,
                    c.CompanyName AS creditorName,
                    c.Phone1 AS phone,
                    c.AreaCode AS area,
                    c.PurchaseAgent AS agent,
                    c.CurrencyCode AS currencyCode,
                    c.DisplayTerm AS displayTerm,
                    c.EmailAddress AS email,
                    c.IsActive AS isActive,
                    summary.invoiceCount AS invoiceCount,
                    summary.outstanding AS outstanding
                FROM Creditor c
                OUTER APPLY (
                    SELECT
                        COUNT(*) AS invoiceCount,
                        SUM(Outstanding) AS outstanding
                    FROM APInvoice i
                    WHERE i.CreditorCode = c.AccNo
                      AND i.Cancelled = 'F'
                ) summary
                ORDER BY c.AccNo
            """,
        )

    def _get_creditor(self, conn, key):
        master = self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    c.AccNo AS creditorCode,
                    c.CompanyName AS creditorName,
                    c.CompanyName AS companyName,
                    c.Phone1 AS phone,
                    c.Phone2 AS phone2,
                    c.Fax1 AS fax,
                    c.EmailAddress AS email,
                    c.WebURL AS webUrl,
                    c.AreaCode AS area,
                    c.PurchaseAgent AS agent,
                    c.CreditorType AS creditorType,
                    c.NatureOfBusiness AS natureOfBusiness,
                    c.CurrencyCode AS currencyCode,
                    c.DisplayTerm AS displayTerm,
                    c.CreditLimit AS creditLimit,
                    c.Address1 AS address1,
                    c.Address2 AS address2,
                    c.Address3 AS address3,
                    c.Address4 AS address4,
                    c.IsActive AS isActive,
                    c.TaxCode AS taxCode,
                    c.InclusiveTax AS inclusiveTax,
                    summary.invoiceCount AS invoiceCount,
                    summary.outstanding AS outstanding,
                    c.Note AS note
                FROM Creditor c
                OUTER APPLY (
                    SELECT
                        COUNT(*) AS invoiceCount,
                        SUM(Outstanding) AS outstanding
                    FROM APInvoice i
                    WHERE i.CreditorCode = c.AccNo
                      AND i.Cancelled = 'F'
                ) summary
                WHERE c.AccNo = %s
            """,
            (key,),
        )
        if not master:
            return None

        master["lines"] = self._fetch_all(
            conn,
            """
                SELECT TOP 100
                    i.DocKey AS docKey,
                    i.DocNo AS docNo,
                    i.DocDate AS docDate,
                    i.SupplierInvoiceNo AS supplierInvoiceNo,
                    i.Description AS description,
                    i.CurrencyCode AS currencyCode,
                    i.NetTotal AS netTotal,
                    i.PaymentAmt AS paymentAmt,
                    i.Outstanding AS outstanding,
                    i.DocStatus AS status,
                    i.Cancelled AS cancelled
                FROM APInvoice i
                WHERE i.CreditorCode = %s
                ORDER BY i.DocDate DESC, i.DocKey DESC
            """,
            (master["creditorCode"],),
        )
        master["paymentLines"] = self._fetch_all(
            conn,
            """
                SELECT TOP 50
                    p.DocKey AS docKey,
                    p.DocNo AS docNo,
                    p.DocDate AS docDate,
                    p.Description AS description,
                    p.CurrencyCode AS currencyCode,
                    p.PaymentAmt AS paymentAmt,
                    p.KnockOffAmt AS knockOffAmt,
                    p.LocalUnappliedAmount AS unappliedAmount,
                    cb.DocNo AS cashBookDocNo,
                    p.DocStatus AS status,
                    p.Cancelled AS cancelled
                FROM APPayment p
                LEFT JOIN CB cb ON cb.DocKey = p.CBKey
                WHERE p.CreditorCode = %s
                ORDER BY p.DocDate DESC, p.DocKey DESC
            """,
            (master["creditorCode"],),
        )
        return master

    def _list_debtors(self, conn):
        sql = """
            SELECT TOP 200
                AccNo AS debtorCode,
                CompanyName AS debtorName,
                Phone1 AS phone,
                AreaCode AS area,
                SalesAgent AS agent,
                CurrencyCode AS currencyCode,
                DisplayTerm AS displayTerm,
                IsActive AS isActive
            FROM Debtor
            ORDER BY AccNo
        """
        return self._fetch_all(conn, sql)

    def _list_debtor_project_candidates(self, conn, limit):
        top = min(max(int(limit or 200), 1), 500)
        sql = f"""
            SELECT TOP {top}
                AccNo AS debtorCode,
                CompanyName AS debtorName,
                CompanyName AS companyName,
                Phone1 AS phone,
                Phone2 AS phone2,
                AreaCode AS area,
                SalesAgent AS agent,
                CurrencyCode AS currencyCode,
                DisplayTerm AS displayTerm,
                Address1 AS address1,
                Address2 AS address2,
                Address3 AS address3,
                Address4 AS address4,
                IsActive AS isActive
            FROM Debtor
            ORDER BY AccNo
        """
        return self._fetch_all(conn, sql)

    def _list_debtors_by_codes(self, conn, debtor_codes):
        placeholders = ",".join("%s" for _ in debtor_codes)
        sql = f"""
            SELECT
                AccNo AS debtorCode,
                CompanyName AS debtorName,
                CompanyName AS companyName,
                Phone1 AS phone,
                Phone2 AS phone2,
                AreaCode AS area,
                SalesAgent AS agent,
                CurrencyCode AS currencyCode,
                DisplayTerm AS displayTerm,
                Address1 AS address1,
                Address2 AS address2,
                Address3 AS address3,
                Address4 AS address4,
                IsActive AS isActive
            FROM Debtor
            WHERE AccNo IN ({placeholders})
        """
        return self._fetch_all(conn, sql, tuple(debtor_codes))

    def _get_debtor(self, conn, key):
        return self._fetch_one(
            conn,
            """
                SELECT TOP 1
                    AccNo AS debtorCode,
                    CompanyName AS debtorName,
                    CompanyName AS companyName,
                    Phone1 AS phone,
                    Phone2 AS phone2,
                    Fax1 AS fax,
                    EmailAddress AS email,
                    AreaCode AS area,
                    SalesAgent AS agent,
                    CurrencyCode AS currencyCode,
                    DisplayTerm AS displayTerm,
                    CreditLimit AS creditLimit,
                    Address1 AS address1,
                    Address2 AS address2,
                    Address3 AS address3,
                    Address4 AS address4,
                    IsActive AS isActive
                FROM Debtor
                WHERE AccNo = %s
            """,
            (key,),
        )

    def _fetch_all(self, conn, sql, params=()):
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return [self._convert_row(row) for row in cursor.fetchall()]

    def _fetch_one(self, conn, sql, params=()):
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return self._convert_row(row) if row else None

    def _convert_row(self, row):
        return {key: self._convert_value(value) for key, value in row.items()}

    @staticmethod
    def _convert_value(value):
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value
