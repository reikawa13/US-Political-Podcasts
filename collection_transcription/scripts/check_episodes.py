import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Load CSV files
def load_csv(file_path):
    df = pd.read_csv(file_path, dtype=str)
    df = df[['podName', 'date']]
    df['date'] = pd.to_datetime(df['date'], utc=True, errors='coerce')
    return df

# Load all datasets
files = ["final_podMetadata_June.csv", "final_podMetadata_beforeNov5.csv", "podMetadata_Nov5_After.csv"]
df_list = [load_csv(file) for file in files]
df = pd.concat(df_list)

# Pivot the data
pivot_df = df.pivot_table(index='podName', columns=df['date'].dt.date, aggfunc=lambda x: 1, fill_value=0)

# Split the plot into multiple pages if necessary
rows_per_page = 50  # Adjust the number of podcast series per page
num_pages = int(np.ceil(len(pivot_df) / rows_per_page))

# Expand x-axis by increasing figure width
fig_width = 60  # 5 times wider
tick_interval = max(1, len(pivot_df.columns) // 20)  # Show fewer x-axis labels

for page in range(num_pages):
    start_idx = page * rows_per_page
    end_idx = min((page + 1) * rows_per_page, len(pivot_df))
    
    plt.figure(figsize=(fig_width, 8))  # Make the figure wider
    plt.imshow(pivot_df.iloc[start_idx:end_idx], aspect='auto', cmap='gray_r')

    # Labeling
    plt.xlabel("Date")
    plt.ylabel("Podcast Series")
    plt.title(f"Podcast Episode Availability by Date (Page {page + 1})")

    # Show fewer x-ticks to avoid clutter
    x_positions = np.arange(len(pivot_df.columns))
    x_labels = pivot_df.columns
    plt.xticks(x_positions[::tick_interval], x_labels[::tick_interval], rotation=45, ha="right")

    plt.yticks(range(end_idx - start_idx), pivot_df.index[start_idx:end_idx], fontsize=8)

    # Save each page separately
    plt.savefig(f"podcast_episode_availability_page_{page + 1}.png", dpi=300, bbox_inches="tight")
    plt.close()  # Close the figure to avoid overlapping plots

print(f"Saved {num_pages} pages of plots.")
s