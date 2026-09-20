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
├── s2twp-custom-mpdp.json         # 同上，分割改用 mpdp 外掛（現行預設）
├── s2twp-overlay-phrases.txt      # 詞組修正（STPhrases 層）
├── s2twp-overlay-chars.txt        # 單字修正（STCharacters 層）
└── s2twp-overlay-tw.txt           # 台灣用語修正（TWPhrases 層，**鍵為繁體**）
```

> ⚠️ `overlay-tw` 的鍵必須是**繁體**（chain2 在 s2t 之後才執行），
> 例：`的士氣`（✅）而非 `的士气`（❌）。反之，mpdp 的分割詞表需要**簡體形**，
> 故改動 overlay-tw 後必須重建 mpdp 合併詞表（見底下專節）。

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

# 若要用 mpdp 分割（現行預設）→ 編譯外掛 + 產生合併詞表
cd /mnt/public/Develop/Projects/external_projects/OpenCC
python3 plugins/mpdp/tools/install.py
```

> ⚠️ **改了 overlay 就要重建 mpdp 合併詞表**，否則新加的盾牌詞不在分割詞表內，
> 會被 DP 切開而失效（詳見底下專節）。

> 使用 overlay 後**不需**再編譯/複製 `.ocd2`（直接使用 pip 套件內建的字典）。

> ⚠️ `s2twp-custom.json` 係以 **site-packages 內安裝的 `s2twp.json`（1.4.2 格式）** 為基礎，
> 升級 OpenCC 後需重新對齊。

### 使用

```python
from opencc import OpenCC
c = OpenCC('s2twp-custom-mpdp')   # 客製版 + 詞頻 DP 分割（預設）
c = OpenCC('s2twp-custom')        # 客製版 + mmseg
c = OpenCC('s2twp')               # upstream 原版
```

應用層 `natekit.api.text_processor._get_opencc_converter()` 依序嘗試
`s2twp-custom-mpdp` → `s2twp-custom` → `s2twp`，任一層失敗都會 `logger.exception`
後降級（未安裝外掛的環境仍可運作）。

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
| 新加的 overlay 在 mmseg 生效、mpdp 不生效 | 沒重建 mpdp 合併詞表 | 跑 `plugins/mpdp/tools/install.py` |
| 新加 overlay-tw 盾牌兩個模式都失效 | 鍵寫成簡體（chain2 需要繁體鍵） | 改成繁體，例：`的士氣` |
| mpdp 下多字盾牌失效（mmseg 正常） | chain2 繁體 key 沒補 t2s 簡體形 | 重建詞表（builder 規則 4） |
| 詞明明在字典卻被切開 | 詞條頻率輸給單字切分聯合機率 | builder 規則 3 會補到 `phrase_freq` |

---

## 字典修改原則

1. **先查詞組表再查單字表**：OpenCC 使用 Max-match，詞組優先於單字。只改單字表可能無法覆蓋詞組層級的映射。
2. **同步考慮反向映射**：修改 `ST*.txt` 時，cmake 會自動更新對應 `TS*.txt`，但必須 full rebuild，不能只做單一檔案。
3. **台灣用語優先在 TWPhrases**：語言偏好（如 网络→網路）應該放在 `TWPhrases.txt`，不要在 `STCharacters.txt` 處理。

---

## MaxMatch 貪心誤拆處理

OpenCC 使用 **MaxMatch（最長匹配）** 分詞，這會導致短詞組「搶先」命中，誤拆更長的正確詞彙。

### 典型案例 1：短詞組搶拆

`TWPhrases.txt` 有 `的士 → 計程車`，遇到「**通讯的士兵**」時，MaxMatch 優先命中 2 字的「的士」，結果變成「**通訊計程車兵**」。

### 典型案例 2：缺詞導致誤拆（長/發）

`STPhrases.txt` 有 `长发 → 長髮`（長頭髮），但「**校長**」不在字典
（OpenCC 認為 `长→長` 單字即可）。於是「**校长发起**」在 `长` 處貪心命中「长发」：

