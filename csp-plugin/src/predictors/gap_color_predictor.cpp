#include "predictors/gap_color_predictor.hpp"

#include <algorithm>
#include <unordered_map>

namespace gap_assist {

void applyPredictions(std::vector<GapCandidate>& gaps,
                      const std::vector<PredictResult>& predictions,
                      const Settings& settings) {
  std::unordered_map<int, const PredictResult*> byId;
  for (const auto& prediction : predictions) byId[prediction.gapId] = &prediction;
  for (auto& gap : gaps) {
    const auto found = byId.find(gap.id);
    if (found == byId.end() || !found->second->suggestedColor.has_value()) {
      gap.suggestedColor.reset();
      gap.confidence = 0.0;
      gap.confidenceBand = ConfidenceBand::Low;
      gap.apply = false;
      gap.status = ReviewStatus::MarkOnly;
      gap.debugInfo = found == byId.end() ? "prediction missing" : found->second->debugInfo;
      continue;
    }
    const auto& prediction = *found->second;
    gap.suggestedColor = prediction.suggestedColor;
    gap.confidence = std::clamp(prediction.confidence, 0.0, 1.0);
    gap.confidenceBand = classifyConfidence(gap.confidence, settings.confidencePreset);
    gap.apply = gap.confidenceBand == ConfidenceBand::High;
    gap.status = gap.apply ? ReviewStatus::Apply : ReviewStatus::Unreviewed;
    gap.sourceOwnerId = prediction.sourceOwnerId;
    gap.debugInfo = prediction.debugInfo;
  }
}

}  // namespace gap_assist
