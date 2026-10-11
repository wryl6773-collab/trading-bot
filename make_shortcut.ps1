# יוצר בשולחן העבודה קיצור "בוט מסחר" עם אייקון, ומעביר לתיקייה את הקובץ הישן (בלי למחוק)
param([string]$Folder)
$Folder = $Folder.TrimEnd('\')
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut((Join-Path $desktop 'בוט מסחר.lnk'))
$lnk.TargetPath = 'wscript.exe'
$lnk.Arguments = '"' + (Join-Path $Folder 'start_bot.vbs') + '"'
$lnk.WorkingDirectory = $Folder
$lnk.IconLocation = (Join-Path $Folder 'bot_icon.ico')
$lnk.Description = 'בוט מסחר וירטואלי - כסף דמיוני בלבד'
$lnk.Save()
$old = Join-Path $desktop 'start_bot.bat'
if (Test-Path $old) {
    $dest = Join-Path $Folder 'old_launchers'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Move-Item -Force $old (Join-Path $dest 'start_bot_desktop_old.bat')
}
Write-Output 'OK'
