#include <algorithm>
#include <atomic>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>

#include "core/correction_output.hpp"
#include "core/settings.hpp"
#include "core/smart_gap_propagation.hpp"
#include "io/png_io.hpp"
#include "io/review_artifacts.hpp"
#include "predictors/rule_based_predictor.hpp"
#include "ui/review_session.hpp"

namespace {

struct Arguments {
  std::filesystem::path input;
  std::filesystem::path correction;
  std::filesystem::path highlight;
  std::filesystem::path corrected;
  std::filesystem::path manifest;
  std::filesystem::path contactSheet;
  std::filesystem::path selection;
  std::filesystem::path decisions;
  std::filesystem::path settingsPath;
  std::filesystem::path saveSettingsPath;
  gap_assist::Settings settings;
  bool applyHigh{};
};

void usage() {
  std::cout
      << "Gap Assist PNG harness\n\n"
      << "Usage: gap_assist_cli --input layer.png [options]\n\n"
      << "Outputs:\n"
      << "  --correction FILE     Transparent correction-layer PNG\n"
      << "  --highlight FILE      Confidence marker-layer PNG\n"
      << "  --corrected FILE      Corrected composite preview PNG\n"
      << "  --manifest FILE       JSON review manifest\n"
      << "  --contact-sheet FILE  Before/after review sheet PNG\n\n"
      << "Analysis:\n"
      << "  --mode quick|review|one\n"
      << "  --gap-size small|medium|large|NUMBER\n"
      << "  --alpha-threshold 0..255\n"
      << "  --confidence conservative|balanced|aggressive\n"
      << "  --connectivity 4|8\n"
      << "  --selection FILE      Analyze only nontransparent selection-mask pixels\n"
      << "  --decisions FILE      Lines such as 3=apply, 4=skip, 5=mark_only\n"
      << "  --apply-high          Apply every remaining high-confidence gap\n"
      << "  --predictor rule_based|onnx (ONNX currently falls back locally)\n"
      << "  --no-highlight        Do not write a highlight layer\n"
      << "  --settings FILE       Load persisted settings\n"
      << "  --save-settings FILE  Save effective settings\n"
      << "  --debug               Include predictor diagnostics in the manifest\n";
}

std::string requireValue(int& index, int count, char** values) {
  if (++index >= count)
    throw std::invalid_argument("Missing value after " +
                                std::string(values[index - 1]));
  return values[index];
}

Arguments parseArguments(int count, char** values) {
  Arguments arguments;
  for (int index = 1; index < count; ++index) {
    const std::string option = values[index];
    if (option == "--help" || option == "-h") {
      usage();
      std::exit(0);
    }
    if (option == "--settings") {
      arguments.settingsPath = requireValue(index, count, values);
      if (!std::filesystem::is_regular_file(arguments.settingsPath))
        throw std::invalid_argument("Settings file does not exist: " +
                                    arguments.settingsPath.string());
      arguments.settings = gap_assist::SettingsStore::load(arguments.settingsPath);
    } else if (option == "--input") {
      arguments.input = requireValue(index, count, values);
    } else if (option == "--correction") {
      arguments.correction = requireValue(index, count, values);
    } else if (option == "--highlight") {
      arguments.highlight = requireValue(index, count, values);
    } else if (option == "--corrected") {
      arguments.corrected = requireValue(index, count, values);
    } else if (option == "--manifest") {
      arguments.manifest = requireValue(index, count, values);
    } else if (option == "--contact-sheet") {
      arguments.contactSheet = requireValue(index, count, values);
    } else if (option == "--selection") {
      arguments.selection = requireValue(index, count, values);
      arguments.settings.scope = gap_assist::Scope::SelectionOnly;
    } else if (option == "--decisions") {
      arguments.decisions = requireValue(index, count, values);
    } else if (option == "--save-settings") {
      arguments.saveSettingsPath = requireValue(index, count, values);
    } else if (option == "--mode") {
      const auto value = requireValue(index, count, values);
      if (value == "quick")
        arguments.settings.mode = gap_assist::RunMode::QuickFix;
      else if (value == "review")
        arguments.settings.mode = gap_assist::RunMode::ReviewList;
      else if (value == "one")
        arguments.settings.mode = gap_assist::RunMode::OneByOne;
      else
        throw std::invalid_argument("Invalid mode: " + value);
    } else if (option == "--gap-size") {
      const auto value = requireValue(index, count, values);
      if (value == "small") {
        arguments.settings.gapSizePreset = gap_assist::GapSizePreset::Small;
        arguments.settings.gapThreshold = 3;
      } else if (value == "medium") {
        arguments.settings.gapSizePreset = gap_assist::GapSizePreset::Medium;
        arguments.settings.gapThreshold = 10;
      } else if (value == "large") {
        arguments.settings.gapSizePreset = gap_assist::GapSizePreset::Large;
        arguments.settings.gapThreshold = 30;
      } else {
        if (value.empty() || value.front() == '-')
          throw std::invalid_argument("Custom gap size must be a positive integer.");
        arguments.settings.gapSizePreset = gap_assist::GapSizePreset::Custom;
        arguments.settings.customGapThreshold = std::stoull(value);
        if (arguments.settings.customGapThreshold == 0)
          throw std::invalid_argument("Custom gap size must be greater than zero.");
        arguments.settings.gapThreshold = arguments.settings.customGapThreshold;
      }
    } else if (option == "--alpha-threshold") {
      arguments.settings.alphaThreshold = static_cast<std::uint8_t>(
          std::clamp(std::stoi(requireValue(index, count, values)), 0, 255));
    } else if (option == "--confidence") {
      const auto value = requireValue(index, count, values);
      if (value == "conservative")
        arguments.settings.confidencePreset =
            gap_assist::ConfidencePreset::Conservative;
      else if (value == "balanced")
        arguments.settings.confidencePreset = gap_assist::ConfidencePreset::Balanced;
      else if (value == "aggressive")
        arguments.settings.confidencePreset =
            gap_assist::ConfidencePreset::Aggressive;
      else
        throw std::invalid_argument("Invalid confidence preset: " + value);
    } else if (option == "--connectivity") {
      const auto value = requireValue(index, count, values);
      if (value == "4")
        arguments.settings.connectivity = gap_assist::Connectivity::Four;
      else if (value == "8")
        arguments.settings.connectivity = gap_assist::Connectivity::Eight;
      else
        throw std::invalid_argument("Connectivity must be 4 or 8.");
    } else if (option == "--apply-high") {
      arguments.applyHigh = true;
    } else if (option == "--predictor") {
      const auto value = requireValue(index, count, values);
      if (value != "rule_based" && value != "onnx")
        throw std::invalid_argument("Predictor must be rule_based or onnx.");
      arguments.settings.predictorOnnx = value == "onnx";
    } else if (option == "--no-highlight") {
      arguments.settings.createHighlightLayer = false;
    } else if (option == "--debug") {
      arguments.settings.debugLogging = true;
    } else {
      throw std::invalid_argument("Unknown option: " + option);
    }
  }
  if (arguments.input.empty()) throw std::invalid_argument("--input is required.");
  const auto stem = arguments.input.parent_path() / arguments.input.stem();
  if (arguments.correction.empty()) arguments.correction = stem.string() + ".gap-corrections.png";
  if (arguments.highlight.empty()) arguments.highlight = stem.string() + ".gap-highlights.png";
  if (arguments.corrected.empty()) arguments.corrected = stem.string() + ".gap-corrected.png";
  if (arguments.manifest.empty()) arguments.manifest = stem.string() + ".gap-manifest.json";
  if (arguments.contactSheet.empty()) arguments.contactSheet = stem.string() + ".gap-review.png";
  return arguments;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    auto arguments = parseArguments(argc, argv);
    if (arguments.settings.predictorOnnx) {
      std::cerr << "Gap Assist warning: the local ONNX adapter is not included in this "
                   "build; using Rule-Based prediction. No image data is transmitted.\n";
      arguments.settings.predictorOnnx = false;
    }
    const auto source = gap_assist::loadPng(arguments.input);
    std::optional<gap_assist::SelectionMask> selection;
    if (!arguments.selection.empty())
      selection = gap_assist::loadSelectionPng(arguments.selection, source.width(),
                                                source.height());

    gap_assist::RuleBasedPredictor predictor;
    gap_assist::SmartGapPropagation propagation;
    std::atomic_bool cancelled{false};
    auto result = propagation.analyze(
        source, arguments.settings, predictor,
        selection.has_value() ? &*selection : nullptr, &cancelled,
        [](std::size_t completed, std::size_t total) {
          if (completed == total) std::cerr << ".";
        });
    std::cerr << '\n';
    gap_assist::ReviewSession review(std::move(result.gaps), arguments.settings.mode);
    if (!arguments.decisions.empty())
      gap_assist::applyDecisionFile(arguments.decisions, review);
    if (arguments.applyHigh) review.applyHighConfidence();

    gap_assist::CorrectionOutputGenerator generator;
    const auto outputs = generator.generate(source, review.gaps(), arguments.settings);
    gap_assist::savePng(arguments.correction, outputs.correctionLayer);
    if (arguments.settings.createHighlightLayer)
      gap_assist::savePng(arguments.highlight, outputs.highlightLayer);
    gap_assist::savePng(arguments.corrected, outputs.correctedComposite);
    gap_assist::savePng(arguments.contactSheet,
                        gap_assist::renderReviewContactSheet(source, review.gaps()));
    gap_assist::writeGapManifest(arguments.manifest, review,
                                 arguments.settings.debugLogging);
    if (!arguments.saveSettingsPath.empty())
      gap_assist::SettingsStore::save(arguments.saveSettingsPath, arguments.settings);

    const auto summary = review.summary();
    std::cout << "Detected gaps: " << summary.detected << " (high=" << summary.high
              << ", medium=" << summary.medium << ", low=" << summary.low << ")\n"
              << "Applied: " << outputs.appliedCount
              << ", highlighted: " << outputs.markedCount << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "Gap Assist error: " << error.what() << '\n';
    return 1;
  }
}
