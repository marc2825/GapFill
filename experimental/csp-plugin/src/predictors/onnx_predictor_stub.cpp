#include "predictors/onnx_predictor_stub.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace gap_assist {
namespace {

constexpr std::array<std::int64_t, 4> kInputShape{1, 2, 32, 32};
constexpr std::array<std::int64_t, 4> kOutputShape{1, 1, 32, 32};

void checkCancellation(const PredictInput& input) {
  if (input.cancellationPoll) input.cancellationPoll();
  if (input.cancelled != nullptr && input.cancelled->load())
    throw std::runtime_error("Color prediction cancelled.");
}

void validateDimensions(const Image& coloring, const Image& lineArt) {
  if (coloring.width() != lineArt.width() ||
      coloring.height() != lineArt.height()) {
    throw std::invalid_argument(
        "Line Art dimensions must match the Coloring prediction image.");
  }
}

void validateContract(const ModelContract& contract) {
  if (contract.artifactSha256 != kGapFillModelSha256)
    throw std::runtime_error("GapFill model SHA-256 does not match the frozen artifact.");
  if (contract.inputCount != 1U || contract.outputCount != 1U)
    throw std::runtime_error("GapFill expects exactly one model input and one output.");
  if (contract.inputName != "input_mask" ||
      contract.outputName != "nearest_region_mask")
    throw std::runtime_error("GapFill model input/output names are incompatible.");
  if (contract.inputShape != kInputShape || contract.outputShape != kOutputShape)
    throw std::runtime_error("GapFill model input/output shapes are incompatible.");
  if (contract.inputType != "tensor(float)" ||
      contract.outputType != "tensor(float)")
    throw std::runtime_error("GapFill model input/output must be float32 tensors.");
}

}  // namespace

bool canonicalModelBoundary(Rgba pixel) noexcept {
  const auto red = static_cast<std::uint32_t>(pixel.r);
  const auto green = static_cast<std::uint32_t>(pixel.g);
  const auto blue = static_cast<std::uint32_t>(pixel.b);
  const auto alpha = static_cast<std::uint32_t>(pixel.a);
  const auto luma =
      (red * 4899U + green * 9617U + blue * 1868U + 8192U) >> 14U;
  const auto composited =
      (luma * alpha + 255U * (255U - alpha) + 127U) / 255U;
  return composited <= 128U;
}

LearnedPatch buildLearnedPatch(const Image& coloring, const Image& lineArt,
                               const GapCandidate& gap) {
  validateDimensions(coloring, lineArt);
  if (coloring.empty())
    throw std::invalid_argument("Learned prediction requires a nonempty image.");
  if (gap.pixels.empty())
    throw std::invalid_argument("Learned prediction requires a nonempty gap.");
  if (!std::isfinite(gap.centroid.x) || !std::isfinite(gap.centroid.y))
    throw std::invalid_argument("Gap centroid must be finite.");

  const int centerX = static_cast<int>(std::floor(gap.centroid.x));
  const int centerY = static_cast<int>(std::floor(gap.centroid.y));
  LearnedPatch patch;
  patch.virtualX = centerX - static_cast<int>(kGapFillPatchSize / 2U);
  patch.virtualY = centerY - static_cast<int>(kGapFillPatchSize / 2U);
  patch.tensor.assign(2U * kGapFillPatchPixels, 0.0F);
  patch.valid.assign(kGapFillPatchPixels, 0U);

  for (std::size_t patchY = 0; patchY < kGapFillPatchSize; ++patchY) {
    for (std::size_t patchX = 0; patchX < kGapFillPatchSize; ++patchX) {
      const int sourceX = patch.virtualX + static_cast<int>(patchX);
      const int sourceY = patch.virtualY + static_cast<int>(patchY);
      if (sourceX < 0 || sourceY < 0 || sourceX >= coloring.width() ||
          sourceY >= coloring.height())
        continue;
      const auto patchIndex = patchY * kGapFillPatchSize + patchX;
      patch.valid[patchIndex] = 1U;
      if (canonicalModelBoundary(lineArt.at(sourceX, sourceY)))
        patch.tensor[patchIndex] = 1.0F;
    }
  }

  for (const auto rawIndex : gap.pixels) {
    const auto index = static_cast<std::size_t>(rawIndex);
    if (index >= coloring.size())
      throw std::invalid_argument("Gap pixel is outside the prediction image.");
    if (coloring.atIndex(index).a != 0)
      throw std::invalid_argument(
          "Learned target pixels must be fully transparent Coloring pixels.");
    const int sourceX =
        static_cast<int>(index % static_cast<std::size_t>(coloring.width()));
    const int sourceY =
        static_cast<int>(index / static_cast<std::size_t>(coloring.width()));
    const int patchX = sourceX - patch.virtualX;
    const int patchY = sourceY - patch.virtualY;
    if (patchX >= 0 && patchY >= 0 &&
        patchX < static_cast<int>(kGapFillPatchSize) &&
        patchY < static_cast<int>(kGapFillPatchSize)) {
      const auto patchIndex = static_cast<std::size_t>(patchY) *
                                  kGapFillPatchSize +
                              static_cast<std::size_t>(patchX);
      patch.tensor[kGapFillPatchPixels + patchIndex] = 1.0F;
    }
  }
  return patch;
}

