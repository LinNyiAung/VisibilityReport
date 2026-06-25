import os
import pyodbc
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Dict, Optional

load_dotenv()

app = FastAPI()

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Predefined Program Codes
PROGRAM_MAP = {
    "89": "May Yee Mon",
    "90": "Ovaltine"
}

BASE_IMAGE_URL = "http://sfa.pahtama.com/MerchandiseImage"

def get_dwbi_connection():
    db_user = os.getenv("DWBI_USER")
    db_password = os.getenv("DWBI_PASSWORD")
    conn_str = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=phm\\reportingsvr;'
        'DATABASE=DWBI;'
        f'UID={db_user};'
        f'PWD={db_password};'
    )
    return pyodbc.connect(conn_str)

def get_weekly_dates(target_date: Optional[datetime] = None):
    """
    Returns a list of date strings for the week ending on a given date.
    Defaults to the most recent Friday if target_date is None.
    """
    if target_date is None:
        target_date = datetime.now()
        # Find the most recent Friday (4 = Friday)
        offset = (target_date.weekday() - 4) % 7
        friday = target_date - timedelta(days=offset)
    else:
        friday = target_date
        
    dates = []
    # Get Saturday to Friday (7 days)
    for i in range(6, -1, -1):
        day = friday - timedelta(days=i)
        dates.append(f"{day.year}-{day.month}-{day.day}")
    
    # Format time-frame string for header display (e.g., 13/06/2026 to 19/06/2026)
    start_display = (friday - timedelta(days=6)).strftime("%d/%m/%Y")
    end_display = friday.strftime("%d/%m/%Y")
    
    return dates, f"{start_display} to {end_display}"

@app.get("/api/reports")
def get_visibility_reports(end_date: Optional[str] = None):
    target_date = None
    if end_date:
        try:
            target_date = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD"}

    target_dates, time_frame = get_weekly_dates(target_date)
    raw_data = defaultdict(lambda: defaultdict(list))
    
    # Add a standard browser User-Agent to prevent 403 Forbidden errors
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"\n--- Running report for timeframe: {time_frame} ---")

    # 1. Scrape Images
    for date_str in target_dates:
        folder_url = f"{BASE_IMAGE_URL}/{date_str}/"
        print(f"Checking folder: {folder_url}")
        
        try:
            response = requests.get(folder_url, headers=headers, timeout=10)
            print(f" -> Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a')
                print(f" -> Found {len(links)} total links in directory")
                
                valid_images_found = 0
                for link in links:
                    href = link.get('href')
                    if not href:
                        continue
                        
                    # Extract just the raw file name (e.g., "M_SP..." from "/path/M_SP...")
                    filename = href.split('/')[-1]
                    
                    if filename.endswith('.jpg') and filename.startswith('M_'):
                        valid_images_found += 1
                        parts = filename.split('_')
                        if len(parts) >= 6:
                            sp_code = parts[1]
                            route_code = parts[2]
                            cus_code = next((p for p in parts if p.startswith('C0')), "Unknown")
                            program_code = next((p for p in reversed(parts) if p.isdigit() and len(p) <= 2), "Unknown")
                            
                            # Safely combine the base folder URL with whatever relative path IIS provided
                            img_url = urljoin(folder_url, href)
                            
                            raw_data[program_code][(sp_code, route_code, cus_code)].append(img_url)
                
                print(f" -> Successfully parsed {valid_images_found} valid image files.")
            else:
                print(f" -> Server rejected request or folder doesn't exist.")
                
        except requests.exceptions.RequestException as e:
            print(f" -> Connection Error: {e}")

    # 2. Extract Unique IDs for DB Queries
    unique_cus_codes = set()
    unique_route_codes = set()
    for prog_data in raw_data.values():
        for sp, route, cus in prog_data.keys():
            unique_cus_codes.add(cus)
            unique_route_codes.add(route)

    # 3. Fetch Data from DWBI
    customer_map = {}
    route_map = {}
    
    conn = get_dwbi_connection()
    cursor = conn.cursor()
    
    try:
        # Fetch Customers (Chunking might be needed if the list is > 1000)
        if unique_cus_codes:
            placeholders = ','.join(['?'] * len(unique_cus_codes))
            cus_query = f"SELECT CardCode, CardName FROM Customer_Master WHERE CardCode IN ({placeholders})"
            cursor.execute(cus_query, list(unique_cus_codes))
            for row in cursor.fetchall():
                customer_map[row.CardCode] = row.CardName

        # Fetch Route/Salesman Details
        if unique_route_codes:
            placeholders = ','.join(['?'] * len(unique_route_codes))
            route_query = f"SELECT RouteCode, SupCode, SupName, SPName FROM Master_Route_SaleMan WHERE RouteCode IN ({placeholders})"
            cursor.execute(route_query, list(unique_route_codes))
            for row in cursor.fetchall():
                route_map[row.RouteCode] = {
                    "SupCode": row.SupCode,
                    "SupName": row.SupName,
                    "SPName": row.SPName
                }
    finally:
        cursor.close()
        conn.close()

    # 4. Construct Final Response Payload
    reports = []
    for prog_code, records in raw_data.items():
        program_name = PROGRAM_MAP.get(prog_code, f"Program {prog_code}")
        
        formatted_records = []
        for (sp_code, route_code, cus_code), images in records.items():
            route_info = route_map.get(route_code, {})
            
            formatted_records.append({
                "SaleMan": sp_code,
                "RouteCode": route_code,
                "SM_Name": route_info.get("SPName", "Unknown"),
                "SuperEcode": route_info.get("SupCode", "Unknown"),
                "SuperName": route_info.get("SupName", "Unknown"),
                "CusCode": cus_code,
                "CusName": customer_map.get(cus_code, "Unknown"),
                "DisplayImages": images
            })
            
        reports.append({
            "ProgramCode": prog_code,
            "ProgramName": program_name,
            "TimeFrame": time_frame,
            "Details": formatted_records
        })

    return {"reports": reports}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)