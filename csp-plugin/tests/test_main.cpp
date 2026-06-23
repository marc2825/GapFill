#include <atomic>
#include <filesystem>
#include <functional>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "core/correction_output.hpp"
#include "core/gap_detection.hpp"
#include "core/owner_regions.hpp"
#include "core/quick_fix_pipeline.hpp"
#include "core/smart_gap_propagation.hpp"
#include "io/png_io.hpp"
#include "plugin_entry/gap_assist_command.hpp"
#include "predictors/gap_color_predictor.hpp"
#include "predictors/rule_based_predictor.hpp"
#include "ui/review_session.hpp"

namespace ga = gap_assist;

namespace {

struct TestFailure : std::runtime_error {
  using std::runtime_error::runtime_error;
};

#define CHECK(condition)                                                        \
  do {                                                                          \
    if (!(condition))                                                           \
      throw TestFailure(std::string("CHECK failed: ") + #condition + " at " + \
                        __FILE__ + ":" + std::to_string(__LINE__));             \
  } while (false)

ga::Image opaqueImage(int width, int height, ga::Rgba color = {180, 40, 20, 255}) {
  return ga::Image(width, height, color);
}

ga::GapCandidate makeGap(int id, std::uint32_t pixel, ga::Rgba color,
                         double confidence, ga::ConfidenceBand band) {
  ga::GapCandidate gap;
  gap.id = id;
  gap.pixels = {pixel};
  gap.area = 1;
  gap.bbox = {static_cast<int>(pixel), 0, 1, 1};
  gap.centroid = {static_cast<double>(pixel), 0};
  gap.suggestedColor = color;
  gap.confidence = confidence;
  gap.confidenceBand = band;
  return gap;
}

void detectsSmallTransparentRegion() {
  auto image = opaqueImage(7, 7);
  image.at(3, 3) = {};
  ga::Settings settings;
  settings.gapThreshold = 3;
  const auto gaps = ga::GapDetector().detect(image, settings);
  CHECK(gaps.size() == 1);
  CHECK(gaps[0].area == 1);
  CHECK(gaps[0].bbox.x == 3 && gaps[0].bbox.y == 3);
}

void excludesLargeTransparentRegion() {
  auto image = opaqueImage(7, 7);
  for (int y = 2; y <= 4; ++y)
    for (int x = 2; x <= 4; ++x) image.at(x, y) = {};
  ga::Settings settings;
  settings.gapThreshold = 3;
  CHECK(ga::GapDetector().detect(image, settings).empty());
}

void excludesTransparentRegionConnectedToImageBoundary() {
  auto image = opaqueImage(7, 7);
  image.at(0, 3) = {};
  image.at(1, 3) = {};
  ga::Settings settings;
  settings.gapThreshold = 10;
  CHECK(ga::GapDetector().detect(image, settings).empty());
}

void respectsAlphaThreshold() {
  auto image = opaqueImage(5, 5);
  image.at(2, 2) = {0, 0, 0, 4};
  ga::Settings settings;
  settings.gapThreshold = 3;
  settings.alphaThreshold = 3;
  CHECK(ga::GapDetector().detect(image, settings).empty());
  settings.alphaThreshold = 4;
  CHECK(ga::GapDetector().detect(image, settings).size() == 1);
}

void selectionBoundaryIsTreatedAsOpen() {
  auto image = opaqueImage(7, 7);
  image.at(3, 3) = {};
  ga::SelectionMask selection(7, 7);
  selection.set(3, 3, 255);
  ga::Settings settings;
  settings.scope = ga::Scope::SelectionOnly;
  settings.gapThreshold = 3;
  CHECK(ga::GapDetector().detect(image, settings, &selection).empty());
  for (int y = 2; y <= 4; ++y)
    for (int x = 2; x <= 4; ++x) selection.set(x, y, 255);
  CHECK(ga::GapDetector().detect(image, settings, &selection).size() == 1);
}

void connectivityCanBeEightNeighbor() {
  auto image = opaqueImage(6, 6);
  image.at(2, 2) = {};
  image.at(3, 3) = {};
  ga::Settings settings;
  settings.gapThreshold = 2;
  settings.connectivity = ga::Connectivity::Four;
  CHECK(ga::GapDetector().detect(image, settings).size() == 2);
  settings.connectivity = ga::Connectivity::Eight;
  const auto gaps = ga::GapDetector().detect(image, settings);
  CHECK(gaps.size() == 1 && gaps[0].area == 2);
}

void eightNeighborSelectionDiagonalIsOpen() {
  auto image = opaqueImage(7, 7);
  image.at(3, 3) = {};
  ga::SelectionMask selection(7, 7);
  for (int y = 2; y <= 4; ++y) {
    for (int x = 2; x <= 4; ++x) {
      if (x != 2 || y != 2) selection.set(x, y, 255);
    }
  }
  ga::Settings settings;
  settings.scope = ga::Scope::SelectionOnly;
  settings.gapThreshold = 3;
  settings.connectivity = ga::Connectivity::Four;
  CHECK(ga::GapDetector().detect(image, settings, &selection).size() == 1);
  settings.connectivity = ga::Connectivity::Eight;
  CHECK(ga::GapDetector().detect(image, settings, &selection).empty());
}

void highConfidenceDefaultsToApply() {
  auto image = opaqueImage(9, 9, {100, 120, 140, 255});
  image.at(4, 4) = {};
  ga::Settings settings;
  settings.gapThreshold = 3;
  ga::RuleBasedPredictor predictor;
  const auto analysis = ga::SmartGapPropagation().analyze(image, settings, predictor);
  CHECK(analysis.gaps.size() == 1);
  CHECK(analysis.gaps[0].confidenceBand == ga::ConfidenceBand::High);
  CHECK(analysis.gaps[0].apply);
  CHECK(analysis.gaps[0].status == ga::ReviewStatus::Apply);
  CHECK(analysis.gaps[0].suggestedColor == ga::Rgba({100, 120, 140, 255}));
  CHECK(analysis.gaps[0].sourceOwnerId.has_value());
}

void mediumAndLowDoNotDefaultToApply() {
  std::vector<ga::GapCandidate> gaps(2);
  gaps[0].id = 0;
  gaps[1].id = 1;
  const std::vector<ga::PredictResult> predictions{
      {0, ga::Rgba{1, 2, 3, 255}, 0.60, std::nullopt, ""},
      {1, ga::Rgba{4, 5, 6, 255}, 0.20, std::nullopt, ""}};
  ga::Settings settings;
  ga::applyPredictions(gaps, predictions, settings);
  CHECK(gaps[0].confidenceBand == ga::ConfidenceBand::Medium && !gaps[0].apply);
  CHECK(gaps[1].confidenceBand == ga::ConfidenceBand::Low && !gaps[1].apply);
}

void uncheckedGapIsNotInCorrectionLayer() {
  const auto source = ga::Image(3, 1);
  auto apply = makeGap(0, 0, {255, 0, 0, 255}, 1.0, ga::ConfidenceBand::High);
  apply.apply = true;
  apply.status = ga::ReviewStatus::Apply;
  auto skip = makeGap(1, 1, {0, 255, 0, 255}, 0.2, ga::ConfidenceBand::Low);
  skip.apply = false;
  skip.status = ga::ReviewStatus::Skip;
  const auto output = ga::CorrectionOutputGenerator().generate(source, {apply, skip}, {});
  CHECK(output.correctionLayer.atIndex(0) == ga::Rgba({255, 0, 0, 255}));
  CHECK(output.correctionLayer.atIndex(1).a == 0);
}

void highlightContainsSkippedLowConfidenceGap() {
  const auto source = ga::Image(15, 15);
  auto gap = makeGap(0, 7 * 15 + 7, {255, 0, 0, 255}, 0.1,
                     ga::ConfidenceBand::Low);
  gap.bbox = {7, 7, 1, 1};
  gap.centroid = {7, 7};
  gap.status = ga::ReviewStatus::Skip;
  const auto output = ga::CorrectionOutputGenerator().generate(source, {gap}, {});
  CHECK(output.markedCount == 1);
  bool foundMarker = false;
  for (const auto pixel : output.highlightLayer.pixels()) foundMarker |= pixel.a != 0;
  CHECK(foundMarker);
}

void appliedMediumGapIsNotAlsoHighlighted() {
  const auto source = ga::Image(15, 15);
  auto gap = makeGap(0, 7 * 15 + 7, {30, 40, 50, 255}, 0.6,
                     ga::ConfidenceBand::Medium);
  gap.bbox = {7, 7, 1, 1};
  gap.centroid = {7, 7};
  gap.apply = true;
  gap.status = ga::ReviewStatus::Apply;
  const auto output = ga::CorrectionOutputGenerator().generate(source, {gap}, {});
  CHECK(output.appliedCount == 1 && output.markedCount == 0);
}

void correctionLayerIsTransparentOutsideGapAndSourceUnchanged() {
  const auto source = opaqueImage(4, 4, {9, 8, 7, 255});
  const auto original = source.pixels();
  auto gap = makeGap(0, 5, {1, 2, 3, 255}, 1.0, ga::ConfidenceBand::High);
  gap.apply = true;
  gap.status = ga::ReviewStatus::Apply;
  const auto output = ga::CorrectionOutputGenerator().generate(source, {gap}, {});
  for (std::size_t index = 0; index < output.correctionLayer.size(); ++index)
    CHECK(output.correctionLayer.atIndex(index).a == (index == 5 ? 255 : 0));
  CHECK(source.pixels() == original);
}

void noNearbyColorBecomesLowMarkOnly() {
  ga::Image image(7, 7);
  image.at(0, 0) = {1, 2, 3, 255};
  ga::Settings settings;
  settings.gapThreshold = 40;
  settings.samplingRadius = 1;
  ga::GapCandidate gap;
  gap.id = 0;
  gap.area = 1;
  gap.bbox = {3, 3, 1, 1};
  gap.centroid = {3, 3};
  gap.pixels = {24};
  std::vector<ga::GapCandidate> gaps{gap};
  ga::RuleBasedPredictor predictor;
  const ga::PredictInput input{image, gaps, settings};
  ga::applyPredictions(gaps, predictor.predict(input), settings);
  CHECK(!gaps[0].suggestedColor.has_value());
  CHECK(gaps[0].confidenceBand == ga::ConfidenceBand::Low);
  CHECK(gaps[0].status == ga::ReviewStatus::MarkOnly);
}

void predictionPollCanCancelImmediately() {
  auto image = opaqueImage(7, 7);
  ga::GapCandidate gap;
  gap.id = 0;
  gap.area = 1;
  gap.bbox = {3, 3, 1, 1};
  gap.centroid = {3, 3};
  gap.pixels = {24};
  const std::vector<ga::GapCandidate> gaps{gap};
  const ga::Settings settings;
  std::atomic_bool cancelled{false};
  bool polled = false;
  const ga::PredictInput input{.image = image,
                               .gaps = gaps,
                               .settings = settings,
                               .cancelled = &cancelled,
                               .cancellationPoll = [&] {
                                 polled = true;
                                 cancelled = true;
                               }};
  bool cancelledError = false;
  try {
    static_cast<void>(ga::RuleBasedPredictor().predict(input));
  } catch (const std::runtime_error&) {
    cancelledError = true;
  }
  CHECK(polled);
  CHECK(cancelledError);
}

void reviewModesAreControllable() {
  auto high = makeGap(0, 0, {1, 2, 3, 255}, 0.95, ga::ConfidenceBand::High);
  auto low = makeGap(1, 1, {4, 5, 6, 255}, 0.2, ga::ConfidenceBand::Low);
  ga::ReviewSession quick({high, low}, ga::RunMode::QuickFix);
  CHECK(quick.gaps()[0].apply);
  CHECK(quick.gaps()[1].status == ga::ReviewStatus::MarkOnly);

  ga::ReviewSession one({high, low}, ga::RunMode::OneByOne);
  CHECK(!one.gaps()[0].apply && one.current()->id == 0);
  CHECK(one.applyAndNext());
  CHECK(one.current()->id == 1);
  CHECK(one.skipAndNext());
  CHECK(one.back());
}

void pngRoundTripPreservesRgba() {
  ga::Image image(2, 2);
  image.at(0, 0) = {1, 2, 3, 4};
  image.at(1, 0) = {50, 60, 70, 80};
  image.at(0, 1) = {100, 110, 120, 130};
  image.at(1, 1) = {250, 240, 230, 220};
  const auto path = std::filesystem::temp_directory_path() / "gap-assist-roundtrip.png";
  ga::savePng(path, image);
  const auto decoded = ga::loadPng(path);
  CHECK(decoded.width() == 2 && decoded.height() == 2);
  CHECK(decoded.pixels() == image.pixels());
  std::filesystem::remove(path);
}

class MockHost final : public ga::HostFilterContext {
 public:
  ga::HostCapabilities hostCapabilities{};
  ga::Image source{5, 5, {200, 30, 20, 255}};
  bool acceptDialog{true};
  bool acceptOverwrite{true};
  int createCalls{};
  int overwriteCalls{};
  int transactionCommits{};
  std::atomic_bool cancelled{false};