std::vector<std::int32_t> buildLineRegionLabels(const Image& lineArt) {
  std::vector<std::int32_t> labels(lineArt.size(), 0);
  std::vector<std::uint32_t> queue;
  queue.reserve(lineArt.size());
  std::int32_t nextLabel = 0;
  const auto width = lineArt.width();
  const auto height = lineArt.height();

  for (std::size_t seed = 0; seed < lineArt.size(); ++seed) {
    if (labels[seed] != 0 || canonicalModelBoundary(lineArt.atIndex(seed)))
      continue;
    if (nextLabel == std::numeric_limits<std::int32_t>::max())
      throw std::overflow_error("Line-region label count exceeds int32 capacity.");
    ++nextLabel;
    labels[seed] = nextLabel;
    queue.clear();
    queue.push_back(static_cast<std::uint32_t>(seed));
    for (std::size_t cursor = 0; cursor < queue.size(); ++cursor) {
      const auto index = static_cast<std::size_t>(queue[cursor]);
      const int x =
          static_cast<int>(index % static_cast<std::size_t>(width));
      const int y =
          static_cast<int>(index / static_cast<std::size_t>(width));
      const auto visit = [&](int neighborX, int neighborY) {
        if (neighborX < 0 || neighborY < 0 || neighborX >= width ||
            neighborY >= height)
          return;
        const auto neighbor = static_cast<std::size_t>(neighborY) *
                                  static_cast<std::size_t>(width) +
                              static_cast<std::size_t>(neighborX);
        if (labels[neighbor] != 0 ||
            canonicalModelBoundary(lineArt.atIndex(neighbor)))
          return;
        labels[neighbor] = nextLabel;
        queue.push_back(static_cast<std::uint32_t>(neighbor));
      };
      visit(x - 1, y);
      visit(x + 1, y);
      visit(x, y - 1);
      visit(x, y + 1);
    }
  }
  return labels;
}

LearnedRegionSelection selectLearnedRegion(
    std::span<const Rgba> coloring, std::span<const std::int32_t> labels,
    std::span<const std::uint8_t> valid,
    std::span<const float> probabilities) {
  if (coloring.empty() || coloring.size() != labels.size() ||
      coloring.size() != valid.size() || coloring.size() != probabilities.size())
    throw std::invalid_argument(
        "Canonical postprocessing arrays must be nonempty and equal-sized.");

  std::vector<std::int32_t> labelOrder;
  labelOrder.reserve(labels.size());
  for (std::size_t index = 0; index < labels.size(); ++index) {
    if (!std::isfinite(probabilities[index]) || probabilities[index] < 0.0F ||
        probabilities[index] > 1.0F)
      throw std::runtime_error(
          "GapFill model output must contain finite values within [0, 1].");
    if (labels[index] < 0)
      throw std::invalid_argument("Semantic labels must be nonnegative.");
    if (valid[index] > 1U)
      throw std::invalid_argument("Patch validity values must be binary.");
    if (valid[index] == 0U || labels[index] == 0) continue;
    if (std::find(labelOrder.begin(), labelOrder.end(), labels[index]) ==
        labelOrder.end())
      labelOrder.push_back(labels[index]);
  }

  std::int32_t bestLabel = 0;
  double bestMean = -std::numeric_limits<double>::infinity();
  for (const auto label : labelOrder) {
    double sum = 0.0;
    std::size_t area = 0;
    std::size_t painted = 0;
    for (std::size_t index = 0; index < labels.size(); ++index) {
      if (valid[index] == 0U || labels[index] != label) continue;
      sum += static_cast<double>(probabilities[index]);
      ++area;
      if (coloring[index].a > 0) ++painted;
    }
    if (area == 0 || painted == 0) continue;
    const double mean = sum / static_cast<double>(area);
    if (mean > bestMean) {
      bestMean = mean;
      bestLabel = label;
    }
  }
  if (bestLabel == 0)
    throw std::runtime_error(
        "No painted semantic region is available for prediction.");

  struct ColorCount {
    Rgba color;
    std::size_t count{};
  };
  std::vector<ColorCount> counts;
  LearnedRegionSelection selection;
  selection.label = bestLabel;
  selection.meanProbability = bestMean;
  for (std::size_t index = 0; index < labels.size(); ++index) {
    if (valid[index] == 0U || labels[index] != bestLabel) continue;
    selection.pixelIndices.push_back(static_cast<std::uint32_t>(index));
    if (coloring[index].a == 0) continue;
    const Rgba key{coloring[index].r, coloring[index].g, coloring[index].b, 255};
    const auto found = std::find_if(
        counts.begin(), counts.end(),
        [&](const ColorCount& entry) { return entry.color == key; });
    if (found == counts.end())
      counts.push_back({key, 1U});
    else
      ++found->count;
  }
  if (counts.empty())
    throw std::runtime_error(
        "The selected semantic region has no painted color.");
  const auto selected = std::max_element(
      counts.begin(), counts.end(), [](const ColorCount& left,
                                       const ColorCount& right) {
        return left.count < right.count;
      });
  selection.color = selected->color;
  return selection;
}

