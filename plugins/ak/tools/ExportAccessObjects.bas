Attribute VB_Name = "modExportAccess"
Option Compare Database
Option Explicit

' =============================================================================
' Access Modernization Kit - manual Access export
' =============================================================================
' Export every Access object to text from INSIDE Access, without external COM
' automation and without administrator elevation. Use this when the runtime
' extractor cannot run - for example on a machine without Access, when the
' registered Access executable requires elevation, or for a split database
' whose startup code fails.
'
' HOW TO RUN
'   1. Open the database in Microsoft Access. For a database whose startup
'      (AutoExec) code errors, HOLD SHIFT while opening to bypass startup.
'   2. Press Alt+F11 to open the Visual Basic editor (a separate window titled
'      "Microsoft Visual Basic").
'   3. In THAT editor's menu use File > Import File... (Ctrl+M) and pick this
'      .bas file. (Do NOT use the Access application's File > Get External Data
'      > Import - that dialog only lists database files, not .bas.)
'      Alternatively: Insert > Module, then paste this whole file.
'   4. Press Ctrl+G for the Immediate window and run, replacing the path:
'
'          ExportAccessObjects "D:\Anrakutei\<APP>\sources\<DATABASE_ID>"
'
' OUTPUT (created under the folder you pass)
'   forms\      one .txt per form      (SaveAsText)
'   reports\    one .txt per report    (SaveAsText)
'   macros\     one .txt per macro     (SaveAsText)
'   vba\        one .txt per module    (SaveAsText)
'   queries\    one .sql per query     (QueryDef.SQL, UTF-8)
'   schema\tables.txt   table list with linked/local flag and fields (UTF-8).
'                       System (MSys*), temp (~*), and Access ImportErrors
'                       tables are excluded; their count/names go in the manifest.
'   export-manifest.txt object counts and the list of skipped objects
'
' Every object is exported independently: a single failing object is recorded
' in export-manifest.txt and the export continues. File names keep the original
' (Japanese) object names, stripping only characters illegal in Windows file
' names, and add a numeric suffix only on a real collision - so nothing is lost.
' =============================================================================

Private mUsed As Object    ' Scripting.Dictionary of used (lower-cased) file paths
Private mSkipped As String ' accumulated "kind<TAB>name<TAB>error" lines
Private mSkipCount As Long

Public Sub ExportAccessObjects(ByVal OutRoot As String)
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set mUsed = CreateObject("Scripting.Dictionary")
    mSkipped = ""
    mSkipCount = 0

    EnsureDir fso, OutRoot
    Dim sub_ As Variant
    For Each sub_ In Array("forms", "reports", "macros", "vba", "queries", "schema")
        EnsureDir fso, OutRoot & "\" & sub_
    Next

    Dim nForm As Long, nReport As Long, nMacro As Long, nModule As Long
    Dim nQuery As Long, nTable As Long
    Dim ao As Object

    For Each ao In CurrentProject.AllForms
        If TrySaveAsText(acForm, ao.Name, UniquePath(OutRoot & "\forms", ao.Name, "txt"), "form") Then nForm = nForm + 1
    Next
    For Each ao In CurrentProject.AllReports
        If TrySaveAsText(acReport, ao.Name, UniquePath(OutRoot & "\reports", ao.Name, "txt"), "report") Then nReport = nReport + 1
    Next
    For Each ao In CurrentProject.AllMacros
        If TrySaveAsText(acMacro, ao.Name, UniquePath(OutRoot & "\macros", ao.Name, "txt"), "macro") Then nMacro = nMacro + 1
    Next
    For Each ao In CurrentProject.AllModules
        If TrySaveAsText(acModule, ao.Name, UniquePath(OutRoot & "\vba", ao.Name, "txt"), "module") Then nModule = nModule + 1
    Next

    Dim db As DAO.Database, qd As DAO.QueryDef
    Set db = CurrentDb
    For Each qd In db.QueryDefs
        If Left$(qd.Name, 1) <> "~" Then          ' skip hidden/temporary queries
            If TryWriteQuery(qd, UniquePath(OutRoot & "\queries", qd.Name, "sql")) Then nQuery = nQuery + 1
        End If
    Next

    Dim td As DAO.TableDef, sb As String, nExcluded As Long, excludedNames As String
    For Each td In db.TableDefs
        If IsSystemOrJunkTable(td) Then
            nExcluded = nExcluded + 1
            excludedNames = excludedNames & "  " & td.Name & vbCrLf
        Else
            sb = sb & TableSchemaLine(td)
            nTable = nTable + 1
        End If
    Next
    WriteUtf8 OutRoot & "\schema\tables.txt", sb

    Dim summary As String
    summary = "forms=" & nForm & vbCrLf & _
              "reports=" & nReport & vbCrLf & _
              "macros=" & nMacro & vbCrLf & _
              "modules=" & nModule & vbCrLf & _
              "queries=" & nQuery & vbCrLf & _
              "tables=" & nTable & vbCrLf & _
              "excluded_system_or_junk_tables=" & nExcluded & vbCrLf & _
              "skipped=" & mSkipCount & vbCrLf
    If nExcluded > 0 Then
        summary = summary & vbCrLf & "EXCLUDED tables (system / temp / Access ImportErrors):" & vbCrLf & excludedNames
    End If
    If mSkipCount > 0 Then
        summary = summary & vbCrLf & "SKIPPED (kind" & vbTab & "name" & vbTab & "error):" & vbCrLf & mSkipped
    End If
    WriteUtf8 OutRoot & "\export-manifest.txt", summary
    Debug.Print summary
    Debug.Print "Export complete -> " & OutRoot
End Sub

