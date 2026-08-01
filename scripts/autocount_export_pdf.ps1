param(
    [string]$Resource,
    [string]$Key,
    [string]$SqlServer,
    [string]$SqlUser,
    [string]$SqlPassword,
    [string]$Database,
    [string]$User,
    [string]$Password,
    [string]$OutputPath,
    [string]$PaymentRequestAmount
)

$ErrorActionPreference = "Stop"

function Write-JsonResult($Payload, [int]$ExitCode = 0) {
    $Payload | ConvertTo-Json -Compress -Depth 8
    exit $ExitCode
}

function Convert-SafeFilePart([string]$Value) {
    $safe = $Value -replace '[\\/:*?"<>|]+', '-'
    $safe = $safe.Trim()
    if ([string]::IsNullOrWhiteSpace($safe)) {
        return "document"
    }
    return $safe
}

function Load-AutoCountAssemblies {
    $installDir = $env:AUTOCOUNT_INSTALL_DIR
    if ([string]::IsNullOrWhiteSpace($installDir)) {
        $installDir = "C:\Program Files\AutoCount\Accounting 2.2"
    }

    Set-Location $installDir
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    Add-Type -TypeDefinition @"
using System;
using System.IO;
using System.Reflection;

public static class AutoCountPdfBridgeAssemblyResolver
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
    [AutoCountPdfBridgeAssemblyResolver]::Register($installDir)

    foreach ($dll in @(
        "AutoCount.dll",
        "AutoCount.UI.dll",
        "AutoCount.Accounting.dll",
        "AutoCount.Accounting.UI.dll",
        "AutoCount.GL.dll",
        "AutoCount.ARAP.dll",
        "AutoCount.Invoicing.dll",
        "AutoCount.Sales.dll",
        "AutoCount.Purchase.dll",
        "AutoCount.Stock.dll",
        "AutoCount.StockMaint.dll",
        "DevExpress.Data.v22.2.dll",
        "DevExpress.Drawing.v22.2.dll",
        "DevExpress.Printing.v22.2.Core.dll",
        "DevExpress.XtraPrinting.v22.2.dll",
        "DevExpress.XtraReports.v22.2.dll",
        "Microsoft.Extensions.DependencyInjection.Abstractions.dll",
        "Microsoft.Extensions.DependencyInjection.dll",
        "Microsoft.Extensions.Logging.Abstractions.dll",
        "Microsoft.Extensions.Logging.dll",
        "Microsoft.Extensions.Options.dll",
        "Microsoft.Extensions.Primitives.dll"
    )) {
        [Reflection.Assembly]::LoadFrom((Resolve-Path $dll)) | Out-Null
    }

    return $installDir
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

function Expand-SystemReport([string]$InstallDir, [string]$ReportFilename) {
    $cacheDir = "C:\ProgramData\WSLGuard\ERPReports"
    New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null

    $targetPath = Join-Path $cacheDir $ReportFilename
    if (Test-Path $targetPath) {
        return $targetPath
    }

    $reportDat = Join-Path $InstallDir "report.dat"
    if (-not (Test-Path $reportDat)) {
        throw "AutoCount report.dat not found."
    }

    $zip = [System.IO.Compression.ZipFile]::OpenRead($reportDat)
    try {
        $entry = $zip.Entries | Where-Object { $_.FullName -eq $ReportFilename } | Select-Object -First 1
        if ($null -eq $entry) {
            throw "AutoCount report format not found: $ReportFilename"
        }

        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $targetPath, $true)
    } finally {
        $zip.Dispose()
    }

    return $targetPath
}

function Get-DatabaseReportTemplate($Db, [string]$ReportType) {
    $row = $Db.GetFirstDataRow(
        "SELECT TOP 1 ReportName, ReportTemplate FROM Report WHERE ReportType=? ORDER BY AutoKey DESC",
        [object[]]@($ReportType)
    )

    if ($null -eq $row -or $row["ReportTemplate"] -eq [DBNull]::Value) {
        return $null
    }

    return @{
        reportName = [string]$row["ReportName"]
        reportBytes = [byte[]]$row["ReportTemplate"]
    }
}

function Resolve-DocKey($Command, [string]$DocumentKey) {
    $parsed = 0L
    if ([Int64]::TryParse($DocumentKey, [ref]$parsed)) {
        return $parsed
    }
    return [Int64]$Command.GetDocKeyByDocNo($DocumentKey)
}

function Invoke-DocumentReportControl($Session, [System.Data.DataSet]$DataSet, [string]$ReportType) {
    try {
        $control = [AutoCount.Invoicing.DocumentReportControl]::new($Session, $DataSet)
        $controlType = [AutoCount.Invoicing.DocumentReportControl]
        $runControl = $controlType.GetMethod(
            "RunDocumentReportControl",
            [System.Reflection.BindingFlags] "Instance,Public,NonPublic"
        )
        if ($null -ne $runControl) {
            $runControl.Invoke($control, @($Session, $DataSet, $ReportType)) | Out-Null
            return
        }

        $autoMerge = $controlType.GetMethod(
            "AutoMergeDetail",
            [System.Reflection.BindingFlags] "Instance,Public"
        )
        if ($null -ne $autoMerge) {
            try {
                $autoMerge.Invoke($control, @()) | Out-Null
            } catch {
                # Some AutoCount datasets do not include every optional merge column.
            }
        }
    } catch {
        throw "AutoCount document report control failed: $($_.Exception.Message)"
    }
}

