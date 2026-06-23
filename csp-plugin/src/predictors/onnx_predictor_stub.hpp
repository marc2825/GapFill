#pragma once

#include <filesystem>

#include "predictors/gap_color_predictor.hpp"

namespace gap_assist {

class OnnxPredictorStub final : public GapColorPredictor {
 public:
  explicit OnnxPredictorStub(std::filesystem::path modelPath)
      : modelPath_(std::move(modelPath)) {}

  [[nodiscard]] bool available() const { return false; }
  [[nodiscard]] std::vector<PredictResult> predict(
      const PredictInput& input) const override;

 private:
  std::filesystem::path modelPath_;
};

}  // namespace gap_assist
