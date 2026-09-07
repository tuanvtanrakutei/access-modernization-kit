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
'   ui\controls.json    every control on every form and report: name, type,
'                       caption, ATTACHED LABEL, tooltip, visible, position and
'                       OnClick. Two of those cannot be recovered from the
'                       definition text. Access stores a button's visible text on
'                       a separate label control and records no link between the
'                       two, so reading a button's Name as its caption is a guess;
'                       and a hidden control looks exactly like a live one.
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
            If nTable > 0 Then sb = sb & "," & vbCrLf
            sb = sb & TableSchemaJson(td)
            nTable = nTable + 1
        End If
    Next
    WriteUtf8 OutRoot & "\schema\tables.json", "[" & vbCrLf & sb & vbCrLf & "]" & vbCrLf

    ' The control inventory. A separate pass because it opens each object in
    ' design view - slower, and able to fail per object - and because an operator
    ' may want to re-run only this part after a form changes.
    ExportControlInventory OutRoot

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

Private Function JsonEscape(ByVal s As String) As String
    Dim r As String
    r = Replace$(s, "\", "\\")
    r = Replace$(r, """", "\""")
    r = Replace$(r, vbCr, "\r")
    r = Replace$(r, vbLf, "\n")
    r = Replace$(r, vbTab, "\t")
    JsonEscape = r
End Function

' Emits one record of schema/tables.json, the shape specifications/evidence-layout.yaml
' declares for both routes. The tab-delimited tables.txt this replaced carried no index
' detail and no field flags, so an export could never supply field_inventory or
' key_index_inventory and Phase 1 was reachable only by extracting here.
Private Function TableSchemaJson(ByVal td As Object) As String
    On Error Resume Next
    Dim s As String, fld As Object, idx As Object, ixf As Object
    Dim parts As String, first As Boolean, readErr As String

    s = "  {" & vbCrLf
    s = s & "    ""name"": """ & JsonEscape(td.name) & """," & vbCrLf
    s = s & "    ""source_table_name"": """ & JsonEscape(td.SourceTableName) & """," & vbCrLf
    s = s & "    ""connect"": """ & JsonEscape(RedactConnect(td.Connect)) & """," & vbCrLf
    s = s & "    ""attributes"": " & CStr(td.Attributes) & "," & vbCrLf

    parts = ""
    first = True
    For Each fld In td.Fields
        If Not first Then parts = parts & "," & vbCrLf
        parts = parts & "      {""name"": """ & JsonEscape(fld.name) & """, ""type"": " & CStr(fld.Type) & _
                ", ""size"": " & CStr(fld.Size) & ", ""required"": " & LCase$(CStr(fld.Required)) & "}"
        first = False
    Next
    s = s & "    ""fields"": [" & vbCrLf & parts & vbCrLf & "    ]," & vbCrLf

    parts = ""
    first = True
    For Each idx In td.Indexes
        Dim ixFields As String, ixFirst As Boolean
        ixFields = ""
        ixFirst = True
        For Each ixf In idx.Fields
            If Not ixFirst Then ixFields = ixFields & ", "
            ixFields = ixFields & """" & JsonEscape(ixf.name) & """"
            ixFirst = False
        Next
        If Not first Then parts = parts & "," & vbCrLf
        parts = parts & "      {""name"": """ & JsonEscape(idx.name) & """, ""primary"": " & LCase$(CStr(idx.Primary)) & _
                ", ""unique"": " & LCase$(CStr(idx.Unique)) & ", ""fields"": [" & ixFields & "]}"
        first = False
    Next
    s = s & "    ""indexes"": [" & vbCrLf & parts & vbCrLf & "    ]," & vbCrLf

    ' A table linked to a missing external file throws when its fields are read. Keep
    ' the identity and the link target: an unreachable interface is boundary evidence,
    ' and dropping it would hide the very thing Phase 1 needs.
    If Err.Number <> 0 Then
        readErr = Err.Description
        AddSkip "table", td.name, Err.Description
    End If
    Err.Clear
    s = s & "    ""read_error"": """ & JsonEscape(readErr) & """" & vbCrLf
    s = s & "  }"
    On Error GoTo 0
    TableSchemaJson = s
End Function

' Connection strings can carry credentials. The runtime extractor redacts the same
' keys; an export that did not would put them in a file someone copies around.
Private Function RedactConnect(ByVal value As String) As String
    Dim r As String
    r = value
    If Len(r) = 0 Then
        RedactConnect = ""
        Exit Function
    End If
    r = RedactKey(r, "PWD")
    r = RedactKey(r, "PASSWORD")
    r = RedactKey(r, "UID")
    RedactConnect = r
End Function

Private Function RedactKey(ByVal value As String, ByVal key As String) As String
    Dim upper As String, pos As Long, tail As Long, result As String
    result = value
    upper = UCase$(result)
    pos = InStr(upper, key & "=")
    Do While pos > 0
        tail = InStr(pos, result, ";")
        If tail = 0 Then tail = Len(result) + 1
        result = Left$(result, pos + Len(key)) & "<REDACTED>" & Mid$(result, tail)
        upper = UCase$(result)
        pos = InStr(pos + Len(key) + 10, upper, key & "=")
    Loop
    RedactKey = result
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

' =============================================================================
' Control inventory - the half SaveAsText cannot give you
' =============================================================================
' SaveAsText writes every control's properties, but two things a reader needs
' are not recoverable from that text without guessing:
'
'   The visible label. Access stores a button's caption on a SEPARATE label
'   control, and the definition text does not say which label belongs to which
'   button - only that both exist at certain coordinates. Reading the button's
'   Name as though it were the caption produced three wrong claims in one
'   analysis, including test instructions naming buttons that appear on no tab.
'   A control's attached label is Controls(0) at run time, and that is exact.
'
'   Visible. A control the designer hid is still in the definition text, with
'   nothing to distinguish it from one an operator uses every morning. In the
'   A05 frontend 21 buttons are hidden, 14 of them on the main menu alone -
'   including one this analysis had reported as a live hazard.
'
' Each object is opened in DESIGN view, hidden, read, and closed with acSaveNo.
' Design view does not fire Form_Open or Form_Load, so startup code never runs.
' Nothing is ever saved: the 印刷設定 module in this very application shows what
' opening a report acDesign and closing acSaveYes does to a file.
' =============================================================================
Public Sub ExportControlInventory(ByVal OutRoot As String)
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    EnsureDir fso, OutRoot
    EnsureDir fso, OutRoot & "\ui"

    Dim ao As Object, sb As String, first As Boolean, n As Long, failed As Long
    first = True

    For Each ao In CurrentProject.AllForms
        Dim body As String
        body = ObjectControlsJson(acForm, "form", ao.Name)
        If Len(body) > 0 Then
            If Not first Then sb = sb & "," & vbCrLf
            sb = sb & body
            first = False
            n = n + 1
        Else
            failed = failed + 1
        End If
    Next
    For Each ao In CurrentProject.AllReports
        body = ObjectControlsJson(acReport, "report", ao.Name)
        If Len(body) > 0 Then
            If Not first Then sb = sb & "," & vbCrLf
            sb = sb & body
            first = False
            n = n + 1
        Else
            failed = failed + 1
        End If
    Next

    WriteUtf8 OutRoot & "\ui\controls.json", "[" & vbCrLf & sb & vbCrLf & "]" & vbCrLf
    Debug.Print "Control inventory: " & n & " object(s) read, " & failed & " could not be opened"
    Debug.Print "  -> " & OutRoot & "\ui\controls.json"
End Sub

Private Function ObjectControlsJson(ByVal objType As Integer, ByVal kind As String, _
                                    ByVal objName As String) As String
    On Error GoTo Failed
    Dim obj As Object, ctl As Object, sb As String, first As Boolean

    If objType = acForm Then
        DoCmd.OpenForm objName, acDesign, , , , acHidden
        Set obj = Forms(objName)
    Else
        DoCmd.OpenReport objName, acDesign, , , acHidden
        Set obj = Reports(objName)
    End If

    first = True
    For Each ctl In obj.Controls
        If Not first Then sb = sb & "," & vbCrLf
        sb = sb & ControlJson(ctl)
        first = False
    Next

    If objType = acForm Then
        DoCmd.Close acForm, objName, acSaveNo
    Else
        DoCmd.Close acReport, objName, acSaveNo
    End If

    ObjectControlsJson = "  {" & vbCrLf & _
        "    ""object"": """ & JsonEscape(objName) & """," & vbCrLf & _
        "    ""kind"": """ & kind & """," & vbCrLf & _
        "    ""controls"": [" & vbCrLf & sb & vbCrLf & "    ]" & vbCrLf & "  }"
    Exit Function

Failed:
    ' Close whatever managed to open, save nothing, and record the failure the
    ' same way the rest of this module does: an object that cannot be read is
    ' reported, never silently dropped.
    On Error Resume Next
    If objType = acForm Then
        DoCmd.Close acForm, objName, acSaveNo
    Else
        DoCmd.Close acReport, objName, acSaveNo
    End If
    AddSkip kind & "-controls", objName, Err.Description
    ObjectControlsJson = ""
End Function

Private Function ControlJson(ByVal ctl As Object) As String
    On Error Resume Next
    Dim cap As String, tip As String, onClick As String, vis As String
    Dim lbl As String, sect As String, parentName As String

    cap = "": cap = CStr(ctl.Caption)
    tip = "": tip = CStr(ctl.ControlTipText)
    onClick = "": onClick = CStr(ctl.OnClick)
    vis = "true": vis = LCase$(CStr(ctl.Visible))
    sect = "": sect = CStr(ctl.Section)
    parentName = "": parentName = CStr(ctl.Parent.Name)

    ' The attached label. This is the visible text for a control that has no
    ' caption of its own, and it is the association the definition text loses.
    lbl = ""
    If ctl.Controls.Count > 0 Then lbl = CStr(ctl.Controls(0).Caption)

    ControlJson = "      {""name"": """ & JsonEscape(CStr(ctl.Name)) & """" & _
        ", ""type"": " & CStr(ctl.ControlType) & _
        ", ""caption"": """ & JsonEscape(cap) & """" & _
        ", ""attached_label"": """ & JsonEscape(lbl) & """" & _
        ", ""tooltip"": """ & JsonEscape(tip) & """" & _
        ", ""visible"": " & vis & _
        ", ""on_click"": """ & JsonEscape(onClick) & """" & _
        ", ""section"": """ & JsonEscape(sect) & """" & _
        ", ""parent"": """ & JsonEscape(parentName) & """" & _
        ", ""left"": " & CStr(NzLong(ctl.Left)) & _
        ", ""top"": " & CStr(NzLong(ctl.Top)) & _
        ", ""width"": " & CStr(NzLong(ctl.Width)) & _
        ", ""height"": " & CStr(NzLong(ctl.Height)) & "}"
End Function

Private Function NzLong(ByVal v As Variant) As Long
    On Error Resume Next
    NzLong = 0
    NzLong = CLng(v)
End Function
