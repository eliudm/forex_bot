import re

# Fix every single file that could have confidence hardcoded
files = [
    'main_bot.py',
    'ai_engine/enhanced_engine.py', 
    'ai_engine/strategy_engine.py',
    'config/settings.py',
]

for fpath in files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            code = f.read()
        original = code
        code = re.sub(r'0\.65', '0.40', code)
        code = re.sub(r'0\.60', '0.40', code)
        code = re.sub(r'65%', '40%', code)
        code = re.sub(r'60%', '40%', code)
        if code != original:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(code)
            print(f'Fixed: {fpath}')
        else:
            print(f'No change needed: {fpath}')
    except Exception as e:
        print(f'Error on {fpath}: {e}')

print('All done - confidence set to 40%')