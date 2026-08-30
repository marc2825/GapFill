#pragma once

#include <cstdint>
#include <filesystem>
#include <vector>

#include "core/image_types.hpp"

namespace gap_assist {

[[nodiscard]] Image loadPng(const std::filesystem::path& path);
[[nodiscard]] std::vector<std::uint8_t> encodePng(const Image& image);
void savePng(const std::filesystem::path& path, const Image& image);
[[nodiscard]] SelectionMask loadSelectionPng(const std::filesystem::path& path,
                                             int expectedWidth,
                                             int expectedHeight);

}  // namespace gap_assist
