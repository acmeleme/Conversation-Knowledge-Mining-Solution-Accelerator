-- Create user for system-assigned identity
CREATE USER [api-financeirax01] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [api-financeirax01];
ALTER ROLE db_datawriter ADD MEMBER [api-financeirax01];

-- Create user for user-assigned identity  
CREATE USER [id-financeirax01] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [id-financeirax01];
ALTER ROLE db_datawriter ADD MEMBER [id-financeirax01];

-- Verify users were created
SELECT name, type, type_desc FROM sys.database_principals WHERE name IN ('api-financeirax01', 'id-financeirax01');
