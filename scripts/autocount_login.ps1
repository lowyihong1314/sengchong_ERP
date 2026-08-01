param(
    [string]$SqlServer,
    [string]$SqlUser,
    [string]$SqlPassword,
    [string]$Database,
    [string]$User,
    [string]$Password
)

$ErrorActionPreference = "Stop"

function Write-JsonResult($Payload, [int]$ExitCode = 0) {
    $Payload | ConvertTo-Json -Compress -Depth 8
    exit $ExitCode
}

try {
    $installDir = $env:AUTOCOUNT_INSTALL_DIR
    if ([string]::IsNullOrWhiteSpace($installDir)) {
        $installDir = "C:\Program Files\AutoCount\Accounting 2.2"
    }

    Set-Location $installDir

    foreach ($dll in @(
        "AutoCount.dll",
        "AutoCount.Accounting.dll",
        "AutoCount.ARAP.dll",
        "AutoCount.MainEntry.dll"
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
    $ok = $session.Login($User, $Password)

    if (-not $ok) {
        Write-JsonResult @{
            ok = $false
            error = "Invalid AutoCount username or password."
        } 1
    }

    Write-JsonResult @{
        ok = $true
        user = $session.LoginUserID
        database = $session.DBSetting.DBName
        server = $session.DBSetting.ServerName
    }
} catch {
    Write-JsonResult @{
        ok = $false
        error = $_.Exception.Message
    } 1
}