function Get-DocumentDataSet($Document, [string]$DocumentLabel) {
    if ($null -eq $Document) {
        throw "$DocumentLabel document was not loaded."
    }

    $dataSet = $Document.DataSet
    if ($null -eq $dataSet) {
        throw "$DocumentLabel dataset was not loaded."
    }

    return $dataSet
}

function Ensure-DataColumn($Table, [string]$ColumnName, [Type]$DataType) {
    if ($null -eq $Table -or $Table.Columns.Contains($ColumnName)) {
        return
    }
    if ($null -eq $DataType) {
        $DataType = [string]
    }
    $Table.Columns.Add($ColumnName, $DataType) | Out-Null
}

function Get-RowValue($Row, [string]$ColumnName) {
    if ($null -eq $Row -or -not $Row.Table.Columns.Contains($ColumnName)) {
        return $null
    }

    $value = $Row[$ColumnName]
    if ($value -eq [DBNull]::Value) {
        return $null
    }
    return $value
}

function Convert-ToReportDataSet($Source, [string]$Label) {
    if ($null -eq $Source) {
        throw "$Label report data source was not loaded."
    }

    if ($Source -is [System.Data.DataSet]) {
        return $Source
    }

    if ($Source -is [System.Data.DataTable]) {
        $dataSet = [System.Data.DataSet]::new()
        $dataSet.Tables.Add($Source.Copy()) | Out-Null
        return $dataSet
    }

    if ($Source -is [System.Data.DataView]) {
        $dataSet = [System.Data.DataSet]::new()
        $dataSet.Tables.Add($Source.ToTable()) | Out-Null
        return $dataSet
    }

    foreach ($propertyName in @("DataSet", "ResultDataSet", "DataSource")) {
        $property = $Source.GetType().GetProperty($propertyName)
        if ($null -eq $property) {
            continue
        }

        $value = $property.GetValue($Source, $null)
        if ($null -ne $value -and -not [object]::ReferenceEquals($Source, $value)) {
            return Convert-ToReportDataSet $value $Label
        }
    }

    throw "$Label report data source is not a DataSet."
}

function Convert-DecimalValue($Value) {
    if ($null -eq $Value -or $Value -eq [DBNull]::Value) {
        return [DBNull]::Value
    }
    return [decimal]$Value
}

function Format-DecimalText($Value) {
    if ($null -eq $Value -or $Value -eq [DBNull]::Value) {
        return ""
    }
    return ([decimal]$Value).ToString("0.00")
}

function Set-GeneratedDetailColumns($Table) {
    if ($null -eq $Table) {
        return
    }

    Ensure-DataColumn $Table "UOMRate" ([decimal])
    Ensure-DataColumn $Table "SG_AutoNumbering" ([string])
    Ensure-DataColumn $Table "SG_UnitPrice" ([string])
    Ensure-DataColumn $Table "SG_SubTotalWithTax" ([string])

    $lineNo = 1
    foreach ($row in $Table.Rows) {
        if ($row.RowState -eq [System.Data.DataRowState]::Deleted) {
            continue
        }

        $printOut = Get-RowValue $row "PrintOut"
        $isPrintable = if ($null -eq $printOut) { $true } else { [bool]$printOut }

        if ($row["UOMRate"] -eq [DBNull]::Value) {
            $row["UOMRate"] = Convert-DecimalValue (Get-RowValue $row "Rate")
        }
        if ($isPrintable) {
            $row["SG_AutoNumbering"] = [string]$lineNo
        } else {
            $row["SG_AutoNumbering"] = ""
        }
        if ([string]::IsNullOrWhiteSpace([string]$row["SG_UnitPrice"])) {
            $row["SG_UnitPrice"] = Format-DecimalText (Get-RowValue $row "UnitPrice")
        }
        if ([string]::IsNullOrWhiteSpace([string]$row["SG_SubTotalWithTax"])) {
            $withTax = Get-RowValue $row "SubTotalWithTax"
            if ($null -eq $withTax) {
                $withTax = Get-RowValue $row "SubTotal"
            }
            $row["SG_SubTotalWithTax"] = Format-DecimalText $withTax
        }
        if ($isPrintable) {
            $lineNo += 1
        }
    }
}

function Ensure-Relation($DataSet, [string]$RelationName, $ParentTable, [string]$ParentColumn, $ChildTable, [string]$ChildColumn) {
    if (
        $null -eq $DataSet -or
        $null -eq $ParentTable -or
        $null -eq $ChildTable -or
        $DataSet.Relations.Contains($RelationName) -or
        -not $ParentTable.Columns.Contains($ParentColumn) -or
        -not $ChildTable.Columns.Contains($ChildColumn)
    ) {
        return
    }

    foreach ($relation in $DataSet.Relations) {
        if (
            $relation.ParentColumns.Count -eq 1 -and
            $relation.ChildColumns.Count -eq 1 -and
            $relation.ParentColumns[0] -eq $ParentTable.Columns[$ParentColumn] -and
            $relation.ChildColumns[0] -eq $ChildTable.Columns[$ChildColumn]
        ) {
            if (-not $DataSet.Relations.Contains($RelationName)) {
                $relation.RelationName = $RelationName
            }
            return
        }
    }

    $relation = [System.Data.DataRelation]::new(
        $RelationName,
        $ParentTable.Columns[$ParentColumn],
        $ChildTable.Columns[$ChildColumn],
        $false
    )
    $DataSet.Relations.Add($relation)
}

