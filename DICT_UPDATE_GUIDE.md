# OpenCC 字典更新說明

OpenCC 的二進制字典檔 `.ocd2` 是由 `data/dictionary/*.txt` 原始檔編譯而來。
修改字典必須遵循 **編輯文字檔 → 重新編譯 `.ocd2` → 覆蓋 site-packages** 的流程。

---

## 字典檔結構

```
data/dictionary/
├── STCharacters.txt      # 簡→繁 單字映射（如 娘 → 娘 孃）
├── STPhrases.txt         # 簡→繁 詞組映射（如 娘亲 → 娘親）
├── TSCharacters.txt      # 繁→簡 單字反向映射
├── TWPhrases.txt         # 台灣用语偏好詞組
├── TWVariants.txt        # 台灣字形變體
└── ...
```

格式說明（以 `STCharacters.txt` 為例）：
```
# key → value(s)，多個 value 用空格分隔
娘 娘 孃          # 簡體「娘」→ 繁體「娘」或「孃」
娘 娘              # 修正後：只映射「娘」
```

---

## 完整更新流程

### 1. 編輯原始字典

修改 `data/dictionary/` 目錄下的 `.txt` 檔案：

```bash
vim data/dictionary/STCharacters.txt
grep "^娘\b" data/dictionary/TSCharacters.txt  # 確認反向表是否需要同步修改
```

### 2. 重新編譯

```bash
# 進入編譯目錄
cd build/rel

# 關鍵步驟：刪除舊的 .ocd2，否則 CMake 不會重新生成
rm -f data/STCharacters.ocd2 data/STPhrases.ocd2

# 重新編譯受影響的字典
make Dictionaries
```

> ⚠️ **重要**：CMake 不會自動檢測 `.txt` 的變更。如果沒有先 `rm` 舊檔案，`make` 會認為已是最新，跳過編譯。

### 3. 驗證輸出

```bash
# 將 .ocd2 轉回文字檢查
../src/tools/opencc_dict \
    --input data/STCharacters.ocd2 \
    --output /tmp/STCharacters_verify.txt \
    --from ocd2 --to text

grep "^娘\b" /tmp/STCharacters_verify.txt
```

### 4. 覆蓋 Python site-packages 中的字典

OpenCC Python 套件會從 `site-packages/opencc/clib/share/opencc/` 讀取 `.ocd2`：

```bash
# 找到安裝位置
python3 -c "import opencc, os; print(os.path.dirname(opencc.__file__))"
# → /home/nate/.conda/envs/py311/lib/python3.11/site-packages/opencc

# 覆蓋（請替換為實際路徑）
TARGET="/home/nate/.conda/envs/py311/lib/python3.11/site-packages/opencc/clib/share/opencc"
cp data/STCharacters.ocd2 "$TARGET/"
cp data/STPhrases.ocd2 "$TARGET/"
# 若修改了 TSCharacters/TSPhrases，也一併覆蓋
```

### 5. 測試

```bash
python3 -c "
from opencc import OpenCC
c = OpenCC('s2twp')
print(c.convert('娘'))
print(c.convert('娘亲在床上睡着了'))
"
# 預期輸出：
# 娘
# 娘親在床上睡著了
```

---

## 只修改單一檔案時的快捷指令

```bash
cd /mnt/public/Develop/Projects/external_projects/OpenCC/build/rel

# 根據修改的檔案刪除對應的 .ocd2
rm -f data/STCharacters.ocd2 data/STPhrases.ocd2 data/TSCharacters.ocd2 data/TSPhrases.ocd2

# 重新編譯
make Dictionaries

# 覆蓋到 Python site-packages
TARGET="/home/nate/.conda/envs/py311/lib/python3.11/site-packages/opencc/clib/share/opencc"
cp data/STCharacters.ocd2 data/STPhrases.ocd2 "$TARGET/"

# 測試
python3 -c "from opencc import OpenCC; print(OpenCC('s2twp').convert('娘亲'))"
```

---

## 常見陷阱

| 問題 | 原因 | 解法 |
|------|------|------|
| 修改了 `.txt` 但測試沒變 | `.ocd2` 沒重新編譯 | `rm` 舊 `.ocd2` 再 `make Dictionaries` |
| 編譯成功但 Python 沒生效 | `.ocd2` 沒覆蓋到 site-packages | `cp` 到 `opencc/clib/share/opencc/` |
| 單字改了但詞組仍舊 | `STPhrases.txt` 沒同步修改 | 同時修改單字表和詞組表 |
| `TSCharacters` 沒更新 | 反向映射是 cmake 自動生成 | 清理 `build/rel/data/` 重新編譯全套字典 |

---

## 字典修改原則

1. **先查詞組表再查單字表**：OpenCC 使用 Max-match，詞組優先於單字。只改單字表可能無法覆蓋詞組層級的映射。
2. **同步考慮反向映射**：修改 `ST*.txt` 時，cmake 會自動更新對應 `TS*.txt`，但必須 full rebuild，不能只做單一檔案。
3. **台灣用語優先在 TWPhrases**：語言偏好（如 网络→網路）應該放在 `TWPhrases.txt`，不要在 `STCharacters.txt` 處理。

---

## 相關工具位置

| 工具 | 路徑 |
|------|------|
| 字典編譯器 | `build/rel/src/tools/opencc_dict` |
| 源文字檔 | `data/dictionary/*.txt` |
| 設定檔 | `data/config/s2twp.json` |
| 輸出二進制 | `build/rel/data/*.ocd2` |
| Python 字典目錄 | `site-packages/opencc/clib/share/opencc/` |

---

## 參考指令

```bash
# 查看字典內容
opencc_dict --input STCharacters.ocd2 --output /tmp/out.txt --from ocd2 --to text

# 從文字檔建立 ocd2
opencc_dict --input STCharacters.txt --output STCharacters.ocd2 --from text --to ocd2
```
