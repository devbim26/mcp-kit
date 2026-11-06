# Регистрация задач Планировщика Windows по разрешённому описанию.
# Общий движок каркаса mcp_kit: используется всеми проектами.
#
# Описание готовит Python (`mcp_kit.ops.build_task_specs`): сюда приходят
# уже собранные команды, а PowerShell только регистрирует их. Иначе
# правила формирования команд разъезжаются между двумя языками.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File register_tasks.ps1 `
#       -Spec <путь к resolved.json> -Action Install|Uninstall|Status
#
# Настройки задач (одинаковые для всех):
#   триггер — вход в систему; RestartOnFailure — 3 попытки по 1 минуте;
#   ExecutionTimeLimit — TimeSpan.Zero (снять дефолтные 72 часа);
#   MultipleInstances — IgnoreNew (запрет дублей); StartWhenAvailable — true;
#   учётная запись — текущий пользователь, LogonType Interactive
#   (пароль в Планировщик не пишется).
#
# В PS 5.1 имя `$spec` для переменной-результата ConvertFrom-Json приводит
# к тому, что командлет возвращает исходную строку, а не PSCustomObject
# (баг привязки параметров в скриптовом контексте). Поэтому используем
# `$cfg`.
param(
    [Parameter(Mandatory = $true)][string]$Spec,
    [ValidateSet('Install', 'Uninstall', 'Status')][string]$Action = 'Install'
)

$ErrorActionPreference = 'Stop'
$specPath = (Resolve-Path -LiteralPath $Spec).Path
$raw = Get-Content -LiteralPath $specPath -Raw -Encoding UTF8
$cfg = $raw | ConvertFrom-Json
$root = $cfg.root
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

function Stop-TaskProcess {
    param([string]$Name)
    $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($task) { Stop-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue }
}

# Дубли туннелей: один туннель — один процесс. Ищем по config+tunnel в
# командной строке; остановка нужна, чтобы задача подняла свой экземпляр.
if ($Action -eq 'Install') {
    foreach ($task in $cfg.tasks) {
        if (-not $task.dedupe) { continue }
        $pattern = '*' + $task.dedupe.config + '*' + $task.dedupe.tunnel + '*'
        $dupes = Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like $pattern }
        foreach ($dup in $dupes) {
            Write-Host "    останавливаем дубль туннеля PID $($dup.ProcessId)"
            Stop-Process -Id $dup.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }

    # Порты освобождаем до регистрации: иначе новая задача не займёт порт.
    foreach ($port in $cfg.ports) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $conns) {
            Write-Host "    освобождаем порт ${port}: останавливаем PID $($conn.OwningProcess)"
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

foreach ($task in $cfg.tasks) {
    $name = $task.name
    $delay = [int]$task.delay_seconds

    Write-Host "[$Action] $name : $($task.arguments)"

    if ($Action -eq 'Status') {
        $registered = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($registered) {
            $info = Get-ScheduledTaskInfo -TaskName $name
            Write-Host ("    состояние={0} последний результат={1} последний запуск={2}" -f $registered.State, $info.LastTaskResult, $info.LastRunTime)
        }
        else {
            Write-Host '    задача не зарегистрирована'
        }
        continue
    }

    if ($Action -eq 'Uninstall') {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        Stop-TaskProcess -Name $name
        continue
    }

    # Install: снять старую, зарегистрировать, запустить
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    Stop-TaskProcess -Name $name

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $task.log) | Out-Null

    $actionDef = New-ScheduledTaskAction -Execute $task.execute -Argument $task.arguments -WorkingDirectory $task.working_dir
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    if ($delay -gt 0) { $trigger.Delay = "PT${delay}S" }
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -StartWhenAvailable

    Register-ScheduledTask -TaskName $name -Action $actionDef -Trigger $trigger `
        -Principal $principal -Settings $settings -Force | Out-Null

    Start-ScheduledTask -TaskName $name
    Write-Host "    задача зарегистрирована и запущена"
}