function Ensure-CompanyProfileTable($DataSet, $Db) {
    if ($DataSet.Tables.Contains("CompanyProfile")) {
        return
    }

    $table = [System.Data.DataTable]::new("CompanyProfile")
    $table.Columns.Add("CompanyName", [string]) | Out-Null
    $table.Columns.Add("ReportHeader", [string]) | Out-Null
    $table.Columns.Add("Address1", [string]) | Out-Null
    $table.Columns.Add("Phone1", [string]) | Out-Null
    $table.Columns.Add("Phone2", [string]) | Out-Null
    $table.Columns.Add("RegisterNo", [string]) | Out-Null
    $table.Columns.Add("Logo", [byte[]]) | Out-Null

    $profile = [AutoCount.CompanyProfile]::Create($Db)
    $row = $table.NewRow()
    $row["CompanyName"] = [string]$profile.CompanyName
    $row["ReportHeader"] = [string]$profile.ReportHeader
    $row["Address1"] = [string]$profile.Address1
    $row["Phone1"] = [string]$profile.Phone1
    $row["Phone2"] = [string]$profile.Phone2
    $row["RegisterNo"] = [string]$profile.RegisterNo
    $table.Rows.Add($row)
    $DataSet.Tables.Add($table)
}

function Ensure-CurrentUserTable($DataSet, $Session) {
    if ($DataSet.Tables.Contains("CurrentUser")) {
        return
    }

    $table = [System.Data.DataTable]::new("CurrentUser")
    $table.Columns.Add("UserID", [string]) | Out-Null
    $table.Columns.Add("UserName", [string]) | Out-Null

    $row = $table.NewRow()
    $row["UserID"] = [string]$Session.LoginUserID
    $row["UserName"] = [string]$Session.LoginUserID
    $table.Rows.Add($row)
    $DataSet.Tables.Add($table)
}

function Ensure-ReportOptionTable($DataSet, [string]$Criteria, [DateTime]$FromDate, [DateTime]$ToDate) {
    if ($DataSet.Tables.Contains("Report Option")) {
        return
    }

    $table = [System.Data.DataTable]::new("Report Option")
    $table.Columns.Add("Criteria", [string]) | Out-Null
    $table.Columns.Add("ShowCriteria", [string]) | Out-Null
    $table.Columns.Add("GroupBy", [string]) | Out-Null
    $table.Columns.Add("SortBy", [string]) | Out-Null
    $table.Columns.Add("ShowTransactionDescription", [string]) | Out-Null
    $table.Columns.Add("ShowProject", [string]) | Out-Null
    $table.Columns.Add("ShowDepartment", [string]) | Out-Null
    $table.Columns.Add("FromDate", [DateTime]) | Out-Null
    $table.Columns.Add("ToDate", [DateTime]) | Out-Null

    $row = $table.NewRow()
    $row["Criteria"] = $Criteria
    $row["ShowCriteria"] = "False"
    $row["GroupBy"] = "None"
    $row["SortBy"] = "Document No"
    $row["ShowTransactionDescription"] = "True"
    $row["ShowProject"] = "False"
    $row["ShowDepartment"] = "False"
    $row["FromDate"] = $FromDate
    $row["ToDate"] = $ToDate
    $table.Rows.Add($row)
    $DataSet.Tables.Add($table)
}

function Prepare-InvoicingReportDataSet($DataSet, $Session, $Db) {
    $master = $DataSet.Tables["Master"]
    $detail = $DataSet.Tables["Detail"]
    $packageDetail = $DataSet.Tables["PackageDetail"]

    if ($null -ne $master) {
        Ensure-DataColumn $master "CurrencySymbol" ([string])
        Ensure-DataColumn $master "TotalWithTax" ([decimal])

        foreach ($row in $master.Rows) {
            if ([string]::IsNullOrWhiteSpace([string]$row["CurrencySymbol"])) {
                $currencyCode = Get-RowValue $row "CurrencyCode"
                $row["CurrencySymbol"] = if ($null -ne $currencyCode) { [string]$currencyCode } else { "" }
            }
            if ($row["TotalWithTax"] -eq [DBNull]::Value) {
                $total = Get-RowValue $row "FinalTotal"
                if ($null -eq $total) {
                    $total = Get-RowValue $row "Total"
                }
                $row["TotalWithTax"] = Convert-DecimalValue $total
            }
        }
    }

    Set-GeneratedDetailColumns $detail
    Set-GeneratedDetailColumns $packageDetail

    Ensure-Relation $DataSet "MasterDetailRelation" $master "DocKey" $detail "DocKey"
    Ensure-Relation $DataSet "SubDetailRelation" $detail "DtlKey" $packageDetail "ParentDtlKey"
    Ensure-CompanyProfileTable $DataSet $Db
    Ensure-CurrentUserTable $DataSet $Session

    return $DataSet
}

