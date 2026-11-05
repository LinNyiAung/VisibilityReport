import os
import re
import io
import pyodbc
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple
from PIL import Image as PILImage
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

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
    "51": "Hair Care-Bottle",
    "52": "Oral Care",
    "53": "Fabric Care",
    "54": "Blade & razor",
    "55": "Home Care",
    "57": "Medical Nutrition",
    "58": "Pediatric Nutrition",
    "59": "Nutrition Supplement",
    "60": "Beverage",
    "62": "Cake & Pie",
    "63": "Instant Noodle Any",
    "64": "Cereal",
    "65": "Potato Chip",
    "66": "Biscuit & Cookies",
    "67": "Sugar Supplement",
    "68": "Cooking Oil",
    "69": "Snack",
    "70": "Cake Rusk",
    "71": "Ready to Eat (Balachaung)",
    "72": "Coffee",
    "74": "Condiment",
    "75": "Process Food",
    "77": "Pickled Tea and Related Item",
    "86": "Preserve Fruit",
    "87": "Butter & Spreads",
    "88": "Ice Cream",
    "89": "May Yee Mon",
    "90": "Ovaltine",
    "91": "MYM Congee",
    "92": "Sweety Masala",
    "93": "Joy Joy Peanut Butter",
    "94": "Snack Display Program",
    "95": " ABBOTT CLP Program"
}

BASE_IMAGE_URL = "http://sfa.pahtama.com/MerchandiseImage"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

DATE_FOLDER_RE = re.compile(r'^(\d{4})-(\d{1,2})-(\d{1,2})$')


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


