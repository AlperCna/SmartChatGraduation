# ai_module/punctuation_fixer.py

def suggest_punctuation(text):
    """
    Adds a period to the end of the sentence if missing.
    Handles common sentence-ending punctuation.
    """
    text = text.strip()
    if not text:
        return text

    if text[-1] not in [".", "!", "?"]:
        return text + "."
    return text


# Test amaçlı
if __name__ == "__main__":
    examples = [
        "This is a complete sentence",
        "What is your name",
        "Hello!",
        "",
        "Already done."
    ]

    for e in examples:
        print(f"📝 Input : {e}")
        print(f"✅ Output: {suggest_punctuation(e)}\n")