function Prepare-ARInvoiceAsInvoiceDocumentDataSet($DataSet, $Session, $Db) {
    $master = $DataSet.Tables["Master"]
    $detail = $DataSet.Tables["Detail"]
    if ($null -eq $master -or $null -eq $detail) {
        throw "AR invoice dataset is missing Master or Detail table."
    }

    Ensure-DataColumn $master "DebtorName" ([string])
    Ensure-DataColumn $master "InvAddr1" ([string])
    Ensure-DataColumn $master "InvAddr2" ([string])
    Ensure-DataColumn $master "InvAddr3" ([string])
    Ensure-DataColumn $master "InvAddr4" ([string])
    Ensure-DataColumn $master "Attention" ([string])
    Ensure-DataColumn $master "Phone1" ([string])
    Ensure-DataColumn $master "Fax1" ([string])
    Ensure-DataColumn $master "FinalTotal" ([decimal])
    Ensure-DataColumn $master "TotalWithTax" ([decimal])
    Ensure-DataColumn $master "RoundAdj" ([decimal])
    Ensure-DataColumn $master "FinalTotalInCurrentCultureInfo" ([string])

    foreach ($row in $master.Rows) {
        $finalTotal = Get-RowValue $row "NetTotal"
        if ($null -eq $finalTotal) {
            $finalTotal = Get-RowValue $row "Total"
        }
        $currencyCode = Get-RowValue $row "CurrencyCode"
        if ($null -eq $currencyCode) {
            $currencyCode = Get-RowValue $row "CurrencySymbol"
        }

        $row["DebtorName"] = [string](Get-RowValue $row "DebtorCompanyName")
        $row["InvAddr1"] = [string](Get-RowValue $row "DebtorAddress1")
        $row["InvAddr2"] = [string](Get-RowValue $row "DebtorAddress2")
        $row["InvAddr3"] = [string](Get-RowValue $row "DebtorAddress3")
        $row["InvAddr4"] = [string](Get-RowValue $row "DebtorAddress4")
        $row["Attention"] = [string](Get-RowValue $row "DebtorAttention")
        $row["Phone1"] = [string](Get-RowValue $row "DebtorPhone1")
        $row["Fax1"] = [string](Get-RowValue $row "DebtorFax1")
        $row["FinalTotal"] = Convert-DecimalValue $finalTotal
        $row["TotalWithTax"] = Convert-DecimalValue $finalTotal
        $row["RoundAdj"] = [decimal]0
        $row["FinalTotalInCurrentCultureInfo"] = ("{0} {1}" -f [string]$currencyCode, (Format-DecimalText $finalTotal)).Trim()
    }

    Ensure-DataColumn $detail "DtlKey" ([Int64])
    Ensure-DataColumn $detail "Qty" ([decimal])
    Ensure-DataColumn $detail "UserUOM" ([string])
    Ensure-DataColumn $detail "UnitPrice" ([decimal])
    Ensure-DataColumn $detail "Discount" ([string])
    Ensure-DataColumn $detail "FurtherDescription" ([string])
    Ensure-DataColumn $detail "OurDONo" ([string])
    Ensure-DataColumn $detail "YourPONo" ([string])
    Ensure-DataColumn $detail "SerialNoListCalc" ([string])
    Ensure-DataColumn $detail "SubTotalWithTax" ([decimal])
    Ensure-DataColumn $detail "PrintOut" ([bool])

    $lineNo = 1
    foreach ($row in $detail.Rows) {
        if ($row.RowState -eq [System.Data.DataRowState]::Deleted) {
            continue
        }

        $amount = Get-RowValue $row "NetAmount"
        if ($null -eq $amount) {
            $amount = Get-RowValue $row "Amount"
        }
        if ($null -eq $amount) {
            $amount = Get-RowValue $row "SubTotal"
        }

        $row["DtlKey"] = [Int64]$lineNo
        $row["Qty"] = [decimal]1
        $row["UserUOM"] = ""
        $row["UnitPrice"] = Convert-DecimalValue $amount
        $row["Discount"] = ""
        $row["FurtherDescription"] = ""
        $row["OurDONo"] = ""
        $row["YourPONo"] = ""
        $row["SerialNoListCalc"] = ""
        $row["SubTotalWithTax"] = Convert-DecimalValue $amount
        $row["PrintOut"] = $true
        $lineNo += 1
    }

    if (-not $DataSet.Tables.Contains("PackageDetail")) {
        $packageDetail = [System.Data.DataTable]::new("PackageDetail")
        $packageDetail.Columns.Add("DtlKey", [Int64]) | Out-Null
        $packageDetail.Columns.Add("ParentDtlKey", [Int64]) | Out-Null
        $packageDetail.Columns.Add("Description", [string]) | Out-Null
        $packageDetail.Columns.Add("Qty", [decimal]) | Out-Null
        $packageDetail.Columns.Add("SG_AutoNumbering", [string]) | Out-Null
        $DataSet.Tables.Add($packageDetail)
    }

    Set-GeneratedDetailColumns $detail
    Set-GeneratedDetailColumns $DataSet.Tables["PackageDetail"]
    Ensure-Relation $DataSet "MasterDetailRelation" $master "DocKey" $detail "DocKey"
    Ensure-Relation $DataSet "SubDetailRelation" $detail "DtlKey" $DataSet.Tables["PackageDetail"] "ParentDtlKey"
    Ensure-CompanyProfileTable $DataSet $Db
    Ensure-CurrentUserTable $DataSet $Session

    return $DataSet
}

function Resolve-FirstReportValue($DataSet, [string]$DataMember) {
    if ($null -eq $DataSet -or [string]::IsNullOrWhiteSpace($DataMember)) {
        return $null
    }

    $parts = $DataMember.Split(".")
    if ($parts.Length -lt 2 -or -not $DataSet.Tables.Contains($parts[0])) {
        return $null
    }

    $table = $DataSet.Tables[$parts[0]]
    if ($table.Rows.Count -eq 0) {
        return $null
    }

    $row = $table.Rows[0]
    for ($index = 1; $index -lt ($parts.Length - 1); $index += 1) {
        $relation = $DataSet.Relations[$parts[$index]]
        if ($null -eq $relation) {
            return $null
        }
        $children = $row.GetChildRows($relation)
        if ($children.Count -eq 0) {
            return $null
        }
        $row = $children[0]
    }

    $columnName = $parts[$parts.Length - 1]
    if (-not $row.Table.Columns.Contains($columnName)) {
        return $null
    }
    $value = $row[$columnName]
    if ($value -eq [DBNull]::Value) {
        return $null
    }
    return $value
}

