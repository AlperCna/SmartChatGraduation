import pandas as pd

# -----------------------------------------
# 1. Define heuristic rules
# -----------------------------------------

INFORMAL_PRONOUNS = ["ben", "sen"]
FORMAL_PRONOUNS = ["biz", "siz"]

# informal slang, fillers, emojis, casual style markers
INFORMAL_LEXICAL = [
    "kanka", "abi", "abla", "ya", "lan", "lol",
    "bro", "kardeş", "😂", "😅", "🙂", "😉",
    "moruk", "şaka", "yaa", "napıyorsun", "ne yapıyon"
]

# formal expressions, polite terms, bureaucratic language
FORMAL_LEXICAL = [
    "sayın", "lütfen", "rica", "tarafından", "gerek",
    "bilgilendirmek", "edilmiştir", "uygun", "tez zamanda",
    "yardım", "iletmek isterim", "dikkate alınız"
]


def contains_any(text, words):
    """Check if any word from the list exists in the text (case-insensitive)."""
    t = text.lower()
    return any(w in t for w in words)


# -----------------------------------------
# 2. Apply rules to classify formal/informal
# -----------------------------------------

def heuristic_label(text):
    t = text.lower().strip()

    # Pronoun rules (strong indicators)
    if contains_any(t, INFORMAL_PRONOUNS):
        return "informal"
    if contains_any(t, FORMAL_PRONOUNS):
        return "formal"

    # Lexical slang / casual markers
    if contains_any(t, INFORMAL_LEXICAL):
        return "informal"

    # Polite / bureaucratic markers
    if contains_any(t, FORMAL_LEXICAL):
        return "formal"

    # If none matched → ambiguous
    return None


# -----------------------------------------
# 3. Pipeline
# -----------------------------------------

def clean_dataset(input_csv, output_csv):
    df = pd.read_csv(input_csv)

    # Remove neutral class if present
    if "label" in df.columns:
        df = df[df["label"] != "neutral"]

    df["text"] = df["text"].astype(str)

    results = []

    for _, row in df.iterrows():
        text = row["text"]
        label = heuristic_label(text)

        # Drop ambiguous sentences
        if label is not None:
            results.append({"text": text, "label": label})

    # Final DataFrame
    cleaned = pd.DataFrame(results)

    # Shuffle for training
    cleaned = cleaned.sample(frac=1, random_state=42).reset_index(drop=True)

    # Save output
    cleaned.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print(f"Saved → {output_csv}")
    print("\nClass distribution:")
    print(cleaned["label"].value_counts())


# -----------------------------------------
# 4. Run
# -----------------------------------------

if __name__ == "__main__":
    clean_dataset(
        input_csv="StyleAdapterDataset_Final_Balanced.csv",
        output_csv="clean_formal_informal_dataset.csv"
    )
