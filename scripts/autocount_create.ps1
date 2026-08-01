param(
    [string]$Resource,
    [string]$PayloadJson,
    [string]$SqlServer,
    [string]$SqlUser,
    [string]$SqlPassword,
    [string]$Database,
    [string]$User,
    [string]$Password
)

$ErrorActionPreference = "Stop"

function Convert-DbValue($Value) {
    if ($null -eq $Value -or $Value -is [DBNull]) {
        return $null
    }
    if ($Value -is [DateTime]) {
        return $Value.ToString("yyyy-MM-dd")
    }
    if ($Value.GetType().IsEnum) {
        return $Value.ToString()
    }
    return $Value
}

function Write-JsonResult($Payload, [int]$ExitCode = 0) {
    $Payload | ConvertTo-Json -Compress -Depth 12
    exit $ExitCode
}

function Load-AutoCountAssemblies {
    $installDir = $env:AUTOCOUNT_INSTALL_DIR
    if ([string]::IsNullOrWhiteSpace($installDir)) {
        $installDir = "C:\Program Files\AutoCount\Accounting 2.2"
    }

    Set-Location $installDir
    Add-Type -TypeDefinition @"
using System;
using System.IO;
using System.Reflection;

public static class AutoCountBridgeAssemblyResolver
{
    public static string BasePath;

    public static void Register(string basePath)
    {
        BasePath = basePath;
        AppDomain.CurrentDomain.AssemblyResolve += Resolve;
    }

    public static Assembly Resolve(object sender, ResolveEventArgs args)
    {
        string name = new AssemblyName(args.Name).Name;
        foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            if (assembly.GetName().Name == name)
            {
                return assembly;
            }
        }

        string path = Path.Combine(BasePath, name + ".dll");
        if (File.Exists(path))
        {
            return Assembly.LoadFrom(path);
        }

        return null;
    }
}
"@
    [AutoCountBridgeAssemblyResolver]::Register($installDir)

    foreach ($dll in @(
        "AutoCount.dll",
        "AutoCount.Accounting.dll",
        "AutoCount.ARAP.dll",
        "AutoCount.Invoicing.dll",
        "AutoCount.Sales.dll",
        "AutoCount.Purchase.dll",
        "AutoCount.Stock.dll",
        "AutoCount.StockMaint.dll",
        "Microsoft.Extensions.DependencyInjection.Abstractions.dll",
        "Microsoft.Extensions.DependencyInjection.dll",
        "Microsoft.Extensions.Logging.Abstractions.dll",
        "Microsoft.Extensions.Logging.dll",
        "Microsoft.Extensions.Options.dll",
        "Microsoft.Extensions.Primitives.dll"
    )) {
        [Reflection.Assembly]::LoadFrom((Resolve-Path $dll)) | Out-Null
    }
}

function New-AutoCountSession {
    $db = [AutoCount.Data.DBSetting]::new(
        [AutoCount.Data.DBServerType]::SQL2000,
        $SqlServer,
        $SqlUser,
        $SqlPassword,
        $Database
    )

    $session = [AutoCount.Authentication.UserSession]::new($db)
    if (-not $session.Login($User, $Password)) {
        Write-JsonResult @{ error = "AutoCount session expired or login failed." } 1
    }

    return @($db, $session)
}

function Has-Prop($Object, [string]$Name) {
    if ($null -eq $Object) {
        return $false
    }
    return $null -ne $Object.PSObject.Properties[$Name]
}

function Get-Prop($Object, [string]$Name, $Default = $null) {
    if (Has-Prop $Object $Name) {
        return $Object.PSObject.Properties[$Name].Value
    }
    return $Default
}

function Require-Prop($Object, [string]$Name, [string]$Label) {
    $value = Get-Prop $Object $Name $null
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
        Write-JsonResult @{ error = "$Label is required." } 1
    }
    return $value
}

function Get-Text($Object, [string]$Name, [string]$Default = "") {
    $value = Get-Prop $Object $Name $Default
    if ($null -eq $value) {
        return $Default
    }
    return [string]$value
}

function Get-Decimal($Object, [string]$Name, [decimal]$Default = 0) {
    $value = Get-Prop $Object $Name $null
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
        return $Default
    }
    return [decimal]$value
}

function Get-Bool($Object, [string]$Name, [bool]$Default = $false) {
    $value = Get-Prop $Object $Name $null
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
        return $Default
    }
    return [System.Convert]::ToBoolean($value)
}