function Apply-ControlTextFormats($Control, $DataSet) {
    try {
        $dateBinding = $null
        foreach ($binding in $Control.DataBindings) {
            if (
                [string]$binding.PropertyName -eq "Text" -and
                [string]$binding.DataMember -match "(^|\.)(DocDate|Date|PaymentDate|InvoiceDate|StatementDate)$"
            ) {
                $dateBinding = [string]$binding.DataMember
                break
            }
        }

        switch ($Control.Name) {
            "xrDate" {
                $Control.TextFormatString = "{0:dd/MM/yyyy}"
            }
            "xrQty" {
                $Control.TextFormatString = "{0:0.##}"
            }
            "xrPackageQty" {
                $Control.TextFormatString = "{0:0.##}"
            }
        }

        if ($null -ne $dateBinding) {
            $dateValue = Resolve-FirstReportValue $DataSet $dateBinding
            if ($dateValue -is [DateTime]) {
                $Control.DataBindings.Clear()
                $Control.Text = $dateValue.ToString("dd/MM/yyyy")
            } else {
                $Control.TextFormatString = "{0:dd/MM/yyyy}"
            }
        }
    } catch {
    }

    foreach ($child in $Control.Controls) {
        Apply-ControlTextFormats $child $DataSet
    }
}

function New-XRLabel([string]$Text, [float]$Left, [float]$Top, [float]$Width, [float]$Height) {
    $label = New-Object DevExpress.XtraReports.UI.XRLabel
    $label.Text = $Text
    $label.LeftF = $Left
    $label.TopF = $Top
    $label.WidthF = $Width
    $label.HeightF = $Height
    $label.TextAlignment = [DevExpress.XtraPrinting.TextAlignment]::MiddleRight
    Write-Output -NoEnumerate $label
}

function Set-XRControlBoldFont($Control, $ReferenceControl) {
    if ($null -eq $Control) {
        return
    }

    $baseFont = $Control.Font
    if ($null -ne $ReferenceControl -and $null -ne $ReferenceControl.Font) {
        $baseFont = $ReferenceControl.Font
    }
    if ($null -eq $baseFont) {
        return
    }

    if ($baseFont.GetType().FullName -eq "DevExpress.Drawing.DXFont") {
        $boldStyle = [DevExpress.Drawing.DXFontStyle]([int]$baseFont.Style -bor [int][DevExpress.Drawing.DXFontStyle]::Bold)
        $Control.Font = New-Object DevExpress.Drawing.DXFont -ArgumentList @($baseFont, $boldStyle)
    } else {
        $boldStyle = [System.Drawing.FontStyle]([int]$baseFont.Style -bor [int][System.Drawing.FontStyle]::Bold)
        $Control.Font = New-Object System.Drawing.Font -ArgumentList @($baseFont, $boldStyle)
    }
    try { $Control.StylePriority.UseFont = $true } catch { }
}

function Copy-XRLabelAppearance($Target, $Reference, [bool]$CopyBorders) {
    if ($null -eq $Target) {
        return
    }

    if ($null -ne $Reference) {
        foreach ($propertyName in @("ForeColor", "BackColor", "Padding", "TextAlignment")) {
            try { $Target.$propertyName = $Reference.$propertyName } catch { }
        }

        if ($CopyBorders) {
            foreach ($propertyName in @("Borders", "BorderColor", "BorderDashStyle", "BorderWidth")) {
                try { $Target.$propertyName = $Reference.$propertyName } catch { }
            }
            try { $Target.StylePriority.UseBorders = $true } catch { }
            try { $Target.StylePriority.UseBorderColor = $true } catch { }
            try { $Target.StylePriority.UseBorderDashStyle = $true } catch { }
            try { $Target.StylePriority.UseBorderWidth = $true } catch { }
        }
    }

    try { $Target.StylePriority.UseBackColor = $true } catch { }
    try { $Target.StylePriority.UseForeColor = $true } catch { }
    try { $Target.StylePriority.UsePadding = $true } catch { }
    try { $Target.StylePriority.UseTextAlignment = $true } catch { }
    Set-XRControlBoldFont $Target $Reference
}

function Set-XRControlForeColor($Control, [System.Drawing.Color]$Color) {
    if ($null -eq $Control) {
        return
    }

    $Control.ForeColor = $Color
    try { $Control.StylePriority.UseForeColor = $true } catch { }
}

function Find-XRControlByName($Control, [string]$Name) {
    if ($null -eq $Control) {
        return $null
    }
    if ([string]$Control.Name -eq $Name) {
        Write-Output -NoEnumerate $Control
        return
    }

    foreach ($child in $Control.Controls) {
        $match = Find-XRControlByName $child $Name
        if ($null -ne $match) {
            Write-Output -NoEnumerate $match
            return
        }
    }

    return $null
}

function Find-XRControlByNameInBand($Band, [string]$Name) {
    if ($null -eq $Band) {
        return $null
    }

    $match = Find-XRControlByName $Band $Name
    if ($null -ne $match) {
        Write-Output -NoEnumerate $match
        return
    }

    $bandsProperty = $Band.GetType().GetProperty("Bands")
    if ($null -ne $bandsProperty) {
        foreach ($childBand in $Band.Bands) {
            $match = Find-XRControlByNameInBand $childBand $Name
            if ($null -ne $match) {
                Write-Output -NoEnumerate $match
                return
            }
        }
    }

    return $null
}

function Find-XRControlByNameInReport($Report, [string]$Name) {
    if ($null -eq $Report -or $null -eq $Report.Bands) {
        return $null
    }

    foreach ($band in $Report.Bands) {
        $match = Find-XRControlByNameInBand $band $Name
        if ($null -ne $match) {
            Write-Output -NoEnumerate $match
            return
        }
    }

    return $null
}

