/*
 * Open Chinese Convert — MPDP segmentation plugin
 *
 * 以「詞頻最大機率」做中文分詞的 OpenCC segmentation 外掛。
 *
 * 動機：內建 mmseg（正向最大匹配）在 `X发Y` 這類歧義上必然出錯，例如
 *       医生发出 → 医 | 生发 | 出   （髮 誤判）
 *       黑头发黑眼睛 → 黑 | 头发 | 黑 | 眼睛  （本例正確，但換 BMM 就壞）
 * 正向、向後都只是「決定信任哪一邊」，無法判斷哪一組切分整體更可能。
 * 本外掛改用 Viterbi/DP 最大化 Σ log P(詞)，需要一份帶詞頻的詞表。
 *
 * 純 C ABI 實作，不連結 libopencc，只需 src/plugin/OpenCCPlugin.h。
 * 建置：見 plugins/mpdp/README.md
 */

#include "plugin/OpenCCPlugin.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <new>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

constexpr double kNegInf = -1e300;

// ---------------------------------------------------------------------------
// UTF-8：必須與 OpenCC 的 UTF8Util::NextCharLengthNoException 完全一致，
// 否則 host 依 codepoint_lengths 還原邊界時會對不上。
// ---------------------------------------------------------------------------
size_t NextCharLength(const char* str) {
  const unsigned char ch = static_cast<unsigned char>(*str);
  if ((ch & 0xF0) == 0xE0) {
    return 3;
  } else if ((ch & 0x80) == 0x00) {
    return 1;
  } else if ((ch & 0xE0) == 0xC0) {
    return 2;
  } else if ((ch & 0xF8) == 0xF0) {
    return 4;
  } else if ((ch & 0xFC) == 0xF8) {
    return 5;
  } else if ((ch & 0xFE) == 0xFC) {
    return 6;
  }
  return 0;
}

size_t CodePointLength(const std::string& text) {
  size_t count = 0;
  for (size_t i = 0; i < text.size();) {
    const size_t len = NextCharLength(text.data() + i);
    i += (len == 0 ? 1 : len);
    count++;
  }
  return count;
}

// ---------------------------------------------------------------------------
// 錯誤物件：訊息一律由外掛配置，free_error() 負責釋放。
// ---------------------------------------------------------------------------
void SetError(opencc_error_t* error, int code, const std::string& message) {
  if (error == nullptr) {
    return;
  }
  delete[] error->message;
  char* buffer = new (std::nothrow) char[message.size() + 1];
  if (buffer != nullptr) {
    std::memcpy(buffer, message.c_str(), message.size() + 1);
  }
  error->message = buffer;
  error->code = code;
}

// 解析 "word freq [pos]"；回傳 false 表示此行無效。
bool ParseEntry(const std::string& line, std::string* word, double* freq,
                bool* hasFreq) {
  const size_t begin = line.find_first_not_of(" \t\r\n");
  if (begin == std::string::npos) {
    return false;  // 空行
  }
  const size_t space = line.find_first_of(" \t", begin);
  if (space == std::string::npos) {
    *word = line.substr(begin);
    *freq = 0.0;
    *hasFreq = false;
    return !word->empty();
  }
  *word = line.substr(begin, space - begin);
  const size_t freqBegin = line.find_first_not_of(" \t", space);
  if (freqBegin == std::string::npos) {
    *freq = 0.0;
    *hasFreq = false;
    return !word->empty();
  }
  const size_t freqEnd = line.find_first_of(" \t", freqBegin);
  const std::string raw = line.substr(freqBegin, freqEnd - freqBegin);
  char* end = nullptr;
  const double parsed = std::strtod(raw.c_str(), &end);
  if (end == raw.c_str() || *end != '\0' || parsed <= 0.0) {
    *freq = 0.0;
    *hasFreq = false;
  } else {
    *freq = parsed;
    *hasFreq = true;
  }
  return !word->empty();
}