  MockHost() { source.at(2, 2) = {}; }
  ga::HostCapabilities capabilities() const override { return hostCapabilities; }
  ga::Image readActiveRasterLayer() override { return source; }
  std::optional<ga::SelectionMask> readSelectionMask() override { return std::nullopt; }
  bool presentReviewDialog(ga::ReviewSession&, const ga::Image&,
                           const ga::Settings&) override {
    return acceptDialog;
  }
  bool confirmOverwrite() override { return acceptOverwrite; }
  void reportProgress(const std::string&, std::size_t, std::size_t) override {}
  std::atomic_bool* cancellationFlag() override { return &cancelled; }
  void beginUndoTransaction(const std::string&) override {}
  void createRasterLayer(const std::string&, const ga::Image&) override { ++createCalls; }
  void overwriteActiveLayer(const ga::Image&) override { ++overwriteCalls; }
  void endUndoTransaction(bool commit) override { transactionCommits += commit ? 1 : 0; }
  void showError(const std::string&) override {}
  void showInformation(const std::string&) override {}
};

void cancelDoesNotModifyHost() {
  MockHost host;
  host.hostCapabilities = {.createRasterLayer = true, .customReviewDialog = true,
                           .undoTransaction = true};
  host.acceptDialog = false;
  const auto result = ga::GapAssistCommand().run(host, {});
  CHECK(result.status == ga::CommandStatus::Cancelled);
  CHECK(host.createCalls == 0 && host.overwriteCalls == 0 && host.transactionCommits == 0);
}

void missingLayerCapabilityFailsSafely() {
  MockHost host;
  host.hostCapabilities = {.overwriteActiveLayer = true, .customReviewDialog = true,
                           .undoTransaction = true};
  const auto result = ga::GapAssistCommand().run(host, {});
  CHECK(result.status == ga::CommandStatus::UnsupportedSafeOutput);
  CHECK(host.createCalls == 0 && host.overwriteCalls == 0 && host.transactionCommits == 0);
}

void missingReviewDialogCapabilityFailsSafely() {
  MockHost host;
  host.hostCapabilities = {.createRasterLayer = true, .undoTransaction = true};
  const auto result = ga::GapAssistCommand().run(host, {});
  CHECK(result.status == ga::CommandStatus::UnsupportedSafeOutput);
  CHECK(host.createCalls == 0 && host.overwriteCalls == 0 && host.transactionCommits == 0);
}

void overwriteWithoutUndoCapabilityFailsSafely() {
  MockHost host;
  host.hostCapabilities = {.overwriteActiveLayer = true, .customReviewDialog = true};
  ga::Settings settings;
  settings.outputMode = ga::OutputMode::OverwriteActiveLayer;
  const auto result = ga::GapAssistCommand().run(host, settings);
  CHECK(result.status == ga::CommandStatus::UnsupportedSafeOutput);
  CHECK(host.createCalls == 0 && host.overwriteCalls == 0 && host.transactionCommits == 0);
}

void settingsRoundTripPreservesUserChoices() {
  ga::Settings settings;
  settings.mode = ga::RunMode::OneByOne;
  settings.gapSizePreset = ga::GapSizePreset::Custom;
  settings.gapThreshold = 17;
  settings.customGapThreshold = 17;
  settings.alphaThreshold = 9;
  settings.confidencePreset = ga::ConfidencePreset::Conservative;
  settings.outputMode = ga::OutputMode::OverwriteActiveLayer;
  settings.scope = ga::Scope::SelectionOnly;
  settings.connectivity = ga::Connectivity::Eight;
  settings.createHighlightLayer = false;
  settings.predictorOnnx = true;
  const auto path = std::filesystem::temp_directory_path() / "gap-assist-settings.ini";
  ga::SettingsStore::save(path, settings);
  const auto loaded = ga::SettingsStore::load(path);
  std::filesystem::remove(path);
  CHECK(loaded.mode == settings.mode);
  CHECK(loaded.gapSizePreset == settings.gapSizePreset);
  CHECK(loaded.gapThreshold == 17 && loaded.customGapThreshold == 17);
  CHECK(loaded.alphaThreshold == settings.alphaThreshold);
  CHECK(loaded.confidencePreset == settings.confidencePreset);
  CHECK(loaded.outputMode == settings.outputMode);
  CHECK(loaded.scope == settings.scope);
  CHECK(loaded.connectivity == settings.connectivity);
  CHECK(!loaded.createHighlightLayer && loaded.predictorOnnx);
}

void preCancelledCommandDoesNotModifyHost() {
  MockHost host;
  host.hostCapabilities = {.createRasterLayer = true, .customReviewDialog = true,
                           .undoTransaction = true};
  host.cancelled = true;
  const auto result = ga::GapAssistCommand().run(host, {});
  CHECK(result.status == ga::CommandStatus::Cancelled);
  CHECK(host.createCalls == 0 && host.overwriteCalls == 0 && host.transactionCommits == 0);
}

void quickFixPipelineOnlyChangesHighConfidenceGaps() {
  auto source = opaqueImage(9, 9, {90, 110, 130, 255});
  source.at(4, 4) = {};
  ga::Settings settings;
  settings.gapThreshold = 3;
  const auto result = ga::QuickFixPipeline().run(source, settings);
  CHECK(result.detected == 1 && result.high == 1 && result.applied == 1);
  CHECK(result.correctedComposite.at(4, 4) == ga::Rgba({90, 110, 130, 255}));
  CHECK(source.at(4, 4).a == 0);
}

void quickFixPipelineHonorsSelectionBoundary() {
  auto source = opaqueImage(9, 9, {90, 110, 130, 255});
  source.at(4, 4) = {};
  ga::SelectionMask selection(9, 9);
  selection.set(4, 4, 255);
  ga::Settings settings;
  settings.gapThreshold = 3;
  const auto result = ga::QuickFixPipeline().run(source, settings, &selection);
  CHECK(result.detected == 0 && result.applied == 0);
  CHECK(result.correctedComposite.at(4, 4).a == 0);
}

}  // namespace

