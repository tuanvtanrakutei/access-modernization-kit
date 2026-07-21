Attribute VB_Name = "ExportAccessObjects"
Option Compare Database
Option Explicit

' =============================================================================
' SMS Legacy Investigation Kit - manual Access export
' =============================================================================
' Export every Access object to text from INSIDE Access, without external COM
' automation and without administrator elevation. Use this when the runtime
' extractor (scripts/extract_access.py) cannot run - for example on a machine
' without Access, or when the registered Access executable requires elevation.
'
' HOW TO RUN
'   1. Open the database in Microsoft Access.
'   2. Press Alt+F11 to open the VBA editor, then Ctrl+G for the Immediate window
'      (or import this .bas via File > Import File).
'   3. Paste this module (VBA editor: Insert > Module, then paste) OR import it.
'   4. In the Immediate window type, replacing the path, then press Enter:
'
'          ExportAccessObjects "D:\Anrakutei\A05\sources"
'
' OUTPUT (created under the folder you pass)
'   forms\      one .txt per form      (SaveAsText)
'   reports\    one .txt per report    (SaveAsText)
'   macros\     one .txt per macro     (SaveAsText)
'   vba\        one .txt per module    (SaveAsText)
'   queries\    one .sql per query     (QueryDef.SQL, UTF-8)
'   schema\tables.txt  table list with linked/local flag and fields (UTF-8)
'   export-manifest.txt  object counts
'
' The output folder is meant to be the app workspace "sources" folder (or copied
' into it) so the six-phase investigation runs in export mode. File names keep
' the original (Japanese) object names and strip only characters that are
' illegal in Windows file names; on a real collision a numeric suffix is added,
' so no object is ever lost by overwrite.
' =============================================================================

Private mUsed As Object   ' Scripting.Dictionary of used (lower-cased) file paths

Public Sub ExportAccessObjects(ByVal OutRoot As String)
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set mUsed = CreateObject("Scripting.Dictionary")

    EnsureDir fso, OutRoot
    Dim sub_ As Variant
    For Each sub_ In Array("forms", "reports", "macros", "vba", "queries", "schema")
        EnsureDir fso, OutRoot & "\" & sub_
    Next

    Dim nForm As Long, nReport As Long, nMacro As Long, nModule As Long
    Dim nQuery As Long, nTable As Long
    Dim ao As Object

    For Each ao In CurrentProject.AllForms
        Application.SaveAsText acForm, ao.Name, UniquePath(OutRoot & "\forms", ao.Name, "txt")
        nForm = nForm + 1
    Next
    For Each ao In CurrentProject.AllReports
        Application.SaveAsText acReport, ao.Name, UniquePath(OutRoot & "\reports", ao.Name, "txt")
        nReport = nReport + 1
    Next
    For Each ao In CurrentProject.AllMacros
        Application.SaveAsText acMacro, ao.Name, UniquePath(OutRoot & "\macros", ao.Name, "txt")
        nMacro = nMacro + 1
    Next
    For Each ao In CurrentProject.AllModules
        Application.SaveAsText acModule, ao.Name, UniquePath(OutRoot & "\vba", ao.Name, "txt")
        nModule = nModule + 1
    Next

    Dim db As DAO.Database, qd As DAO.QueryDef
    Set db = CurrentDb
    For Each qd In db.QueryDefs
        If Left$(qd.Name, 1) <> "~" Then          ' skip hidden/temporary queries
            WriteUtf8 UniquePath(OutRoot & "\queries", qd.Name, "sql"), qd.SQL
            nQuery = nQuery + 1
        End If
    Next

    Dim td As DAO.TableDef, fld As DAO.Field, sb As String
    For Each td In db.TableDefs
        If Left$(td.Name, 4) <> "MSys" Then       ' skip system tables
            sb = sb & "TABLE" & vbTab & td.Name & vbTab
            If Len(td.Connect) > 0 Then
                sb = sb & "LINKED" & vbTab & td.SourceTableName
            Else
                sb = sb & "LOCAL"
            End If
            sb = sb & vbCrLf
            For Each fld In td.Fields
                sb = sb & vbTab & "FIELD" & vbTab & fld.Name & _
                     vbTab & "type=" & fld.Type & vbTab & "size=" & fld.Size & vbCrLf
            Next
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
              "tables=" & nTable & vbCrLf
    WriteUtf8 OutRoot & "\export-manifest.txt", summary
    Debug.Print summary
    Debug.Print "Export complete -> " & OutRoot
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