// 相對資源路徑解析：原樣 → config 目錄 → config 上層 → OPENCC_DATA_DIR
std::string ResolvePath(const std::string& raw, const std::string& configDir) {
  auto readable = [](const std::string& path) {
    if (path.empty()) {
      return false;
    }
    std::ifstream ifs(path.c_str(), std::ios::binary);
    return ifs.is_open();
  };
  if (raw.empty() || readable(raw)) {
    return raw;
  }
  if (!configDir.empty()) {
    const std::string direct = configDir + "/" + raw;
    if (readable(direct)) {
      return direct;
    }
    const size_t pos = configDir.find_last_of("/\\");
    if (pos != std::string::npos && pos > 0) {
      const std::string parent = configDir.substr(0, pos) + "/" + raw;
      if (readable(parent)) {
        return parent;
      }
    }
  }
  const char* dataDir = std::getenv("OPENCC_DATA_DIR");
  if (dataDir != nullptr && *dataDir != '\0') {
    const std::string candidate = std::string(dataDir) + "/" + raw;
    if (readable(candidate)) {
      return candidate;
    }
  }
  return raw;
}

// ---------------------------------------------------------------------------
// 外掛狀態：詞表的 log 機率 + 依首字分組的最大詞長（DP 上界）
// ---------------------------------------------------------------------------
struct MpdpHandle {
  std::unordered_map<std::string, double> weight;   // 詞 → log P(詞)
  std::unordered_map<std::string, size_t> maxLenByFirst;  // 首字 → 最長詞長
  size_t maxWordLength = 1;
  double unknownWeight = 0.0;  // 未收錄單字的 log P
};

// 讀入詞表；回傳新增/覆蓋的詞數。baseTotal 為 0 時代表這是基礎詞表。
size_t LoadDictionary(const std::string& path, MpdpHandle* handle,
                      bool isBase, double* baseTotal, double* baseMinFreq,
                      double* medianWeightOut) {
  std::ifstream ifs(path.c_str());
  if (!ifs.is_open()) {
    throw std::runtime_error("cannot open dictionary: " + path);
  }
  std::vector<std::pair<std::string, double>> entries;
  double total = 0.0;
  double minFreq = 0.0;
  std::string line;
  while (std::getline(ifs, line)) {
    std::string word;
    double freq = 0.0;
    bool hasFreq = false;
    if (!ParseEntry(line, &word, &freq, &hasFreq)) {
      continue;
    }
    entries.emplace_back(word, hasFreq ? freq : 0.0);
    if (hasFreq) {
      total += freq;
      if (minFreq == 0.0 || freq < minFreq) {
        minFreq = freq;
      }
    }
  }
  if (entries.empty()) {
    throw std::runtime_error("dictionary is empty: " + path);
  }
  if (isBase) {
    if (total <= 0.0 || minFreq <= 0.0) {
      throw std::runtime_error("base dictionary has no usable frequencies: " +
                               path);
    }
    *baseTotal = total;
    *baseMinFreq = minFreq;
  }

  const double referenceTotal = isBase ? total : *baseTotal;
  const double fallback = isBase ? 0.0 : *medianWeightOut;

  std::vector<double> weights;
  weights.reserve(entries.size());
  for (const auto& entry : entries) {
    double logWeight;
    if (entry.second > 0.0) {
      logWeight = std::log(entry.second / referenceTotal);
    } else {
      logWeight = fallback;  // user_dict 未給頻率 → 用基礎詞表中位數
    }
    handle->weight[entry.first] = logWeight;
    weights.push_back(logWeight);
    const size_t cpLen = CodePointLength(entry.first);
    if (cpLen > handle->maxWordLength) {
      handle->maxWordLength = cpLen;
    }
    // 以首個 code point 為鍵記錄最長詞長
    const size_t firstLen = NextCharLength(entry.first.c_str());
    const std::string first = entry.first.substr(0, firstLen == 0 ? 1 : firstLen);
    auto existing = handle->maxLenByFirst.find(first);
    if (existing == handle->maxLenByFirst.end() || existing->second < cpLen) {
      handle->maxLenByFirst[first] = cpLen;
    }
  }
  if (isBase) {
    std::sort(weights.begin(), weights.end());
    *medianWeightOut = weights[weights.size() / 2];
    handle->unknownWeight = std::log(*baseMinFreq / referenceTotal);
  }
  return entries.size();
}

