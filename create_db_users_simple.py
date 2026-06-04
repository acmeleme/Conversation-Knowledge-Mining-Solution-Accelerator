import pyodbc
import struct
import subprocess
import json

def create_database_users():
    """Create database users for managed identities"""
    
    # SQL Server details
    server = "sql-financeirax01.database.windows.net"
    database = "financeirax01"
    driver = "{ODBC Driver 17 for SQL Server}"
    
    # Get token using Azure CLI
    token_cmd = 'az account get-access-token --resource "https://database.windows.net" --query accessToken -o tsv'
    try:
        token = subprocess.check_output(token_cmd, shell=True, text=True).strip()
    except Exception as e:
        print(f"Error getting token: {e}")
        raise
    
    print(f"✓ Got access token")
    
    # Prepare token for pyodbc
    token_bytes = token.encode("utf-16-LE")
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
        # SQL commands to create users
        commands = [
            # Create user for system-assigned managed identity
            "IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'api-financeirax01') "
            "BEGIN "
            "  CREATE USER [api-financeirax01] FROM EXTERNAL PROVIDER; "
            "  ALTER ROLE db_datareader ADD MEMBER [api-financeirax01]; "
            "  ALTER ROLE db_datawriter ADD MEMBER [api-financeirax01]; "
            "  PRINT 'Created user for system-assigned managed identity'; "
            "END "
            "ELSE BEGIN PRINT 'System-assigned user already exists'; END",
            
            # Create user for user-assigned managed identity  
            "IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'id-financeirax01') "
            "BEGIN "
            "  CREATE USER [id-financeirax01] FROM EXTERNAL PROVIDER; "
            "  ALTER ROLE db_datareader ADD MEMBER [id-financeirax01]; "
            "  ALTER ROLE db_datawriter ADD MEMBER [id-financeirax01]; "
            "  PRINT 'Created user for user-assigned managed identity'; "
            "END "
            "ELSE BEGIN PRINT 'User-assigned user already exists'; END"
        ]
        
        for cmd in commands:
            cursor.execute(cmd)
            result = cursor.fetchone()
            if result:
                print(f"✓ {result[0]}")
        
        conn.commit()
        print("✓ All database users created/verified successfully")
        
    except Exception as e:
        print(f"Error creating database users: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_database_users()