std::vector<PredictResult> LearnedGapPredictor::predict(
    const PredictInput& input) const {
  if (input.gaps.empty()) return {};
  if (input.lineArtImage == nullptr)
    throw std::invalid_argument("Learned prediction requires a Line Art image.");
  validateDimensions(input.image, *input.lineArtImage);

  checkCancellation(input);
  validateContract(backend_.contract());
  checkCancellation(input);
  const auto fullLabels = buildLineRegionLabels(*input.lineArtImage);

  std::vector<PredictResult> pending;
  pending.reserve(input.gaps.size());
  for (const auto& gap : input.gaps) {
    checkCancellation(input);
    const auto patch = buildLearnedPatch(input.image, *input.lineArtImage, gap);
    if (patch.tensor.size() != 2U * kGapFillPatchPixels)
      throw std::logic_error("Canonical model tensor has an invalid size.");
    checkCancellation(input);
    const auto output = backend_.run(patch.tensor);
    // ONNX Runtime calls are synchronous and cannot be interrupted. This poll
    // is the first cancellation boundary after a completed backend call.
    checkCancellation(input);
    if (output.size() != kGapFillPatchPixels)
      throw std::runtime_error("GapFill model returned an invalid output size.");

    std::vector<Rgba> coloringPatch(kGapFillPatchPixels);
    std::vector<std::int32_t> labelPatch(kGapFillPatchPixels, 0);
    for (std::size_t patchY = 0; patchY < kGapFillPatchSize; ++patchY) {
      for (std::size_t patchX = 0; patchX < kGapFillPatchSize; ++patchX) {
        const auto patchIndex = patchY * kGapFillPatchSize + patchX;
        if (patch.valid[patchIndex] == 0U) continue;
        const int sourceX = patch.virtualX + static_cast<int>(patchX);
        const int sourceY = patch.virtualY + static_cast<int>(patchY);
        const auto sourceIndex = static_cast<std::size_t>(sourceY) *
                                     static_cast<std::size_t>(input.image.width()) +
                                 static_cast<std::size_t>(sourceX);
        coloringPatch[patchIndex] = input.image.atIndex(sourceIndex);
        labelPatch[patchIndex] = fullLabels[sourceIndex];
      }
    }
    const auto selected = selectLearnedRegion(
        coloringPatch, labelPatch, patch.valid, output);
    PredictResult result;
    result.gapId = gap.id;
    result.suggestedColor = selected.color;
    result.provenance = PredictionProvenance::Learned;
    result.learnedConfidence = selected.meanProbability;
    result.semanticRegionLabel = selected.label;
    result.confidence = selected.meanProbability;
    std::ostringstream debug;
    debug << "learned_region=" << selected.label
          << ", mean_probability=" << selected.meanProbability;
    result.debugInfo = debug.str();
    pending.push_back(std::move(result));
  }
  checkCancellation(input);
  return pending;
}

std::vector<PredictResult> OnnxPredictorStub::predict(const PredictInput&) const {
  throw std::runtime_error(
      "The CSP build has no ONNX Runtime adapter. Learned prediction cannot run; "
      "choose the explicitly labeled Rule-Based heuristic if desired. Requested "
      "model: " +
      modelPath_.string());
}

}  // namespace gap_assist
