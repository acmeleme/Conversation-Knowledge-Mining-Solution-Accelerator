IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'api-financeirax01')
BEGIN
    CREATE USER [api-financeirax01] FROM EXTERNAL PROVIDER;
    ALTER ROLE db_datareader ADD MEMBER [api-financeirax01];
    ALTER ROLE db_datawriter ADD MEMBER [api-financeirax01];
    SELECT 'Created api-financeirax01' AS Result;
END
ELSE
    SELECT 'api-financeirax01 already exists' AS Result;