function Add-InvoicePaymentSummary($Report, $DataSet, $RequestAmount) {
    if (
        $null -eq $DataSet -or
        -not $DataSet.Tables.Contains("Master") -or
        -not $DataSet.Tables["Master"].Columns.Contains("PaymentAmt") -or
        -not $DataSet.Tables["Master"].Columns.Contains("Outstanding") -or
        $DataSet.Tables["Master"].Rows.Count -eq 0
    ) {
        return
    }

    $masterRow = $DataSet.Tables["Master"].Rows[0]
    $paidText = Format-DecimalText (Get-RowValue $masterRow "PaymentAmt")
    $outstandingAmount = [decimal](Get-RowValue $masterRow "Outstanding")
    $outstandingText = Format-DecimalText $outstandingAmount
    $hasRequestAmount = $null -ne $RequestAmount
    $requestAmountValue = [decimal]0
    $balanceAfterRequest = $outstandingAmount

    if ($hasRequestAmount) {
        $requestAmountValue = [decimal]$RequestAmount
        if ($requestAmountValue -le 0) {
            Write-JsonResult @{ error = "Request amount must be greater than zero." } 1
        }
        if ($requestAmountValue -gt $outstandingAmount) {
            Write-JsonResult @{ error = "Request amount cannot exceed invoice outstanding." } 1
        }
        $balanceAfterRequest = $outstandingAmount - $requestAmountValue
    }

    $panel = Find-XRControlByNameInReport $Report "xrPanel1"
    if ($null -ne $panel) {
        $labelAnchor = Find-XRControlByName $panel "lblFinalTotal"
        $valueAnchor = Find-XRControlByName $panel "xrFinalTotal"
        if ($null -eq $labelAnchor -or $null -eq $valueAnchor) {
            $labelAnchor = Find-XRControlByName $panel "xrNetTotal"
            $valueAnchor = Find-XRControlByName $panel "xrNetTotal"
        }

        $labelWidth = [float]95
        $valueWidth = [float]130
        $labelLeft = [float]530
        $valueLeft = [float]627
        $top = [float]64
        $height = [float]15
        if ($null -ne $labelAnchor) {
            $labelLeft = [float]$labelAnchor.LeftF
            $labelWidth = [float]$labelAnchor.WidthF
            $top = [float]([double]$labelAnchor.TopF + [double]$labelAnchor.HeightF + 3)
            $height = [float]$labelAnchor.HeightF
        }
        if ($null -ne $valueAnchor) {
            $valueLeft = [float]$valueAnchor.LeftF
            $valueWidth = [float]$valueAnchor.WidthF
            $candidateTop = [float]([double]$valueAnchor.TopF + [double]$valueAnchor.HeightF + 3)
            if ($candidateTop -gt $top) {
                $top = $candidateTop
            }
        }
        if ($hasRequestAmount -and $labelWidth -lt 165 -and $valueLeft -gt 170) {
            $labelLeft = [float]($valueLeft - 170)
            $labelWidth = [float]166
        }

        $paidCaption = New-XRLabel "Paid" $labelLeft $top $labelWidth $height
        $paidValue = New-XRLabel $paidText $valueLeft $top $valueWidth $height
        $outstandingCaption = New-XRLabel "Outstanding" $labelLeft ([float]($top + $height + 3)) $labelWidth $height
        $outstandingValue = New-XRLabel $outstandingText $valueLeft ([float]($top + $height + 3)) $valueWidth $height
        foreach ($caption in @($paidCaption, $outstandingCaption)) {
            Copy-XRLabelAppearance $caption $labelAnchor $false
        }
        foreach ($value in @($paidValue, $outstandingValue)) {
            Copy-XRLabelAppearance $value $valueAnchor $true
        }

        $panel.Controls.Add($paidCaption) | Out-Null
        $panel.Controls.Add($paidValue) | Out-Null
        $panel.Controls.Add($outstandingCaption) | Out-Null
        $panel.Controls.Add($outstandingValue) | Out-Null

        $rowCount = 2
        if ($hasRequestAmount) {
            $requestTop = [float]($top + (($height + 3) * 2))
            $balanceTop = [float]($top + (($height + 3) * 3))
            $requestCaption = New-XRLabel "This Request" $labelLeft $requestTop $labelWidth $height
            $requestValue = New-XRLabel (Format-DecimalText $requestAmountValue) $valueLeft $requestTop $valueWidth $height
            $balanceCaption = New-XRLabel "Balance After Request" $labelLeft $balanceTop $labelWidth $height
            $balanceValue = New-XRLabel (Format-DecimalText $balanceAfterRequest) $valueLeft $balanceTop $valueWidth $height
            foreach ($caption in @($requestCaption, $balanceCaption)) {
                Copy-XRLabelAppearance $caption $labelAnchor $false
            }
            foreach ($value in @($requestValue, $balanceValue)) {
                Copy-XRLabelAppearance $value $valueAnchor $true
            }
            $requestBlue = [System.Drawing.Color]::FromArgb(0, 87, 184)
            Set-XRControlForeColor $requestCaption $requestBlue
            Set-XRControlForeColor $requestValue $requestBlue

            $panel.Controls.Add($requestCaption) | Out-Null
            $panel.Controls.Add($requestValue) | Out-Null
            $panel.Controls.Add($balanceCaption) | Out-Null
            $panel.Controls.Add($balanceValue) | Out-Null
            $rowCount = 4
        }

        $requiredHeight = [float]($top + (($height + 3) * $rowCount) + 4)
        if ($panel.HeightF -lt $requiredHeight) {
            $panel.HeightF = $requiredHeight
        }
        if ($null -ne $panel.Parent -and $panel.Parent.HeightF -lt ([float]($panel.TopF + $panel.HeightF))) {
            $panel.Parent.HeightF = [float]($panel.TopF + $panel.HeightF)
        }
        return
    }

    Write-JsonResult @{ error = "Invoice total panel was not found in the report template." } 1
}

