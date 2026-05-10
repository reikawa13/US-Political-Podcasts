# import pandas as pd

# Load the CSV file
# file_path = 'podcast_rankings.csv'  # Replace with your local file path
# data = pd.read_csv(file_path)

# Define the column to search for matches (column 11 in zero-indexed terms)
# target_column = data.columns[28]  # Adjust if column 11 isn't the target column
# target_values = data[target_column].tolist()

# Apply highlighting
# highlighted_data = data.style.applymap(lambda x: 'background-color: yellow' if x in target_values else '')

# Save as an HTML file
# output_path = 'highlighted_output.html'  # Specify your desired output path
# highlighted_data.to_html(output_path)

# print(f"Highlighted HTML saved at {output_path}")


import pandas as pd

# Load the CSV file
file_path = 'podcast_rankings.csv'  # Replace with your local file path
data = pd.read_csv(file_path)

# Define the column to search for matches (column 11 in zero-indexed terms)
target_column = data.columns[28]  # Column 11 in one-indexed terms
target_values = data[target_column].tolist()

# Create a copy of the data to insert the count row
data_with_count = pd.concat([pd.DataFrame([[''] * data.shape[1]], columns=data.columns), data], ignore_index=True)

# Count matches per column and place in the second row
for col in data.columns:
    data_with_count.at[1, col] = sum(data[col].isin(target_values))

# Apply styling to highlight matching cells
highlighted_data = data_with_count.style.applymap(
    lambda x: 'background-color: yellow' if x in target_values else '',
    subset=pd.IndexSlice[2:, :]
)

# Save as an HTML file
output_path = 'highlighted_output.html'  # Specify your desired output path
highlighted_data.to_html(output_path)

print(f"Highlighted HTML with counts saved at {output_path}")

