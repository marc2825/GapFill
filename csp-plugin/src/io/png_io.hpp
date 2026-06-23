#pragma once

#include <filesystem>

#include "core/image_types.hpp"

namespace gap_assist {

[[nodiscard]] Image loadPng(const std::filesystem::path& path);
void savePng(const std::filesystem::path& path, const Image& image);
[[nodiscard]] SelectionMask loadSelectionPng(const std::filesystem::path& path,
                                             int expectedWidth,
                                             int expectedHeight);

}  // namespace gap_assist
