"""
Purpose:
The purpose of this script is to conduct metadata and transcript validation.

Author:
Reishiro Kawakami
"""
import csv
import pandas as pd
import re
from typing import List, Tuple

metadata = "copy_final_podMetadata.csv"
HHMMSS = re.compile(r"^\s*(\d+):([0-5]?\d):([0-5]?\d)\s*$")  # 00:56:00
MMSS   = re.compile(r"^\s*([0-5]?\d):([0-5]?\d)\s*$")        # 22:38
INTSEC = re.compile(r"^\s*(\d+)\s*$")                        # 3018

def find_other_duration_formats(
    csv_path: str,
    duration_field: str = "duration",
) -> List[Tuple[int, str]]:
    """
    Returns a list of (row_number, raw_duration) for rows whose
    duration format is NOT hh:mm:ss, mm:ss, or integer seconds.

    Row numbers correspond to the CSV file line numbers
    (header = line 1).
    """
    bad_rows = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames or duration_field not in reader.fieldnames:
            raise KeyError(f"Missing '{duration_field}' column")

        for line_no, row in enumerate(reader, start=2):  # header is line 1
            raw = str(row.get(duration_field, "")).strip()

            if raw == "":
                continue  # treat empty as OK; remove this if you want to flag it

            if HHMMSS.match(raw) or MMSS.match(raw) or INTSEC.match(raw):
                continue

            bad_rows.append((line_no, raw))

    return bad_rows

def duration_to_seconds(duration: str) -> int:
    """Convert hh:mm:ss | mm:ss | seconds → integer seconds."""
    s = str(duration).strip()

    m = HHMMSS.match(s)
    if m:
        h, m_, s_ = map(int, m.groups())
        return h * 3600 + m_ * 60 + s_

    m = MMSS.match(s)
    if m:
        m_, s_ = map(int, m.groups())
        return m_ * 60 + s_

    if INTSEC.match(s):
        return int(s)

    raise ValueError(f"Unexpected duration format: {duration!r}")

def update_duration_and_write_csv(
    input_csv: str,
    output_csv: str,
    duration_col: str = "duration",
):
    """
    Reads input_csv, converts the `duration` column to integer seconds,
    and writes the result to output_csv.
    """
    with open(input_csv, newline="", encoding="utf-8") as fin:
        reader = csv.DictReader(fin)

        if duration_col not in reader.fieldnames:
            raise KeyError(f"'{duration_col}' column not found")

        fieldnames = reader.fieldnames  # preserve column order

        with open(output_csv, "w", newline="", encoding="utf-8") as fout:
            writer = csv.DictWriter(fout, fieldnames=fieldnames)
            writer.writeheader()

            for line_no, row in enumerate(reader, start=2):
                try:
                    row[duration_col] = str(duration_to_seconds(row[duration_col]))
                    writer.writerow(row)
                except Exception as e:
                    raise RuntimeError(
                        f"Error on line {line_no}: duration={row.get(duration_col)!r}"
                    ) from e

def main():
    """
    The main function of the script.
    Contains the primary logic to be executed.
    """
    # check_series()
    # check_fields()
    # add_leanings_and_split()
    # extract_bad_rows()
    # remove_bad_cols()
    # remove_trailing_commas("copy_final_podMetadata.csv", "output.csv")
    # bad = find_other_duration_formats("podMetadata_Nov5_with_leaning.csv")
    # print(bad)
    update_duration_and_write_csv("podMetadata_Nov5_with_leaning.csv", "podcasts_duration_seconds.csv")

    return

if __name__ == "__main__":
    main()


################### Archive Functions #######################

def check_blank():
    """
    Check for blank entries in the metadata file.
    """
    with open(metadata, 'r', encoding='utf-8') as file:
        datareader = csv.reader(file)
        datareader.__next__()
        count = 0
        for row in datareader:
            if row[7] != "":
                print(row[7])
                count += 1
        print("non-blank count: ", count) 

def check_keyword():
    """
    Check for blank entries in the metadata file.
    """
    with open(metadata, 'r', encoding='utf-8') as file:
        datareader = csv.reader(file)
        datareader.__next__()
        count = 0
        for row in datareader:
            if row[8] != "Not Available":
                print(row[7])
                count += 1
        print("Keyword count: ", count) 

def delete_blank():
    """
    Delete blank entries from the metadata file and save to a new file.
    """
    df = pd.read_csv(metadata)
    df_cleaned = df[df['blank'].notna()]  # Replace 'column_name' with the actual column name to check
    df_cleaned.to_csv('cleaned_metadata.csv', index=False)  

# def check_fields():
#     fields = ["ID", "podName", "epNum", "date","duration", "title", "guid", "description"]

#     with open(metadata, newline="", encoding="utf-8") as f:
#         reader = csv.DictReader(f)

#         # 1. Check header
#         if reader.fieldnames != fields:
#             raise ValueError(
#                 f"Header mismatch!\n"
#                 f"Expected: {fields}\n"
#                 f"Found:    {reader.fieldnames}"
#             )

#         # 2. Check rows
#         bad_rows = []
#         for i, row in enumerate(reader, start=2):  # row 2 = first data row
#             missing = [k for k in fields if not row.get(k)]
#             if missing:
#                 bad_rows.append((i, missing))

#         if bad_rows:
#             for row_num, missing in bad_rows:
#                 print(f"Row {row_num} missing values for: {missing}")
#             raise ValueError("CSV validation failed")
#         else:
#             print("All rows are valid")  