```
校长发起  →  校 + 长发 + 起  →  校長髮起  ❌
```

**解法**：把 `X长` 詞補進 overlay，讓 segmentation 先吃掉「长」：

```
校长	校長
队长	隊長
成长	成長
```

補完後 `校` → `校长`（詞組）→ `发起` → `校長發起` ✅。

> ⚠️ 受影響的 `X长` 詞很多：職稱（`校长/队长/部长/院长/首长…`）、
> 複合職稱（`小队长/卫队长/学院长/监狱长/班组长…`）、常用詞（`成长/增长/延长/生长…`）。

> ⚠️ **不可用盾牌**：`长发出`/`长发下` 有「長髮」真義（如「她的长发出」「藏在长发下」），
> 加盾牌會誤傷，必須補 `X长` 詞。

### 典型案例 3：古典義詞條干擾現代用法（被發）

`STPhrases.txt` 有 `被发 → 被髮`（古典義「被髮」，如「被发佯狂」），
但現代中文的 `被` 幾乎都是被動標記，`被发X` 幾乎恆為「被發X」：

```
被发到了  →  被发 + 到了  →  被髮到了  ❌
```

**解法**：覆蓋 `被发 → 被發`。古典四字詞（如 `被发佯狂 → 被髮佯狂`）
仍由更長匹配正確命中；頭髮義另加盾牌 `被发胶 → 被髮膠`。

### 典型案例 4：一詞多義的短詞條（是只）

`STPhrases.txt` 有 `是只 → 是隻`（量詞義，如「這是隻貓」），
但現代中文的 `是只X` 99% 是「是 + 只X」（只=only）：

```
但是只有她  →  但 + 是只 + 有  →  但是隻 有  ❌
```

**解法**：覆蓋 `是只 → 是只`，再為真正的「隻」義補盾牌：

- 由 STPhrases 所有 `只X → 隻X` 詞條生成 `是只X → 是隻X`
  （隻字不提、隻身、隻手遮天…）
- 量詞 + 名詞：`是只母`、`是只老`、`是只鸟`

### 典型案例 5：2 字「Y发」詞條在詞尾被啟動（发→髮 誤判）

STPhrases 有 ~90 條 `Y发 → Y髮`（如 `断发 → 斷髮`、`白发 → 白髮`），
當 `Y` 恰好是前一個詞的尾字時就會搶拆：

```
结束发言   →  结 + 束发 + 言   →  結束髮言  ❌
不断发出   →  不 + 断发 + 出   →  不斷髮出  ❌
明白发生了 →  明 + 白发 + 生   →  明白髮生  ❌
```

**解法**：補上「前一個詞」讓 MaxMatch 先吃掉 `Y`（不是補 `Y发` 盾牌，
因為這樣每個動詞都得列）：

- 补 `结束`/`不断`/`果断`/`判断`/`打断`/`切断`/`中断`/`垄断`/`隔断`/`独断`/`诊断`/`决断`
- 补 segmentation 盾牌（自映射，本身不改字）：`明白`、`一直`
- 動詞組盾牌：`直发抖`、`直发呆`、`直发愣`、`直发慌`、`理发呆`

實測這批修正使全量小說誤判 `髮` 從 1875 降至 14。

### 典型案例 6：多值詞條取第一值，領域詞誤套一般語境

`TWPhrases.txt` 有些詞條是**多值**（同一個 key 列多個候選，以空格分隔），
OpenCC 的 `MatchPrefix` 只取**第一個值**：

```
對象	物件 對象      → 查验对象  變成 查驗物件  ❌
循環	迴圈 循環      → 恶性循环  變成 惡性迴圈  ❌
菜單	選單 菜單      → 特别菜单  變成 特別選單  ❌
```

問題在於被選中的值多是**領域專用詞**（`物件`=物品、`迴圈`=程式 loop、
`選單`=軟體 UI），套到一般語境就語意錯誤。

**解法**：在 `overlay-tw` 加自映射盾牌，把第一值改成一般義，
再為特殊義補**更長的**盾牌（與典型案例 1 同手法）：

