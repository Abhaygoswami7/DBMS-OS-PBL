import os

def is_emoji(char):
    cp = ord(char)
    # Emoji ranges
    return (
        0x1F300 <= cp <= 0x1F5FF or
        0x1F600 <= cp <= 0x1F64F or
        0x1F680 <= cp <= 0x1F6FF or
        0x1F700 <= cp <= 0x1F77F or
        0x1F780 <= cp <= 0x1F7FF or
        0x1F800 <= cp <= 0x1F8FF or
        0x1F900 <= cp <= 0x1F9FF or
        0x1FA00 <= cp <= 0x1FA6F or
        0x1FA70 <= cp <= 0x1FAFF or
        0x2600 <= cp <= 0x26FF or
        0x2700 <= cp <= 0x27BF
    )

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
total_emojis = 0

print("=== EMOJI AUDIT RESULTS ===")
for root, _, files in os.walk(frontend_dir):
    for f in sorted(files):
        if f.endswith((".html", ".js", ".css")):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as fp:
                text = fp.read()
            emojis = [c for c in text if is_emoji(c)]
            count = len(emojis)
            total_emojis += count
            print(f"File: {f:<25} Emojis Found: {count}")

print("----------------------------")
print(f"TOTAL EMOJIS DETECTED: {total_emojis}")
