#pragma once

#include "predictors/gap_color_predictor.hpp"

namespace gap_assist {

class RuleBasedPredictor final : public GapColorPredictor {
 public:
  [[nodiscard]] std::vector<PredictResult> predict(
      const PredictInput& input) const override;
};

}  // namespace gap_assist
