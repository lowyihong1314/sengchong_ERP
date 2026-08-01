param(
    [string]$Resource,
    [string]$SqlServer,
    [string]$SqlUser,
    [string]$SqlPassword,
    [string]$Database,
    [string]$User,
    [string]$Password,
    [int]$Limit = 200
)

$ErrorActionPreference = "Stop"

function Convert-DbValue($Value) {
    if ($null -eq $Value -or $Value -is [DBNull]) {
        return $null
    }
    if ($Value -is [DateTime]) {
        return $Value.ToString("yyyy-MM-dd")
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

function Convert-TableRows($Table, $Map, [int]$Limit) {
    $rows = @()
    if ($null -eq $Table) {
        return $rows
    }

    $count = 0
    foreach ($row in $Table.Rows) {
        if ($count -ge $Limit) { break }
        $item = [ordered]@{}
        foreach ($key in $Map.Keys) {
            $item[$key] = Get-Field $row $Map[$key]
        }
        $rows += $item
        $count += 1
    }
    return $rows
}

function Write-JsonResult($Payload, [int]$ExitCode = 0) {
    $Payload | ConvertTo-Json -Compress -Depth 8
    exit $ExitCode
}

function Write-DataRows($Rows) {
    if ($null -eq $Rows) {
        Write-JsonResult @{ data = [object[]]@() }
    }
    Write-JsonResult @{ data = [object[]]@($Rows) }
}

try {
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

    switch ($Resource) {
        "invoices" {
            $cmd = [AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess]::Create($session, $db)
            $criteria = [AutoCount.SearchFilter.SearchCriteria]::new()
            $cols = [string[]]@(
                "DocKey", "DocNo", "DocDate", "DebtorCode", "Description",
                "CurrencyCode", "NetTotal", "Outstanding", "PaymentAmt",
                "Cancelled", "DocStatus"
            )
            $table = $cmd.LoadARInvoiceData($cols, $criteria, $null)
            $map = [ordered]@{
                docKey = @("DocKey")
                docNo = @("DocNo")
                docDate = @("DocDate")
                debtorCode = @("DebtorCode")
                description = @("Description")
                currencyCode = @("CurrencyCode")
                netTotal = @("NetTotal")
                outstanding = @("Outstanding")
                status = @("DocStatus")
            }
            Write-DataRows (Convert-TableRows $table $map $Limit)
        }
        "debtors" {
            $report = [AutoCount.ARAP.Debtor.DebtorReportCommand]::Create($session)
            $criteria = [AutoCount.ARAP.Debtor.DebtorReportingCriteria]::new()
            $criteria.IsPrintActive = [AutoCount.ARAP.ActiveOption]::All
            $dataSource = $report.GetDocumentListingReportDataSource("Debtor", $criteria)

            $table = $null
            if ($dataSource -is [System.Data.DataSet]) {
                foreach ($candidate in $dataSource.Tables) {
                    if (
                        $candidate.Columns.Contains("AccNo") -or
                        $candidate.Columns.Contains("DebtorCode") -or
                        $candidate.Columns.Contains("DebtorCompanyName")
                    ) {
                        $table = $candidate
                        break
                    }
                }
            } elseif ($dataSource -is [System.Data.DataTable]) {
                $table = $dataSource
            } elseif ($dataSource -is [System.Data.DataView]) {
                $table = $dataSource.Table
            }

            $map = [ordered]@{
                debtorCode = @("AccNo", "DebtorCode")
                debtorName = @("CompanyName", "DebtorName", "Name", "DebtorCompanyName")
                phone = @("Phone1", "Phone", "Tel", "DebtorPhone1")
                area = @("AreaCode", "Area", "DebtorAreaCode")
                agent = @("SalesAgent", "Agent", "DebtorSalesAgent")
                currencyCode = @("CurrencyCode", "DebtorCurrencyCode")
                displayTerm = @("DisplayTerm", "CreditTerm", "DebtorDisplayTerm")
                isActive = @("IsActive", "Active")
            }
            $rows = @(Convert-TableRows $table $map $Limit)

            if ($rows.Count -eq 0) {
                $codes = [ordered]@{}

                $arCmd = [AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess]::Create($session, $db)
                $arCriteria = [AutoCount.SearchFilter.SearchCriteria]::new()
                $arTable = $arCmd.LoadARInvoiceData([string[]]@("DebtorCode"), $arCriteria, $null)
                foreach ($row in $arTable.Rows) {
                    $code = Get-Field $row @("DebtorCode")
                    if (-not [string]::IsNullOrWhiteSpace($code)) {
                        $codes[$code] = $true
                    }
                }

                $quotationCmd = [AutoCount.Invoicing.Sales.Quotation.QuotationCommand]::Create($session, $db)
                $quotationTable = $quotationCmd.LoadMasterData("DebtorCode,DebtorName", $null)
                foreach ($row in $quotationTable.Rows) {
                    $code = Get-Field $row @("DebtorCode")
                    if (-not [string]::IsNullOrWhiteSpace($code)) {
                        $codes[$code] = $true
                    }
                }

                foreach ($code in $codes.Keys) {
                    if ($rows.Count -ge $Limit) { break }
                    $debtor = $arCmd.GetDebtorData($code, [DateTime]::Today)
                    $rows += @([ordered]@{
                        debtorCode = $code
                        debtorName = Convert-DbValue $debtor.CompanyName
                        phone = $null
                        area = $null
                        agent = Convert-DbValue $debtor.Agent
                        currencyCode = Convert-DbValue $debtor.CurrencyCode
                        displayTerm = Convert-DbValue $debtor.DisplayTerm
                        isActive = $null
                    })
                }
            }

            Write-DataRows $rows
        }
        "quotations" {
            $cmd = [AutoCount.Invoicing.Sales.Quotation.QuotationCommand]::Create($session, $db)
            $table = $cmd.LoadMasterData("*", $null)
            $map = [ordered]@{
                docKey = @("DocKey")
                docNo = @("DocNo")
                docDate = @("DocDate")
                debtorCode = @("DebtorCode")
                debtorName = @("DebtorName")
                description = @("Description")
                currencyCode = @("CurrencyCode")
                finalTotal = @("FinalTotal", "NetTotal")
                status = @("DocStatus")
            }
            Write-DataRows (Convert-TableRows $table $map $Limit)
        }
        "items" {
            $cmd = [AutoCount.Stock.Item.OldItem.StockItemMaintenance]::Create($session, $db)
            $rows = @()
            $itemCode = $cmd.LoadFirst()
            $count = 0
            while (-not [string]::IsNullOrWhiteSpace($itemCode) -and $count -lt $Limit) {
                $cmd.EditItem($itemCode)
                if ($cmd.ItemTable.Rows.Count -gt 0) {
                    $item = $cmd.ItemTable.Rows[0]
                    $uom = $null
                    if ($cmd.ItemUOMTable.Rows.Count -gt 0) {
                        $uom = $cmd.ItemUOMTable.Rows[0]
                    }
                    $rows += [ordered]@{
                        itemCode = Convert-DbValue $item["ItemCode"]
                        description = Convert-DbValue $item["Description"]
                        baseUom = Convert-DbValue $item["BaseUOM"]
                        salesUom = Convert-DbValue $item["SalesUOM"]
                        purchaseUom = Convert-DbValue $item["PurchaseUOM"]
                        price = if ($null -ne $uom) { Convert-DbValue $uom["Price"] } else { $null }
                        isActive = Convert-DbValue $item["IsActive"]
                    }
                    $count += 1
                }
                $nextCode = $cmd.LoadNext($itemCode)
                if ($nextCode -eq $itemCode) { break }
                $itemCode = $nextCode
            }
            Write-DataRows $rows
        }
        "purchase-orders" {
            $cmd = [AutoCount.Invoicing.Purchase.PurchaseOrder.PurchaseOrderCommand]::Create($session, $db)
            $table = $cmd.LoadMasterData("*", $null)
            $map = [ordered]@{
                docKey = @("DocKey")
                docNo = @("DocNo")
                docDate = @("DocDate")
                creditorCode = @("CreditorCode")
                creditorName = @("CreditorName")
                description = @("Description")
                currencyCode = @("CurrencyCode")
                finalTotal = @("FinalTotal", "NetTotal")
                status = @("DocStatus")
            }
            Write-DataRows (Convert-TableRows $table $map $Limit)
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
