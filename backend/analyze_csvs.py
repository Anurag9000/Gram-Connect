import csv
import os
import pandas as pd

def analyze_csvs():
    p1_path = r"backend/people_2.csv"
    p2_path = r"data/people.csv"
    
    # Resolve relative paths relative to script location or just use full paths if possible
    # Since I am in the root or backend, let's be safe.
    base_dir = r"d:/Finished Projects/Resume/SocialCode"
    p1_path = os.path.join(base_dir, p1_path)
    p2_path = os.path.join(base_dir, p2_path)
    
    output_file = os.path.join(base_dir, "analysis_output.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Analyzing:\n1. {p1_path}\n2. {p2_path}\n\n")
        
        try:
            df1 = pd.read_csv(p1_path)
            df2 = pd.read_csv(p2_path)
        except Exception as e:
            f.write(f"Error reading CSVs: {e}\n")
            return

        f.write(f"--- Schema Comparison ---\n")
        f.write(f"people_2.csv columns: {list(df1.columns)}\n")
        f.write(f"people.csv   columns: {list(df2.columns)}\n")
        
        common = set(df1.columns).intersection(set(df2.columns))
        only_p1 = set(df1.columns) - set(df2.columns)
        only_p2 = set(df2.columns) - set(df1.columns)
        
        f.write(f"Common columns: {common}\n")
        f.write(f"Only in people_2.csv: {only_p1}\n")
        f.write(f"Only in people.csv:   {only_p2}\n")
        
        f.write(f"\n--- Statistics ---\n")
        f.write(f"people_2.csv row count: {len(df1)}\n")
        f.write(f"people.csv   row count: {len(df2)}\n")
        
        f.write(f"\n--- ID Analysis ---\n")
        # Normalize IDs: Remove leading 'U' and leading zeros to compare numeric part
        def norm_id(pid):
            if pd.isna(pid): return None
            pid_str = str(pid).strip().upper()
            if pid_str.startswith('U'):
                try:
                    return int(pid_str[1:])
                except ValueError:
                    return pid_str
            return pid_str

        df1['norm_id'] = df1['person_id'].apply(norm_id)
        df2['norm_id'] = df2['person_id'].apply(norm_id)
        
        ids1 = set(df1['norm_id'].dropna())
        ids2 = set(df2['norm_id'].dropna())
        
        overlap = ids1.intersection(ids2)
        f.write(f"Unique normalized IDs in people_2.csv: {len(ids1)}\n")
        f.write(f"Unique normalized IDs in people.csv:   {len(ids2)}\n")
        f.write(f"Overlapping IDs: {len(overlap)}\n")
        
        if len(overlap) > 0:
            sample_id = list(overlap)[0]
            row1 = df1[df1['norm_id'] == sample_id].iloc[0]
            row2 = df2[df2['norm_id'] == sample_id].iloc[0]
            f.write(f"\nSample Overlapping Record (ID {sample_id}):\n")
            f.write(f"people_2.csv original ID: {row1['person_id']}\n")
            f.write(f"people.csv   original ID: {row2['person_id']}\n")
            f.write(f"Names: '{row1['name']}' vs '{row2['name']}'\n")
            
            # Check if text is same
            if row1['text'] == row2['text']:
                f.write("Text content matches exactly for sample record.\n")
            else:
                f.write("Text content differs for sample record.\n")
                f.write(f"P2_2 Text Snippet: {str(row1['text'])[:100]}...\n")
                f.write(f"People Text Snippet: {str(row2['text'])[:100]}...\n")

        f.write(f"\n--- Coverage Analysis ---\n")
        if ids1.issubset(ids2):
            f.write("people_2.csv is a subset of people.csv (by normalized IDs).\n")
        elif ids2.issubset(ids1):
            f.write("people.csv is a subset of people_2.csv (by normalized IDs).\n")
        else:
            f.write("Neither file is a strict subset of the other.\n")
    print(f"Results written to {output_file}")


if __name__ == "__main__":
    analyze_csvs()