def check_series():
    seen = set()

    with open(metadata, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header

        for row in reader:
            val = row[1]
            if val not in seen:
                seen.add(val)
                print(val)

def add_leanings():    
    with open("copy_final_podMetadata.csv" , newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            # If there are extra columns, they appear under the None key
            extras = row.get(None)
            if extras:
                # In your case it's just [''] from a trailing comma, so drop it
                if all(x == "" for x in extras):
                    row.pop(None, None)
                else:
                    # If it's not empty, keep track because that's a real parsing problem
                    print(f"Row {i} has non-empty extra columns: {extras}")
                    row.pop(None, None)  # or raise an error
            
            if None in row:
                print("Bad row at line:", i)
                print("Extra pieces:", row[None])
                break
    
    return
    
    # File paths
    episodes_csv = "copy_final_podMetadata.csv"          # first CSV
    leanings_csv = "podName&Leaning.csv"  # second CSV
    output_csv = "episodes_with_leaning.csv"

    # --------------------------------------------------
    # Step 1: Load podName -> political leaning mapping
    # --------------------------------------------------
    pod_to_leaning = {}

    with open(leanings_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pod_name = row["podName"].strip()
            leaning = row["Leaning"].strip()
            pod_to_leaning[pod_name] = leaning

    # --------------------------------------------------
    # Step 2: Read episodes and add political_leaning
    # --------------------------------------------------
    with open(episodes_csv, newline="", encoding="utf-8") as infile, \
        open(output_csv, "w", newline="", encoding="utf-8") as outfile:

        reader = csv.DictReader(infile)

        # Add new column to existing fields
        fieldnames = reader.fieldnames + ["political_leaning"]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)

        writer.writeheader()

        for row in reader:
            pod_name = row["podName"].strip()
            row["political_leaning"] = pod_to_leaning.get(pod_name, "Unknown")
            writer.writerow(row)

    print(f"Done! Output written to {output_csv}")

def add_leanings_and_split(): 
    episodes_csv = "output.csv"
    leanings_csv = "podName&Leaning.csv"

    good_output = "episodes_with_leaning.csv"
    bad_output = "episodes_bad_rows.csv"
        # ---------------------------
    # Load podName -> leaning map
    # ---------------------------
    pod_to_leaning = {}
    with open(leanings_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pod_to_leaning[row["podName"].strip()] = row["Leaning"].strip()

    # ---------------------------
    # Open files
    # ---------------------------
    with open(episodes_csv, newline="", encoding="utf-8") as infile, \
         open(good_output, "w", newline="", encoding="utf-8") as good_f, \
         open(bad_output, "w", newline="", encoding="utf-8") as bad_f:

        reader = csv.DictReader(infile)

        # Good rows: add political_leaning
        good_fields = list(reader.fieldnames or []) + ["political_leaning"]
        good_writer = csv.DictWriter(
            good_f,
            fieldnames=good_fields,
            extrasaction="ignore",
        )
        good_writer.writeheader()

        # Bad rows: keep original fields + an "extra_fields" column
        bad_fields = list(reader.fieldnames or []) + ["extra_fields"]
        bad_writer = csv.DictWriter(
            bad_f,
            fieldnames=bad_fields,
            extrasaction="ignore",
        )
        bad_writer.writeheader()

        # ---------------------------
        # Process rows
        # ---------------------------
        for i, row in enumerate(reader, start=2):
            extras = row.get(None)

            # Trailing-comma case: extras == ['']
            if extras:
                row_copy = dict(row)
                row_copy["extra_fields"] = extras
                row_copy.pop(None, None)
                bad_writer.writerow(row_copy)
                continue

            pod = (row.get("podName") or "").strip()
            row["political_leaning"] = pod_to_leaning.get(pod, "Unknown")
            good_writer.writerow(row)

    print("Done.")
    print(f"Good rows  → {good_output}")
    print(f"Bad rows   → {bad_output}")

def extract_bad_rows():
    input_csv = "copy_final_podMetadata.csv"
    bad_output = "episodes_bad_rows.csv"
    with open(input_csv, newline="", encoding="utf-8") as infile, \
         open(bad_output, "w", newline="", encoding="utf-8") as bad_f:

        reader = csv.DictReader(infile)

        # Original columns + debug info
        fieldnames = list(reader.fieldnames or []) + ["extra_fields", "source_line"]
        writer = csv.DictWriter(bad_f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for line_no, row in enumerate(reader, start=2):
            extras = row.get(None)

            # Only treat as bad if extras exist AND at least one is non-empty
            if extras and any(x not in ("", None) for x in extras):
                bad_row = dict(row)
                bad_row["extra_fields"] = extras
                bad_row["source_line"] = line_no
                bad_row.pop(None, None)
                writer.writerow(bad_row)

    print(f"Done. Bad rows written to {bad_output}")

def remove_bad_cols():
    input_csv = "episodes_bad_rows.csv"
    output_csv = "episodes_no_audio.csv"

    AUDIO_COL_INDEX = 7  # 0-based index

    with open(input_csv, newline="", encoding="utf-8") as infile, \
        open(output_csv, "w", newline="", encoding="utf-8") as outfile:

        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        for row in reader:
            # drop audio URL
            if len(row) > AUDIO_COL_INDEX:
                row = row[:AUDIO_COL_INDEX] + row[AUDIO_COL_INDEX + 1 :]

            # drop last column (source_line)
            if len(row) > 0:
                row = row[:-1]

            writer.writerow(row)

def remove_trailing_commas(input_csv, output_csv):
    """
    Remove a trailing comma at the end of each line in a CSV file, if present.
    Safe for quoted fields containing commas.
    """
    with open(input_csv, encoding="utf-8") as fin, \
         open(output_csv, "w", encoding="utf-8", newline="") as fout:
        for line in fin:
            fout.write(line.rstrip("\n").rstrip(",") + "\n")