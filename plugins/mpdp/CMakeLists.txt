cmake_minimum_required(VERSION 3.10)
project(opencc_mpdp CXX)

# MPDP segmentation plugin for OpenCC.
#
# 純 C ABI 外掛，只依賴 OpenCC 的公開外掛標頭，不需要連結 libopencc。
# 用法:
#   cmake -S . -B build -DOPENCC_SOURCE_DIR=/path/to/OpenCC
#   cmake --build build
#
# 產出: build/libopencc-mpdp.so

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

if(NOT DEFINED OPENCC_SOURCE_DIR)
  set(OPENCC_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../..")
endif()
if(NOT EXISTS "${OPENCC_SOURCE_DIR}/src/plugin/OpenCCPlugin.h")
  message(FATAL_ERROR
    "找不到 ${OPENCC_SOURCE_DIR}/src/plugin/OpenCCPlugin.h；"
    "請以 -DOPENCC_SOURCE_DIR=/path/to/OpenCC 指定 OpenCC 原始碼根目錄")
endif()

add_library(opencc_mpdp MODULE src/MpdpPlugin.cpp)
target_include_directories(opencc_mpdp PRIVATE "${OPENCC_SOURCE_DIR}/src")
set_target_properties(opencc_mpdp PROPERTIES
  PREFIX "lib"
  OUTPUT_NAME "opencc-mpdp"
  POSITION_INDEPENDENT_CODE ON
)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(opencc_mpdp PRIVATE -Wall -Wextra -Wno-unused-parameter)
endif()

# 安裝位置對齊 OpenCC 的外掛搜尋路徑: <libdir>/opencc/plugins
include(GNUInstallDirs)
install(TARGETS opencc_mpdp
  LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}/opencc/plugins"
)
