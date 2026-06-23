#pragma once

#include <atomic>
#include <functional>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "core/image_types.hpp"
#include "core/owner_regions.hpp"
#include "core/settings.hpp"

namespace gap_assist {

struct PredictInput {
  const Image& image;
  const std::vector<GapCandidate>& gaps;
  const Settings& settings;
  const Image* referenceImage{};
  const Image* lineArtImage{};
  const Image* guideImage{};
  const OwnerMap* owners{};
  const SelectionMask* selection{};
  const std::atomic_bool* cancelled{};
  std::function<void()> cancellationPoll{};
};

struct PredictResult {
  int gapId{};
  std::optional<Rgba> suggestedColor;
  double confidence{};
  std::optional<int> sourceOwnerId;
  std::string debugInfo;
};

class GapColorPredictor {
 public:
  virtual ~GapColorPredictor() = default;
  [[nodiscard]] virtual std::vector<PredictResult> predict(
      const PredictInput& input) const = 0;
};

void applyPredictions(std::vector<GapCandidate>& gaps,
                      const std::vector<PredictResult>& predictions,
                      const Settings& settings);

}  // namespace gap_assist