function Apply-ReportTextFormats($Report, $DataSet) {
    foreach ($band in $Report.Bands) {
        Apply-ControlTextFormats $band $DataSet
    }
}

function Get-ReportPayload($Resource, $Key, $Db, $Session) {
    switch ($Resource) {
        "invoices" {
            $invoiceCmd = [AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess]::Create($Session, $Db)
            $doc = $invoiceCmd.GetARInvoice($Key)
            if ($null -eq $doc) {
                Write-JsonResult @{ error = "Invoice not found: $Key" } 1
            }

            $reportCmd = [AutoCount.ARAP.ARInvoice.ARInvoiceReportCommand]::Create($Session)
            $criteria = [AutoCount.ARAP.ARInvoice.ARInvoiceReportingCriteria]::new()
            $dataSet = $reportCmd.GetReportDataSource([Int64]$doc.DocKey, $criteria)
            Prepare-ARInvoiceAsInvoiceDocumentDataSet $dataSet $Session $Db | Out-Null
            $requestAmount = $null
            $reportType = "Invoice Document"
            if (-not [string]::IsNullOrWhiteSpace($PaymentRequestAmount)) {
                $requestAmount = [decimal]$PaymentRequestAmount
                $reportType = "Invoice Payment Request"
            }

            return @{
                dataSet = $dataSet
                docNo = [string]$doc.DocNo
                reportFile = "Invoice.art"
                reportName = "Invoice.art"
                reportType = $reportType
                addPaymentSummary = $true
                requestAmount = $requestAmount
            }
        }
        "ar-payments" {
            $paymentCmd = [AutoCount.ARAP.ARPayment.ARPaymentDataAccess]::Create($Session, $Db)
            $doc = $null
            $parsedDocKey = 0L
            if ([Int64]::TryParse($Key, [ref]$parsedDocKey)) {
                $doc = $paymentCmd.GetARPayment($parsedDocKey)
            }
            if ($null -eq $doc) {
                $doc = $paymentCmd.GetARPayment($Key)
            }
            if ($null -eq $doc) {
                Write-JsonResult @{ error = "AR payment not found: $Key" } 1
            }

            if ($null -eq $doc.CBKey -or [Int64]$doc.CBKey -le 0) {
                Write-JsonResult @{ error = "AR payment has no linked CashBook official receipt: $Key" } 1
            }

            $criteria = [AutoCount.GL.CashBook.CashBookReportCriteria]::new($Db)
            $reportCmd = [AutoCount.GL.CashBook.CashBookReportCommand]::Create($Session, $criteria)
            $dataSet = Convert-ToReportDataSet (
                $reportCmd.GetOfficialReceiptReportDataSource(
                    "Official Receipt",
                    [Int64[]]@([Int64]$doc.CBKey)
                )
            ) "Official receipt"
            Ensure-CompanyProfileTable $dataSet $Db
            Ensure-CurrentUserTable $dataSet $Session
            $databaseReport = Get-DatabaseReportTemplate $Db "Official Receipt"
            $reportFile = "OR - Letter.art"
            $reportBytes = $null
            $reportName = $reportFile
            if ($null -ne $databaseReport) {
                $reportFile = $null
                $reportBytes = $databaseReport.reportBytes
                $reportName = $databaseReport.reportName
            }

            return @{
                dataSet = $dataSet
                docNo = [string]$doc.DocNo
                reportFile = $reportFile
                reportBytes = $reportBytes
                reportName = $reportName
                reportType = "Official Receipt"
            }
        }
        "debtors" {
            $invoiceCmd = [AutoCount.ARAP.ARInvoice.ARInvoiceDataAccess]::Create($Session, $Db)
            $debtor = $invoiceCmd.GetDebtorData($Key, [DateTime]::Today)
            if ($null -eq $debtor) {
                Write-JsonResult @{ error = "Debtor not found: $Key" } 1
            }

            $criteria = [AutoCount.ARAP.DebtorStatement.DebtorStatementCriteria]::new()
            if ($null -eq $criteria.DebtorFilter) {
                $criteria.DebtorFilter = [AutoCount.SearchFilter.ReportFilter]::new()
            }
            $criteria.DebtorFilter.ByOne($Key)
            $criteria.FromDate = [DateTime]::Today.AddMonths(-12).Date
            $criteria.ToDate = [DateTime]::Today.Date
            $criteria.StatementType = [AutoCount.ARAP.DebtorStatementStringID]::DebtorDefault
            $criteria.IsNormalStatement = $true
            $criteria.IsIncludeZeroAmountTransaction = $false
            $criteria.ShowGroupCompany = $false
            $criteria.ShowSubCompany = $false
            $criteria.ShowInLocalCurrency = $false
            $criteria.ShowPaidTransaction = $true
            $criteria.ZeroBalanceMethod = [AutoCount.ARAP.StatementZeroBalanceOption]::IncludeWithActiveTransactionOnly

            $statement = [AutoCount.ARAP.DebtorStatement.DebtorStatement]::Create($Session)
            $statement.Inquire($criteria) | Out-Null
            $dataSet = Convert-ToReportDataSet ($statement.GetReportDataSource()) "Debtor statement"
            Ensure-CompanyProfileTable $dataSet $Db
            Ensure-CurrentUserTable $dataSet $Session

            return @{
                dataSet = $dataSet
                docNo = [string]$Key
                reportFile = "Debtor Statement - 12 Months.art"
                reportType = "Statement of Account"
            }
        }
        "quotations" {
            $cmd = [AutoCount.Invoicing.Sales.Quotation.QuotationCommand]::Create($Session, $Db)
            $docKey = Resolve-DocKey $cmd $Key
            if ($docKey -le 0) {
                Write-JsonResult @{ error = "Quotation not found: $Key" } 1
            }

            $doc = $cmd.Edit($docKey)
            $dataSet = Get-DocumentDataSet $doc "Quotation"
            Prepare-InvoicingReportDataSet $dataSet $Session $Db | Out-Null
            Invoke-DocumentReportControl $Session $dataSet "Quotation Document"
            Set-GeneratedDetailColumns $dataSet.Tables["Detail"]
            Set-GeneratedDetailColumns $dataSet.Tables["PackageDetail"]

            return @{
                dataSet = $dataSet
                docNo = [string]$doc.DocNo
                reportFile = "Quotation.art"
                reportType = "Quotation Document"
            }
        }
        "purchase-orders" {
            $cmd = [AutoCount.Invoicing.Purchase.PurchaseOrder.PurchaseOrderCommand]::Create($Session, $Db)
            $docKey = Resolve-DocKey $cmd $Key
            if ($docKey -le 0) {
                Write-JsonResult @{ error = "Purchase order not found: $Key" } 1
            }

            $doc = $cmd.Edit($docKey)
            $dataSet = Get-DocumentDataSet $doc "Purchase order"
            Prepare-InvoicingReportDataSet $dataSet $Session $Db | Out-Null
            Invoke-DocumentReportControl $Session $dataSet "Purchase Order Document"
            Set-GeneratedDetailColumns $dataSet.Tables["Detail"]
            Set-GeneratedDetailColumns $dataSet.Tables["PackageDetail"]

            return @{
                dataSet = $dataSet
                docNo = [string]$doc.DocNo
                reportFile = "Purchase Order.art"
                reportType = "Purchase Order Document"
            }
        }
        default {
            Write-JsonResult @{ error = "PDF export is not supported for resource: $Resource" } 1
        }
    }
}

