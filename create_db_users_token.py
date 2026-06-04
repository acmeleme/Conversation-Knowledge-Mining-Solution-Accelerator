import pyodbc
import struct
import subprocess

def create_db_users_with_token():
    server = "sql-financeirax01.database.windows.net"
    database = "financeirax01"
    driver = "{ODBC Driver 17 for SQL Server}"
    
    # Get access token
    print("Getting access token...")
    token_cmd = 'az account get-access-token --resource "https://database.windows.net" --query accessToken -o tsv'
    token = subprocess.check_output(token_cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    print(f"✓ Got access token (length: {len(token)})")
    
    # Prepare token for SQL Server
    token_bytes = token.encode("utf-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    
    # Connection string
    connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};"
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    
    # Connect
    print(f"Connecting to {server}/{database}...")
    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    print("✓ Connected successfully")
    
    cursor = conn.cursor()
    
    try:
        # SQL commands
        commands = [
            """
            IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'api-financeirax01')
            BEGIN
                CREATE USER [api-financeirax01] FROM EXTERNAL PROVIDER;
                ALTER ROLE db_datareader ADD MEMBER [api-financeirax01];
                ALTER ROLE db_datawriter ADD MEMBER [api-financeirax01];
                PRINT 'Created user for system-assigned managed identity';
            END
            ELSE
                PRINT 'System-assigned user already exists';
            """,
            """
            IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'id-financeirax01')
            BEGIN
                CREATE USER [id-financeirax01] FROM EXTERNAL PROVIDER;
                ALTER ROLE db_datareader ADD MEMBER [id-financeirax01];
                ALTER ROLE db_datawriter ADD MEMBER [id-financeirax01];
                PRINT 'Created user for user-assigned managed identity';
            END
            ELSE
                PRINT 'User-assigned user already exists';
            """
        ]
        
        for cmd in commands:
            cursor.execute(cmd)
            result = cursor.fetchone()
            if result:
                print(f"✓ {result[0]}")
        
        conn.commit()
        print("\n✓ All database users created/verified successfully")
        
    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_db_users_with_token()
