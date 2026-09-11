# OpenCC 字典更新說明

OpenCC 的二進制字典檔 `.ocd2` 是由 `data/dictionary/*.txt` 原始檔編譯而來。

本 fork 的客製修正採 **Overlay 方案**（見下節），**不改動 upstream 字典檔**，
因此 sync upstream 時不會產生 merge conflict。

---

## 客製化方式：Overlay（推薦）

### 架構

```
data/overlay/
├── s2twp-custom.json              # 自訂 config（複製 s2twp.json 並插入 overlay）
├── s2twp-overlay-phrases.txt      # 詞組修正（STPhrases 層）
├── s2twp-overlay-chars.txt        # 單字修正（STCharacters 層）
└── s2twp-overlay-tw.txt           # 台灣用語修正（TWPhrases 層）
```

### 原理

OpenCC config 支援 `group` dict 與 `text` dict：

- **`text`**：純文字字典，**執行時載入，免編譯**
- **`group`**：多字典組合

> ✅ **環境**：已升級至 OpenCC **1.4.2**（支援 `match_policy: union`，取最長匹配）。
> 注意：**1.3.1 不支援 `union`**（會被當成 `short_circuit`），若環境回退舊版，
> dict 順序即優先序，需確保**單字 overlay 排在詞組表之後**。

### dict 順序

```
conversion_chain[0] inner group（union，取最長）:
  [ overlay-phrases, overlay-chars, STPhrases, STPhrases_Generated ]
```

`union` 取最長匹配，故 1 字的 `台` 不會遮蔽 2 字的 `台面`（→ `檯面`）。
同長度時**第一個 dict 優先**，所以 overlay 必須排在 upstream 字典之前才能覆蓋。

> ⚠️ 若在 **1.3.1** 執行，`union` 失效，此時必須改為 `short_circuit` 並重排為
> `[ overlay-phrases, STPhrases, overlay-chars, STCharacters ]`，否則 `台面 → 台面`。

### 部署

```bash
# 首次或升級：安裝指定版本
pip install -U opencc==1.4.2

# 部署 overlay（config 相對路徑以自身目錄為基準，須同目錄）
TARGET="/home/nate/.conda/envs/py311/lib/python3.11/site-packages/opencc/clib/share/opencc"
cp /mnt/public/Develop/Projects/external_projects/OpenCC/data/overlay/* "$TARGET/"
```

> 使用 overlay 後**不需**再編譯/複製 `.ocd2`（直接使用 pip 套件內建的字典）。

> ⚠️ `s2twp-custom.json` 係以 **site-packages 內安裝的 `s2twp.json`（1.4.2 格式）** 為基礎，
> 升級 OpenCC 後需重新對齊。

### 使用

```python
from opencc import OpenCC
c = OpenCC('s2twp-custom')   # 客製版
c = OpenCC('s2twp')          # upstream 原版
```

應用層 `natekit.api.text_processor._get_opencc_converter()` 優先載入 `s2twp-custom`，
載入失敗才退回 `s2twp`。

### 新增客製項目

1. 編輯 `data/overlay/s2twp-overlay-*.txt`（格式同一般字典 `key\tvalue`）
2. 複製到 site-packages（**無需重新編譯**）
3. 測試

> **刪除 upstream 條目**無法用 overlay 直接表達；改用**自映射**（`key\tkey`）達到相同效果。

### 從 upstream 字典差異重建 overlay

若曾直接改過 `data/dictionary/*.txt`，可用以下邏輯重建 overlay：

```python
# 對每個 key：
#   修改項  → overlay[key] = 我們的 value
#   新增項  → overlay[key] = 我們的 value
#   刪除項  → overlay[key] = key（自映射）
```

---

## 直接修改字典（僅供臨時驗證）

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

## MaxMatch 貪心誤拆處理

OpenCC 使用 **MaxMatch（最長匹配）** 分詞，這會導致短詞組「搶先」命中，誤拆更長的正確詞彙。

### 典型案例

`TWPhrases.txt` 有 `的士 → 計程車`，遇到「**通讯的士兵**」時，MaxMatch 優先命中 2 字的「的士」，結果變成「**通訊計程車兵**」。

### 解決策略：加長詞組「盾牌」

**不要**刪除短詞組（會犧牲「的士→計程車」的正常功能），而是在同一字典中加入**更長的詞組**作為盾牌：

```
# TWPhrases.txt
的士	計程車      # 保留原有映射
的士兵	的士兵    # 3 字盾牌，MaxMatch 優先命中
的士官	的士官
的士氣	的士氣
```

> ⚠️ **關鍵**：`TWPhrases` 在 `s2t` 轉換**之後**才應用，輸入鍵必須是**繁體形式**。
> - ❌ 錯誤：`的士气	的士气`（簡體「气」在 s2t 階段已變「氣」，TWPhrases 階段找不到匹配）
> - ✅ 正確：`的士氣	的士氣`（繁體鍵，TWPhrases 階段才能命中）

### 通用原則

遇到 MaxMatch 誤拆時，優先採用以下順序處理：

1. **檢查詞組表**：先確認是否有短詞組搶先命中（如 `余思 → 餘思` 搶拆「余思晗」）。
2. **加長詞組盾牌**：用更長詞組覆蓋誤拆路徑（如 `的士兵 → 的士兵`）。
3. **最後才改單字表**：刪除單字映射是最後手段（如 `余 → 餘 余` 改為 `余 → 余`），因為會影響所有含該字的詞組。

---

## 相關工具位置

| 工具 | 路徑 |
|------|------|
| 字典編譯器 | `build/rel/src/tools/opencc_dict` |
| 源文字檔（upstream，勿改） | `data/dictionary/*.txt` |
| **客製 overlay** | `data/overlay/*.txt` |
| **客製 config** | `data/overlay/s2twp-custom.json` |
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
