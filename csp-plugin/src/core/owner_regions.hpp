#pragma once

#include <atomic>
#include <cstdint>
#include <vector>

#include "core/gap_detection.hpp"
#include "core/image_types.hpp"
#include "core/settings.hpp"

namespace gap_assist {

struct OwnerRegion {
  int id{};
  std::size_t area{};
  Rect bbox;
  Rgba meanColor{};
};

struct OwnerMap {
  int width{};
  int height{};
  std::vector<std::int32_t> labels;
  std::vector<OwnerRegion> regions;

  [[nodiscard]] int ownerAt(int x, int y) const noexcept {
    if (x < 0 || y < 0 || x >= width || y >= height) return -1;
    return labels[static_cast<std::size_t>(y) * width + x];
  }
};

class OwnerRegionDetector {
 public:
  [[nodiscard]] OwnerMap detect(
      const Image& image, const Settings& settings,
      const SelectionMask* selection = nullptr,
      const std::atomic_bool* cancelled = nullptr,
      const ProgressCallback& progress = {}) const;
};

}  // namespace gap_assist
