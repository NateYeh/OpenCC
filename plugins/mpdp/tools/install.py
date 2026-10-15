#!/usr/bin/env python3
"""建置並安裝 MPDP 分割外掛（build + dict + config 一次完成）。

安裝目標為「目前 Python 環境所用的 opencc 套件」：
  <site-packages>/opencc/clib/opencc/plugins/libopencc-mpdp.so   ← 外掛本體
  <site-packages>/opencc/clib/share/opencc/mpdp/jieba_mpdp.dict.utf8 ← 詞表
  <site-packages>/opencc/clib/share/opencc/s2twp-custom-mpdp.json    ← 設定

用法:
  python3 plugins/mpdp/tools/install.py            # 自動偵測 opencc 套件位置
  python3 plugins/mpdp/tools/install.py --uninstall
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(PLUGIN_ROOT))
BUILD_DIR = os.path.join(PLUGIN_ROOT, 'build')
LIB_NAME = 'libopencc-mpdp.so'


def opencc_share_dir() -> str:
    """回傳目前環境 opencc 套件的 share/opencc 目錄。"""
    import opencc  # 延後載入，才能給出清楚的錯誤訊息
    package_dir = os.path.dirname(os.path.abspath(opencc.__file__))
    return os.path.join(package_dir, 'clib', 'share', 'opencc')


def opencc_plugin_dir() -> str:
    """OpenCC 搜尋外掛的 <libdir>/opencc/plugins 目錄。"""
    share = opencc_share_dir()
    clib = os.path.dirname(os.path.dirname(share))  # .../clib
    return os.path.join(clib, 'opencc', 'plugins')


def run(cmd: list[str]) -> None:
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def atomic_copy(src: str, dst: str) -> None:
    """原子替換複製檔案（先寫同目錄暫存檔，再 os.replace）。

    以 shutil.copy2 直接覆寫是「就地截斷重寫同一 inode」；若目標是
    .so，已被執行中行程 dlopen（mmap）的話，該行程會執行到被換掉的
    程式碼頁而 SIGSEGV（2026-10-14 book_web 崩潰即此因）。
    原子替換讓執行中的行程續用舊 inode，新行程才會載入新版。

    Args:
        src: 來源檔案。
        dst: 目標路徑。
    """
    directory = os.path.dirname(dst)
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix='.mpdp-install-', dir=directory)
    os.close(fd)
    try:
        shutil.copy2(src, temp_path)
        os.replace(temp_path, dst)
    except BaseException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def build() -> str:
    os.makedirs(BUILD_DIR, exist_ok=True)
    lib = os.path.join(BUILD_DIR, LIB_NAME)
    run([
        'g++', '-std=c++17', '-O2', '-fPIC', '-shared',
        '-Wall', '-Wextra', '-Wno-unused-parameter',
        '-I', os.path.join(REPO_ROOT, 'src'),
        '-o', lib,
        os.path.join(PLUGIN_ROOT, 'src', 'MpdpPlugin.cpp'),
    ])
    return lib


def install(args: argparse.Namespace) -> int:
    share = opencc_share_dir()
    plugins = opencc_plugin_dir()
    dict_dir = os.path.join(share, 'mpdp')
    os.makedirs(plugins, exist_ok=True)
    os.makedirs(dict_dir, exist_ok=True)

    lib = build()
    atomic_copy(lib, os.path.join(plugins, LIB_NAME))
    print(f'安裝外掛 -> {plugins}/{LIB_NAME}')

    run([
        sys.executable,
        os.path.join(HERE, 'build_mpdp_dict.py'),
        '--output', os.path.join(dict_dir, 'jieba_mpdp.dict.utf8'),
        '--phrase-freq', str(args.phrase_freq),
        '--repo-root', REPO_ROOT,
    ])

    overlay_dir = os.path.join(REPO_ROOT, 'data', 'overlay')
    if os.path.isdir(overlay_dir):
        # overlay 字典是 runtime 讀取的 text 字典，**複製到站點目錄才會生效**。
        # 過去這一步靠人工 cp，漏抄就會出現「來源改了、實際沒生效」的假象。
        for name in sorted(os.listdir(overlay_dir)):
            src = os.path.join(overlay_dir, name)
            if os.path.isfile(src):
                atomic_copy(src, os.path.join(share, name))
        print(f'安裝 overlay 字典與設定 -> {share}/')

    user_src = os.path.join(HERE, 'data', 'user.dict.utf8')
    if os.path.isfile(user_src):
        atomic_copy(user_src, os.path.join(dict_dir, 'user.dict.utf8'))
        print(f'安裝使用者覆寫詞表 → {dict_dir}/user.dict.utf8')
        print(f'安裝設定 -> {share}/s2twp-custom-mpdp.json')

    print('\n完成。驗證：')
    check = subprocess.run(
        [sys.executable, '-c',
         'from opencc import OpenCC;'
         'print(OpenCC("s2twp-custom-mpdp").convert("医生发出，断发纹身"))'],
        capture_output=True, text=True)
    print(' ', check.stdout.strip() or check.stderr.strip())
    print('\n注意：已載入舊外掛的執行中行程仍在使用舊版（inode 未被動到），'
          '要讓服務吃到新版請重啟該服務（如 scripts/services.sh）。')
    return 0 if check.returncode == 0 else 1


def uninstall() -> int:
    share = opencc_share_dir()
    for path in [
        os.path.join(opencc_plugin_dir(), LIB_NAME),
        os.path.join(share, 's2twp-custom-mpdp.json'),
    ]:
        if os.path.isfile(path):
            os.remove(path)
            print(f'移除 {path}')
    dict_dir = os.path.join(share, 'mpdp')
    if os.path.isdir(dict_dir):
        shutil.rmtree(dict_dir)
        print(f'移除 {dict_dir}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--phrase-freq', type=int, default=100,
                        help='轉換詞條在 DP 中的權重（預設 100）')
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    return uninstall() if args.uninstall else install(args)


if __name__ == '__main__':
    raise SystemExit(main())
