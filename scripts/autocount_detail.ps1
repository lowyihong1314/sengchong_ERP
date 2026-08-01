param(
    [string]$Resource,
    [string]$Key,
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

function Get-Field($Row, [string[]]$Names) {
    foreach ($name in $Names) {
        if ($Row.Table.Columns.Contains($name)) {
            return Convert-DbValue $Row[$name]
        }
    }
    return $null
}

function Get-PropertyValue($Object, [string]$Name) {
    $property = $Object.GetType().GetProperty($Name)
    if ($null -eq $property) {
        return $null
    }
    return Convert-DbValue $property.GetValue($Object, $null)
}

function Convert-Row($Row, $Map) {
    $item = [ordered]@{}
    foreach ($key in $Map.Keys) {
        $item[$key] = Get-Field $Row $Map[$key]
    }
    return $item
}

function Convert-Rows($Table, $Map) {
    $rows = @()
    if ($null -eq $Table) {
        return $rows
    }
    foreach ($row in $Table.Rows) {
        $rows += Convert-Row $row $Map
    }
    return $rows
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

try {
    if ([string]::IsNullOrWhiteSpace($Key)) {
        Write-JsonResult @{ error = "Detail key is required." } 1
    }

    Load-AutoCountAssemblies
    $login = New-AutoCountSession
    $db = $login[0]
    $session = $login[1]

    switch ($Resource) {
        "invoices" {
            $cmd = [AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess]::Create($session, $db)
            $doc = $cmd.GetARInvoice($Key)
            if ($null -eq $doc) {
                Write-JsonResult @{ error = "AR invoice not found: $Key" } 1
            }
            $debtorData = $cmd.GetDebtorData($doc.DebtorCode, $doc.DocDate)

            $lineMap = [ordered]@{
                seq = @("Seq")
                accNo = @("AccNo")
                description = @("Description")
                amount = @("Amount")
                subTotal = @("SubTotal")
                taxCode = @("TaxCode")
                tax = @("Tax")
                netAmount = @("NetAmount")
                projNo = @("ProjNo")
                deptNo = @("DeptNo")
            }

            Write-JsonResult @{
                data = [ordered]@{
                    docKey = Get-PropertyValue $doc "DocKey"
                    docNo = Get-PropertyValue $doc "DocNo"
                    docDate = Get-PropertyValue $doc "DocDate"
                    dueDate = Get-PropertyValue $doc "DueDate"
                    debtorCode = Get-PropertyValue $doc "DebtorCode"
                    debtorName = Get-PropertyValue $debtorData "CompanyName"
                    description = Get-PropertyValue $doc "Description"
                    currencyCode = Get-PropertyValue $doc "CurrencyCode"
                    currencyRate = Get-PropertyValue $doc "CurrencyRate"
                    journalType = Get-PropertyValue $doc "JournalType"
                    total = Get-PropertyValue $doc "Total"
                    tax = Get-PropertyValue $doc "Tax"
                    netTotal = Get-PropertyValue $doc "NetTotal"
                    paymentAmt = Get-PropertyValue $doc "PaymentAmt"
                    outstanding = Get-PropertyValue $doc "Outstanding"
                    status = Get-PropertyValue $doc "DocStatus"
                    cancelled = Get-PropertyValue $doc "Cancelled"
                    lines = [object[]](Convert-Rows $doc.ARInvoiceDTLTable $lineMap)
                }
            }
        }
        "debtors" {
            $cmd = [AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess]::Create($session, $db)
            $debtor = $cmd.GetDebtorData($Key, [DateTime]::Today)
            if ($null -eq $debtor) {
                Write-JsonResult @{ error = "Debtor not found: $Key" } 1
            }

            Write-JsonResult @{
                data = [ordered]@{
                    debtorCode = $Key
                    debtorName = Get-PropertyValue $debtor "CompanyName"
                    companyName = Get-PropertyValue $debtor "CompanyName"
                    phone = Get-PropertyValue $debtor "Phone1"
                    phone2 = Get-PropertyValue $debtor "Phone2"
                    fax = Get-PropertyValue $debtor "Fax1"
                    email = Get-PropertyValue $debtor "EmailAddress"
                    area = Get-PropertyValue $debtor "AreaCode"
                    agent = Get-PropertyValue $debtor "Agent"
                    currencyCode = Get-PropertyValue $debtor "CurrencyCode"
                    displayTerm = Get-PropertyValue $debtor "DisplayTerm"
                    creditLimit = Get-PropertyValue $debtor "CreditLimit"
                    address1 = Get-PropertyValue $debtor "Address1"
                    address2 = Get-PropertyValue $debtor "Address2"
                    address3 = Get-PropertyValue $debtor "Address3"
                    address4 = Get-PropertyValue $debtor "Address4"
                    isActive = Get-PropertyValue $debtor "IsActive"
                }
            }
        }
        "quotations" {
            $cmd = [AutoCount.Invoicing.Sales.Quotation.QuotationCommand]::Create($session, $db)
            $doc = $cmd.Edit($Key)

            $lineMap = [ordered]@{
                seq = @("Seq")
                itemCode = @("ItemCode")
                description = @("Description")
                qty = @("Qty")
                uom = @("UOM")
                unitPrice = @("UnitPrice")
                discount = @("Discount")
                subTotal = @("SubTotal")
                taxCode = @("TaxCode")
                tax = @("Tax")
                projNo = @("ProjNo")
                deptNo = @("DeptNo")
            }

            Write-JsonResult @{
                data = [ordered]@{
                    docKey = Get-PropertyValue $doc "DocKey"
                    docNo = Get-PropertyValue $doc "DocNo"
                    docDate = Get-PropertyValue $doc "DocDate"
                    debtorCode = Get-PropertyValue $doc "DebtorCode"
                    debtorName = Get-PropertyValue $doc "DebtorName"
                    description = Get-PropertyValue $doc "Description"
                    currencyCode = Get-PropertyValue $doc "CurrencyCode"
                    currencyRate = Get-PropertyValue $doc "CurrencyRate"
                    agent = Get-PropertyValue $doc "Agent"
                    yourRef = Get-PropertyValue $doc "YourRef"
                    validity = Get-PropertyValue $doc "Validity"
                    paymentTerm = Get-PropertyValue $doc "PaymentTerm"
                    deliveryTerm = Get-PropertyValue $doc "DeliveryTerm"
                    tax = Get-PropertyValue $doc "Tax"
                    netTotal = Get-PropertyValue $doc "NetTotal"
                    finalTotal = Get-PropertyValue $doc "FinalTotal"
                    status = Get-PropertyValue $doc "DocStatus"
                    transferable = Get-PropertyValue $doc "Transferable"
                    isTransfered = Get-PropertyValue $doc "IsTransfered"
                    lines = [object[]](Convert-Rows $doc.DataTableDetail $lineMap)
                }
            }
        }
        "purchase-orders" {
            $cmd = [AutoCount.Invoicing.Purchase.PurchaseOrder.PurchaseOrderCommand]::Create($session, $db)
            $doc = $cmd.Edit($Key)

            $lineMap = [ordered]@{
                seq = @("Seq")
                itemCode = @("ItemCode")
                description = @("Description")
                qty = @("Qty")
                uom = @("UOM")
                unitPrice = @("UnitPrice")
                discount = @("Discount")
                subTotal = @("SubTotal")
                taxCode = @("TaxCode")
                tax = @("Tax")
                projNo = @("ProjNo")
                deptNo = @("DeptNo")
            }

            Write-JsonResult @{
                data = [ordered]@{
                    docKey = Get-PropertyValue $doc "DocKey"
                    docNo = Get-PropertyValue $doc "DocNo"
                    docDate = Get-PropertyValue $doc "DocDate"
                    creditorCode = Get-PropertyValue $doc "CreditorCode"
                    creditorName = Get-PropertyValue $doc "CreditorName"
                    description = Get-PropertyValue $doc "Description"
                    currencyCode = Get-PropertyValue $doc "CurrencyCode"
                    currencyRate = Get-PropertyValue $doc "CurrencyRate"
                    agent = Get-PropertyValue $doc "Agent"
                    tax = Get-PropertyValue $doc "Tax"
                    netTotal = Get-PropertyValue $doc "NetTotal"
                    finalTotal = Get-PropertyValue $doc "FinalTotal"
                    status = Get-PropertyValue $doc "DocStatus"
                    transferable = Get-PropertyValue $doc "Transferable"
                    isTransfered = Get-PropertyValue $doc "IsTransfered"
                    lines = [object[]](Convert-Rows $doc.DataTableDetail $lineMap)
                }
            }
        }
        "items" {
            $cmd = [AutoCount.Stock.Item.OldItem.StockItemMaintenance]::Create($session, $db)
            if (-not $cmd.QueryItemCode($Key)) {
                Write-JsonResult @{ error = "Item not found: $Key" } 1
            }
            $cmd.EditItem($Key)
            $item = $cmd.ItemTable.Rows[0]

            $uomMap = [ordered]@{
                uom = @("UOM")
                rate = @("Rate")
                price = @("Price")
                cost = @("Cost")
                minSalePrice = @("MinSalePrice")
                maxSalePrice = @("MaxSalePrice")
                barcode = @("BarCode")
            }

            Write-JsonResult @{
                data = [ordered]@{
                    itemCode = Get-Field $item @("ItemCode")
                    description = Get-Field $item @("Description")
                    desc2 = Get-Field $item @("Desc2")
                    itemGroup = Get-Field $item @("ItemGroup")
                    itemType = Get-Field $item @("ItemType")
                    itemBrand = Get-Field $item @("ItemBrand")
                    itemCategory = Get-Field $item @("ItemCategory")
                    baseUom = Get-Field $item @("BaseUOM")
                    salesUom = Get-Field $item @("SalesUOM")
                    purchaseUom = Get-Field $item @("PurchaseUOM")
                    stockControl = Get-Field $item @("StockControl")
                    taxCode = Get-Field $item @("TaxCode")
                    purchaseTaxCode = Get-Field $item @("PurchaseTaxCode")
                    isActive = Get-Field $item @("IsActive")
                    discontinued = Get-Field $item @("Discontinued")
                    isSalesItem = Get-Field $item @("IsSalesItem")
                    isPurchaseItem = Get-Field $item @("IsPurchaseItem")
                    uoms = [object[]](Convert-Rows $cmd.ItemUOMTable $uomMap)
                }
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