function Get-DateValue($Object, [string]$Name, [DateTime]$Default) {
    $value = Get-Prop $Object $Name $null
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
        return $Default
    }
    return [DateTime]::Parse([string]$value)
}

function Set-NullableTextProperty($Target, [string]$Name, $Value) {
    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        $Target.$Name = $null
    } else {
        $Target.$Name = [string]$Value
    }
}

function Set-OptionalTextProperty($Target, [string]$Name, $Source, [string]$SourceName) {
    if (Has-Prop $Source $SourceName) {
        $Target.$Name = Get-Text $Source $SourceName ""
    }
}

function Set-OptionalDecimalProperty($Target, [string]$Name, $Source, [string]$SourceName) {
    if (Has-Prop $Source $SourceName) {
        $Target.$Name = Get-Decimal $Source $SourceName 0
    }
}

function Set-OptionalDateProperty($Target, [string]$Name, $Source, [string]$SourceName) {
    if (Has-Prop $Source $SourceName) {
        $Target.$Name = Get-DateValue $Source $SourceName ([DateTime]::Today)
    }
}

function Get-Lines($Payload) {
    $lines = Get-Prop $Payload "lines" $null
    if ($null -eq $lines) {
        Write-JsonResult @{ error = "At least one line is required." } 1
    }
    $items = @($lines)
    if ($items.Count -eq 0) {
        Write-JsonResult @{ error = "At least one line is required." } 1
    }
    return $items
}

function Apply-DocumentBase($Doc, $Payload) {
    $Doc.DocNo = Get-Text $Payload "docNo" "<<New>>"
    $Doc.DocDate = Get-DateValue $Payload "docDate" ([DateTime]::Today)
    Set-OptionalDateProperty $Doc "TaxDate" $Payload "taxDate"
    Set-OptionalTextProperty $Doc "Description" $Payload "description"
    Set-OptionalTextProperty $Doc "YourRef" $Payload "yourRef"
    Set-OptionalTextProperty $Doc "PaymentTerm" $Payload "paymentTerm"
    $Doc.CurrencyRate = Get-Decimal $Payload "currencyRate" 1
    $Doc.RoundingMethod = [AutoCount.Document.DocumentRoundingMethod]::LineByLine_Ver2
    $Doc.InclusiveTax = Get-Bool $Payload "inclusiveTax" $false
}

function Apply-ItemLine($Detail, $Line) {
    $Detail.ItemCode = Require-Prop $Line "itemCode" "Item code"
    Set-OptionalTextProperty $Detail "Description" $Line "description"
    $Detail.Qty = Get-Decimal $Line "qty" 1
    $uom = Get-Text $Line "uom" ""
    if (-not [string]::IsNullOrWhiteSpace($uom)) {
        $Detail.UOM = $uom
    }
    $Detail.UnitPrice = Get-Decimal $Line "unitPrice" 0
    Set-OptionalTextProperty $Detail "Discount" $Line "discount"
    if (Has-Prop $Line "taxCode") {
        Set-NullableTextProperty $Detail "TaxCode" (Get-Prop $Line "taxCode" $null)
    }
    if ($Detail.DetailRow.Table.Columns.Contains("TaxCode") -and [string]::IsNullOrWhiteSpace([string]$Detail.DetailRow["TaxCode"])) {
        $Detail.DetailRow["TaxCode"] = [DBNull]::Value
    }
    Set-OptionalTextProperty $Detail "ProjNo" $Line "projNo"
    Set-OptionalTextProperty $Detail "DeptNo" $Line "deptNo"
}

function Apply-SalesInvoiceLine($Detail, $Line) {
    Set-OptionalTextProperty $Detail "ItemCode" $Line "itemCode"
    $Detail.AccNo = Get-Text $Line "accNo" "500-0000"
    $Detail.Description = Get-Text $Line "description" "Service charge"
    Set-OptionalDecimalProperty $Detail "Qty" $Line "qty"
    Set-OptionalTextProperty $Detail "UOM" $Line "uom"
    Set-OptionalDecimalProperty $Detail "UnitPrice" $Line "unitPrice"
    Set-OptionalDecimalProperty $Detail "SubTotal" $Line "subTotal"
    Set-OptionalTextProperty $Detail "Discount" $Line "discount"
    if (Has-Prop $Line "taxCode") {
        Set-NullableTextProperty $Detail "TaxCode" (Get-Prop $Line "taxCode" $null)
    }
    if ($Detail.DetailRow.Table.Columns.Contains("TaxCode") -and [string]::IsNullOrWhiteSpace([string]$Detail.DetailRow["TaxCode"])) {
        $Detail.DetailRow["TaxCode"] = [DBNull]::Value
    }
    Set-OptionalTextProperty $Detail "ProjNo" $Line "projNo"
    Set-OptionalTextProperty $Detail "DeptNo" $Line "deptNo"
}

