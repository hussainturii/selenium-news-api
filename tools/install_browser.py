"""Install matching official Chrome for Testing and ChromeDriver releases."""
import argparse
from pathlib import Path
import shutil
import stat
import tempfile
import urllib.request
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--version', required=True)
args = parser.parse_args()
destination = Path('/opt/chrome')
destination.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as temporary:
    for binary in ('chrome', 'chromedriver'):
        url = f'https://storage.googleapis.com/chrome-for-testing-public/{args.version}/linux64/{binary}-linux64.zip'
        archive = Path(temporary) / f'{binary}.zip'
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as package:
            package.extractall(destination)
            for info in package.infolist():
                target = destination / info.filename
                mode = info.external_attr >> 16
                if mode and target.is_file():
                    target.chmod(mode)
driver = destination / 'chromedriver-linux64' / 'chromedriver'
driver.chmod(driver.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
shutil.copy2(driver, '/usr/local/bin/chromedriver')
chrome = destination / 'chrome-linux64' / 'chrome'
chrome.chmod(chrome.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
