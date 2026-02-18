"""
Download RKLB historical data from Yahoo Finance and convert to LEAN format
"""
import yfinance as yf
import pandas as pd
import os
import zipfile

def download_and_save(ticker, start_date, end_date, output_dir):
    """Download data for a ticker and save in LEAN daily format"""
    print(f"Downloading {ticker} data from Yahoo Finance...")
    
    stock = yf.Ticker(ticker)
    data = stock.history(start=start_date, end=end_date, interval="1d")
    
    if data.empty:
        print(f"No data found for {ticker}")
        return
    
    print(f"Downloaded {len(data)} rows for {ticker}")
    print(f"Date range: {data.index[0]} to {data.index[-1]}")
    print(f"Sample data:\n{data.head()}")
    
    # Reset index to avoid alignment issues
    data = data.reset_index()
    
    # Create LEAN directory structure
    os.makedirs(output_dir, exist_ok=True)
    
    # Convert to LEAN format (datetime, open, high, low, close, volume)
    # LEAN expects: YYYYMMDD HH:MM for daily data
    # LEAN expects prices in 10000x format for equities
    lean_data = pd.DataFrame({
        'datetime': data['Date'].dt.strftime('%Y%m%d 00:00'),
        'open': (data['Open'] * 10000).round().astype(int),
        'high': (data['High'] * 10000).round().astype(int),
        'low': (data['Low'] * 10000).round().astype(int),
        'close': (data['Close'] * 10000).round().astype(int),
        'volume': data['Volume'].astype(int)
    })
    
    print(f"\nConverted data sample:\n{lean_data.head()}")
    
    # Save as zipped CSV (LEAN format)
    csv_content = lean_data.to_csv(index=False, header=False)
    zip_path = os.path.join(output_dir, f"{ticker.lower()}.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{ticker.lower()}.csv", csv_content)
    
    print(f"\nSaved {len(lean_data)} rows to {zip_path}")

# Download RKLB daily data (went public Aug 25, 2021 via SPAC)
download_and_save(
    "RKLB", 
    "2021-08-25",
    "2025-04-15",
    "/Users/kfinney89/Documents/QuantConnect/Data/equity/usa/daily"
)

print("\nDone! RKLB daily data is ready for LEAN.")