function Get-TableValue($Row, [string]$Name) {
    if ($Row.Table.Columns.Contains($Name)) {
        return Convert-DbValue $Row[$Name]
    }
    return $null
}

function Get-ARInvoiceForPayment($Db, $Session, $Payload) {
    $invoiceDocKey = Get-Prop $Payload "invoiceDocKey" $null
    $invoiceDocNo = Get-Text $Payload "invoiceDocNo" ""

    if (($null -eq $invoiceDocKey -or [string]::IsNullOrWhiteSpace([string]$invoiceDocKey)) -and
        [string]::IsNullOrWhiteSpace($invoiceDocNo)) {
        Write-JsonResult @{ error = "Invoice doc key or doc no is required." } 1
    }

    $invoiceCmd = [AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess]::Create($Session, $Db)
    if ($null -ne $invoiceDocKey -and -not [string]::IsNullOrWhiteSpace([string]$invoiceDocKey)) {
        return $invoiceCmd.GetARInvoice([int64]$invoiceDocKey)
    }

    return $invoiceCmd.GetARInvoice($invoiceDocNo)
}

try {
    if ([string]::IsNullOrWhiteSpace($PayloadJson)) {
        Write-JsonResult @{ error = "Payload JSON is required." } 1
    }

    $payload = $PayloadJson | ConvertFrom-Json
    Load-AutoCountAssemblies
    $login = New-AutoCountSession
    $db = $login[0]
    $session = $login[1]

    switch ($Resource) {
        "delete-ar-invoices" {
            $cmd = [AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess]::Create($session, $db)
            $docNos = Get-Prop $payload "docNos" $null
            if ($null -eq $docNos) {
                Write-JsonResult @{ error = "docNos is required." } 1
            }

            $deleted = @()
            foreach ($docNo in @($docNos)) {
                $text = [string]$docNo
                if (-not [string]::IsNullOrWhiteSpace($text)) {
                    $doc = $cmd.GetARInvoice($text)
                    if ($null -ne $doc) {
                        if ([decimal]$doc.PaymentAmt -ne 0) {
                            Write-JsonResult @{ error = "Cannot delete AR invoice with payment."; docNo = $text } 1
                        }
                        $cmd.DeleteARInvoice($text)
                        $deleted += $text
                    }
                }
            }

            Write-JsonResult @{
                ok = $true
                resource = $Resource
                deleted = [object[]]$deleted
            }
        }
        "delete-sales-invoices" {
            $cmd = [AutoCount.Invoicing.Sales.Invoice.InvoiceCommand]::Create($session, $db)
            $docNos = Get-Prop $payload "docNos" $null
            if ($null -eq $docNos) {
                Write-JsonResult @{ error = "docNos is required." } 1
            }

            $deleted = @()
            foreach ($docNo in @($docNos)) {
                $text = [string]$docNo
                if (-not [string]::IsNullOrWhiteSpace($text)) {
                    $cmd.Delete($text)
                    $deleted += $text
                }
            }

            Write-JsonResult @{
                ok = $true
                resource = $Resource
                deleted = [object[]]$deleted
            }
        }
        "debtors" {
            $cmd = [AutoCount.ARAP.Debtor.DebtorDataAccess]::Create($session, $db)
            $doc = $cmd.NewDebtor()
            $doc.AccNo = Require-Prop $payload "debtorCode" "Debtor code"
            $doc.CompanyName = Require-Prop $payload "debtorName" "Debtor name"
            Set-OptionalTextProperty $doc "Address1" $payload "address1"
            Set-OptionalTextProperty $doc "Address2" $payload "address2"
            Set-OptionalTextProperty $doc "Address3" $payload "address3"
            Set-OptionalTextProperty $doc "Address4" $payload "address4"
            Set-OptionalTextProperty $doc "Attention" $payload "attention"
            Set-OptionalTextProperty $doc "Phone1" $payload "phone"
            $doc.ControlAccount = Get-Text $payload "controlAccount" "300-0000"
            $doc.CurrencyCode = Get-Text $payload "currencyCode" "SGD"
            $doc.DisplayTerm = Get-Text $payload "displayTerm" "C.O.D."
            $doc.IsActive = Get-Bool $payload "isActive" $true

            $cmd.SaveDebtor($doc, $session.LoginUserID)

            Write-JsonResult @{
                ok = $true
                resource = $Resource
                debtorCode = Convert-DbValue $doc.AccNo
                debtorName = Convert-DbValue $doc.CompanyName
                currencyCode = Convert-DbValue $doc.CurrencyCode
            }
        }
        "invoices" {
            $cmd = [AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess]::Create($session, $db)
            $doc = $cmd.NewARInvoice()
            $doc.DebtorCode = Require-Prop $payload "debtorCode" "Debtor code"
            $doc.DocNo = Get-Text $payload "docNo" "<<New>>"
            $doc.DocDate = Get-DateValue $payload "docDate" ([DateTime]::Today)
            Set-OptionalDateProperty $doc "DueDate" $payload "dueDate"
            Set-OptionalDateProperty $doc "TaxDate" $payload "taxDate"
            $doc.Description = Get-Text $payload "description" "ERP invoice"
            Set-OptionalTextProperty $doc "Note" $payload "note"
            Set-OptionalTextProperty $doc "RefNo2" $payload "refNo2"
            $doc.CurrencyRate = Get-Decimal $payload "currencyRate" 1
            $doc.JournalType = Get-Text $payload "journalType" "SALES"
            $doc.RoundingMethod = [AutoCount.Document.DocumentRoundingMethod]::LineByLine_Ver2
            $doc.InclusiveTax = Get-Bool $payload "inclusiveTax" $false

            foreach ($line in (Get-Lines $payload)) {
                $detail = $doc.NewDetail()
                $detail.AccNo = Require-Prop $line "accNo" "Sales account"
                $detail.Description = Get-Text $line "description" "Service charge"
                $detail.Amount = Get-Decimal $line "amount" 0
                Set-NullableTextProperty $detail "TaxCode" (Get-Prop $line "taxCode" $null)
                Set-OptionalTextProperty $detail "ProjNo" $line "projNo"
                Set-OptionalTextProperty $detail "DeptNo" $line "deptNo"
            }

            $cmd.SaveARInvoice($doc, $session.LoginUserID, $true)

            Write-JsonResult @{
                ok = $true
                resource = $Resource
                docNo = Convert-DbValue $doc.DocNo
                docKey = Convert-DbValue $doc.DocKey
                status = Convert-DbValue $doc.DocStatus
                netTotal = Convert-DbValue $doc.NetTotal
            }
        }
        "sales-invoices" {
            $cmd = [AutoCount.Invoicing.Sales.Invoice.InvoiceCommand]::Create($session, $db)
            $doc = $cmd.AddNew()
            $doc.DocNo = Get-Text $payload "docNo" "<<New>>"
            $doc.DocDate = Get-DateValue $payload "docDate" ([DateTime]::Today)
            Set-OptionalDateProperty $doc "TaxDate" $payload "taxDate"
            $doc.DebtorCode = Require-Prop $payload "debtorCode" "Debtor code"
            $doc.Description = Get-Text $payload "description" "INVOICE"
            Set-OptionalTextProperty $doc "Ref" $payload "ref"
            Set-OptionalTextProperty $doc "Note" $payload "note"
            Set-OptionalTextProperty $doc "DeliverAddr1" $payload "deliverAddr1"
            Set-OptionalTextProperty $doc "DeliverAddr2" $payload "deliverAddr2"
            Set-OptionalTextProperty $doc "DeliverAddr3" $payload "deliverAddr3"
            Set-OptionalTextProperty $doc "DeliverAddr4" $payload "deliverAddr4"
            Set-OptionalTextProperty $doc "DisplayTerm" $payload "displayTerm"
            Set-OptionalTextProperty $doc "Agent" $payload "agent"
            Set-OptionalDecimalProperty $doc "CurrencyRate" $payload "currencyRate"
            $doc.RoundingMethod = [AutoCount.Document.DocumentRoundingMethod]::LineByLine_Ver2
            $doc.InclusiveTax = Get-Bool $payload "inclusiveTax" $false

            foreach ($line in (Get-Lines $payload)) {
                Apply-SalesInvoiceLine ($doc.AddDetail()) $line
            }

            $doc.Save($true)

            Write-JsonResult @{
                ok = $true
                resource = $Resource
                docNo = Convert-DbValue $doc.DocNo
                docKey = Convert-DbValue $doc.DocKey
                debtorCode = Convert-DbValue $doc.DebtorCode
                debtorName = Convert-DbValue $doc.DebtorName
                status = Convert-DbValue $doc.DocStatus
                finalTotal = Convert-DbValue $doc.FinalTotal
            }
        }
        "ar-payments" {
            $amount = Get-Decimal $payload "amount" 0
            if ($amount -le 0) {
                Write-JsonResult @{ error = "Payment amount must be greater than zero." } 1
            }

            $invoice = Get-ARInvoiceForPayment $db $session $payload
            if ($null -eq $invoice) {
                Write-JsonResult @{ error = "Invoice not found." } 1
            }
            if ($invoice.Cancelled) {
                Write-JsonResult @{ error = "Cannot create AR payment for a cancelled invoice." } 1
            }
            if ($amount -gt [decimal]$invoice.Outstanding) {
                Write-JsonResult @{
                    error = "Payment amount exceeds invoice outstanding."
                    outstanding = Convert-DbValue $invoice.Outstanding
                } 1
            }

            $paymentMethod = Get-Text $payload "paymentMethod" "CASH"
            if ([string]::IsNullOrWhiteSpace($paymentMethod)) {
                Write-JsonResult @{ error = "Payment method is required." } 1
            }

            $cmd = [AutoCount.ARAP.ARPayment.ARPaymentDataAccess]::Create($session, $db)
            $doc = $cmd.NewARPayment()
            $doc.DebtorCode = $invoice.DebtorCode
            $doc.DocNo = Get-Text $payload "docNo" "<<New>>"
            $doc.DocDate = Get-DateValue $payload "docDate" ([DateTime]::Today)
            $doc.Description = Get-Text $payload "description" ("Payment for " + [string]$invoice.DocNo)
            Set-OptionalTextProperty $doc "Note" $payload "note"

            $detail = $doc.NewDetail()
            $detail.PaymentMethod = $paymentMethod
            Set-OptionalTextProperty $detail "PaymentBy" $payload "paymentBy"
            Set-OptionalTextProperty $detail "ChequeNo" $payload "chequeNo"
            $detail.PaymentAmt = $amount
            $detail.EndEdit()

            $doc.KnockOff("RI", [int64]$invoice.DocKey, $amount)
            $doc.UpdatePayment()
            $cmd.SaveARPayment($doc, $session.LoginUserID, $true)

            Write-JsonResult @{
                ok = $true
                resource = $Resource
                docNo = Convert-DbValue $doc.DocNo
                docKey = Convert-DbValue $doc.DocKey
                debtorCode = Convert-DbValue $doc.DebtorCode
                invoiceDocNo = Convert-DbValue $invoice.DocNo
                invoiceDocKey = Convert-DbValue $invoice.DocKey
                paymentAmt = Convert-DbValue $doc.PaymentAmt
                knockOffAmt = Convert-DbValue $doc.KnockOffAmt
                status = Convert-DbValue $doc.DocStatus
            }
        }
        "quotations" {
            $cmd = [AutoCount.Invoicing.Sales.Quotation.QuotationCommand]::Create($session, $db)
            $doc = $cmd.AddNew()
            Apply-DocumentBase $doc $payload
            $doc.DebtorCode = Require-Prop $payload "debtorCode" "Debtor code"
            $doc.Agent = Get-Text $payload "agent" $session.LoginUserID
            $doc.Transferable = Get-Bool $payload "transferable" $true
            Set-OptionalTextProperty $doc "Validity" $payload "validity"
            Set-OptionalTextProperty $doc "DeliveryTerm" $payload "deliveryTerm"

            foreach ($line in (Get-Lines $payload)) {
                Apply-ItemLine ($doc.AddDetail()) $line
            }

            $doc.Save($true)

            Write-JsonResult @{
                ok = $true
                resource = $Resource
                docNo = Convert-DbValue $doc.DocNo
                docKey = Convert-DbValue $doc.DocKey
                status = Convert-DbValue $doc.DocStatus
                finalTotal = Convert-DbValue $doc.FinalTotal
            }
        }
        "purchase-orders" {
            $cmd = [AutoCount.Invoicing.Purchase.PurchaseOrder.PurchaseOrderCommand]::Create($session, $db)
            $doc = $cmd.AddNew()
            Apply-DocumentBase $doc $payload
            $doc.CreditorCode = Require-Prop $payload "creditorCode" "Creditor code"
            $doc.Agent = Get-Text $payload "agent" $session.LoginUserID
            $doc.Transferable = Get-Bool $payload "transferable" $true

            foreach ($line in (Get-Lines $payload)) {
                Apply-ItemLine ($doc.AddDetail()) $line
            }

            $doc.Save($true)

            Write-JsonResult @{
                ok = $true
                resource = $Resource
                docNo = Convert-DbValue $doc.DocNo
                docKey = Convert-DbValue $doc.DocKey
                status = Convert-DbValue $doc.DocStatus
                finalTotal = Convert-DbValue $doc.FinalTotal
            }
        }
        "items" {
            $itemCode = Require-Prop $payload "itemCode" "Item code"
            $cmd = [AutoCount.Stock.Item.OldItem.StockItemMaintenance]::Create($session, $db)
            $allowUpdate = Get-Bool $payload "allowUpdate" $false

            if ($cmd.QueryItemCode($itemCode)) {
                if (-not $allowUpdate) {
                    Write-JsonResult @{ error = "Item already exists: $itemCode" } 1
                }
                $cmd.EditItem($itemCode)
            } else {
                $cmd.NewItem()
            }

            $item = $cmd.ItemTable.Rows[0]
            $item["ItemCode"] = $itemCode
            $item["Description"] = Get-Text $payload "description" "ERP item"
            $item["BaseUOM"] = Get-Text $payload "baseUom" "pcs"
            $item["SalesUOM"] = Get-Text $payload "salesUom" (Get-Text $payload "baseUom" "pcs")
            $item["PurchaseUOM"] = Get-Text $payload "purchaseUom" (Get-Text $payload "baseUom" "pcs")
            $item["IsActive"] = if (Get-Bool $payload "isActive" $true) { "T" } else { "F" }
            $item["Discontinued"] = if (Get-Bool $payload "discontinued" $false) { "T" } else { "F" }
            $item["IsSalesItem"] = if (Get-Bool $payload "isSalesItem" $true) { "T" } else { "F" }
            $item["IsPurchaseItem"] = if (Get-Bool $payload "isPurchaseItem" $true) { "T" } else { "F" }

            $optionalItemFields = [ordered]@{
                desc2 = "Desc2"
                itemGroup = "ItemGroup"
                itemType = "ItemType"
                itemBrand = "ItemBrand"
                itemCategory = "ItemCategory"
                taxCode = "TaxCode"
                purchaseTaxCode = "PurchaseTaxCode"
            }

            foreach ($sourceName in $optionalItemFields.Keys) {
                if (Has-Prop $payload $sourceName) {
                    $value = Get-Prop $payload $sourceName $null
                    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
                        $item[$optionalItemFields[$sourceName]] = [DBNull]::Value
                    } else {
                        $item[$optionalItemFields[$sourceName]] = [string]$value
                    }
                }
            }

            $baseUom = Get-Text $payload "baseUom" "pcs"
            if ($cmd.ItemUOMTable.Rows.Count -eq 0) {
                $cmd.InitialItemUOMNewRow($itemCode, $baseUom, 1)
            }

            $uom = $cmd.ItemUOMTable.Rows[0]
            $uom["UOM"] = $baseUom
            $uom["Rate"] = Get-Decimal $payload "uomRate" 1
            $uom["Price"] = Get-Decimal $payload "price" 0
            if (Has-Prop $payload "cost") {
                $uom["Cost"] = Get-Decimal $payload "cost" 0
            }

            $result = $cmd.Save($itemCode)
            if (-not $result.Success) {
                Write-JsonResult @{ error = "Save item failed." } 1
            }

            Write-JsonResult @{
                ok = $true
                resource = $Resource
                itemCode = $itemCode
                description = Get-TableValue $item "Description"
                baseUom = Get-TableValue $item "BaseUOM"
                price = Get-TableValue $uom "Price"
            }
        }
        default {
            Write-JsonResult @{ error = "Unsupported resource: $Resource" } 1
        }
    }
} catch {
    Write-JsonResult @{
        error = $_.Exception.Message
    } 1
}
