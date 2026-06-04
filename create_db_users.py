import asyncio
import os
from helpers.azure_credential_utils import get_azure_credential_async
import pyodbc
import struct
import sys

async def create_database_users():
    """Create database users for managed identities"""
    
    # Managed identity details
    system_principal_id = "c14cc1bf-546a-4c14-a382-a9d6c352ea7f"
    user_principal_id = "0b502954-b320-4d80-b888-f098bdbe4d82"
    
    # SQL Server details
    server = "sql-financeirax01.database.windows.net"
    database = "financeirax01"
    driver = "{ODBC Driver 17 for SQL Server}"
    
    # Get credential for current user (admin)
    credential = await get_azure_credential_async()
    token = await credential.get_token("https://database.windows.net/.default")
    
    token_bytes = token.token.encode("utf-16-LE")
    token_struct = struct.pack(
        f"<I{len(token_bytes)}s",
        len(token_bytes),
        token_bytes
    )
    
    connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};"
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    
    conn = pyodbc.connect(
        connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}
    )
    cursor = conn.cursor()
    
    try:
        # Create user for system-assigned managed identity
        sql_cmd = f"""
        IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE sid = CONVERT(varbinary(85), '{system_principal_id}', 2))
        BEGIN
            CREATE USER [api-financeirax01] FROM EXTERNAL PROVIDER;
            ALTER ROLE db_datareader ADD MEMBER [api-financeirax01];
            ALTER ROLE db_datawriter ADD MEMBER [api-financeirax01];
            PRINT 'Created database user for system-assigned managed identity (api-financeirax01)';
        END
        ELSE
        BEGIN
            PRINT 'Database user for system-assigned managed identity already exists';
        END
        """
        
        cursor.execute(sql_cmd)
        conn.commit()
        print("✓ System-assigned managed identity user created/verified")
        
        # Create user for user-assigned managed identity
        sql_cmd = f"""
        IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE sid = CONVERT(varbinary(85), '{user_principal_id}', 2))
        BEGIN
            CREATE USER [id-financeirax01] FROM EXTERNAL PROVIDER;
            ALTER ROLE db_datareader ADD MEMBER [id-financeirax01];
            ALTER ROLE db_datawriter ADD MEMBER [id-financeirax01];
            PRINT 'Created database user for user-assigned managed identity (id-financeirax01)';
        END
        ELSE
        BEGIN
            PRINT 'Database user for user-assigned managed identity already exists';
        END
        """
        
        cursor.execute(sql_cmd)
        conn.commit()
        print("✓ User-assigned managed identity user created/verified")
        
    except Exception as e:
        print(f"Error creating database users: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
        await credential.close()

if __name__ == "__main__":
    asyncio.run(create_database_users())
