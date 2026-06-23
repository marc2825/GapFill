#pragma once

#include <atomic>
#include <functional>
#include <vector>

#include "core/image_types.hpp"
#include "core/settings.hpp"

namespace gap_assist {

using ProgressCallback = std::function<void(std::size_t completed, std::size_t total)>;

class GapDetector {
 public:
  [[nodiscard]] std::vector<GapCandidate> detect(
      const Image& image, const Settings& settings,
      const SelectionMask* selection = nullptr,
      const std::atomic_bool* cancelled = nullptr,
      const ProgressCallback& progress = {}) const;
};

}  // namespace gap_assist
