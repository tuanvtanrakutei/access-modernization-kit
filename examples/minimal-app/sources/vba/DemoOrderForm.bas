Attribute VB_Name = "DemoOrderForm"
Option Compare Database

Private Sub Save_Click()
    CurrentDb.Execute "UPDATE DemoOrders SET Status='Saved' WHERE OrderId=1"
End Sub
