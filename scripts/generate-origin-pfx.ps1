#Requires -Version 5.1

<#
.SYNOPSIS
    Converts a Cloudflare Origin Certificate (PEM) into a PFX file for upload
    to Azure Key Vault.

.DESCRIPTION
    Cloudflare issues Origin Certificates as two PEM files: a certificate (.pem)
    and a private key (.key or .pem). Azure Key Vault expects a PKCS#12 / PFX
    bundle that contains both. This script runs `openssl pkcs12` to produce that
    bundle.

    openssl is required. It ships with:
      - Git for Windows (in C:\Program Files\Git\usr\bin\openssl.exe)
      - Windows 10/11 builds that include the OpenSSL component
      - Any manual OpenSSL installation on PATH

    The output PFX is protected by the password you supply. That same password
    must be entered (or supplied programmatically) when uploading to Key Vault.

    UPLOAD COMMAND (after running this script):
      az keyvault secret set `
        --vault-name <your-kv-name> `
        --name cloudflare-origin-cert `
        --file <OutPath> `
        --encoding base64 `
        --content-type application/x-pkcs12

    See docs/RUNBOOK.md section "Custom Domain -- Cloudflare Origin Cert Rotation"
    for the full end-to-end procedure.

.PARAMETER CertPath
    Path to the Cloudflare Origin Certificate PEM file (the public certificate).
    Download this from the Cloudflare dashboard: SSL/TLS > Origin Server >
    Create Certificate > copy the "Certificate" value and save as a .pem file.

.PARAMETER KeyPath
    Path to the private key PEM file that pairs with the certificate.
    Download this from the same Cloudflare dialog as the "Private Key" value.
    Keep this file secure -- it is equivalent to a password.

.PARAMETER OutPath
    Destination path for the generated PFX file (e.g. .\origin.pfx).
    The directory must already exist. If the file already exists, it will be
    overwritten after confirmation unless -Force is specified.

.PARAMETER Password
    Password to protect the PFX. Passed as a SecureString so it is never
    visible in plain text in process listings or transcripts.
    To generate a strong random password in PowerShell:
      $pw = Read-Host -AsSecureString -Prompt "Enter PFX password"

.PARAMETER Force
    Overwrite OutPath without prompting if it already exists.

.EXAMPLE
    # Interactive -- prompts for password securely
    $pw = Read-Host -AsSecureString -Prompt "PFX password"
    .\generate-origin-pfx.ps1 `
        -CertPath .\rslsiege-origin.pem `
        -KeyPath  .\rslsiege-origin.key `
        -OutPath  .\rslsiege-origin.pfx `
        -Password $pw

.EXAMPLE
    # With -Verbose to see each step
    $pw = Read-Host -AsSecureString -Prompt "PFX password"
    .\generate-origin-pfx.ps1 `
        -CertPath .\cert.pem `
        -KeyPath  .\key.pem `
        -OutPath  .\out.pfx `
        -Password $pw `
        -Verbose

.NOTES
    Author : Claude Code (on behalf of cbeaulieu-gt)
    Requires: openssl on PATH (Git for Windows, system OpenSSL, or WSL openssl)

    Security: The PFX password is briefly visible in process listings during
    openssl execution due to command-line argument limitations. Run this script
    on a trusted workstation, not on shared/monitored systems.
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [ValidateScript({
        if (-not (Test-Path -LiteralPath $_ -PathType Leaf)) {
            throw "CertPath '$_' does not exist or is not a file."
        }
        $true
    })]
    [string]$CertPath,

    [Parameter(Mandatory)]
    [ValidateScript({
        if (-not (Test-Path -LiteralPath $_ -PathType Leaf)) {
            throw "KeyPath '$_' does not exist or is not a file."
        }
        $true
    })]
    [string]$KeyPath,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$OutPath,

    [Parameter(Mandatory)]
    [System.Security.SecureString]$Password,

    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Resolve absolute paths early so openssl receives unambiguous paths ─────────

$certAbsolute = (Resolve-Path -LiteralPath $CertPath).Path
$keyAbsolute  = (Resolve-Path -LiteralPath $KeyPath).Path
$outAbsolute  = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutPath)

Write-Verbose "Cert  : $certAbsolute"
Write-Verbose "Key   : $keyAbsolute"
Write-Verbose "Output: $outAbsolute"

# ── Guard: output file already exists ─────────────────────────────────────────

if (Test-Path -LiteralPath $outAbsolute -PathType Leaf) {
    if (-not $Force) {
        if (-not $PSCmdlet.ShouldProcess($outAbsolute, 'Overwrite existing PFX file')) {
            Write-Warning "Aborted. Use -Force to overwrite without prompting."
            return
        }
    }
    Write-Verbose "Overwriting existing file: $outAbsolute"
}

# ── Locate openssl ─────────────────────────────────────────────────────────────

Write-Verbose "Searching for openssl on PATH..."

$openssl = Get-Command -Name 'openssl' -ErrorAction SilentlyContinue

