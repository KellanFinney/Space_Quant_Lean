import pandas as pd 
import kagglehub
import re 
import os

path = kagglehub.dataset_download("dadalyndell/elon-musk-tweets-2010-to-2025-march")
print(f"Dataset downloaded to: {path}")

# The downloaded dataset is extracted to a directory, we need to find the CSV file
csv_path = os.path.join(path, "all_musk_posts.csv")  # Use the main posts file

df = pd.read_csv(csv_path, encoding='latin-1', low_memory=False)

# Select the relevant columns: createdAt (timestamp) and fullText (tweet content)
df = df[["createdAt", "fullText"]]
df.columns = ["Time", "Tweet"]  # Rename to match your expected names

# Convert Time to datetime and sort chronologically (oldest first)
df['Time'] = pd.to_datetime(df['Time'])
df = df.sort_values('Time').reset_index(drop=True)

# Remove rows with NaN tweets
df = df.dropna(subset=['Tweet'])

# Remove URLs from tweets
def remove_urls(text):
    if pd.isna(text):
        return text
    return re.sub(r'https?://[^\s]+', '', str(text)).strip()

df['Tweet'] = df['Tweet'].apply(remove_urls)

# Remove empty tweets after URL removal
df = df[df['Tweet'].str.len() > 0]

print(f"Total tweets after cleaning: {len(df)}")
print(f"Date range: {df['Time'].min()} to {df['Time'].max()}")
print(f"\nSample from beginning:")
print(df.head())
print(f"\nSample from end:")
print(df.tail())

# Save to the Data directory
output_path = "/Users/kfinney89/Documents/QuantConnect/Data/2010_2025muskTweetsPreProcessed.csv"
df.to_csv(output_path, index=False)
print(f"\nSaved to: {output_path}")
