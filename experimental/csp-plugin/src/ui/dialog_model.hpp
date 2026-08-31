#pragma once

#include <optional>
#include <string>
#include <vector>

#include "core/image_types.hpp"
#include "ui/review_session.hpp"

namespace gap_assist {

struct ReviewRow {
  bool apply{};
  int gapId{};
  double confidence{};
  ConfidenceBand band{ConfidenceBand::Low};
  PredictionProvenance predictionProvenance{PredictionProvenance::None};
  std::optional<double> learnedConfidence;
  std::optional<double> heuristicScore;
  std::optional<Rgba> suggestedColor;
  ReviewStatus status{ReviewStatus::Unreviewed};
  Rect thumbnailSource;
};

struct GapDetail {
  int gapId{};
  Rect previewSource;
  std::optional<Rgba> suggestedColor;
  double confidence{};
  ConfidenceBand band{ConfidenceBand::Low};
  PredictionProvenance predictionProvenance{PredictionProvenance::None};
  std::optional<double> learnedConfidence;
  std::optional<double> heuristicScore;
  std::optional<std::int32_t> semanticRegionLabel;
  std::optional<int> sourceOwnerId;
};

class DialogModel {
 public:
  explicit DialogModel(ReviewSession& session) : session_(session) {}

  [[nodiscard]] std::vector<ReviewRow> rows() const;
  [[nodiscard]] std::optional<GapDetail> detail(int gapId) const;

 private:
  ReviewSession& session_;
};

}  // namespace gap_assist