// ---------------------------------------------------------------------------
// ABI 實作
// ---------------------------------------------------------------------------
int CreateSegmentation(opencc_segmentation_create_args_t* args) {
  if (args == nullptr || args->struct_size < sizeof(*args) ||
      args->out == nullptr) {
    SetError(args == nullptr ? nullptr : args->error,
             OPENCC_ERROR_INVALID_ARGUMENT, "invalid create arguments");
    return -1;
  }
  *args->out = nullptr;

  std::string configDir;
  std::string dictPath;
  std::string userDictPath;
  std::string maxLenText;
  for (size_t i = 0; i < args->config_size; i++) {
    const char* key = args->config[i].key;
    const char* value = args->config[i].value;
    if (key == nullptr || value == nullptr) {
      continue;
    }
    const std::string name(key);
    if (name == "__config_dir") {
      configDir = value;
    } else if (name == "dict_path") {
      dictPath = value;
    } else if (name == "user_dict_path") {
      userDictPath = value;
    } else if (name == "max_word_length") {
      maxLenText = value;
    }
  }
  if (dictPath.empty()) {
    SetError(args->error, OPENCC_ERROR_PLUGIN_RESOURCE_MISSING,
             "required resource missing: dict_path");
    return -1;
  }

  MpdpHandle* handle = new (std::nothrow) MpdpHandle();
  if (handle == nullptr) {
    SetError(args->error, OPENCC_ERROR_PLUGIN_RUNTIME_FAILURE,
             "out of memory");
    return -1;
  }
  try {
    double baseTotal = 0.0;
    double baseMinFreq = 0.0;
    double medianWeight = 0.0;
    const std::string resolvedDict = ResolvePath(dictPath, configDir);
    LoadDictionary(resolvedDict, handle, true, &baseTotal, &baseMinFreq,
                   &medianWeight);
    if (!userDictPath.empty()) {
      const std::string resolvedUser = ResolvePath(userDictPath, configDir);
      std::ifstream probe(resolvedUser.c_str());
      if (probe.is_open()) {
        probe.close();
        LoadDictionary(resolvedUser, handle, false, &baseTotal, &baseMinFreq,
                       &medianWeight);
      }
    }
    if (!maxLenText.empty()) {
      const long limit = std::strtol(maxLenText.c_str(), nullptr, 10);
      if (limit > 0 && static_cast<size_t>(limit) < handle->maxWordLength) {
        handle->maxWordLength = static_cast<size_t>(limit);
      }
    }
  } catch (const std::exception& ex) {
    delete handle;
    SetError(args->error, OPENCC_ERROR_PLUGIN_RUNTIME_FAILURE, ex.what());
    return -1;
  }

  *args->out = reinterpret_cast<opencc_segmentation_handle_t*>(handle);
  return 0;
}

