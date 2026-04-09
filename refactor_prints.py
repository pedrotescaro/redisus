import re

with open("heal_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Replace prints with loggers
# Replace print("... Erro ...")
text = re.sub(r'print\(\s*(f?"[^"]*Erro[^"]*")\s*\)', r'logger.exception(\1)', text)
# Replace print(f"... Erro ... {e}")
text = re.sub(r'print\(\s*(f?"[^"]*Erro[^"]*\{e\}[^"]*")\s*\)', r'logger.exception(\1)', text)
# Fallback print to logger.info
text = re.sub(r'print\(', r'logger.info(', text)

with open("heal_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Print replacements done.")
