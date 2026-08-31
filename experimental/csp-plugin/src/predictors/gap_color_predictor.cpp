#include "predictors/gap_color_predictor.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
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
      gap.predictionProvenance =
          found == byId.end() ? PredictionProvenance::None
                              : found->second->provenance;
      gap.learnedConfidence.reset();
      gap.heuristicScore =
          found == byId.end() ? std::nullopt : found->second->heuristicScore;
      gap.semanticRegionLabel.reset();
      gap.confidence = 0.0;
      gap.confidenceBand = ConfidenceBand::Low;
      gap.apply = false;
      gap.status = ReviewStatus::MarkOnly;
      gap.debugInfo = found == byId.end() ? "prediction missing" : found->second->debugInfo;
      continue;
    }
    const auto& prediction = *found->second;
    gap.suggestedColor = prediction.suggestedColor;
    gap.predictionProvenance = prediction.provenance;
    gap.learnedConfidence = prediction.learnedConfidence;
    gap.heuristicScore = prediction.heuristicScore;
    gap.semanticRegionLabel = prediction.semanticRegionLabel;
    if (prediction.provenance == PredictionProvenance::Learned) {
      if (!prediction.learnedConfidence.has_value() ||
          !std::isfinite(*prediction.learnedConfidence) ||
          *prediction.learnedConfidence < 0.0 ||
          *prediction.learnedConfidence > 1.0) {
        throw std::invalid_argument(
            "Learned predictions require a finite confidence within [0, 1].");
      }
      if (prediction.heuristicScore.has_value())
        throw std::invalid_argument(
            "Learned predictions cannot carry a heuristic score.");
      if (!prediction.semanticRegionLabel.has_value() ||
          *prediction.semanticRegionLabel <= 0)
        throw std::invalid_argument(
            "Learned predictions require a positive semantic-region label.");
      gap.confidence = *prediction.learnedConfidence;
      gap.confidenceBand =
          classifyConfidence(gap.confidence, settings.confidencePreset);
      gap.apply = gap.confidenceBand == ConfidenceBand::High;
      gap.status = gap.apply ? ReviewStatus::Apply : ReviewStatus::Unreviewed;
    } else if (prediction.provenance ==
               PredictionProvenance::HeuristicFallback) {
      if (prediction.learnedConfidence.has_value())
        throw std::invalid_argument(
            "Heuristic fallback cannot carry learned confidence.");
      if (prediction.semanticRegionLabel.has_value())
        throw std::invalid_argument(
            "Heuristic fallback cannot claim a learned semantic region.");
      gap.confidence = 0.0;
      gap.confidenceBand = ConfidenceBand::Low;
      gap.apply = false;
      gap.status = ReviewStatus::Unreviewed;
    } else {
      throw std::invalid_argument(
          "A color prediction must declare learned or heuristic provenance.");
    }
    gap.sourceOwnerId = prediction.sourceOwnerId;
    gap.debugInfo = prediction.debugInfo;
  }
}

}  // namespace gap_assist
