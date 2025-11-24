# ai_module/punctuation_fixer.py

def suggest_punctuation(text):
    text = text.strip()
    if not text:
        return text

    # Zaten noktalama içeriyorsa dokunma
    if text[-1] in [".", "!", "?"]:
        return text

    # Soru kelimeleri varsa soru işareti koy
    question_words = ["mi", "mı", "mu", "mü", "kim", "ne", "nasıl", "neden", "niye", "hangi", "nerede"]
    lower = text.lower()

    if any(lower.endswith(" " + w) or lower.endswith(w) for w in question_words):
        return text + "?"

    # Ünlem gerektiren kelimeler
    exclaim_words = ["aman", "hey", "oha", "yuh", "vay"]
    if any(lower.startswith(w) for w in exclaim_words):
        return text + "!"

    # Default: nokta ekle
    return text + "."

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
