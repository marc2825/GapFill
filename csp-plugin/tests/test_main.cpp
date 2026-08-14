#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <iterator>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "cli/arguments.hpp"
#include "core/correction_output.hpp"
#include "core/gap_detection.hpp"
#include "core/owner_regions.hpp"
#include "core/quick_fix_pipeline.hpp"
#include "core/smart_gap_propagation.hpp"
#include "io/atomic_output.hpp"
#include "io/png_io.hpp"
#include "io/review_artifacts.hpp"
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

ga::GapCandidate validGap(int id, int width, std::uint32_t pixel,
                          ga::Rgba color = {1, 2, 3, 255}) {
  auto gap = makeGap(id, pixel, color, 1.0, ga::ConfidenceBand::High);
  const int x = static_cast<int>(pixel % static_cast<std::uint32_t>(width));
  const int y = static_cast<int>(pixel / static_cast<std::uint32_t>(width));
  gap.bbox = {x, y, 1, 1};
  gap.centroid = {static_cast<double>(x), static_cast<double>(y)};
  gap.apply = true;
  gap.status = ga::ReviewStatus::Apply;
  return gap;
}

template <typename Callable>
void checkInvalidArgument(Callable&& callable) {
  bool rejected = false;
  try {
    callable();
  } catch (const std::invalid_argument&) {
    rejected = true;
  }
  CHECK(rejected);
}

std::filesystem::path phase3TemporaryDirectory(const std::string& name) {
  const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
  const auto path = std::filesystem::temp_directory_path() /
                    ("gap-assist-phase3-" + name + "-" + std::to_string(nonce));
  std::filesystem::create_directories(path);
  return path;
}

void writeBytes(const std::filesystem::path& path, const std::string& bytes) {
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  output << bytes;
  if (!output) throw TestFailure("Cannot write test fixture " + path.string());
}

