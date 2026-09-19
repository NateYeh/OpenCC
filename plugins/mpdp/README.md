# MPDP Segmentation Plugin

以「詞頻最大機率」做中文分詞的 OpenCC segmentation 外掛。

## 為什麼需要它

OpenCC 內建的 `mmseg` 是**正向最大匹配（FMM）**：從左到右貪婪取最長詞，命中即鎖定、
不回溯。遇到 `X发Y` 這類歧義時，它只會「信任左邊」：

```
医生发出   →  医 | 生发 | 出      ❌   （應為 医 | 生 | 发出）
会发出     →  会发 | 出           ❌
黑头发黑眼睛 →  黑 | 头发 | 黑 | 眼睛  ✅   ← 本例對，但換成向後匹配（BMM）就壞
```

向後匹配只是「信任右邊」，錯得一樣多（`修理头发还是在` → `修理 | 头 | 发还 | 是 | 在` ❌）。
**兩者都無法判斷哪一組切分整體更可能**，因為它們都沒有打分依據。

本外掛改用具全域判準的 **Viterbi/DP**，最大化 `Σ log P(詞)`：

```
医生发出   →  医生 | 发出           ✅
黑头发黑眼睛 →  黑头发 | 黑眼睛        ✅
```

詞頻來自 `plugins/jieba/deps/cppjieba/dict/jieba.dict.utf8`（348,981 詞，
已隨 OpenCC 原始碼提供），因此**不需要 cppjieba 的程式碼**，也不需連結 libopencc。

## 建置與安裝

```bash
# 一鍵：編譯 + 產生合併詞表 + 安裝到目前 Python 環境的 opencc 套件
python3 plugins/mpdp/tools/install.py

# 只編譯
g++ -std=c++17 -O2 -fPIC -shared -Isrc \
    -o plugins/mpdp/build/libopencc-mpdp.so plugins/mpdp/src/MpdpPlugin.cpp

# 只產生詞表
python3 plugins/mpdp/tools/build_mpdp_dict.py --output /path/jieba_mpdp.dict.utf8
```

安裝後的檔案位置（Linux，Python 套件版 OpenCC）：

| 檔案 | 位置 |
|------|------|
| 外掛 | `<site-packages>/opencc/clib/opencc/plugins/libopencc-mpdp.so` |
| 詞表 | `<site-packages>/opencc/clib/share/opencc/mpdp/jieba_mpdp.dict.utf8` |
| 設定 | `<site-packages>/opencc/clib/share/opencc/s2twp-custom-mpdp.json` |

搜尋路徑亦可用環境變數覆寫：`OPENCC_SEGMENTATION_PLUGIN_PATH=/path/to/dir`。

## 設定用法

```json
{
  "segmentation": {
    "type": "mpdp",
    "resources": {
      "dict_path": "mpdp/jieba_mpdp.dict.utf8",
      "user_dict_path": "mpdp/user.dict.utf8"
    }
  }
}
```

| 資源 | 必填 | 說明 |
|------|------|------|
| `dict_path` | 是 | 詞頻表，格式 `詞 頻率 [詞性]` |
| `user_dict_path` | 否 | 補充詞表；頻率可省略（省略時用基礎詞表中位權重）。檔案不存在時靜默略過 |
| `max_word_length` | 否 | 限制 DP 候選詞最大字數（加速用） |

相對路徑會依序往「設定檔目錄 → 上層目錄 → `$OPENCC_DATA_DIR`」尋找。

## 合併詞表為什麼需要轉換詞條

OpenCC 的流程是「先分割，各轉換字典**只在段內**做最長前綴比對」。
若分割器把一個轉換詞條切開，該詞條就永遠不會生效：

```
被发佯狂  →  被 | 发佯狂  →  被發佯狂  ❌   （詞條 被发佯狂 被切開）
面包      →  手面 | 包   →  面包      ❌   （mmseg 自己也會犯）
```

因此 `build_mpdp_dict.py` 會把 `STPhrases`、產生的區域詞表、overlay 詞表、
`TWPhrases`／`TWVariantsPhrases`／`TWVariants` 中 jieba 沒有的詞條補進詞表，
並給定 `--phrase-freq`（預設 100）。

> `phrase_freq` 只要「足以壓過切分」即可；因為切分會多出詞數、多付罰分，
> 長詞天然佔優。設太大（例如 1000 以上）反而會蓋掉 jieba 的正確切分
> （實測 `反制得挺快` → `反製得挺快`）。實測 3/20/100 結果一致。

## 設計實作

* `src/MpdpPlugin.cpp` — 單一檔案，純 C ABI（`opencc_get_segmentation_plugin_v2`）
* `tools/build_mpdp_dict.py` — 合併詞表產生器
* `tools/install.py` — 建置 + 安裝

DP 細節：

* 逐 code point 由右往左計算 `best[i] = max(log P(詞) + best[i+len])`
* 單字一律可切；未收錄的單字給 `log(最短頻率/總頻)`，因此未知字串不會被貪婪合併
* 多字詞候選上界 = `min(首字最長詞長, max_word_length, 剩餘長度)`
* `free_segment_lengths` 釋放 `new uint32_t[]`；`create`/`segment` 的例外一律轉成
  `opencc_error_t`，不讓例外跨越 ABI 邊界

## 效能

詞表 372,810 條，載入約 0.3–0.5 秒（每個 `OpenCC()` 實例一次）。
DP 為 O(n × 平均候選長度)。

## 實測（2M 字小說語料，對照 `s2twp-custom`）

| 項目 | mmseg + overlay | mpdp + overlay |
|------|----------------|----------------|
| `医生发出` | 醫生髮出 ❌ | 醫生發出 ✅ |
| 隻/只 誤判 | 11 處 | **0** ✅ |
| 瞭/了 誤判 | 51 處 | **2** ✅ |
| 製/制 誤判 | 4 處 | **0** ✅ |
| 裡/里、麵/面、後/后、蒐/搜、遊/游、幾/几 | 多處未轉換 | **全部修正** ✅ |
| 輸出長度差異（文字遺失） | — | 0 ✅ |

已知殘留：`真的遇到瞭解决不了的`（`了` 被 jieba 的 `了解` 搶走）、
`簡單明了`（TW 應為 `明瞭`）。可用 `user_dict` 或 overlay 補盾牌處理。

## 移除

```bash
python3 plugins/mpdp/tools/install.py --uninstall
```