```
對象	對象
循環	循環
菜單	菜單
死循環	死迴圈      無限循環	無限迴圈
下拉菜單	下拉選單     系統菜單	系統選單
                        主菜單	主選單
```

判斷依據要**看語料實際義項分布**，不要憑感覺：

| 詞條 | 語料實測 | 處理 |
|------|---------|------|
| `对象` | 966 次全是「人/目標」，`物件`義 0 | 自映射 |
| `循环` | 306 次，自然義 ~270、程式義 ~36 | 自映射 + 2 條程式盾牌 |
| `菜单` | 51 次全是餐廳，軟體義 0 | 自映射 |
| `消息` | 21395 次，`訊息` 確為台灣標準 | 不動（語體偏好） |
| `打開` | 7599 次，`開啟` 屬語體偏好 | 不動 |

> ⚠️ 語**意**錯誤（`物件`/`迴圈`/`選單` 是別的意思）才改；
> 語**體**偏好（`訊息`/`開啟`/`高階`）維持 upstream，不要自作主張。
> 可用這行撈出所有多值詞條：
> ```bash
> awk -F'\t' 'NF>=2 && $1 !~ /^#/ && split($2,v," ")>1' data/dictionary/TWPhrases.txt
> ```

### 典型案例 7：詞條本身語意錯誤（别只 → 別隻）

`STPhrases.txt` 有 `别只 → 別隻`（量詞義），但 `别` 是禁止/勸阻副詞，
後面接的 `只` **恆為「only」**（`別只報結果`、`別只顧著自己`、`別只身前往`）：

```
别只报结果  →  别只 + 报结果  →  別隻報結果  ❌
```

**解法**：overlay 內容覆蓋 `别只 → 別只`（key 簡體、value 繁體）。
`别+隻` 在現代中文不成立（量詞需 `一/兩/這/那/幾` 在前），故免補盾牌。

> ⚠️ **這類修 mpdp 幫不上忙**：`别只` 是**詞條內容**錯誤（同案例 6），
> 且 mpdp 的合併詞表（builder 規則 2）反而會把 `别只` 保留成單一 token，
> 讓錯誤詞條穩定命中。只能用 overlay 覆蓋。

### 典型案例 8：姓氏字被過度轉換（岳 → 嶽、游 → 遊）

`s2twp` 的單字映射含 `岳 → 嶽 岳`（多值取第一值），凡**詞組表沒收錄的人名**
就會落到單字映射：山嶽義成立，姓氏義不成立。

```
岳不群   →  嶽不群   ❌（《笑傲江湖》華山派掌門）
岳灵珊   →  嶽靈珊   ❌
岳飞     →  岳飛     ✅（STPhrases 已收錄）
五岳     →  五嶽     ✅（山嶽義，正確）
东岳     →  東嶽     ✅
岳父     →  岳父     ✅
```

**解法**：overlay 補人名（key 簡體、value 繁體）：

```
岳不群	岳不群
岳灵珊	岳靈珊
游坦之	游坦之
```

> ⚠️ **同族還有「游」**：`游坦之 → 遊坦之` ❌（天龍八部，姓氏「游」）。
> 但詞組表已處理好 `游泳`／`上游`／`游牧`／`游擊`／`游離` 等常見詞，
> 只有**沒收錄的人名**才落到單字映射 `游 → 遊`，所以只需補人名。
>
> ⚠️ **不要**直接刪掉單字映射 `岳 → 嶽`：`五岳 → 五嶽`、`东岳 → 東嶽`、
> `山岳 → 山嶽` 全靠它。只補人名例外（與 `岳飞` 同一手法）。
>
> ⚠️ **identity 值要逐字確認**：`岳不群`／`游坦之` 各字繁中同形，值可寫
> identity；但 `岳灵珊` 的 `灵` 必須轉 `靈`，值應為 `岳靈珊`——寫成
> `岳灵珊` 會把字級 `灵→靈` 一起擋掉（實測：`与岳灵珊 → 與岳灵珊` ❌）。