function Export-Pdf($ReportFile, $Payload, $Session, $OutputPath) {
    if ($null -ne $Payload.reportBytes) {
        $stream = [System.IO.MemoryStream]::new([byte[]]$Payload.reportBytes)
        try {
            $template = [AutoCount.Report.ReportTemplateUtil]::LoadReportStream(
                $stream,
                [AutoCount.Report.BaseReport],
                $Payload.dataSet
            )
        } finally {
            $stream.Dispose()
        }
    } else {
        $template = [AutoCount.Report.ReportTemplateUtil]::LoadReportFile(
            $ReportFile,
            [AutoCount.Report.BaseReport],
            $Payload.dataSet
        )
    }
    $report = $template.Report
    $report.DataSource = $Payload.dataSet

    $setSession = $report.GetType().GetMethod(
        "SetUserSession",
        [System.Reflection.BindingFlags] "Instance,Public,NonPublic"
    )
    if ($null -ne $setSession) {
        $setSession.Invoke($report, @($Session)) | Out-Null
    }

    if ($Payload.addPaymentSummary) {
        Add-InvoicePaymentSummary $report $Payload.dataSet $Payload.requestAmount
    }

    Apply-ReportTextFormats $report $Payload.dataSet

    $report.CreateDocument()
    $report.ExportToPdf($OutputPath)
}

try {
    if ([string]::IsNullOrWhiteSpace($Resource)) {
        Write-JsonResult @{ error = "Resource is required." } 1
    }
    if ([string]::IsNullOrWhiteSpace($Key)) {
        Write-JsonResult @{ error = "Document key is required." } 1
    }

    $installDir = Load-AutoCountAssemblies
    $login = New-AutoCountSession
    $db = $login[0]
    $session = $login[1]
    $payload = Get-ReportPayload $Resource $Key $db $session
    $reportFile = $null
    if ($null -ne $payload.reportFile) {
        $reportFile = Expand-SystemReport $installDir $payload.reportFile
    }

    if ([string]::IsNullOrWhiteSpace($OutputPath)) {
        $exportDir = "C:\ProgramData\WSLGuard\ERPExports"
        New-Item -ItemType Directory -Force -Path $exportDir | Out-Null
        $OutputPath = Join-Path $exportDir ("{0}-{1}.pdf" -f $Resource, [Guid]::NewGuid().ToString("N"))
    } else {
        New-Item -ItemType Directory -Force -Path (Split-Path $OutputPath -Parent) | Out-Null
    }

    Export-Pdf $reportFile $payload $session $OutputPath

    $safeDocNo = Convert-SafeFilePart $payload.docNo
    $filename = "{0}-{1}.pdf" -f $Resource, $safeDocNo
    Write-JsonResult @{
        ok = $true
        path = $OutputPath
        filename = $filename
        docNo = $payload.docNo
        reportFile = $payload.reportFile
        reportName = $payload.reportName
        reportType = $payload.reportType
        size = (Get-Item $OutputPath).Length
    }
} catch {
    $errorPayload = @{
        ok = $false
        error = $_.Exception.Message
    }
    if ($env:ERP_PDF_DEBUG -eq "1") {
        $errorPayload.position = $_.InvocationInfo.PositionMessage
        $errorPayload.stack = $_.ScriptStackTrace
    }
    Write-JsonResult $errorPayload 1
}
