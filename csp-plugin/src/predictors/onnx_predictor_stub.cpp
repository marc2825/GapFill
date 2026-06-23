#include "predictors/onnx_predictor_stub.hpp"

#include <stdexcept>

namespace gap_assist {

std::vector<PredictResult> OnnxPredictorStub::predict(const PredictInput&) const {
  throw std::runtime_error(
      "The CSP build has no ONNX Runtime adapter. Use RuleBasedPredictor; no image data "
      "will be sent to an external service. Requested model: " +
      modelPath_.string());
}

}  // namespace gap_assist