**驗證**：`岳不群`／`岳灵珊`／`游坦之`／`与岳灵珊`／`这是岳灵珊` 皆正確，
且 `五岳`／`东岳`／`山岳`／`岳父`／`岳飞`／`游泳`／`上游`／`游擊` 輸出零變化；
全語料重生後受影響檔案只差這一行（`嶽不群` → `岳不群`）。

> ⚠️ **動了 overlay 就一定要重建 mpdp 詞表**，不然會出現「短詞正常、
> 長句裡失傚」的假象：實測 `台阶 → 台階` 在單獨測試時正確，但整句
> `改口必给台阶自己下` 仍輸出 `臺階`——因為分割器把 `台阶` 切開了，
> 詞條根本沒機會命中。重跑 `install.py` 後才修好。
>
> ⚠️ **`install.py` 不會複製 overlay txt**（只更新 config 與 mpdp 詞表）。
> 改完 `data/overlay/*.txt` 必須手動 `cp data/overlay/*.txt "$TARGET/"`，
> 否則 runtime 讀到的還是 site-packages 裡的舊檔——本案例實測踩到：
> 詞表已含新詞條、轉換卻毫無變化。

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
2. **缺詞誤拆**：若某詞不在字典，貪心匹配會喫掉下一個詞的首字（如 `校长` 不在字典，`长` 被 `长发` 喫掉）；解法是把該詞補進 overlay。
3. **加長詞組盾牌**：用更長詞組覆蓋誤拆路徑（如 `的士兵 → 的士兵`）。
4. **最後才改單字表**：刪除單字映射是最後手段（如 `余 → 餘 余` 改為 `余 → 余`），因為會影響所有含該字的詞組。

> ⚠️ **用 `s2twp.convert()` 產生 overlay 值時要小心**：若詞含「台」，upstream 會輸出「臺」
> （如 `台长 → 臺長`），必須手動把值中的 `臺` 改回 `台`。產生後建議掃描 overlay 值是否殘留 `臺`。

---

## 分割層修正：MPDP 外掛（取代逐條補詞）

上面案例 1～5 的病根都是 **mmseg（正向最大匹配）只能「信任左邊」**：
`X发Y` 這類歧義它無法判斷，只能靠逐條補詞去擋。
（案例 6 不同：它是 chain2 詞條內容問題，與分割方式無關，mpdp 亦然。）
若改用 `plugins/mpdp/`（詞頻 DP 分割外掛），案例 1～5 這一類修正可整批退場：

```json
"segmentation": { "type": "mpdp",
                  "resources": { "dict_path": "mpdp/jieba_mpdp.dict.utf8" } }
```

實測（2M 字小說，對照 `s2twp-custom`）：`隻/只` 誤判 11 → 0，
`瞭/了` 51 → 2，`製/制` 4 → 0，`裡/里`、`麵/面`、`後/后`、
`蒐/搜`、`遊/游`、`幾/几` 全部修正，輸出長度無差異（無文字遺失）。

詳見 `plugins/mpdp/README.md`。上述策略（案例 1～5 的解法）仍適用於
必須使用 `mmseg` 的場合，以及 mpdp 也處理不掉的**詞條內容**問題（案例 6）。

### 已清理的補詞（mpdp 上線後）

案例 2／3／4／5 的補詞已從 overlay 移除，共 **162 條**：

| 類別 | 條數 | 例 |
|------|------|-----|
| `X长` 型（案例 2） | 119 | 校长、队长、部长、专长、修长… |
| `是只X` 型（案例 4） | 28 | 是只、是只字、是只字不提… |
| 前置詞（案例 5） | 14 | 结束、不断、明白、果断、判断、打断… |
| 動詞組盾牌（案例 5） | 4 | 直发呆、直发愣、直发慌、理发呆 |
| `被发` 前置 | 1 | —（`被发 → 被發` 本體保留，屬內容修正） |

**只留 5 條**（實測移除後 mpdp 輸出真的會變）：

```
是只母	是隻母      是只老	是隻老
是只鸟	是隻鳥      是只日	是隻日
直发抖	直發抖
```

