# Crea un certificado de code-signing AUTOFIRMADO para PROBAR el pipeline de
# firma de CimX. NO sirve para distribución real (SmartScreen seguirá avisando),
# solo valida que la mecánica de firma funciona. Ver SIGNING.md.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\crear-cert-prueba.ps1
#
# Genera el .pfx en tu carpeta de usuario (fuera del repo) y te muestra las
# variables de entorno a definir antes de 'npm run make'.

$ErrorActionPreference = 'Stop'

$pfxPath = Join-Path $env:USERPROFILE 'cimx-test-cert.pfx'
$password = 'cimxtest123'

Write-Host "Creando certificado de prueba (CN=CimX Test Publisher)..." -ForegroundColor Cyan
$cert = New-SelfSignedCertificate -Type CodeSigningCert `
  -Subject 'CN=CimX Test Publisher' `
  -CertStoreLocation 'Cert:\CurrentUser\My' `
  -KeyExportPolicy Exportable -KeySpec Signature -KeyUsage DigitalSignature `
  -FriendlyName 'CimX Test Signing' -NotAfter (Get-Date).AddYears(2)

$secure = ConvertTo-SecureString -String $password -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $secure | Out-Null

# Quitar del almacén: dejamos solo el .pfx exportado.
Remove-Item "Cert:\CurrentUser\My\$($cert.Thumbprint)" -Force

Write-Host ""
Write-Host "Certificado de prueba creado en:" -ForegroundColor Green
Write-Host "  $pfxPath"
Write-Host ""
Write-Host "Para firmar el build con este certificado de prueba:" -ForegroundColor Yellow
Write-Host "  `$env:CIMX_CSC_LINK = '$pfxPath'"
Write-Host "  `$env:CIMX_CSC_KEY_PASSWORD = '$password'"
Write-Host "  npm run make"
Write-Host ""
Write-Host "Recuerda: es autofirmado; NO elimina el aviso de SmartScreen." -ForegroundColor DarkYellow
