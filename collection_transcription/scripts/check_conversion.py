import pandas as pd

# Load the CSV files into DataFrames
df1 = pd.read_csv('conversion.csv', header=None)  # Assuming no headers in file1
df2 = pd.read_csv('errorLog_Transcription3.csv', header=None)  # Assuming no headers in file2

# Filter out rows in File 2 that contain "Human-Events-Daily-with-Jack-Posobiec"
# df2_filtered = df2[~df2[2].str.contains("Human-Events-Daily-with-Jack-Posobiec")]


# Function to extract show name and ID from File 1's format (pod_The-Clay-Travis-and-Buck-Sexton-Show_7252.wav)
def extract_show_and_id_from_file1(file1_row):
    file1_str = file1_row[0]
    # Remove 'pod_' and '.wav', then split the string by '_' to get show name and ID
    cleaned_str = file1_str.replace('pod_', '').replace('.wav', '')
    parts = cleaned_str.rsplit('_', 1)  # Split from the right to separate show name and ID
    return parts[0], parts[1]

# Function to check if File 2 row exists in File 1
def is_match_in_file1(file2_row, df1):
    show2, id2 = file2_row[2], str(file2_row[3])  # Extract show name and ID from File 2

    for _, file1_row in df1.iterrows():
        show1, id1 = extract_show_and_id_from_file1(file1_row)  # Extract show and ID from File 1

        # Check if the show name and ID match exactly
        if show1 == show2 and id1 == id2:
            return True  # Match found
    return False  # No match

# Apply the matching function to each row in File 2
df2['Exists_in_File1'] = df2.apply(lambda row: is_match_in_file1(row, df1), axis=1)

# Rows in File 2 that have matches in File 1
matches = df2[df2['Exists_in_File1'] == True]
print("Matching rows in File 2 (exist in File 1):\n", matches)

# Rows in File 2 that don't have matches in File 1
non_matches = df2[df2['Exists_in_File1'] == False]
print("Non-matching rows in File 2 (don't exist in File 1):\n", non_matches)