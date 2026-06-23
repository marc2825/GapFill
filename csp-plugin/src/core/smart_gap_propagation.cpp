#include "core/smart_gap_propagation.hpp"

namespace gap_assist {

AnalysisResult SmartGapPropagation::analyze(
    const Image& image, const Settings& settings, const GapColorPredictor& predictor,
    const SelectionMask* selection, const std::atomic_bool* cancelled,
    const ProgressCallback& progress,
    const std::function<void()>& cancellationPoll) const {
  GapDetector gapDetector;
  OwnerRegionDetector ownerDetector;
  AnalysisResult result;
  result.gaps = gapDetector.detect(image, settings, selection, cancelled, progress);
  const auto owners = ownerDetector.detect(image, settings, selection, cancelled, progress);
  const PredictInput input{.image = image,
                           .gaps = result.gaps,
                           .settings = settings,
                           .owners = &owners,
                           .selection = selection,
                           .cancelled = cancelled,
                           .cancellationPoll = cancellationPoll};
  applyPredictions(result.gaps, predictor.predict(input), settings);
  return result;
}

}  // namespace gap_assist
