#!/usr/bin/env python3
"""產生 MPDP 分割外掛用的合併詞表。

分割先決定段落，各轉換字典只在「段內」做最長前綴比對；
因此分割器詞表必須涵蓋轉換詞條，否則跨段詞組會失去轉換
（例：被发佯狂 → 被發佯狂）。

合併規則：
  1. jieba 詞頻表原樣保留（提供真實頻率，供 DP 打分）
  2. 轉換詞條中 jieba 沒有的，補上並給定 phrase_freq
     （長詞天然勝過切分，故只需足以壓過切分即可）
  3. 轉換詞條 jieba 已收錄、但頻率低於 phrase_freq 的，補到 phrase_freq
     （jieba 對冷門詞給的頻率可能輸給單字切分的聯合機率，例：
     字段 freq=6 輸給 字|段（20380×23395），被 DP 拆開後
     TWPhrases 的 字段→欄位 永遠不生效；mmseg 反而能整詞匹配）

用法:
  python3 build_mpdp_dict.py --output /path/jieba_mpdp.dict.utf8 [--phrase-freq 3]
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import tempfile

# 轉換鏈會用到、其 key 可能出現在輸入中的詞表
DEFAULT_SOURCES = [
    'data/dictionary/STPhrases.txt',
    'data/overlay/s2twp-overlay-phrases.txt',
    'data/overlay/s2twp-overlay-chars.txt',
    'data/overlay/s2twp-overlay-tw.txt',
    'data/dictionary/TWPhrases.txt',
    'data/dictionary/TWVariantsPhrases.txt',
    'data/dictionary/TWVariants.txt',
]
# 「區域詞條轉簡體」的產生詞表是建置產物（未進版控），需另外解析
REGIONAL_SOURCE = 'build/rel/data/STPhrases_GeneratedFromRegionalPhrases.txt'
REGIONAL_OCD2 = 'STPhrases_GeneratedFromRegionalPhrases.ocd2'
JIEBA_DICT = 'plugins/jieba/deps/cppjieba/dict/jieba.dict.utf8'


def resolve_regional_source() -> str | None:
    """取得「區域詞條轉簡體」詞表。

    優先讀建置產物；否則用已安裝的 ``opencc_dict`` 從 ``.ocd2`` 轉出。

    Returns:
        str | None: 可讀取的檔案路徑；無法取得時回傳 None。
    """
    if os.path.isfile(REGIONAL_SOURCE):
        return REGIONAL_SOURCE
    try:
        import opencc  # noqa: PLC0415
    except ImportError:
        return None
    share = os.path.join(os.path.dirname(os.path.abspath(opencc.__file__)),
                         'clib', 'share', 'opencc')
    clib = os.path.dirname(os.path.dirname(share))
    tool = os.path.join(clib, 'bin', 'opencc_dict')
    ocd2 = os.path.join(share, REGIONAL_OCD2)
    if not os.path.isfile(tool) or not os.path.isfile(ocd2):
        return None
    out = os.path.join(tempfile.gettempdir(), REGIONAL_OCD2 + '.txt')
    try:
        subprocess.run(
            [tool, '--from', 'ocd2', '--to', 'text', '--input', ocd2,
             '--output', out],
            check=True, capture_output=True)
    except (subprocess.CalledProcessError, OSError):
        return None
    return out if os.path.isfile(out) else None


def load_keys(path: str) -> set[str]:
    keys: set[str] = set()
    with io.open(path, encoding='utf-8') as handle:
        for line in handle:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 2 and parts[0]:
                keys.add(parts[0])
    return keys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--phrase-freq', type=int, default=3,
                        help='轉換詞條在 DP 中的權重（頻率）')
    parser.add_argument('--jieba-dict', default=JIEBA_DICT)
    parser.add_argument('--repo-root', default=os.getcwd())
    args = parser.parse_args()

    os.chdir(args.repo_root)
    if not os.path.isfile(args.jieba_dict):
        print(f'找不到 jieba 詞頻表: {args.jieba_dict}', file=sys.stderr)
        return 1

    sources = list(DEFAULT_SOURCES)
    regional = resolve_regional_source()
    if regional is None:
        print('警告：找不到 STPhrases_GeneratedFromRegionalPhrases，'
              '區域詞條（如 台式机）可能失去轉換', file=sys.stderr)
    else:
        sources.append(regional)

    # 先讀完轉換詞條，才能在寫 jieba 詞行時就地補頻率（規則 3）
    conversion_keys: set[str] = set()
    for source in sources:
        if not os.path.isfile(source):
            print(f'略過不存在的詞表: {source}', file=sys.stderr)
            continue
        conversion_keys |= load_keys(source)

    seen: set[str] = set()
    extra: set[str] = set()
    with io.open(args.output, 'w', encoding='utf-8') as out:
        with io.open(args.jieba_dict, encoding='utf-8') as handle:
            for line in handle:
                parts = line.split()
                if len(parts) >= 2:
                    seen.add(parts[0])
                    # 轉換詞條頻率不足 → 補到 phrase_freq，避免被單字切分拆開
                    if parts[0] in conversion_keys and int(parts[1]) < args.phrase_freq:
                        parts[1] = str(args.phrase_freq)
                        line = ' '.join(parts) + '\n'
                out.write(line if line.endswith('\n') else line + '\n')

        for key in sorted(conversion_keys - seen):
            seen.add(key)
            extra.add(key)
            out.write(f'{key} {args.phrase_freq} n\n')

    print(f'jieba 原有 {len(seen) - len(extra)}，補入轉換詞條 {len(extra)}，'
          f'總計 {len(seen)}；phrase_freq={args.phrase_freq}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
