#include "ui/dialog_model.hpp"

#include <algorithm>

namespace gap_assist {

std::vector<ReviewRow> DialogModel::rows() const {
  std::vector<ReviewRow> result;
  result.reserve(session_.gaps().size());
  for (const auto& gap : session_.gaps()) {
    result.push_back({.apply = gap.apply,
                      .gapId = gap.id,
                      .confidence = gap.confidence,
                      .band = gap.confidenceBand,
                      .predictionProvenance = gap.predictionProvenance,
                      .learnedConfidence = gap.learnedConfidence,
                      .heuristicScore = gap.heuristicScore,
                      .suggestedColor = gap.suggestedColor,
                      .status = gap.status,
                      .thumbnailSource = gap.bbox});
  }
  return result;
}

std::optional<GapDetail> DialogModel::detail(int gapId) const {
  const auto& gaps = session_.gaps();
  const auto found = std::find_if(gaps.begin(), gaps.end(),
                                  [&](const auto& gap) { return gap.id == gapId; });
  if (found == gaps.end()) return std::nullopt;
  return GapDetail{.gapId = found->id,
                   .previewSource = found->bbox,
                   .suggestedColor = found->suggestedColor,
                   .confidence = found->confidence,
                   .band = found->confidenceBand,
                   .predictionProvenance = found->predictionProvenance,
                   .learnedConfidence = found->learnedConfidence,
                   .heuristicScore = found->heuristicScore,
                   .semanticRegionLabel = found->semanticRegionLabel,
                   .sourceOwnerId = found->sourceOwnerId};
}

}  // namespace gap_assist
