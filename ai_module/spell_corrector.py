# ai_module/spell_corrector.py

import language_tool_python

# İngilizce dil denetleyicisi
tool = language_tool_python.LanguageTool('en-US')

def correct_spelling(text):
    """
    Spelling and grammar correction for English text.
    """
    matches = tool.check(text)
    corrected_text = language_tool_python.utils.correct(text, matches)
    return corrected_text


# Örnek test bloğu
if __name__ == "__main__":
    example_text = "I has a bad grammer and speling in thiss sentence."
    print("🔤 Original :", example_text)
    print("✅ Corrected:", correct_spelling(example_text))
