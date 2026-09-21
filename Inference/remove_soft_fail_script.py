import json
import sys
import os

if len(sys.argv) != 2:
    print("Usage: python script.py <input_file>")
    sys.exit(1)

file_path = sys.argv[1]
temp_path = file_path + ".tmp"

with open(file_path, "r") as infile:
    text = infile.read()

decoder = json.JSONDecoder()
pos = 0

with open(temp_path, "w") as outfile:
    while pos < len(text):
        # Skip whitespace
        while pos < len(text) and text[pos].isspace():
            pos += 1
        
        if pos >= len(text):
            break
        
        record, offset = decoder.raw_decode(text, pos)
        pos = offset

        if record.get("RAG_status") != "soft_fail":
            outfile.write(json.dumps(record) + "\n")

# Replace original file safely
os.replace(temp_path, file_path)

print(f"Updated file saved: {file_path}")