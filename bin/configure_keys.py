"""Open private API settings locally; never print or inspect existing values."""
from pathlib import Path
import os
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from kildeanalyse.credentials import prepare_file

if __name__ == '__main__':
    path = prepare_file()
    print(f'Private settings file: {path}')
    print('Fill only the keys you want to use. Save and close. Do not share the completed file.')
    if os.name == 'nt':
        subprocess.Popen(['notepad.exe',str(path)])
