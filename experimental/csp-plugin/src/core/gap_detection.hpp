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
      const DetectionGeometry& geometry, const Settings& settings,
      const SelectionMask* selection = nullptr,
      const std::atomic_bool* cancelled = nullptr,
      const ProgressCallback& progress = {}) const;

  // Compatibility entry point for the current single-active-layer CLI/host.
  // It normalizes canonical alpha-zero Coloring membership with empty Line and
  // Guide boundaries, then delegates to the pure multi-layer contract.
  [[nodiscard]] std::vector<GapCandidate> detect(
      const Image& image, const Settings& settings,
      const SelectionMask* selection = nullptr,
      const std::atomic_bool* cancelled = nullptr,
      const ProgressCallback& progress = {}) const;
};

}  // namespace gap_assist