int Segment(opencc_segmentation_segment_args_t* args) {
  if (args == nullptr || args->struct_size < sizeof(*args) ||
      args->handle == nullptr || args->segment_lengths == nullptr ||
      args->utf8_text == nullptr) {
    SetError(args == nullptr ? nullptr : args->error,
             OPENCC_ERROR_INVALID_ARGUMENT, "invalid segment arguments");
    return -1;
  }
  auto* handle = reinterpret_cast<MpdpHandle*>(args->handle);
  args->segment_lengths->codepoint_lengths = nullptr;
  args->segment_lengths->segment_count = 0;

  try {
    const std::string text(args->utf8_text);
    if (text.empty()) {
      return 0;
    }
    // 切成 code point
    std::vector<std::string> cps;
    cps.reserve(text.size());
    for (size_t i = 0; i < text.size();) {
      size_t len = NextCharLength(text.data() + i);
      if (len == 0 || i + len > text.size()) {
        len = 1;
      }
      cps.emplace_back(text, i, len);
      i += len;
    }

    const size_t n = cps.size();
    std::vector<double> best(n + 1, kNegInf);
    std::vector<uint32_t> bestLen(n + 1, 1);
    best[n] = 0.0;

    for (size_t i = n; i-- > 0;) {
      // 單字一律可切（未收錄者給 unknownWeight）
      auto single = handle->weight.find(cps[i]);
      const double singleWeight =
          single != handle->weight.end() ? single->second : handle->unknownWeight;
      best[i] = singleWeight + best[i + 1];
      bestLen[i] = 1;

      // 多字詞：以首字的最長詞長為上界
      auto limitIt = handle->maxLenByFirst.find(cps[i]);
      if (limitIt == handle->maxLenByFirst.end()) {
        continue;
      }
      size_t limit = std::min(limitIt->second, handle->maxWordLength);
      limit = std::min(limit, n - i);
      std::string candidate = cps[i];
      for (size_t len = 2; len <= limit; len++) {
        candidate += cps[i + len - 1];
        auto it = handle->weight.find(candidate);
        if (it == handle->weight.end()) {
          continue;
        }
        const double score = it->second + best[i + len];
        if (score > best[i]) {
          best[i] = score;
          bestLen[i] = static_cast<uint32_t>(len);
        }
      }
    }

    std::vector<uint32_t> lengths;
    lengths.reserve(n / 2 + 1);
    for (size_t i = 0; i < n;) {
      uint32_t len = bestLen[i];
      if (len == 0 || i + len > n) {
        len = 1;
      }
      lengths.push_back(len);
      i += len;
    }

    uint32_t* buffer = new (std::nothrow) uint32_t[lengths.size()];
    if (buffer == nullptr) {
      SetError(args->error, OPENCC_ERROR_PLUGIN_RUNTIME_FAILURE,
               "out of memory");
      return -1;
    }
    std::copy(lengths.begin(), lengths.end(), buffer);
    args->segment_lengths->codepoint_lengths = buffer;
    args->segment_lengths->segment_count = lengths.size();
    return 0;
  } catch (const std::exception& ex) {
    SetError(args->error, OPENCC_ERROR_PLUGIN_RUNTIME_FAILURE, ex.what());
    return -1;
  } catch (...) {
    SetError(args->error, OPENCC_ERROR_PLUGIN_RUNTIME_FAILURE,
             "unknown error while segmenting");
    return -1;
  }
}

void FreeSegmentLengths(opencc_segment_length_array_t* segmentLengths) {
  if (segmentLengths == nullptr) {
    return;
  }
  delete[] segmentLengths->codepoint_lengths;
  segmentLengths->codepoint_lengths = nullptr;
  segmentLengths->segment_count = 0;
}

void DestroySegmentation(opencc_segmentation_handle_t* handle) {
  delete reinterpret_cast<MpdpHandle*>(handle);
}

void FreeError(opencc_error_t* error) {
  if (error == nullptr) {
    return;
  }
  delete[] error->message;
  error->message = nullptr;
}

const opencc_segmentation_plugin_v2 kMpdpPlugin = {
    sizeof(opencc_segmentation_plugin_v2),
    OPENCC_SEGMENTATION_PLUGIN_ABI_MAJOR,
    OPENCC_SEGMENTATION_PLUGIN_ABI_MINOR,
    "opencc-mpdp",
    "mpdp",
    &CreateSegmentation,
    &Segment,
    &FreeSegmentLengths,
    &DestroySegmentation,
    &FreeError,
};

}  // namespace

extern "C" OPENCC_PLUGIN_EXPORT const opencc_segmentation_plugin_v2*
opencc_get_segmentation_plugin_v2(void) {
  return &kMpdpPlugin;
}