if (-not $openssl) {
    # Git for Windows ships openssl under its usr\bin directory but may not add
    # it to the system PATH. Try the two most common Git installation locations.
    $gitPaths = @(
        'C:\Program Files\Git\usr\bin\openssl.exe'
        'C:\Program Files (x86)\Git\usr\bin\openssl.exe'
    )
    foreach ($candidate in $gitPaths) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            Write-Verbose "Found openssl via Git for Windows: $candidate"
            $openssl = [PSCustomObject]@{ Source = $candidate }
            break
        }
    }
}

if (-not $openssl) {
    throw (
        "openssl was not found on PATH and is not present at the default " +
        "Git for Windows locations. Install Git for Windows or add an " +
        "OpenSSL installation directory to your PATH, then retry."
    )
}

$opensslExe = $openssl.Source
Write-Verbose "Using openssl: $opensslExe"

# ── Convert SecureString password to plain text for openssl argument ───────────
# openssl pkcs12 requires the password as a plain-text argument. The plain text
# string is kept in a local variable and discarded as soon as openssl exits; it
# is never written to disk or emitted to any output stream.

$bstr      = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
$plainPass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

# ── Detect whether the openssl legacy provider is available ───────────────────
#
# OpenSSL 3.x splits legacy ciphers (RC2, 3DES, MD4, DES) into a separate
# loadable "legacy" provider module. Git for Windows ships only the "default"
# provider -- the ossl-modules directory does not exist in that install.
# Passing -legacy when the module is absent causes a hard failure:
#   "pkcs12: unable to load provider legacy"
#
# We probe at runtime: `openssl list -providers` only lists providers that are
# actually loadable. If the output contains a line with "legacy" we know the
# module is present and include -legacy to produce a maximally compatible PFX.
# Otherwise we omit it; OpenSSL 3.x will then use AES-256-CBC, which Azure Key
# Vault accepts without issue.

$providerOutput = & $opensslExe list -providers 2>&1
$hasLegacyProvider = @($providerOutput | Where-Object { $_ -match 'legacy' }).Count -gt 0
Write-Verbose "Legacy provider available: $hasLegacyProvider"

# ── Run openssl pkcs12 ────────────────────────────────────────────────────────
#
# Flags explained:
#   export          -- create a PFX (export mode, as opposed to parse/inspect)
#   -in             -- the certificate PEM file
#   -inkey          -- the private key PEM file
#   -out            -- output PFX path
#   -passout pass:  -- password for the output PFX (plain text passed inline)
#   -passin pass:   -- password to decrypt the input key (empty = unencrypted)
#   -name           -- friendly name embedded in the PFX (informational only)
#   -legacy         -- included only when the legacy provider module is present;
#                      produces RC2/3DES encryption for broadest consumer compat.
#                      Omitted on Git-for-Windows openssl (default provider only),
#                      where AES-256-CBC output is generated instead.

Write-Verbose "Building PFX with openssl pkcs12 -export..."

$opensslArgs = @(
    'pkcs12'
    '-export'
    '-in',      $certAbsolute
    '-inkey',   $keyAbsolute
    '-out',     $outAbsolute
    '-passout', "pass:$plainPass"
    '-passin',  'pass:'
    '-name',    'cloudflare-origin-cert'
)

if ($hasLegacyProvider) {
    $opensslArgs += '-legacy'
}

try {
    $result = & $opensslExe @opensslArgs 2>&1
    $exitCode = $LASTEXITCODE
}
finally {
    # Zero out the plain-text password variable regardless of whether the
    # openssl call succeeded.
    $plainPass = $null
    [System.GC]::Collect()
}

if ($exitCode -ne 0) {
    # openssl writes errors to stderr, which PowerShell captures as ErrorRecord
    # objects mixed into $result. Join them for a readable message.
    $detail = ($result | ForEach-Object { $_.ToString() }) -join "`n"
    $hint = ''
    if ($detail -match 'unable to load key|bad decrypt|Error reading key') {
        $hint = "`nHint: The input key may be passphrase-encrypted; this script expects an unencrypted Cloudflare Origin private key."
    }
    throw "openssl pkcs12 failed (exit $exitCode):`n$detail$hint"
}

Write-Verbose "openssl completed successfully."

# ── Verify the output file was created ────────────────────────────────────────

if (-not (Test-Path -LiteralPath $outAbsolute -PathType Leaf)) {
    throw "openssl reported success but the output file was not created: $outAbsolute"
}

$pfxSize = (Get-Item -LiteralPath $outAbsolute).Length
Write-Verbose "PFX written: $outAbsolute ($pfxSize bytes)"

# ── Emit a result object and final instructions ────────────────────────────────

[PSCustomObject]@{
    PfxPath   = $outAbsolute
    SizeBytes = $pfxSize
    NextStep  = "Upload to Key Vault with: az keyvault secret set --vault-name <kv-name> --name cloudflare-origin-cert --file '$outAbsolute' --encoding base64 --content-type application/x-pkcs12"
}

Write-Verbose "Done. Upload the PFX to Key Vault, then run the Infra Deploy workflow with enableCustomDomain=true."