std::string readBytes(const std::filesystem::path& path) {
  std::ifstream input(path, std::ios::binary);
  return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
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

void canonicalDetectionRequiresExactZeroAlpha() {
  auto image = opaqueImage(5, 5);
  image.at(2, 2) = {0, 0, 0, 4};
  ga::Settings settings;
  settings.gapThreshold = 3;
  settings.alphaThreshold = 254;
  CHECK(ga::GapDetector().detect(image, settings).empty());
  image.at(2, 2).a = 0;
  CHECK(ga::GapDetector().detect(image, settings).size() == 1);
}

void selectionIsAppliedAfterFullGeometry() {
  auto image = opaqueImage(7, 7);
  image.at(2, 3) = {};
  image.at(3, 3) = {};
  image.at(4, 3) = {};
  ga::SelectionMask selection(7, 7);
  selection.set(3, 3, 255);
  ga::Settings settings;
  settings.scope = ga::Scope::SelectionOnly;
  settings.gapThreshold = 3;
  const auto gaps = ga::GapDetector().detect(image, settings, &selection);
  CHECK(gaps.size() == 1);
  CHECK(gaps[0].pixels == std::vector<std::uint32_t>({23, 24, 25}));
  CHECK(gaps[0].applicationPixels == std::vector<std::uint32_t>({24}));
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

void noncanonicalEightNeighborDoesNotUseSelectionAsGeometry() {
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
  CHECK(ga::GapDetector().detect(image, settings, &selection).size() == 1);
}

void lineAndGuideMasksAreCanonicalBoundaries() {
  ga::DetectionGeometry guideRing(7, 7);
  for (int y = 0; y < 7; ++y)
    for (int x = 0; x < 7; ++x) guideRing.coloringGap.set(x, y, true);
  for (int x = 2; x <= 4; ++x) {
    guideRing.guideBoundary.set(x, 2, true);
    guideRing.guideBoundary.set(x, 4, true);
  }
  for (int y = 2; y <= 4; ++y) {
    guideRing.guideBoundary.set(2, y, true);
    guideRing.guideBoundary.set(4, y, true);
  }
  ga::Settings settings;
  settings.gapThreshold = 2;
  const auto guideGaps = ga::GapDetector{}.detect(guideRing, settings);
  CHECK(guideGaps.size() == 1);
  CHECK(guideGaps[0].pixels == std::vector<std::uint32_t>({24}));

  ga::DetectionGeometry isolatedGuide(5, 5);
  for (int y = 0; y < 5; ++y)
    for (int x = 0; x < 5; ++x) isolatedGuide.coloringGap.set(x, y, true);
  isolatedGuide.guideBoundary.set(2, 2, true);
  settings.gapThreshold = 1;
  CHECK(ga::GapDetector{}.detect(isolatedGuide, settings).empty());

  guideRing.lineBoundary.set(2, 2, true);
  guideRing.guideBoundary.set(2, 2, false);
  CHECK(ga::GapDetector{}.detect(guideRing, settings).size() == 1);
}

void largeStreamingTraversalCanCancel() {
  ga::DetectionGeometry geometry(4096, 4096);
  for (int y = 0; y < geometry.height(); ++y)
    for (int x = 0; x < geometry.width(); ++x)
      geometry.coloringGap.set(x, y, true);
  ga::Settings settings;
  settings.gapThreshold = 10;
  CHECK(ga::GapDetector{}.detect(geometry, settings).empty());
  std::atomic_bool cancelled{false};
  bool interrupted = false;
  try {
    static_cast<void>(ga::GapDetector{}.detect(
        geometry, settings, nullptr, &cancelled,
        [&](std::size_t completed, std::size_t) {
          if (completed >= 65) cancelled = true;
        }));
  } catch (const std::runtime_error&) {
    interrupted = true;
  }
  CHECK(interrupted);
}

void checkerboardUsesBoundedIndependentComponents() {
  ga::DetectionGeometry geometry(256, 256);
  for (int y = 0; y < geometry.height(); ++y)
    for (int x = 0; x < geometry.width(); ++x)
      geometry.coloringGap.set(x, y, ((x + y) & 1) == 0);
  ga::Settings settings;
  settings.gapThreshold = 1;
  const auto gaps = ga::GapDetector{}.detect(geometry, settings);
  CHECK(gaps.size() == 32258);
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

void equivalentNormalizedGeometryPreservesRulePrediction() {
  auto image = opaqueImage(9, 9, {100, 120, 140, 255});
  image.at(4, 4) = {};
  ga::Settings settings;
  settings.gapThreshold = 3;
  ga::RuleBasedPredictor predictor;
  const auto legacy = ga::SmartGapPropagation{}.analyze(image, settings, predictor);
  const auto geometry = ga::normalizeCanonicalColoringGeometry(image);
  const auto normalized =
      ga::SmartGapPropagation{}.analyze(image, geometry, settings, predictor);
  CHECK(legacy.gaps.size() == 1 && normalized.gaps.size() == 1);
  CHECK(legacy.gaps[0].pixels == normalized.gaps[0].pixels);
  CHECK(legacy.gaps[0].suggestedColor == normalized.gaps[0].suggestedColor);
  CHECK(legacy.gaps[0].confidence == normalized.gaps[0].confidence);
  CHECK(legacy.gaps[0].confidenceBand == normalized.gaps[0].confidenceBand);
  CHECK(legacy.gaps[0].sourceOwnerId == normalized.gaps[0].sourceOwnerId);
  CHECK(legacy.gaps[0].debugInfo == normalized.gaps[0].debugInfo);
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
  const ga::Settings settings;
  const auto output = ga::CorrectionOutputGenerator().generate(
      source, {apply, skip}, settings,
      ga::captureCandidateContext(source, settings));
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
  const ga::Settings settings;
  const auto output = ga::CorrectionOutputGenerator().generate(
      source, {gap}, settings, ga::captureCandidateContext(source, settings));
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
  const ga::Settings settings;
  const auto output = ga::CorrectionOutputGenerator().generate(
      source, {gap}, settings, ga::captureCandidateContext(source, settings));
  CHECK(output.appliedCount == 1 && output.markedCount == 0);
}

void correctionLayerIsTransparentOutsideGapAndSourceUnchanged() {
  auto source = opaqueImage(4, 4, {9, 8, 7, 255});
  source.atIndex(5) = {};
  const auto original = source.pixels();
  auto gap = makeGap(0, 5, {1, 2, 3, 255}, 1.0, ga::ConfidenceBand::High);
  gap.bbox = {1, 1, 1, 1};
  gap.centroid = {1, 1};
  gap.apply = true;
  gap.status = ga::ReviewStatus::Apply;
  const ga::Settings settings;
  const auto output = ga::CorrectionOutputGenerator().generate(
      source, {gap}, settings, ga::captureCandidateContext(source, settings));
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

void bulkDecisionsOnlyAffectUnreviewedCandidates() {
  const auto makeSession = [] {
    std::vector<ga::GapCandidate> gaps;
    for (int id = 0; id < 4; ++id)
      gaps.push_back(makeGap(id, static_cast<std::uint32_t>(id), {1, 2, 3, 255},
                             0.95, ga::ConfidenceBand::High));
    ga::ReviewSession session(std::move(gaps), ga::RunMode::OneByOne);
    CHECK(session.setApply(1, true));
    CHECK(session.skip(2));
    CHECK(session.markOnly(3));
    return session;
  };

  auto high = makeSession();
  high.applyHighConfidence();
  CHECK(high.gaps()[0].status == ga::ReviewStatus::Apply);
  CHECK(high.gaps()[1].status == ga::ReviewStatus::Apply);
  CHECK(high.gaps()[2].status == ga::ReviewStatus::Skip);
  CHECK(high.gaps()[3].status == ga::ReviewStatus::MarkOnly);

  auto selected = makeSession();
  const std::vector<int> ids{0, 1, 2, 3};
  selected.applySelected(ids);
  CHECK(selected.gaps()[0].status == ga::ReviewStatus::Apply);
  CHECK(selected.gaps()[1].status == ga::ReviewStatus::Apply);
  CHECK(selected.gaps()[2].status == ga::ReviewStatus::Skip);
  CHECK(selected.gaps()[3].status == ga::ReviewStatus::MarkOnly);

  auto skipped = makeSession();
  skipped.skipSelected(ids);
  CHECK(skipped.gaps()[0].status == ga::ReviewStatus::Skip);
  CHECK(skipped.gaps()[1].status == ga::ReviewStatus::Apply);
  CHECK(skipped.gaps()[2].status == ga::ReviewStatus::Skip);
  CHECK(skipped.gaps()[3].status == ga::ReviewStatus::MarkOnly);
}

void conflictingDecisionFileEntriesFail() {
  auto gap = makeGap(0, 0, {1, 2, 3, 255}, 0.95, ga::ConfidenceBand::High);
  ga::ReviewSession session({gap}, ga::RunMode::OneByOne);
  const auto path =
      std::filesystem::temp_directory_path() / "gap-assist-conflicting-decisions.txt";
  {
    std::ofstream output(path);
    output << "0=skip\n0=apply\n";
  }
  bool rejected = false;
  try {
    ga::applyDecisionFile(path, session);
  } catch (const std::runtime_error&) {
    rejected = true;
  }
  std::filesystem::remove(path);
  CHECK(rejected);
}

void identicalDecisionFileEntriesAreIdempotent() {
  auto gap = makeGap(0, 0, {1, 2, 3, 255}, 0.95, ga::ConfidenceBand::High);
  ga::ReviewSession session({gap}, ga::RunMode::OneByOne);
  const auto directory = phase3TemporaryDirectory("identical-decisions");
  const auto path = directory / "decisions.txt";
  writeBytes(path, "0=skip\n0=skip\n");
  ga::applyDecisionFile(path, session);
  session.applyAllRemainingHighConfidence();
  CHECK(session.gaps()[0].status == ga::ReviewStatus::Skip);
  std::filesystem::remove_all(directory);
}

void forgedOpaqueCandidateFailsClosed() {
  const auto source = opaqueImage(4, 4, {9, 8, 7, 255});
  auto gap = makeGap(0, 5, {1, 2, 3, 255}, 1.0, ga::ConfidenceBand::High);
  gap.apply = true;
  gap.status = ga::ReviewStatus::Apply;
  bool rejected = false;
  try {
    const ga::Settings settings;
    static_cast<void>(ga::CorrectionOutputGenerator().generate(
        source, {gap}, settings, ga::captureCandidateContext(source, settings)));
  } catch (const std::invalid_argument&) {
    rejected = true;
  }
  CHECK(rejected);
  CHECK(source.atIndex(5) == ga::Rgba({9, 8, 7, 255}));
}

void forgedCandidateMatrixFailsClosed() {
  const ga::Settings settings;
  ga::Image source(4, 4);
  const auto original = source.pixels();
  const auto context = ga::captureCandidateContext(source, settings);
  const auto generate = [&](const ga::Image& current,
                            const std::vector<ga::GapCandidate>& gaps,
                            const ga::CandidateContext& candidateContext =
                                ga::CandidateContext{}) {
    const auto& selectedContext = candidateContext.width == 0 ? context : candidateContext;
    return ga::CorrectionOutputGenerator().generate(current, gaps, settings,
                                                     selectedContext);
  };

  auto outOfRange = validGap(0, 4, 16);
  checkInvalidArgument([&] { static_cast<void>(generate(source, {outOfRange})); });

  auto duplicate = validGap(0, 4, 5);
  duplicate.pixels.push_back(5);
  duplicate.area = 2;
  checkInvalidArgument([&] { static_cast<void>(generate(source, {duplicate})); });

  const auto overlapA = validGap(0, 4, 5);
  const auto overlapB = validGap(1, 4, 5);
  checkInvalidArgument(
      [&] { static_cast<void>(generate(source, {overlapA, overlapB})); });

  auto duplicateId = validGap(0, 4, 5);
  const auto sameId = validGap(0, 4, 6);
  checkInvalidArgument(
      [&] { static_cast<void>(generate(source, {duplicateId, sameId})); });

  auto wrongArea = validGap(0, 4, 5);
  wrongArea.area = 2;
  checkInvalidArgument([&] { static_cast<void>(generate(source, {wrongArea})); });
  auto wrongBox = validGap(0, 4, 5);
  wrongBox.bbox.x = 0;
  checkInvalidArgument([&] { static_cast<void>(generate(source, {wrongBox})); });
  auto wrongCentroid = validGap(0, 4, 5);
  wrongCentroid.centroid.x += 0.5;
  checkInvalidArgument([&] { static_cast<void>(generate(source, {wrongCentroid})); });
  auto nonfiniteCentroid = validGap(0, 4, 5);
  nonfiniteCentroid.centroid.x = std::numeric_limits<double>::quiet_NaN();
  checkInvalidArgument(
      [&] { static_cast<void>(generate(source, {nonfiniteCentroid})); });

  ga::Image wrongDimensions(5, 4);
  checkInvalidArgument([&] {
    static_cast<void>(generate(wrongDimensions, {validGap(0, 5, 6)}, context));
  });

  auto stale = source;
  stale.atIndex(0) = {9, 8, 7, 255};
  checkInvalidArgument(
      [&] { static_cast<void>(generate(stale, {validGap(0, 4, 5)}, context)); });

  auto changedSettings = settings;
  changedSettings.samplingRadius += 1;
  checkInvalidArgument([&] {
    static_cast<void>(ga::CorrectionOutputGenerator().generate(
        source, {validGap(0, 4, 5)}, changedSettings, context));
  });

  ga::Image partial = source;
  partial.atIndex(5) = {1, 2, 3, 1};
  const auto partialContext = ga::captureCandidateContext(partial, settings);
  checkInvalidArgument([&] {
    static_cast<void>(generate(partial, {validGap(0, 4, 5)}, partialContext));
  });

  CHECK(source.pixels() == original);
}

void candidateSelectionProvenanceFailsClosed() {
  ga::Image source(4, 4);
  ga::SelectionMask selection(4, 4);
  selection.set(5 % 4, 5 / 4, 255);
  ga::Settings settings;
  settings.scope = ga::Scope::SelectionOnly;
  const auto context = ga::captureCandidateContext(source, settings, &selection);
  const auto original = source.pixels();

  checkInvalidArgument([&] {
    static_cast<void>(ga::CorrectionOutputGenerator().generate(
        source, {validGap(0, 4, 6)}, settings, context, &selection));
  });

  auto changedSelection = selection;
  changedSelection.set(0, 0, 255);
  checkInvalidArgument([&] {
    static_cast<void>(ga::CorrectionOutputGenerator().generate(
        source, {validGap(0, 4, 5)}, settings, context, &changedSelection));
  });
  checkInvalidArgument([&] {
    static_cast<void>(ga::CorrectionOutputGenerator().generate(
        source, {validGap(0, 4, 5)}, settings, context));
  });
  CHECK(source.pixels() == original);
}

void fullGeometryCandidateAppliesOnlyInsideSelection() {
  auto source = opaqueImage(5, 5);
  for (int x = 1; x <= 3; ++x) source.at(x, 2) = {};
  ga::SelectionMask selection(5, 5);
  selection.set(2, 2, 255);
  ga::Settings settings;
  settings.scope = ga::Scope::SelectionOnly;
  ga::GapCandidate gap;
  gap.id = 0;
  gap.pixels = {11, 12, 13};
  gap.applicationPixels = {12};
  gap.area = 3;
  gap.bbox = {1, 2, 3, 1};
  gap.centroid = {2, 2};
  gap.suggestedColor = ga::Rgba{1, 2, 3, 255};
  gap.apply = true;
  gap.status = ga::ReviewStatus::Apply;
  const auto output = ga::CorrectionOutputGenerator{}.generate(
      source, {gap}, settings,
      ga::captureCandidateContext(source, settings, &selection), &selection);
  CHECK(output.correctionLayer.atIndex(11).a == 0);
  CHECK(output.correctionLayer.atIndex(12) == ga::Rgba({1, 2, 3, 255}));
  CHECK(output.correctionLayer.atIndex(13).a == 0);
}

void normalizedGeometryProvenanceFailsClosed() {
  ga::Image source(4, 4);
  ga::Settings settings;
  auto geometry = ga::normalizeCanonicalColoringGeometry(source);
  const auto context =
      ga::captureCandidateContext(source, settings, nullptr, &geometry);
  geometry.lineBoundary.set(1, 1, true);
  checkInvalidArgument([&] {
    static_cast<void>(ga::CorrectionOutputGenerator{}.generate(
        source, {validGap(0, 4, 5)}, settings, context, nullptr, true,
        &geometry));
  });
}

void settingsAndCliPrecedenceIsDeterministic() {
  const auto directory = phase3TemporaryDirectory("arguments");
  const auto settingsPath = directory / "settings.ini";
  writeBytes(settingsPath,
             "mode=quick_fix\n"
             "gap_size=small\n"
             "alpha_threshold=1\n"
             "confidence=conservative\n"
             "scope=whole\n"
             "connectivity=4\n"
             "create_highlight=true\n"
             "predictor=rule_based\n");
  const auto selection = (directory / "selection.png").string();
  const std::vector<std::string> overrides{
      "--input", "input.png", "--selection", selection, "--mode", "one",
      "--gap-size", "17", "--alpha-threshold", "9", "--confidence",
      "aggressive", "--connectivity", "8", "--predictor", "onnx",
      "--no-highlight", "--debug"};
  auto firstValues = overrides;
  firstValues.insert(firstValues.begin(), {"--settings", settingsPath.string()});
  auto secondValues = overrides;
  secondValues.insert(secondValues.begin() + 4,
                      {"--settings", settingsPath.string()});
  auto thirdValues = overrides;
  thirdValues.insert(thirdValues.end(), {"--settings", settingsPath.string()});
  const auto first = ga::parseCliArguments(firstValues);
  const auto second = ga::parseCliArguments(secondValues);
  const auto third = ga::parseCliArguments(thirdValues);
  const auto verify = [&](const ga::CliArguments& parsed) {
    CHECK(parsed.settings.mode == ga::RunMode::OneByOne);
    CHECK(parsed.settings.gapSizePreset == ga::GapSizePreset::Custom);
    CHECK(parsed.settings.gapThreshold == 17 && parsed.settings.customGapThreshold == 17);
    CHECK(parsed.settings.alphaThreshold == 9);
    CHECK(parsed.settings.confidencePreset == ga::ConfidencePreset::Aggressive);
    CHECK(parsed.settings.connectivity == ga::Connectivity::Eight);
    CHECK(parsed.settings.scope == ga::Scope::SelectionOnly);
    CHECK(parsed.settings.predictorOnnx);
    CHECK(!parsed.settings.createHighlightLayer);
    CHECK(parsed.settings.debugLogging);
  };
  verify(first);
  verify(second);
  verify(third);
  CHECK(ga::serializeSettings(first.settings) == ga::serializeSettings(second.settings));
  CHECK(ga::serializeSettings(second.settings) == ga::serializeSettings(third.settings));

  const auto repeated = ga::parseCliArguments(
      std::vector<std::string>{"--input", "input.png", "--mode", "quick",
                               "--mode", "one", "--gap-size", "3",
                               "--gap-size", "7"});
  CHECK(repeated.settings.mode == ga::RunMode::OneByOne);
  CHECK(repeated.settings.gapThreshold == 7);
  std::filesystem::remove_all(directory);
}

void invalidConfigurationFailsCleanly() {
  checkInvalidArgument([&] {
    static_cast<void>(ga::parseCliArguments(std::vector<std::string>{
        "--input", "input.png", "--alpha-threshold", "256"}));
  });
  checkInvalidArgument([&] {
    static_cast<void>(ga::parseCliArguments(std::vector<std::string>{
        "--input", "input.png", "--gap-size", "12junk"}));
  });
  const auto directory = phase3TemporaryDirectory("invalid-settings");
  const auto path = directory / "settings.ini";
  writeBytes(path, "mode=surprise\n");
  bool rejected = false;
  try {
    static_cast<void>(ga::parseCliArguments(std::vector<std::string>{
        "--input", "input.png", "--settings", path.string()}));
  } catch (const std::runtime_error&) {
    rejected = true;
  }
  CHECK(rejected);
  std::filesystem::remove_all(directory);
}

void outputPathAliasesAndExistingPolicyAreEnforced() {
  const auto directory = phase3TemporaryDirectory("path-policy");
  const auto source = directory / "source.png";
  writeBytes(source, "source");
  const std::vector<std::uint8_t> bytes{'n', 'e', 'w'};

  checkInvalidArgument([&] {
    ga::validateOutputPlan(source, {{"correction", source, bytes}}, false);
  });
  const auto normalized = directory / "subdirectory" / ".." / "source.png";
  checkInvalidArgument([&] {
    ga::validateOutputPlan(source, {{"correction", normalized, bytes}}, false);
  });
  const auto relative = std::filesystem::relative(source, std::filesystem::current_path());
  checkInvalidArgument([&] {
    ga::validateOutputPlan(source, {{"correction", relative, bytes}}, false);
  });

  std::error_code linkError;
  const auto symlink = directory / "source-symlink.png";
  std::filesystem::create_symlink(source.filename(), symlink, linkError);
  if (!linkError) {
    checkInvalidArgument([&] {
      ga::validateOutputPlan(source, {{"correction", symlink, bytes}}, true);
    });
  }
  linkError.clear();
  const auto hardlink = directory / "source-hardlink.png";
  std::filesystem::create_hard_link(source, hardlink, linkError);
  if (!linkError) {
    checkInvalidArgument([&] {
      ga::validateOutputPlan(source, {{"correction", hardlink, bytes}}, true);
    });
  }

  const auto output = directory / "one.bin";
  checkInvalidArgument([&] {
    ga::validateOutputPlan(source,
                           {{"correction", output, bytes},
                            {"manifest", directory / "." / "one.bin", bytes}},
                           false);
  });
  writeBytes(output, "old");
  checkInvalidArgument([&] {
    ga::validateOutputPlan(source, {{"correction", output, bytes}}, false);
  });
  ga::commitOutputPlan(source, {{"correction", output, bytes}}, true);
  CHECK(readBytes(output) == "new");
  CHECK(readBytes(source) == "source");
  std::filesystem::remove_all(directory);
}

void atomicOutputFailuresRollbackAndCleanStaging() {
  const auto directory = phase3TemporaryDirectory("atomic");
  const auto source = directory / "source.bin";
  const auto first = directory / "first.bin";
  const auto second = directory / "second.bin";
  const auto third = directory / "third-new.bin";
  writeBytes(source, "source");
  const std::vector<ga::OutputFile> outputs{
      {"first", first, {'n', 'e', 'w', '1'}},
      {"second", second, {'n', 'e', 'w', '2'}},
      {"third", third, {'n', 'e', 'w', '3'}},
  };

  const std::vector<std::pair<ga::OutputCommitStage, int>> failures{
      {ga::OutputCommitStage::TemporaryWrite, 3},
      {ga::OutputCommitStage::BackupRename, 2},
      {ga::OutputCommitStage::FinalRename, 3},
      {ga::OutputCommitStage::Cleanup, 1},
  };
  for (const auto& [stage, failAt] : failures) {
    writeBytes(first, "old1");
    writeBytes(second, "old2");
    int occurrences = 0;
    bool rejected = false;
    try {
      ga::commitOutputPlan(
          source, outputs, true,
          [&](ga::OutputCommitStage current, const std::filesystem::path&) {
            if (current == stage && ++occurrences == failAt)
              throw std::runtime_error("injected output failure");
          });
    } catch (const std::runtime_error&) {
      rejected = true;
    }
    CHECK(rejected);
    CHECK(readBytes(source) == "source");
    CHECK(readBytes(first) == "old1");
    CHECK(readBytes(second) == "old2");
    CHECK(!std::filesystem::exists(third));
    for (const auto& entry : std::filesystem::directory_iterator(directory))
      CHECK(entry.path().filename().string().find(".gap-assist-") ==
            std::string::npos);
  }

  writeBytes(first, "old1");
  checkInvalidArgument([&] { static_cast<void>(ga::encodePng(ga::Image())); });
  CHECK(readBytes(first) == "old1");
  std::filesystem::remove_all(directory);
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
  CHECK(result.detected == 1 && result.applied == 0);
  CHECK(result.correctedComposite.at(4, 4).a == 0);
}

}  // namespace

int main() {
  const std::vector<std::pair<std::string, std::function<void()>>> tests{
      {"detects small transparent region", detectsSmallTransparentRegion},
      {"excludes large transparent region", excludesLargeTransparentRegion},
      {"excludes boundary transparent region", excludesTransparentRegionConnectedToImageBoundary},
      {"canonical detection requires alpha zero", canonicalDetectionRequiresExactZeroAlpha},
      {"selection follows full geometry", selectionIsAppliedAfterFullGeometry},
      {"supports eight-neighbor connectivity", connectivityCanBeEightNeighbor},
      {"eight-neighbor selection is not geometry",
       noncanonicalEightNeighborDoesNotUseSelectionAsGeometry},
      {"Line and Guide masks are boundaries", lineAndGuideMasksAreCanonicalBoundaries},
      {"large traversal cancellation", largeStreamingTraversalCanCancel},
      {"checkerboard components stay independent",
       checkerboardUsesBoundedIndependentComponents},
      {"high confidence defaults to apply", highConfidenceDefaultsToApply},
      {"normalized geometry preserves rule prediction",
       equivalentNormalizedGeometryPreservesRulePrediction},
      {"medium and low default off", mediumAndLowDoNotDefaultToApply},
      {"unchecked gap excluded from correction", uncheckedGapIsNotInCorrectionLayer},
      {"highlight marks skipped low gap", highlightContainsSkippedLowConfidenceGap},
      {"applied medium is not highlighted", appliedMediumGapIsNotAlsoHighlighted},
      {"correction is transparent and nondestructive", correctionLayerIsTransparentOutsideGapAndSourceUnchanged},
      {"missing color becomes mark only", noNearbyColorBecomesLowMarkOnly},
      {"prediction polling can cancel", predictionPollCanCancelImmediately},
      {"review modes are controllable", reviewModesAreControllable},
      {"bulk decisions preserve explicit states",
       bulkDecisionsOnlyAffectUnreviewedCandidates},
      {"conflicting decisions fail", conflictingDecisionFileEntriesFail},
      {"identical decisions are idempotent",
       identicalDecisionFileEntriesAreIdempotent},
      {"forged opaque candidate fails closed", forgedOpaqueCandidateFailsClosed},
      {"forged candidate matrix fails closed", forgedCandidateMatrixFailsClosed},
      {"candidate selection provenance fails closed",
       candidateSelectionProvenanceFailsClosed},
      {"selection limits application after geometry",
       fullGeometryCandidateAppliesOnlyInsideSelection},
      {"normalized geometry provenance fails closed",
       normalizedGeometryProvenanceFailsClosed},
      {"settings and CLI precedence is deterministic",
       settingsAndCliPrecedenceIsDeterministic},
      {"invalid configuration fails cleanly", invalidConfigurationFailsCleanly},
      {"output paths and existing policy are enforced",
       outputPathAliasesAndExistingPolicyAreEnforced},
      {"atomic output failures roll back", atomicOutputFailuresRollbackAndCleanStaging},
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
