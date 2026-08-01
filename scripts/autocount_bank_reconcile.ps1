param(
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

public static class AutoCountBankReconAssemblyResolver
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
    [AutoCountBankReconAssemblyResolver]::Register($installDir)

    foreach ($dll in @(
        "AutoCount.dll",
        "AutoCount.Accounting.dll",
        "AutoCount.ARAP.dll",
        "AutoCount.GL.dll",
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
        if (Test-Path $dll) {
            [Reflection.Assembly]::LoadFrom((Resolve-Path $dll)) | Out-Null
        }
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

function Require-Text($Object, [string]$Name, [string]$Label) {
    $value = Get-Prop $Object $Name $null
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
        Write-JsonResult @{ error = "$Label is required." } 1
    }
    return [string]$value
}

function Require-Decimal($Object, [string]$Name, [string]$Label) {
    $value = Get-Prop $Object $Name $null
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
        Write-JsonResult @{ error = "$Label is required." } 1
    }
    return [decimal]$value
}

function Require-Date($Object, [string]$Name, [string]$Label) {
    $value = Get-Prop $Object $Name $null
    if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
        Write-JsonResult @{ error = "$Label is required." } 1
    }
    return [DateTime]::Parse([string]$value)
}

try {
    if ([string]::IsNullOrWhiteSpace($PayloadJson)) {
        Write-JsonResult @{ error = "Payload JSON is required." } 1
    }

    $payload = $PayloadJson | ConvertFrom-Json
    $bankAccount = Require-Text $payload "bankAccount" "Bank account"
    $statementDate = Require-Date $payload "statementDate" "Statement date"
    $actualBalance = Require-Decimal $payload "actualBankStatementBalance" "Actual bank statement balance"
    $rawKeys = @(Get-Prop $payload "bankTransKeys" @())

    $targetKeys = @{}
    foreach ($rawKey in $rawKeys) {
        $key = [string]$rawKey
        if (-not [string]::IsNullOrWhiteSpace($key)) {
            $targetKeys[$key.Trim()] = $true
        }
    }
    if ($targetKeys.Count -eq 0) {
        Write-JsonResult @{ error = "At least one bank transaction is required." } 1
    }

    Load-AutoCountAssemblies
    $login = New-AutoCountSession
    $db = $login[0]
    $session = $login[1]

    $cmd = [AutoCount.GL.BankRecon.BankReconCommand]::Create($session, $db)
    $existingStatement = $cmd.IsBankStatementExist($bankAccount, $statementDate)
    if ($existingStatement) {
        $doc = $cmd.Edit($bankAccount, $statementDate)
    } else {
        $doc = $cmd.AddNew($bankAccount, $statementDate)
    }

    $matchedRows = @()
    foreach ($row in $doc.DataTableDetail.Rows) {
        $bankTransKey = [string](Convert-DbValue $row["BankTransKey"])
        if ($targetKeys.ContainsKey($bankTransKey)) {
            $row["Tick"] = "T"
            $matchedRows += @{
                bankTransKey = Convert-DbValue $row["BankTransKey"]
                docNo = Convert-DbValue $row["DocNo"]
                docDate = Convert-DbValue $row["DocDate"]
                bankAccount = Convert-DbValue $row["AccNo"]
                paymentAmt = Convert-DbValue $row["PaymentAmt"]
            }
        }
    }

    if ($matchedRows.Count -ne $targetKeys.Count) {
        $matchedKeySet = @{}
        foreach ($matched in $matchedRows) {
            $matchedKeySet[[string]$matched.bankTransKey] = $true
        }
        $missing = @()
        foreach ($key in $targetKeys.Keys) {
            if (-not $matchedKeySet.ContainsKey($key)) {
                $missing += $key
            }
        }
        Write-JsonResult @{
            error = "Some bank transactions are not available for this statement."
            missingKeys = $missing
        } 1
    }

    $doc.Save($actualBalance, $true)

    Write-JsonResult @{
        ok = $true
        resource = "bank-transactions"
        action = "reconcile"
        bankAccount = $bankAccount
        statementDate = $statementDate.ToString("yyyy-MM-dd")
        actualBankStatementBalance = Convert-DbValue $actualBalance
        existingStatement = $existingStatement
        matchedCount = $matchedRows.Count
        rows = $matchedRows
    }
} catch {
    Write-JsonResult @{
        error = $_.Exception.Message
    } 1
}
