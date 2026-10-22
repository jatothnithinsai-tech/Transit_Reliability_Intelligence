param([int]$Port = 0, [switch]$UseQueryDefinitions)
$ErrorActionPreference = 'Stop'
$powerbiRoot = Split-Path -Parent $PSScriptRoot
$pbiProcess = Get-Process PBIDesktop -ErrorAction SilentlyContinue | Where-Object { $_.Path } | Select-Object -First 1
if ($pbiProcess) { $pbiBin = Split-Path -Parent $pbiProcess.Path }
else { throw 'Power BI Desktop must be installed and running to locate its TOM libraries.' }
Add-Type -Path (Join-Path $pbiBin 'Microsoft.PowerBI.Tabular.dll')
$modelPath = Join-Path $powerbiRoot 'Transit_Reliability_Intelligence.SemanticModel\definition'
$database = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($modelPath)
$measureCount = 0
foreach ($table in $database.Model.Tables) { $measureCount += $table.Measures.Count }
$relationships = @($database.Model.Relationships | ForEach-Object {
    [ordered]@{ name=$_.Name; from=$_.FromTable.Name + '[' + $_.FromColumn.Name + ']'; to=$_.ToTable.Name + '[' + $_.ToColumn.Name + ']'; fromCardinality=$_.FromCardinality.ToString(); toCardinality=$_.ToCardinality.ToString(); crossFiltering=$_.CrossFilteringBehavior.ToString(); active=$_.IsActive }
})
if (@($relationships | Where-Object { $_.active -and $_.crossFiltering -eq 'BothDirections' }).Count -ne 0) { throw 'An active bidirectional relationship remains.' }
$result = [ordered]@{ tmdlParsed=$true; tables=$database.Model.Tables.Count; measures=$measureCount; relationships=$relationships; liveDaxValidated=$false }
if ($Port -gt 0) {
    Add-Type -Path (Join-Path $pbiBin 'Microsoft.PowerBI.AdomdClient.dll')
    $connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection
    $connection.ConnectionString = "Data Source=localhost:$Port;Application Name=Transit Reliability Report Validation"
    $connection.Open()
    try {
        $prefix = ''
        if ($UseQueryDefinitions) { $prefix = [System.IO.File]::ReadAllText((Join-Path $powerbiRoot 'validation\measure_definitions.dax')) }
        $queries = [ordered]@{
            global = 'EVALUATE ROW("Lines", [Total Tube Lines], "Snapshots", [Total Historical Snapshots], "GoodServicePct", [Observed Good Service %], "DisruptionPct", [Observed Disruption %], "Context", [Observation Context])'
            byLine = 'EVALUATE SUMMARIZECOLUMNS(Dim_Tube_Lines[line_name], "LineGoodPct", [Line Observed Good Service %], "LineSnapshots", [Line Snapshots Observed], "Major", [Major Disruption Snapshots], "Severe", [Severe Delay Snapshots], "ClosureSuspension", [Closure or Suspension Snapshots], "Planned", [Planned Closure Snapshots], "GlobalLines", [Total Tube Lines], "GlobalSnapshots", [Total Historical Snapshots], "GlobalGoodPct", [Observed Good Service %], "GlobalDisruptionPct", [Observed Disruption %]) ORDER BY Dim_Tube_Lines[line_name]'
            daily = 'EVALUATE SUMMARIZECOLUMNS(''analytics vw_daily_disruption_trends''[observation_date], "DisruptionPct", [Daily Observed Disruption %], "CollectionTimes", [Daily Collection Times], "LineObservations", [Daily Line Observations]) ORDER BY ''analytics vw_daily_disruption_trends''[observation_date]'
            status = 'EVALUATE SUMMARIZECOLUMNS(''analytics vw_disruption_severity''[status_description], "Records", [Status Record Count], "SharePct", [Status Record Share %], "Color", [Status Record Color]) ORDER BY [Records] DESC'
        }
        $data = [ordered]@{}
        foreach ($entry in $queries.GetEnumerator()) {
            $command = $connection.CreateCommand()
            $command.CommandText = $prefix + "`n" + $entry.Value
            $reader = $command.ExecuteReader()
            $rows = @()
            try {
                while ($reader.Read()) {
                    $row = [ordered]@{}
                    for ($i=0; $i -lt $reader.FieldCount; $i++) {
                        $value = $reader.GetValue($i)
                        if ($value -is [DBNull]) { $value = $null }
                        elseif ($value -is [DateTime]) { $value = $value.ToString('yyyy-MM-dd HH:mm:ss') }
                        $row[$reader.GetName($i)] = $value
                    }
                    $rows += $row
                }
            } finally { $reader.Close() }
            $data[$entry.Key] = $rows
        }
        $result.liveDaxValidated = $true
        $result['queryDefinitionsUsed'] = [bool]$UseQueryDefinitions
        $result['data'] = $data
        if ($data.byLine.Count -ne 11) { throw 'Expected all 11 Tube lines.' }
        $global = $data.global[0]
        foreach ($row in $data.byLine) {
            if ($row['[GlobalLines]'] -ne $global['[Lines]'] -or $row['[GlobalSnapshots]'] -ne $global['[Snapshots]'] -or $row['[GlobalGoodPct]'] -ne $global['[GoodServicePct]'] -or $row['[GlobalDisruptionPct]'] -ne $global['[DisruptionPct]']) { throw 'A global KPI changes with line context.' }
        }
    } finally { $connection.Close() }
}
$outputPath = Join-Path $powerbiRoot 'validation\model_validation.json'
$result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $outputPath -Encoding UTF8
Write-Output ('TMDL parsed: ' + $result.tables + ' tables, ' + $result.measures + ' measures. Live DAX validated: ' + $result.liveDaxValidated)
if ($result.liveDaxValidated) { $result.data.global | ConvertTo-Json -Depth 5 }