驗證方法：對每個被移除的條目，用載句（key 本身、`key+发起`、`key+发抖`、
`key+兔子`、`key+的`）比對移除前後輸出；再跑全語料 2.5M 字 difflib 對比，
確認**零差異、零長度變化**。

> ⚠️ 比對時務必建立**乾淨的對照環境**：chain1 的 overlay 是 runtime 讀取的
> `text` dict，直接改 `data/overlay/` 會讓「before」也吃到新檔而誤判。
> 做法：另開一個目錄，裡面用 symlink 連到原 share 目錄的字典，
> 只放舊版 overlay txt。

---

## 改了 overlay 就要重建 MPDP 合併詞表

mpdp 的分割詞表（`mpdp/jieba_mpdp.dict.utf8`）是**產生檔**，由
`plugins/mpdp/tools/build_mpdp_dict.py` 從 jieba 詞頻 + 各轉換詞表合成。
只要動了 `data/overlay/*.txt` 或 `data/dictionary/*.txt`，就必須重建：

```bash
cd /mnt/public/Develop/Projects/external_projects/OpenCC
python3 plugins/mpdp/tools/install.py          # 編譯 + 詞表 + 設定一次完成
# 或只重建詞表（不重編外掛）
python3 plugins/mpdp/tools/build_mpdp_dict.py \
    --output "$TARGET/mpdp/jieba_mpdp.dict.utf8" --phrase-freq 100
```

### builder 的四條規則

| # | 規則 | 為什麼 |
|---|------|--------|
| 1 | jieba 詞頻原樣保留 | DP 需要真實頻率才能正確打分 |
| 2 | 轉換詞條 jieba 沒有的補上 | 詞條被切開就永遠不生效（`被发佯狂` → `被發佯狂`） |
| 3 | jieba 已收錄但頻率 < `phrase_freq` 者補到 `phrase_freq` | jieba 對冷門詞的頻率可能輸給單字聯合機率（`字段` freq=6 輸給 `字`×`段`）→ `字段→欄位` 失效 |
| 4 | 所有 key 連同 **t2s 簡體形**一起進詞表 | chain2 的 key 是**繁體**，但分割器跑在**簡體輸入**上；規則 2/3 補了繁體 key 也對不上（`無限循環` vs `无限循环`） |

### `phrase_freq` 怎麼選

只要「足以壓過切分」即可（切分多出詞數、多付罰分，長詞天然佔優）。
設太大反而蓋掉 jieba 的正確切分：

| phrase_freq | 結果 |
|-------------|------|
| 3 / 20 / 100 | 一致（實測），`反制得挺快` 正確 |
| 1000 以上 | `反制得挺快` → `反製得挺快` ❌ |

故定為 **100**。

### 為什麼改了 overlay-tw 特別容易漏

`overlay-tw` 的鍵是**繁體**，需要經過 t2s 才能進分割詞表（規則 4）。
漏掉的症狀是「mmseg 正常、mpdp 不生效」，例如 `系統菜單` 盾牌失效 → `系統菜單`。

---

## 相關工具位置

| 工具 | 路徑 |
|------|------|
| 字典編譯器 | `build/rel/src/tools/opencc_dict` |
| 源文字檔（upstream，勿改） | `data/dictionary/*.txt` |
| **客製 overlay** | `data/overlay/*.txt` |
| **客製 config** | `data/overlay/s2twp-custom.json`、`s2twp-custom-mpdp.json` |
| **mpdp 外掛原始碼** | `plugins/mpdp/src/MpdpPlugin.cpp` |
| **mpdp 合併詞表產生器** | `plugins/mpdp/tools/build_mpdp_dict.py` |
| **mpdp 安裝腳本** | `plugins/mpdp/tools/install.py` |
| mpdp 外掛（已安裝） | `site-packages/opencc/clib/opencc/plugins/libopencc-mpdp.so` |
| mpdp 合併詞表（已安裝） | `site-packages/opencc/clib/share/opencc/mpdp/jieba_mpdp.dict.utf8` |
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
