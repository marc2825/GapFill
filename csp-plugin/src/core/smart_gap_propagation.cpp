#include "core/smart_gap_propagation.hpp"

#include <stdexcept>

namespace gap_assist {

AnalysisResult SmartGapPropagation::analyze(
    const Image& image, const Settings& settings, const GapColorPredictor& predictor,
    const SelectionMask* selection, const std::atomic_bool* cancelled,
    const ProgressCallback& progress,
    const std::function<void()>& cancellationPoll, const Image* lineArtImage,
    const Image* guideImage) const {
  const auto geometry = normalizeCanonicalColoringGeometry(image);
  return analyze(image, geometry, settings, predictor, selection, cancelled,
                 progress, cancellationPoll, lineArtImage, guideImage);
}

AnalysisResult SmartGapPropagation::analyze(
    const Image& image, const DetectionGeometry& geometry,
    const Settings& settings, const GapColorPredictor& predictor,
    const SelectionMask* selection, const std::atomic_bool* cancelled,
    const ProgressCallback& progress,
    const std::function<void()>& cancellationPoll, const Image* lineArtImage,
    const Image* guideImage) const {
  if (geometry.width() != image.width() || geometry.height() != image.height())
    throw std::invalid_argument(
        "Detection geometry dimensions do not match the prediction image.");
  GapDetector gapDetector;
  OwnerRegionDetector ownerDetector;
  AnalysisResult result;
  result.gaps = gapDetector.detect(geometry, settings, selection, cancelled, progress);
  result.candidateContext =
      captureCandidateContext(image, settings, selection, &geometry);
  // An empty candidate batch must not initialize a model backend or perform
  // prediction-only owner/region work.
  if (result.gaps.empty()) return result;
  const auto owners = ownerDetector.detect(image, settings, selection, cancelled, progress);
  const PredictInput input{.image = image,
                           .gaps = result.gaps,
                           .settings = settings,
                           .lineArtImage = lineArtImage,
                           .guideImage = guideImage,
                           .owners = &owners,
                           .selection = selection,
                           .cancelled = cancelled,
                           .cancellationPoll = cancellationPoll};
  applyPredictions(result.gaps, predictor.predict(input), settings);
  return result;
}

}  // namespace gap_assist
