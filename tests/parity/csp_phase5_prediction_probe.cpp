#include <array>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "core/gap_detection.hpp"
#include "core/smart_gap_propagation.hpp"
#include "predictors/onnx_predictor_stub.hpp"

namespace ga = gap_assist;

namespace {

constexpr std::array<std::uint32_t, 32> kBoundaryIndices{
    396, 397, 398, 399, 400, 401, 402, 403, 404, 428, 436,
    460, 468, 492, 500, 524, 532, 556, 564, 588, 596, 620,
    628, 652, 653, 654, 655, 656, 657, 658, 659, 660};
constexpr std::uint32_t kGapIndex = 528;

struct Fixture {
  ga::Image coloring{32, 32};
  ga::Image line{32, 32};
  ga::DetectionGeometry geometry{32, 32};
  ga::GapCandidate gap;
};

Fixture makeFixture() {
  Fixture fixture;
  for (const auto index : kBoundaryIndices)
    fixture.line.atIndex(index) = {0, 0, 0, 255};
  const auto labels = ga::buildLineRegionLabels(fixture.line);
  for (std::size_t index = 0; index < labels.size(); ++index) {
    if (labels[index] == 1)
      fixture.coloring.atIndex(index) = {240, 20, 20, 255};
    else if (labels[index] > 1)
      fixture.coloring.atIndex(index) = {20, 20, 240, 255};
  }
  fixture.coloring.atIndex(kGapIndex) = {};
  fixture.geometry =
      ga::normalizeLegacyRgbaGeometry(fixture.coloring, &fixture.line);
  ga::Settings settings;
  settings.gapThreshold = 10;
  const auto gaps = ga::GapDetector{}.detect(fixture.geometry, settings);
  if (gaps.size() != 1 || gaps[0].pixels != std::vector<std::uint32_t>{kGapIndex})
    throw std::runtime_error("Phase 5 probe fixture did not produce its canonical gap.");
  fixture.gap = gaps[0];
  return fixture;
}

void printActive(std::string_view name, std::span<const float> values) {
  std::cout << name << '=';
  bool first = true;
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (values[index] == 0.0F) continue;
    if (!first) std::cout << ',';
    first = false;
    std::cout << index;
  }
  std::cout << '\n';
}

class FileBackend final : public ga::InferenceBackend {
 public:
  explicit FileBackend(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot read model output fixture.");
    for (float value = 0.0F; input >> value;) output_.push_back(value);
    if (!input.eof()) throw std::runtime_error("Invalid model output fixture.");
  }

  [[nodiscard]] ga::ModelContract contract() const override {
    return {.artifactSha256 = ga::kGapFillModelSha256,
            .inputCount = 1,
            .outputCount = 1,
            .inputName = "input_mask",
            .outputName = "nearest_region_mask",
            .inputShape = {1, 2, 32, 32},
            .outputShape = {1, 1, 32, 32},
            .inputType = "tensor(float)",
            .outputType = "tensor(float)"};
  }

  [[nodiscard]] std::vector<float> run(
      std::span<const float> input) const override {
    lastInput.assign(input.begin(), input.end());
    return output_;
  }

  mutable std::vector<float> lastInput;

 private:
  std::vector<float> output_;
};

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc < 2)
      throw std::invalid_argument("usage: PROBE tensor | predict OUTPUT.txt");
    const auto fixture = makeFixture();
    const std::string command = argv[1];
    if (command == "tensor") {
      const auto patch =
          ga::buildLearnedPatch(fixture.coloring, fixture.line, fixture.gap);
      printActive("boundary", std::span<const float>(patch.tensor).first(1024));
      printActive("target", std::span<const float>(patch.tensor).subspan(1024));
      return 0;
    }
    if (command == "predict" && argc == 3) {
      FileBackend backend(argv[2]);
      ga::LearnedGapPredictor predictor(backend);
      ga::Settings settings;
      settings.gapThreshold = 10;
      const auto analysis = ga::SmartGapPropagation{}.analyze(
          fixture.coloring, fixture.geometry, settings, predictor, nullptr,
          nullptr, {}, {}, &fixture.line);
      if (analysis.gaps.size() != 1)
        throw std::runtime_error("Learned probe did not return exactly one gap.");
      const auto& gap = analysis.gaps[0];
      printActive("boundary", std::span<const float>(backend.lastInput).first(1024));
      printActive("target", std::span<const float>(backend.lastInput).subspan(1024));
      std::cout << "region=" << gap.semanticRegionLabel.value_or(0) << '\n';
      std::cout << std::setprecision(17)
                << "confidence=" << gap.learnedConfidence.value_or(-1.0) << '\n';
      if (!gap.suggestedColor.has_value())
        throw std::runtime_error("Learned probe returned no RGB color.");
      std::cout << "rgb=" << static_cast<int>(gap.suggestedColor->r) << ','
                << static_cast<int>(gap.suggestedColor->g) << ','
                << static_cast<int>(gap.suggestedColor->b) << '\n';
      std::cout << "provenance=" << ga::toString(gap.predictionProvenance) << '\n';
      return 0;
    }
    throw std::invalid_argument("usage: PROBE tensor | predict OUTPUT.txt");
  } catch (const std::exception& error) {
    std::cerr << "Phase 5 CSP probe error: " << error.what() << '\n';
    return 1;
  }
}
