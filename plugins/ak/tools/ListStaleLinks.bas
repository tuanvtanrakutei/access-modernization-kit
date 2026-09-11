Option Compare Database
Option Explicit

' Which linked tables Access named itself, and which are real tables it can no longer
' reach. Run inside the frontend .mdb, from the Immediate window:
'
'     ListStaleLinks
'
' It writes a report beside the database and changes nothing. That is the whole of the
' default behaviour, and it is the default because the alternative edits a running
' application.
'
' -----------------------------------------------------------------------------------
' The rule, and why it is not the obvious one
' -----------------------------------------------------------------------------------
' Access appends a number to the LINK name when the name it wants is taken, and leaves
' the SOURCE table name alone. So a duplicate is a link whose name is its source
' table's name followed by digits, and nothing else is.
'
' Comparing the two names for mere inequality looks equivalent and is not. SQL Server
' returns a schema-qualified source name, so an ODBC link named 商品マスタ reports its
' source as dbo.商品マスタ - unequal, live, and in daily use. On A06 that comparison
' would have removed three tables carrying 16, 43 and 68 fields.
'
' A source table that genuinely ends in digits is also not a duplicate. A06 has one,
' 商品情報20121115, named for a date the way its five local 受YYYYMMDD tables are. A
' rule that looked at the suffix instead of at both names would have deleted it.
'
' -----------------------------------------------------------------------------------
' What has to be true before this offers to delete anything
' -----------------------------------------------------------------------------------
' A candidate is offered only when all four hold:
'
'   1. its name is <source table name> followed by digits;
'   2. a link named exactly <source table name> also exists in this database;
'   3. that base link RESOLVES - its fields can be read right now;
'   4. no saved query names the candidate.
'
' Condition 3 is the one that matters. Deleting 商品マスタ3 while 商品マスタ itself is
' broken removes the only surviving route to the table.
'
' Forms, reports and modules are NOT searched here - a macro cannot read their
' definitions without exporting them. Run `ExportAccessObjects` first and have the kit
' search the export package. On A06 that search covered 87 definitions and found none
' of the 153 candidates referenced anywhere.
'
' -----------------------------------------------------------------------------------
' Deleting
' -----------------------------------------------------------------------------------
' Set DELETE_CONFIRMED to True below, save, and run DeleteStaleLinks. Back the file up
' first: this removes objects and Access has no undo for it. Deleting only ever touches
' candidates that passed all four conditions; a table this reports as unreachable but
' distinct is never deleted, because that is a different decision and nobody has been
' asked for it.

Private Const DELETE_CONFIRMED As Boolean = False

Private Const CLASS_DUPLICATE As String = "AUTO_NUMBERED_DUPLICATE"
Private Const CLASS_UNREACHABLE As String = "UNREACHABLE_DISTINCT"
Private Const CLASS_LIVE As String = "LIVE"
Private Const CLASS_HELD As String = "HELD_BACK"


Public Sub ListStaleLinks()
    Report False
End Sub


Public Sub DeleteStaleLinks()
    If Not DELETE_CONFIRMED Then
        Debug.Print "DELETE_CONFIRMED is False. Nothing was deleted."
        Debug.Print "Edit the constant in this module, save, and run again."
        Report False
        Exit Sub
    End If
    Report True
End Sub


Private Sub Report(ByVal performDelete As Boolean)
    Dim db As DAO.Database
    Dim td As DAO.TableDef
    Dim liveNames As Collection
    Dim allNames As Collection
    Dim queryText As String
    Dim handle As Integer
    Dim path As String
    Dim names() As String
    Dim classes() As String
    Dim details() As String
    Dim total As Long
    Dim index As Long
    Dim countDuplicate As Long
    Dim countUnreachable As Long
    Dim countLive As Long
    Dim countHeld As Long
    Dim deleted As Long

    Set db = CurrentDb()
    Set liveNames = New Collection
    Set allNames = New Collection
    queryText = AllQuerySql(db)

    ' Pass one: every link, whether it resolves, and the set of names present. Both
    ' are needed before anything can be classified, because a candidate is judged by
    ' whether ANOTHER link is readable.
    For Each td In db.TableDefs
        If Len(td.Connect) > 0 And Not IsSystemName(td.Name) Then
            total = total + 1
            AddKey allNames, td.Name
            If LinkResolves(td) Then AddKey liveNames, td.Name
        End If
    Next td

    ReDim names(1 To IIf(total = 0, 1, total))
    ReDim classes(1 To IIf(total = 0, 1, total))
    ReDim details(1 To IIf(total = 0, 1, total))

    index = 0
    For Each td In db.TableDefs
        If Len(td.Connect) > 0 And Not IsSystemName(td.Name) Then
            index = index + 1
            names(index) = td.Name
            classes(index) = Classify(td, liveNames, allNames, queryText, details(index))
            Select Case classes(index)
                Case CLASS_DUPLICATE: countDuplicate = countDuplicate + 1
                Case CLASS_UNREACHABLE: countUnreachable = countUnreachable + 1
                Case CLASS_HELD: countHeld = countHeld + 1
                Case Else: countLive = countLive + 1
            End Select
        End If
    Next td

    path = CurrentProject.Path & Chr(92) & "stale-links-" & _
           Format(Now(), "yyyy-mm-dd-hhnnss") & ".txt"
    handle = FreeFile
    Open path For Output As #handle
    Print #handle, "Database: " & CurrentDb().Name
    Print #handle, "Read at: " & Format(Now(), "yyyy-mm-dd hh:nn:ss")
    Print #handle, "Links: " & total & "  duplicate: " & countDuplicate & _
                   "  unreachable-distinct: " & countUnreachable & _
                   "  held back: " & countHeld & "  live: " & countLive
    Print #handle, ""
    Print #handle, "class" & vbTab & "link" & vbTab & "detail"
    For index = 1 To total
        Print #handle, classes(index) & vbTab & names(index) & vbTab & details(index)
    Next index

    If performDelete Then
        Print #handle, ""
        Print #handle, "--- deleting " & countDuplicate & " links ---"
        For index = 1 To total
            If classes(index) = CLASS_DUPLICATE Then
                db.TableDefs.Delete names(index)
                Print #handle, "deleted" & vbTab & names(index)
                deleted = deleted + 1
            End If
        Next index
        db.TableDefs.Refresh
        Print #handle, "deleted " & deleted & " of " & total & " links"
    End If

    Close #handle

    Debug.Print "Links: " & total & "  duplicate: " & countDuplicate & _
                "  unreachable-distinct: " & countUnreachable & _
                "  held back: " & countHeld & "  live: " & countLive
    If performDelete Then
        Debug.Print "Deleted " & deleted & " auto-numbered duplicate links."
    Else
        Debug.Print "Nothing was changed."
    End If
    Debug.Print "Report: " & path
    Set liveNames = Nothing
    Set allNames = Nothing
    Set db = Nothing
