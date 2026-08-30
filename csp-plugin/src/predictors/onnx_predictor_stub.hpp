#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <span>
#include <string>
#include <vector>

#include "predictors/gap_color_predictor.hpp"

namespace gap_assist {

inline constexpr std::size_t kGapFillPatchSize = 32;
inline constexpr std::size_t kGapFillPatchPixels =
    kGapFillPatchSize * kGapFillPatchSize;
inline constexpr const char* kGapFillModelSha256 =
    "8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78";

struct ModelContract {
  std::string artifactSha256;
  std::size_t inputCount{};
  std::size_t outputCount{};
  std::string inputName;
  std::string outputName;
  std::array<std::int64_t, 4> inputShape{};
  std::array<std::int64_t, 4> outputShape{};
  std::string inputType;
  std::string outputType;
};

class InferenceBackend {
 public:
  virtual ~InferenceBackend() = default;
  [[nodiscard]] virtual ModelContract contract() const = 0;
  [[nodiscard]] virtual std::vector<float> run(
      std::span<const float> input) const = 0;
};

struct LearnedPatch {
  int virtualX{};
  int virtualY{};
  std::vector<float> tensor;
  std::vector<std::uint8_t> valid;
};

struct LearnedRegionSelection {
  std::int32_t label{};
  double meanProbability{};
  Rgba color{};
  std::vector<std::uint32_t> pixelIndices;
};

[[nodiscard]] bool canonicalModelBoundary(Rgba pixel) noexcept;
[[nodiscard]] LearnedPatch buildLearnedPatch(
    const Image& coloring, const Image& lineArt, const GapCandidate& gap);
[[nodiscard]] std::vector<std::int32_t> buildLineRegionLabels(
    const Image& lineArt);
[[nodiscard]] LearnedRegionSelection selectLearnedRegion(
    std::span<const Rgba> coloring, std::span<const std::int32_t> labels,
    std::span<const std::uint8_t> valid,
    std::span<const float> probabilities);

class LearnedGapPredictor final : public GapColorPredictor {
 public:
  explicit LearnedGapPredictor(const InferenceBackend& backend)
      : backend_(backend) {}

  [[nodiscard]] std::vector<PredictResult> predict(
      const PredictInput& input) const override;

 private:
  const InferenceBackend& backend_;
};

// Packaging/runtime adapter placeholder. Phase 5 establishes and tests the
// pure learned pipeline through InferenceBackend; distribution of ONNX Runtime
// for CSP remains a later release-packaging gate.
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