int main() {
  const std::vector<std::pair<std::string, std::function<void()>>> tests{
      {"detects small transparent region", detectsSmallTransparentRegion},
      {"excludes large transparent region", excludesLargeTransparentRegion},
      {"excludes boundary transparent region", excludesTransparentRegionConnectedToImageBoundary},
      {"respects alpha threshold", respectsAlphaThreshold},
      {"selection boundary is open", selectionBoundaryIsTreatedAsOpen},
      {"supports eight-neighbor connectivity", connectivityCanBeEightNeighbor},
      {"eight-neighbor selection diagonal is open",
       eightNeighborSelectionDiagonalIsOpen},
      {"high confidence defaults to apply", highConfidenceDefaultsToApply},
      {"medium and low default off", mediumAndLowDoNotDefaultToApply},
      {"unchecked gap excluded from correction", uncheckedGapIsNotInCorrectionLayer},
      {"highlight marks skipped low gap", highlightContainsSkippedLowConfidenceGap},
      {"applied medium is not highlighted", appliedMediumGapIsNotAlsoHighlighted},
      {"correction is transparent and nondestructive", correctionLayerIsTransparentOutsideGapAndSourceUnchanged},
      {"missing color becomes mark only", noNearbyColorBecomesLowMarkOnly},
      {"prediction polling can cancel", predictionPollCanCancelImmediately},
      {"review modes are controllable", reviewModesAreControllable},
      {"PNG round trip", pngRoundTripPreservesRgba},
      {"cancel is nondestructive", cancelDoesNotModifyHost},
      {"missing layer capability is safe", missingLayerCapabilityFailsSafely},
      {"missing review dialog is safe", missingReviewDialogCapabilityFailsSafely},
      {"overwrite without undo is safe", overwriteWithoutUndoCapabilityFailsSafely},
      {"settings round trip", settingsRoundTripPreservesUserChoices},
      {"pre-cancel is nondestructive", preCancelledCommandDoesNotModifyHost},
      {"quick fix changes high only", quickFixPipelineOnlyChangesHighConfidenceGaps},
      {"quick fix honors selection boundary", quickFixPipelineHonorsSelectionBoundary},
  };
  int failures = 0;
  for (const auto& [name, test] : tests) {
    try {
      test();
      std::cout << "[PASS] " << name << '\n';
    } catch (const std::exception& error) {
      ++failures;
      std::cerr << "[FAIL] " << name << ": " << error.what() << '\n';
    }
  }
  std::cout << tests.size() - failures << '/' << tests.size() << " tests passed\n";
  return failures == 0 ? 0 : 1;
}