End Sub


Private Function Classify(ByVal td As DAO.TableDef, ByVal liveNames As Collection, _
                          ByVal allNames As Collection, ByVal queryText As String, _
                          ByRef detail As String) As String
    Dim source As String
    Dim resolves As Boolean

    source = td.SourceTableName
    resolves = KeyExists(liveNames, td.Name)

    If Not IsAutoNumbered(td.Name, source) Then
        If resolves Then
            Classify = CLASS_LIVE
            detail = "source " & source
        Else
            ' A real table this database names and cannot reach. Reported, never
            ' deleted: it may be the only record that the table ever existed.
            Classify = CLASS_UNREACHABLE
            detail = "source " & source & "; target " & TargetOf(td.Connect)
        End If
        Exit Function
    End If

    If Not KeyExists(allNames, source) Then
        Classify = CLASS_HELD
        detail = "numbered after " & source & ", but no link named " & source & " exists"
        Exit Function
    End If
    If Not KeyExists(liveNames, source) Then
        Classify = CLASS_HELD
        detail = "numbered after " & source & ", and that link does not resolve either"
        Exit Function
    End If
    If NameAppearsIn(queryText, td.Name) Then
        Classify = CLASS_HELD
        detail = "a saved query names it"
        Exit Function
    End If

    Classify = CLASS_DUPLICATE
    detail = source & " is present and resolves; target " & TargetOf(td.Connect)
End Function


Private Function IsAutoNumbered(ByVal linkName As String, ByVal source As String) As Boolean
    Dim tail As String
    Dim position As Long

    IsAutoNumbered = False
    If Len(source) = 0 Then Exit Function
    If linkName = source Then Exit Function
    If Len(linkName) <= Len(source) Then Exit Function
    If Left$(linkName, Len(source)) <> source Then Exit Function

    tail = Mid$(linkName, Len(source) + 1)
    For position = 1 To Len(tail)
        If InStr("0123456789", Mid$(tail, position, 1)) = 0 Then Exit Function
    Next position
    IsAutoNumbered = True
End Function


Private Function LinkResolves(ByVal td As DAO.TableDef) As Boolean
    ' Reading the field collection is what makes Access open the target. A broken link
    ' raises here rather than reporting zero fields, which is why the probe is a read
    ' and not a count comparison.
    On Error GoTo Failed
    Dim fieldCount As Long
    fieldCount = td.Fields.Count
    LinkResolves = (fieldCount >= 0)
    Exit Function
Failed:
    LinkResolves = False
End Function


Private Function AllQuerySql(ByVal db As DAO.Database) As String
    Dim qd As DAO.QueryDef
    Dim parts As String

    On Error Resume Next
    For Each qd In db.QueryDefs
        If Left$(qd.Name, 1) <> "~" Then parts = parts & " " & qd.SQL & " "
    Next qd
    On Error GoTo 0
    AllQuerySql = parts
End Function


Private Function NameAppearsIn(ByVal text As String, ByVal linkName As String) As Boolean
    ' A name followed by another digit is a different, longer name: 商品情報2 must not
    ' match inside 商品情報20121115.
    Dim position As Long
    Dim after As String

    position = InStr(1, text, linkName, vbTextCompare)
    Do While position > 0
        after = Mid$(text, position + Len(linkName), 1)
        If InStr("0123456789", after) = 0 Then
            NameAppearsIn = True
            Exit Function
        End If
        position = InStr(position + 1, text, linkName, vbTextCompare)
    Loop
    NameAppearsIn = False
End Function


Private Function TargetOf(ByVal connect As String) As String
    Dim position As Long

    position = InStr(1, connect, "DATABASE=", vbTextCompare)
    If position = 0 Then
        TargetOf = connect
    Else
        TargetOf = Mid$(connect, position + Len("DATABASE="))
    End If
End Function


Private Function IsSystemName(ByVal name As String) As Boolean
    IsSystemName = (Left$(name, 4) = "MSys") Or (Left$(name, 1) = "~")
End Function


Private Sub AddKey(ByVal target As Collection, ByVal key As String)
    On Error Resume Next
    target.Add key, key
    On Error GoTo 0
End Sub


Private Function KeyExists(ByVal target As Collection, ByVal key As String) As Boolean
    Dim probe As Variant

    On Error GoTo Missing
    probe = target.Item(key)
    KeyExists = True
    Exit Function
Missing:
    KeyExists = False
End Function
