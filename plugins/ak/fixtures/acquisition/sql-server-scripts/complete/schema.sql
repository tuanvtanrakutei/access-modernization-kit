CREATE TABLE dbo.SyntheticOrder (
    OrderId INT NOT NULL,
    OrderDate DATETIME NULL
);

CREATE PROCEDURE dbo.usp_SyntheticOrder
AS
BEGIN
    SELECT 1 AS Placeholder;
END;
