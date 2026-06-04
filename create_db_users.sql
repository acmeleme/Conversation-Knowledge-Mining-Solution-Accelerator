IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'api-financeirax01')
BEGIN
  CREATE USER [api-financeirax01] WITH SID = 0xbfc14cc1546a144ca382a9d6c352ea7f, TYPE = E;
  ALTER ROLE db_datareader ADD MEMBER [api-financeirax01];
  ALTER ROLE db_datawriter ADD MEMBER [api-financeirax01];
  PRINT 'Created api-financeirax01 user';
END
ELSE
BEGIN
  PRINT 'api-financeirax01 user already exists';
END

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'id-financeirax01')
BEGIN
  CREATE USER [id-financeirax01] WITH SID = 0x54295b0b20b3804db888f098bdbe4d82, TYPE = E;
  ALTER ROLE db_datareader ADD MEMBER [id-financeirax01];
  ALTER ROLE db_datawriter ADD MEMBER [id-financeirax01];
  PRINT 'Created id-financeirax01 user';
END
ELSE
BEGIN
  PRINT 'id-financeirax01 user already exists';
END
