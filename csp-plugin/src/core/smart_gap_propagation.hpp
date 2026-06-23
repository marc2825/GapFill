#pragma once

#include <atomic>
#include <functional>

#include "core/gap_detection.hpp"
#include "core/owner_regions.hpp"
#include "predictors/gap_color_predictor.hpp"

namespace gap_assist {

struct AnalysisResult {
  std::vector<GapCandidate> gaps;
};

class SmartGapPropagation {
 public:
  [[nodiscard]] AnalysisResult analyze(
      const Image& image, const Settings& settings,
      const GapColorPredictor& predictor,
      const SelectionMask* selection = nullptr,
      const std::atomic_bool* cancelled = nullptr,
      const ProgressCallback& progress = {},
      const std::function<void()>& cancellationPoll = {}) const;
};

}  // namespace gap_assist