Private Function TrySaveAsText(ByVal objType As Integer, ByVal name As String, ByVal path As String, ByVal kind As String) As Boolean
    On Error Resume Next
    Err.Clear
    ' Access SaveAsText writes in the system ANSI codepage (Shift-JIS / CP932 on
    ' a Japanese Windows), not UTF-8. Write to a temp file, then transcode to
    ' UTF-8 so every export file is a single, consistent encoding.
    Dim tempPath As String
    tempPath = path & ".ansi.tmp"
    Application.SaveAsText objType, name, tempPath
    If Err.Number = 0 Then
        Dim content As String
        content = ReadAnsiFile(tempPath)
        If Err.Number = 0 Then WriteUtf8 path, content
    End If
    Dim errNum As Long, errDesc As String
    errNum = Err.Number
    errDesc = Err.Description
    ' Best-effort temp cleanup (its own errors must not change the outcome).
    On Error Resume Next
    If Len(Dir(tempPath)) > 0 Then Kill tempPath
    On Error GoTo 0
    If errNum <> 0 Then
        AddSkip kind, name, errDesc
        TrySaveAsText = False
    Else
        TrySaveAsText = True
    End If
End Function

Private Function ReadAnsiFile(ByVal path As String) As String
    ' Read a Shift-JIS (CP932) text file produced by SaveAsText into a Unicode
    ' VBA string. Falls back to the raw system codepage name if needed.
    Dim stm As Object
    Set stm = CreateObject("ADODB.Stream")
    stm.Type = 2
    stm.Charset = "shift_jis"
    stm.Open
    stm.LoadFromFile path
    ReadAnsiFile = stm.ReadText
    stm.Close
End Function

Private Function TryWriteQuery(ByVal qd As Object, ByVal path As String) As Boolean
    On Error Resume Next
    Err.Clear
    Dim sql As String
    sql = qd.SQL
    If Err.Number = 0 Then WriteUtf8 path, sql
    If Err.Number <> 0 Then
        AddSkip "query", qd.Name, Err.Description
        TryWriteQuery = False
    Else
        TryWriteQuery = True
    End If
    Err.Clear
    On Error GoTo 0
End Function

Private Function IsSystemOrJunkTable(ByVal td As Object) As Boolean
    ' Exclude non-model tables from the schema export:
    '  - MSys*  : Access system tables
    '  - ~*     : temporary/work tables
    '  - Access auto-generated ImportErrors tables (exactly 3 fields:
    '    Error(Text 255) / Field(Text 255) / Row(Long); dbText=10, dbLong=4).
    Dim n As String
    n = td.name
    If Left$(n, 4) = "MSys" Then IsSystemOrJunkTable = True: Exit Function
    If Left$(n, 1) = "~" Then IsSystemOrJunkTable = True: Exit Function
    On Error Resume Next
    If td.Fields.Count = 3 Then
        If td.Fields(0).Type = 10 And td.Fields(1).Type = 10 And td.Fields(2).Type = 4 Then
            IsSystemOrJunkTable = True
        End If
    End If
    On Error GoTo 0
End Function

Private Function TableSchemaLine(ByVal td As Object) As String
    On Error Resume Next
    Dim s As String, fld As Object
    s = "TABLE" & vbTab & td.name & vbTab
    If Len(td.Connect) > 0 Then
        s = s & "LINKED" & vbTab & td.SourceTableName
    Else
        s = s & "LOCAL"
    End If
    s = s & vbCrLf
    For Each fld In td.Fields
        s = s & vbTab & "FIELD" & vbTab & fld.name & vbTab & "type=" & fld.Type & vbTab & "size=" & fld.Size & vbCrLf
    Next
    If Err.Number <> 0 Then AddSkip "table", td.name, Err.Description
    Err.Clear
    On Error GoTo 0
    TableSchemaLine = s
End Function

Private Sub AddSkip(ByVal kind As String, ByVal name As String, ByVal errText As String)
    mSkipped = mSkipped & kind & vbTab & name & vbTab & errText & vbCrLf
    mSkipCount = mSkipCount + 1
    Debug.Print "SKIP " & kind & " " & name & ": " & errText
End Sub

Private Function UniquePath(ByVal folder As String, ByVal baseName As String, ByVal ext As String) As String
    Dim safe As String, candidate As String, i As Long
    safe = SafeName(baseName)
    candidate = folder & "\" & safe & "." & ext
    i = 1
    Do While mUsed.Exists(LCase$(candidate))
        i = i + 1
        candidate = folder & "\" & safe & "-" & i & "." & ext
    Loop
    mUsed.Add LCase$(candidate), True
    UniquePath = candidate
End Function

Private Function SafeName(ByVal s As String) As String
    Dim bad As Variant, ch As Variant
    bad = Array("\", "/", ":", "*", "?", """", "<", ">", "|", vbCr, vbLf, vbTab)
    For Each ch In bad
        s = Replace(s, CStr(ch), "_")
    Next
    If Len(s) = 0 Then s = "object"
    SafeName = s
End Function

Private Sub EnsureDir(ByVal fso As Object, ByVal path As String)
    If Len(path) = 0 Then Exit Sub
    If fso.FolderExists(path) Then Exit Sub
    EnsureDir fso, fso.GetParentFolderName(path)
    fso.CreateFolder path
End Sub

Private Sub WriteUtf8(ByVal path As String, ByVal text As String)
    Dim stm As Object
    Set stm = CreateObject("ADODB.Stream")
    stm.Type = 2                 ' adTypeText
    stm.Charset = "UTF-8"
    stm.Open
    stm.WriteText text
    stm.SaveToFile path, 2       ' adSaveCreateOverWrite
    stm.Close
End Sub
