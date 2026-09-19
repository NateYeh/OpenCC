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
    shutil.copy2(lib, os.path.join(plugins, LIB_NAME))
    print(f'安裝外掛 -> {plugins}/{LIB_NAME}')

    run([
        sys.executable,
        os.path.join(HERE, 'build_mpdp_dict.py'),
        '--output', os.path.join(dict_dir, 'jieba_mpdp.dict.utf8'),
        '--phrase-freq', str(args.phrase_freq),
        '--repo-root', REPO_ROOT,
    ])

    config_src = os.path.join(REPO_ROOT, 'data', 'overlay', 's2twp-custom-mpdp.json')
    if os.path.isfile(config_src):
        shutil.copy2(config_src, os.path.join(share, 's2twp-custom-mpdp.json'))
        print(f'安裝設定 -> {share}/s2twp-custom-mpdp.json')

    print('\n完成。驗證：')
    check = subprocess.run(
        [sys.executable, '-c',
         'from opencc import OpenCC;'
         'print(OpenCC("s2twp-custom-mpdp").convert("医生发出，断发纹身"))'],
        capture_output=True, text=True)
    print(' ', check.stdout.strip() or check.stderr.strip())
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