def get_available_image_dates() -> List[datetime]:
    """
    Scrapes the root MerchandiseImage directory listing and returns every
    date folder that exists on the server, as datetime objects.
    """
    dates = []
    try:
        response = requests.get(f"{BASE_IMAGE_URL}/", headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return dates
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a'):
            href = link.get('href')
            if not href:
                continue
            name = href.rstrip('/').split('/')[-1]
            match = DATE_FOLDER_RE.match(name)
            if not match:
                continue
            try:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                dates.append(datetime(year, month, day))
            except ValueError:
                continue
    except requests.exceptions.RequestException as e:
        print(f"Error listing image directory: {e}")

    return sorted(set(dates))


def build_periods(dates: List[datetime]):
    """
    Given the list of dates that actually have image folders, build the
    Daily / Weekly / Monthly lists that the frontend will render as clickable
    buttons.
    """
    # --- Daily ---
    daily = []
    for d in sorted(dates, reverse=True):
        daily.append({
            "label": d.strftime("%d/%m/%Y"),  # Changed from %m/%d/%y to %d/%m/%Y
            "date": d.strftime("%Y-%m-%d"),
        })

    # --- Weekly (Saturday -> Friday buckets) ---
    weekly_buckets: Dict[str, Tuple[datetime, datetime]] = {}
    for d in dates:
        # weekday(): Mon=0 ... Fri=4, Sat=5, Sun=6. Week starts Saturday.
        days_since_sat = (d.weekday() - 5) % 7
        week_start = d - timedelta(days=days_since_sat)
        week_end = week_start + timedelta(days=6)
        key = week_end.strftime("%Y-%m-%d")
        weekly_buckets[key] = (week_start, week_end)

    weekly = []
    for end_str, (week_start, week_end) in sorted(weekly_buckets.items(), reverse=True):
        weekly.append({
            # Changed from %m/%d/%y to %d/%m/%Y
            "label": f"{week_start.strftime('%d/%m/%Y')} - {week_end.strftime('%d/%m/%Y')}",
            "end_date": end_str,
        })

    # --- Monthly ---
    monthly_keys = sorted({(d.year, d.month) for d in dates}, reverse=True)
    monthly = []
    for year, month in monthly_keys:
        monthly.append({
            "label": datetime(year, month, 1).strftime("%B %Y"),
            "year": year,
            "month": month,
        })

    return daily, weekly, monthly


@app.get("/api/periods")
def get_periods():
    """
    Returns the available Daily, Weekly, and Monthly periods that have at
    least one image folder on the server, for the frontend to render as
    clickable lists.
    """
    dates = get_available_image_dates()
    daily, weekly, monthly = build_periods(dates)
    return {"daily": daily, "weekly": weekly, "monthly": monthly}


def scrape_dates_into_raw_data(target_dates: List[str]):
    """
    Scrapes the given list of date-folder strings (e.g. '2026-6-19') for
    merchandise images and groups them by program / salesman / route / customer.
    """
    raw_data = defaultdict(lambda: defaultdict(list))

    print(f"\n--- Scraping {len(target_dates)} date folder(s) ---")

    for date_str in target_dates:
        folder_url = f"{BASE_IMAGE_URL}/{date_str}/"
        print(f"Checking folder: {folder_url}")

        try:
            response = requests.get(folder_url, headers=HEADERS, timeout=10)
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

                            raw_data[program_code][(date_str, sp_code, route_code, cus_code)].append(img_url)

                print(f" -> Successfully parsed {valid_images_found} valid image files.")
            else:
                print(f" -> Server rejected request or folder doesn't exist.")

        except requests.exceptions.RequestException as e:
            print(f" -> Connection Error: {e}")

    return raw_data


def build_visibility_reports(
    period_type: str = "weekly",
    date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    """
    Shared by /api/reports and /api/reports/export-excel.

    period_type: "daily" | "weekly" | "monthly"
      - daily:   requires `date` (YYYY-MM-DD)
      - weekly:  requires `end_date` (YYYY-MM-DD, must be a Friday) - falls
                 back to the most recent Friday if omitted
      - monthly: requires `year` and `month`
    """
    target_dates: List[str] = []
    time_frame = ""

    if period_type == "daily":
        if not date:
            return {"error": "date is required for a daily report"}
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD"}
        target_dates = [f"{d.year}-{d.month}-{d.day}"]
        time_frame = d.strftime("%d/%m/%Y")

    elif period_type == "monthly":
        if not year or not month:
            return {"error": "year and month are required for a monthly report"}
        try:
            start = datetime(year, month, 1)
        except ValueError:
            return {"error": "Invalid year/month"}
        next_month = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        days_in_month = (next_month - start).days
        for i in range(days_in_month):
            d = start + timedelta(days=i)
            target_dates.append(f"{d.year}-{d.month}-{d.day}")
        time_frame = start.strftime("%B %Y")

    elif period_type == "weekly":
        target_date = None
        if end_date:
            try:
                target_date = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return {"error": "Invalid date format. Use YYYY-MM-DD"}
        target_dates, time_frame = get_weekly_dates(target_date)

    else:
        return {"error": f"Unknown period_type '{period_type}'. Use daily, weekly, or monthly."}

    print(f"--- Running report for timeframe: {time_frame} ---")

    # 1. Scrape Images
    raw_data = scrape_dates_into_raw_data(target_dates)

    # 2. Extract Unique IDs for DB Queries
    unique_cus_codes = set()
    unique_route_codes = set()
    for prog_data in raw_data.values():
        for date_str, sp, route, cus in prog_data.keys():
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

        # Fetch Route/Salesman Details including the new 'Active' column
        if unique_route_codes:
            placeholders = ','.join(['?'] * len(unique_route_codes))
            route_query = f"SELECT RouteCode, SupCode, SupName, SPName, Active FROM Master_Route_SaleMan WHERE RouteCode IN ({placeholders})"
            cursor.execute(route_query, list(unique_route_codes))
            for row in cursor.fetchall():
                route_map[row.RouteCode] = {
                    "SupCode": row.SupCode,
                    "SupName": row.SupName,
                    "SPName": row.SPName,
                    "Active": row.Active
                }
    finally:
        cursor.close()
        conn.close()

    # 4. Construct Final Response Payload
    reports = []
    for prog_code, records in raw_data.items():
        program_name = PROGRAM_MAP.get(prog_code, f"Program {prog_code}")

        formatted_records = []
        for (date_str, sp_code, route_code, cus_code), images in records.items():
            route_info = route_map.get(route_code, {})

            formatted_records.append({
                "Date": date_str,
                "SaleMan": sp_code,
                "RouteCode": route_code,
                "SM_Name": route_info.get("SPName", "Unknown"),
                "SuperEcode": route_info.get("SupCode", "Unknown"),
                "SuperName": route_info.get("SupName", "Unknown"),
                "CusCode": cus_code,
                "CusName": customer_map.get(cus_code, "Unknown"),
                "DisplayImages": images,
                "Active": route_info.get("Active", "N") # Added Active status
            })

        reports.append({
            "ProgramCode": prog_code,
            "ProgramName": program_name,
            "TimeFrame": time_frame,
            "Details": formatted_records
        })

    return {"reports": reports, "time_frame": time_frame}


@app.get("/api/reports")
def get_visibility_reports(
    period_type: str = "weekly",
    date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    result = build_visibility_reports(period_type, date, end_date, year, month)
    if "error" in result:
        return result
    return {"reports": result["reports"]}


def safe_sheet_name(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:\[\]]', '', name)
    return cleaned[:31] or "Sheet"


def safe_filename_part(label: str) -> str:
    return re.sub(r'[\/\s-]', '_', label)


def fetch_thumbnail(img_url: str, max_size=(110, 110)) -> Optional[Tuple[io.BytesIO, Tuple[int, int]]]:
    """
    Downloads and resizes an image, returning a PNG-encoded BytesIO buffer
    plus its pixel size. openpyxl needs a buffer (not a bare PIL Image) here
    - a PIL Image that has been through convert()/thumbnail() loses the
    `.fp` attribute openpyxl's image writer relies on.
    """
    try:
        response = requests.get(img_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return None
        img = PILImage.open(io.BytesIO(response.content))
        img = img.convert("RGB")
        img.thumbnail(max_size)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer, img.size
    except Exception as e:
        print(f" -> Failed to fetch/thumbnail image {img_url}: {e}")
        return None


HEADER_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
HEADER_FONT = Font(bold=True)
COLUMNS = ["Date", "SaleMan", "RouteCode", "SM_Name", "SuperEcode", "SuperName", "CusCode", "CusName"]
IMAGE_COL_WIDTH = 16
IMAGE_ROW_HEIGHT = 86
THUMB_SIZE = (105, 105)


def build_report_sheet(wb: Workbook, report: dict, report_type: str):
    ws = wb.create_sheet(title=safe_sheet_name(report["ProgramName"]))

    details = report["Details"]
    max_images = 1
    if report_type == "Detail":
        max_images = max((len(row.get("DisplayImages", [])) for row in details), default=1) or 1

    # Header row
    for col_idx, header in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL

    first_image_col = len(COLUMNS) + 1
    last_image_col = first_image_col + max_images - 1
    ws.cell(row=1, column=first_image_col, value="Display Images").font = HEADER_FONT
    ws.cell(row=1, column=first_image_col).fill = HEADER_FILL
    if last_image_col > first_image_col:
        ws.merge_cells(start_row=1, start_column=first_image_col, end_row=1, end_column=last_image_col)

    for col_idx in range(first_image_col, last_image_col + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = IMAGE_COL_WIDTH

    # Data rows
    for row_idx, row in enumerate(details, start=2):
        ws.cell(row=row_idx, column=1, value=row["Date"])
        ws.cell(row=row_idx, column=2, value=row["SaleMan"])
        ws.cell(row=row_idx, column=3, value=row["RouteCode"])
        ws.cell(row=row_idx, column=4, value=row["SM_Name"])
        ws.cell(row=row_idx, column=5, value=row["SuperEcode"])
        ws.cell(row=row_idx, column=6, value=row["SuperName"])
        ws.cell(row=row_idx, column=7, value=row["CusCode"])
        ws.cell(row=row_idx, column=8, value=row["CusName"])

        if report_type == "Detail":
            ws.row_dimensions[row_idx].height = IMAGE_ROW_HEIGHT
            for img_idx, img_url in enumerate(row.get("DisplayImages", [])):
                thumb = fetch_thumbnail(img_url, THUMB_SIZE)
                if thumb is None:
                    continue
                buffer, size = thumb
                xl_img = XLImage(buffer)
                xl_img.width, xl_img.height = size
                col_letter = get_column_letter(first_image_col + img_idx)
                ws.add_image(xl_img, f"{col_letter}{row_idx}")
        else:
            cell = ws.cell(
                row=row_idx,
                column=first_image_col,
                value=f"{report['ProgramName']} visibility\nActive: {row.get('Active', 'N')}",
            )
            cell.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
            cell.font = Font(bold=True)
            ws.row_dimensions[row_idx].height = 40

    for col_idx in range(1, len(COLUMNS) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 16


@app.get("/api/reports/export-excel")
def export_reports_excel(
    period_type: str = "weekly",
    date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    report_type: str = "Detail",
    program: str = "All",
):
    result = build_visibility_reports(period_type, date, end_date, year, month)
    if "error" in result:
        return result

    reports = result["reports"]
    if program != "All":
        reports = [r for r in reports if r["ProgramCode"] == program]

    wb = Workbook()
    wb.remove(wb.active)

    if not reports:
        wb.create_sheet(title="No Data")
    else:
        for report in reports:
            build_report_sheet(wb, report, report_type)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    safe_label = safe_filename_part(result["time_frame"])
    filename = f"Report_{safe_label}_{report_type}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000)